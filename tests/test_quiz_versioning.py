import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api.videos import evaluate_quiz, get_quiz
from backend.database.database import Base
from backend.models.video import Question, Video
from backend.schemas.video import ExamSubmission
from backend.services import quiz_service


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def transcript():
    return {
        "text": (
            "Neural networks learn patterns from data. Training adjusts weights to reduce error. "
            "Validation checks how well a model generalizes."
        ),
        "segments": [
            {"start": 1, "text": "Neural networks learn patterns from data."},
            {"start": 5, "text": "Training adjusts weights to reduce error."},
            {"start": 9, "text": "Validation checks how well a model generalizes."},
        ],
    }


@pytest.fixture
def video(db):
    row = Video(
        source_type="upload",
        stored_filename="test.mp4",
        file_path="test.mp4",
        status="completed",
    )
    db.add(row)
    db.commit()
    return row


def question_snapshot(questions):
    return [
        (q.id, q.video_id, q.quiz_version, q.question_text, q.options_json,
         q.correct_answer, q.explanation, q.difficulty, q.timestamp_seconds)
        for q in questions
    ]


def test_first_generation_uses_version_one(db, video, transcript):
    count = quiz_service.persist_questions(db, video.id, transcript)
    rows = db.query(Question).filter_by(video_id=video.id).all()

    assert count > 0
    assert {row.quiz_version for row in rows} == {1}


def test_regeneration_increments_version_and_preserves_old_rows(db, video, transcript):
    quiz_service.persist_questions(db, video.id, transcript)
    old_rows = db.query(Question).filter_by(video_id=video.id).order_by(Question.id).all()
    old_snapshot = question_snapshot(old_rows)

    count = quiz_service.persist_questions(db, video.id, transcript)
    rows = db.query(Question).filter_by(video_id=video.id).order_by(Question.id).all()

    assert count == len(old_rows)
    assert {row.quiz_version for row in rows} == {1, 2}
    assert question_snapshot(rows[:len(old_rows)]) == old_snapshot
    assert all(row.id > old_rows[-1].id for row in rows[len(old_rows):])


def test_retrieval_returns_only_latest_version(db, video, transcript):
    quiz_service.persist_questions(db, video.id, transcript)
    quiz_service.persist_questions(db, video.id, transcript)

    response = get_quiz(video.id, db)

    assert response["quiz_version"] == 2
    assert response["questions"]
    assert all(
        row.quiz_version == response["quiz_version"]
        for row in db.query(Question).filter(
            Question.id.in_([item["id"] for item in response["questions"]])
        )
    )


def test_grading_rejects_question_id_from_older_version(db, video, transcript):
    quiz_service.persist_questions(db, video.id, transcript)
    old_id = db.query(Question.id).filter_by(video_id=video.id).order_by(Question.id).first()[0]
    quiz_service.persist_questions(db, video.id, transcript)

    with pytest.raises(HTTPException) as error:
        evaluate_quiz(video.id, ExamSubmission(answers={old_id: "anything"}), db)

    assert error.value.status_code == 400


def test_failed_insert_keeps_previous_version_usable(db, video, transcript, monkeypatch):
    quiz_service.persist_questions(db, video.id, transcript)
    before = question_snapshot(db.query(Question).filter_by(video_id=video.id).order_by(Question.id).all())

    def fail_flush():
        raise RuntimeError("simulated insert failure")

    monkeypatch.setattr(db, "flush", fail_flush)
    with pytest.raises(RuntimeError, match="simulated insert failure"):
        quiz_service.persist_questions(db, video.id, transcript)
    monkeypatch.undo()

    after = question_snapshot(db.query(Question).filter_by(video_id=video.id).order_by(Question.id).all())
    assert after == before
    assert get_quiz(video.id, db)["quiz_version"] == 1


def test_empty_generation_does_not_create_new_version(db, video, transcript, monkeypatch):
    quiz_service.persist_questions(db, video.id, transcript)
    before = question_snapshot(db.query(Question).filter_by(video_id=video.id).all())
    monkeypatch.setattr(quiz_service, "generate_baseline_questions", lambda *_args, **_kwargs: [])

    assert quiz_service.persist_questions(db, video.id, transcript) == 0
    assert question_snapshot(db.query(Question).filter_by(video_id=video.id).all()) == before
    assert get_quiz(video.id, db)["quiz_version"] == 1


def test_latest_version_grading_preserves_missing_answer_behavior(db, video, transcript):
    quiz_service.persist_questions(db, video.id, transcript)
    quiz_service.persist_questions(db, video.id, transcript)

    result = evaluate_quiz(video.id, ExamSubmission(answers={}), db)

    assert result["quiz_version"] == 2
    assert result["score"] == 0
    assert result["total"] > 0
    assert len(result["results"]) == result["total"]
