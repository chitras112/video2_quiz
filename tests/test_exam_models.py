from datetime import datetime

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database.database import Base
from backend.models import ExamAttempt, ExamResponse, Question, Video


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(connection, _record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def exam_data(db):
    video = Video(stored_filename="lesson.mp4", file_path="lesson.mp4")
    db.add(video)
    db.flush()
    question = Question(
        video_id=video.id,
        quiz_version=1,
        question_text="Which concept is described?",
        options_json='["A", "B", "C", "D"]',
        correct_answer="A",
        explanation="The transcript explains A.",
    )
    db.add(question)
    db.flush()
    attempt = ExamAttempt(
        video_id=video.id,
        quiz_version=question.quiz_version,
        idempotency_key="attempt-key-1",
        total_questions=1,
    )
    db.add(attempt)
    db.flush()
    return video, question, attempt


def response_for(attempt, question, **overrides):
    values = {
        "attempt_id": attempt.id,
        "question_id": question.id,
        "selected_answer": None,
        "is_correct": False,
        "answered_at": None,
        "question_text": question.question_text,
        "options_json": question.options_json,
        "correct_answer": question.correct_answer,
        "explanation": question.explanation,
    }
    values.update(overrides)
    return ExamResponse(**values)


def test_attempt_pins_version_and_relationships_store_snapshots(db, exam_data):
    video, question, attempt = exam_data
    response = response_for(attempt, question)
    db.add(response)
    db.commit()
    db.refresh(attempt)

    assert attempt.quiz_version == question.quiz_version == 1
    assert attempt.video is video
    assert video.exam_attempts == [attempt]
    assert response.attempt is attempt
    assert response.question is question
    assert question.responses == [response]
    assert response.question_text == question.question_text
    assert response.options_json == question.options_json
    assert response.correct_answer == question.correct_answer
    assert response.explanation == question.explanation


def test_unanswered_response_can_be_persisted(db, exam_data):
    _, question, attempt = exam_data
    response = response_for(attempt, question)
    db.add(response)
    db.commit()

    assert response.selected_answer is None
    assert response.answered_at is None
    assert response.is_correct is False


def test_idempotency_key_must_be_unique(db, exam_data):
    video, _, _ = exam_data
    db.add(ExamAttempt(video_id=video.id, quiz_version=1, idempotency_key="attempt-key-1"))

    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_attempt_question_response_pair_must_be_unique(db, exam_data):
    _, question, attempt = exam_data
    db.add(response_for(attempt, question))
    db.commit()
    db.add(response_for(attempt, question, selected_answer="A", answered_at=datetime.utcnow()))

    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_question_referenced_by_response_cannot_be_deleted(db, exam_data):
    _, question, attempt = exam_data
    db.add(response_for(attempt, question))
    db.commit()
    question_id = question.id

    db.delete(question)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    assert db.get(Question, question_id) is not None


def test_video_with_attempt_history_cannot_be_deleted(db, exam_data):
    video, question, attempt = exam_data
    db.add(response_for(attempt, question))
    db.commit()
    video_id = video.id

    db.delete(video)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    assert db.get(Video, video_id) is not None
    assert db.query(ExamAttempt).filter_by(video_id=video_id).count() == 1
    assert db.query(ExamResponse).filter_by(attempt_id=attempt.id).count() == 1
