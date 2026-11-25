import json
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool

from backend import main
from backend.api import videos as videos_api
from backend.database import database
import backend.models  # noqa: F401; register models before creating the isolated test schema
from backend.models import ExamAttempt, ExamResponse, Question, Video
from backend.schemas.video import ExamAttemptSubmission


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Exercise the real API and SQLAlchemy models without requiring MySQL to be
    # running on the developer machine. Production MySQL remains configured by
    # DATABASE_URL and is checked separately when the app is started.
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(test_engine, "connect")
    def enable_sqlite_foreign_keys(connection, _record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    old_bind = database.SessionLocal.kw.get("bind")
    database.SessionLocal.configure(bind=test_engine)
    monkeypatch.setattr(main, "engine", test_engine)
    monkeypatch.setattr(videos_api, "VIDEO_DIR", tmp_path)
    monkeypatch.setattr(
        videos_api,
        "unique_video_path",
        lambda extension: ("test-video" + extension, tmp_path / ("test-video" + extension)),
    )
    monkeypatch.setattr(videos_api, "process_video", lambda video_id: None)
    database.Base.metadata.create_all(bind=test_engine)

    with TestClient(main.app) as test_client:
        yield test_client

    database.SessionLocal.configure(bind=old_bind)
    test_engine.dispose()


def create_processed_video(question_versions=None):
    if question_versions is None:
        question_versions = {1: [("Original question", ["A", "B"], "A")]}
    db = database.SessionLocal()
    video = Video(
        source_type="upload",
        stored_filename="exam-test.mp4",
        file_path="exam-test.mp4",
        status="completed",
    )
    db.add(video)
    db.flush()
    questions = {}
    for version, specs in question_versions.items():
        questions[version] = []
        for text, options, correct_answer in specs:
            question = Question(
                video_id=video.id,
                quiz_version=version,
                question_text=text,
                options_json=json.dumps(options),
                correct_answer=correct_answer,
                explanation=f"Explanation for {text}",
                difficulty="easy",
                timestamp_seconds=5,
            )
            db.add(question)
            db.flush()
            questions[version].append(question.id)
    video_id = video.id
    db.commit()
    db.close()
    return video_id, questions


def test_health_and_docs(client):
    assert client.get("/").json()["status"] == "healthy"
    assert client.get("/docs").status_code == 200


def test_upload_rejects_unsupported_extension(client):
    response = client.post(
        "/api/videos/upload",
        files={"file": ("notes.txt", b"not a video", "text/plain")},
    )
    assert response.status_code == 400


def test_youtube_rejects_non_youtube_host(client):
    response = client.post("/api/videos/youtube", json={"url": "https://youtube.com.example.org/watch?v=x"})
    assert response.status_code == 400


def test_upload_persists_video_and_creates_file(client, tmp_path):
    response = client.post(
        "/api/videos/upload",
        files={"file": ("lesson.mp4", b"test video bytes", "video/mp4")},
    )
    assert response.status_code == 202
    video = response.json()
    assert video["status"] == "uploaded"
    assert (tmp_path / video["stored_filename"]).read_bytes() == b"test video bytes"

    listed = client.get("/api/videos").json()
    assert [item["id"] for item in listed] == [video["id"]]


def test_start_exam_uses_latest_version_without_revealing_answers(client):
    video_id, question_ids = create_processed_video({
        1: [("Old question", ["old", "answer"], "answer")],
        2: [("Latest question", ["A", "B"], "B")],
    })

    response = client.post(
        f"/api/videos/{video_id}/attempts",
        json={"idempotency_key": "start-latest-1"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["quiz_version"] == 2
    assert body["total_questions"] == 1
    assert [item["id"] for item in body["questions"]] == question_ids[2]
    assert "correct_answer" not in body["questions"][0]
    assert "explanation" not in body["questions"][0]


def test_start_exam_retry_with_same_key_returns_same_attempt(client):
    video_id, _ = create_processed_video()
    payload = {"idempotency_key": "start-retry-1"}

    first = client.post(f"/api/videos/{video_id}/attempts", json=payload)
    retry = client.post(f"/api/videos/{video_id}/attempts", json=payload)

    assert first.status_code == 201
    assert retry.status_code == 200
    assert retry.json()["attempt_id"] == first.json()["attempt_id"]
    db = database.SessionLocal()
    try:
        assert db.query(ExamAttempt).filter_by(idempotency_key="start-retry-1").count() == 1
    finally:
        db.close()


def test_start_exam_without_quiz_returns_clear_conflict(client):
    video_id, _ = create_processed_video({})

    response = client.post(
        f"/api/videos/{video_id}/attempts",
        json={"idempotency_key": "no-quiz-1"},
    )

    assert response.status_code == 409
    assert "No quiz questions" in response.json()["detail"]


def test_submit_persists_score_and_unanswered_responses(client):
    video_id, question_ids = create_processed_video({
        1: [
            ("First question", ["A", "B"], "A"),
            ("Second question", ["C", "D"], "D"),
        ],
    })
    started = client.post(
        f"/api/videos/{video_id}/attempts",
        json={"idempotency_key": "submit-persist-1"},
    ).json()

    submitted = client.post(
        f"/api/videos/attempts/{started['attempt_id']}/submit",
        json={"answers": {str(question_ids[1][0]): "a"}},
    )

    assert submitted.status_code == 200
    result = submitted.json()
    assert result["status"] == "completed"
    assert result["score"] == 1
    assert result["total"] == 2
    assert result["percentage"] == 50
    by_id = {row["question_id"]: row for row in result["results"]}
    assert by_id[question_ids[1][0]]["correct"] is True
    assert by_id[question_ids[1][1]]["selected_answer"] is None
    assert by_id[question_ids[1][1]]["correct"] is False

    db = database.SessionLocal()
    try:
        attempt = db.get(ExamAttempt, started["attempt_id"])
        responses = db.query(ExamResponse).filter_by(attempt_id=attempt.id).all()
        assert attempt.score == 1
        assert attempt.percentage == 50
        assert attempt.submitted_at is not None
        assert len(responses) == 2
        assert sum(response.selected_answer is None for response in responses) == 1
    finally:
        db.close()


def test_submit_rejects_question_from_another_video(client):
    video_id, _ = create_processed_video()
    other_video_id, other_question_ids = create_processed_video()
    started = client.post(
        f"/api/videos/{video_id}/attempts",
        json={"idempotency_key": "wrong-video-1"},
    ).json()

    response = client.post(
        f"/api/videos/attempts/{started['attempt_id']}/submit",
        json={"answers": {str(other_question_ids[1][0]): "A"}},
    )

    assert response.status_code == 400
    assert "do not belong" in response.json()["detail"]
    assert other_video_id != video_id


def test_submit_rejects_question_from_another_version(client):
    video_id, question_ids = create_processed_video({
        1: [("Old version", ["A", "B"], "A")],
        2: [("Current version", ["C", "D"], "C")],
    })
    started = client.post(
        f"/api/videos/{video_id}/attempts",
        json={"idempotency_key": "wrong-version-1"},
    ).json()

    response = client.post(
        f"/api/videos/attempts/{started['attempt_id']}/submit",
        json={"answers": {str(question_ids[1][0]): "A"}},
    )

    assert response.status_code == 400


def test_repeated_submission_returns_saved_result_without_duplicate_responses(client):
    video_id, question_ids = create_processed_video()
    started = client.post(
        f"/api/videos/{video_id}/attempts",
        json={"idempotency_key": "submit-retry-1"},
    ).json()
    submit_url = f"/api/videos/attempts/{started['attempt_id']}/submit"
    first = client.post(submit_url, json={"answers": {str(question_ids[1][0]): "A"}})
    retry = client.post(submit_url, json={"answers": {"99999": "wrong"}})

    assert first.status_code == retry.status_code == 200
    assert retry.json() == first.json()
    db = database.SessionLocal()
    try:
        assert db.query(ExamResponse).filter_by(attempt_id=started["attempt_id"]).count() == 1
    finally:
        db.close()


def test_result_uses_snapshots_after_new_quiz_version_exists(client):
    video_id, question_ids = create_processed_video({
        1: [("Historical question", ["A", "B"], "A")],
    })
    started = client.post(
        f"/api/videos/{video_id}/attempts",
        json={"idempotency_key": "historical-result-1"},
    ).json()
    assert started["quiz_version"] == 1

    from backend.services.quiz_service import persist_questions
    db = database.SessionLocal()
    try:
        assert persist_questions(db, video_id, {
            "text": "Neural networks learn patterns from data. Training adjusts weights to reduce error. "
                    "Validation checks how well a model generalizes.",
            "segments": [
                {"start": 1, "text": "Neural networks learn patterns from data."},
                {"start": 5, "text": "Training adjusts weights to reduce error."},
                {"start": 9, "text": "Validation checks how well a model generalizes."},
            ],
        }) > 0
    finally:
        db.close()

    submit_url = f"/api/videos/attempts/{started['attempt_id']}/submit"
    assert client.post(submit_url, json={"answers": {str(question_ids[1][0]): "A"}}).status_code == 200
    result = client.get(f"/api/videos/attempts/{started['attempt_id']}")

    assert result.status_code == 200
    assert result.json()["quiz_version"] == 1
    assert result.json()["results"][0]["question"] == "Historical question"
    assert result.json()["results"][0]["options"] == ["A", "B"]


def test_submission_transaction_rolls_back_on_persistence_failure(client, monkeypatch):
    video_id, question_ids = create_processed_video()
    started = client.post(
        f"/api/videos/{video_id}/attempts",
        json={"idempotency_key": "rollback-submit-1"},
    ).json()
    db = database.SessionLocal()

    def fail_flush():
        raise RuntimeError("simulated response persistence failure")

    monkeypatch.setattr(db, "flush", fail_flush)
    try:
        from backend.api.videos import submit_exam_attempt
        with pytest.raises(RuntimeError, match="simulated response persistence failure"):
            submit_exam_attempt(
                started["attempt_id"],
                ExamAttemptSubmission(answers={question_ids[1][0]: "A"}),
                db,
            )
    finally:
        monkeypatch.undo()
        db.close()

    check = database.SessionLocal()
    try:
        attempt = check.get(ExamAttempt, started["attempt_id"])
        assert attempt.status == "in_progress"
        assert attempt.score is None
        assert check.query(ExamResponse).filter_by(attempt_id=attempt.id).count() == 0
    finally:
        check.close()


def test_attempt_history_is_empty_for_video_without_attempts(client):
    video_id, _ = create_processed_video()

    response = client.get(f"/api/videos/{video_id}/attempts")

    assert response.status_code == 200
    assert response.json() == []


def test_attempt_history_is_scoped_sorted_and_excludes_answer_snapshots(client):
    video_id, question_ids = create_processed_video()
    other_video_id, _ = create_processed_video()
    db = database.SessionLocal()
    now = datetime.utcnow()
    older = ExamAttempt(
        video_id=video_id,
        quiz_version=1,
        status="completed",
        total_questions=1,
        score=1,
        percentage=100,
        idempotency_key="history-complete-1",
        started_at=now - timedelta(days=2),
        submitted_at=now - timedelta(days=2) + timedelta(minutes=5),
    )
    newer = ExamAttempt(
        video_id=video_id,
        quiz_version=1,
        status="in_progress",
        total_questions=1,
        score=None,
        percentage=None,
        idempotency_key="history-incomplete-1",
        started_at=now - timedelta(days=1),
        submitted_at=None,
    )
    foreign = ExamAttempt(
        video_id=other_video_id,
        quiz_version=1,
        status="in_progress",
        total_questions=1,
        idempotency_key="history-other-video-1",
        started_at=now,
    )
    db.add_all([older, newer, foreign])
    db.flush()
    question = db.get(Question, question_ids[1][0])
    db.add(ExamResponse(
        attempt_id=older.id,
        question_id=question.id,
        selected_answer="A",
        is_correct=True,
        question_text="Private snapshot question",
        options_json='["A", "B"]',
        correct_answer="A",
        explanation="Private snapshot explanation",
    ))
    db.commit()
    older_id, newer_id = older.id, newer.id
    db.close()

    response = client.get(f"/api/videos/{video_id}/attempts")

    assert response.status_code == 200
    history = response.json()
    assert [item["attempt_id"] for item in history] == [newer_id, older_id]
    assert all(item["video_id"] == video_id for item in history)
    assert history[0]["status"] == "in_progress"
    assert history[0]["score"] is None
    assert history[0]["percentage"] is None
    assert history[0]["submitted_at"] is None
    assert history[1]["status"] == "completed"
    assert history[1]["score"] == 1
    assert history[1]["percentage"] == 100
    assert history[1]["submitted_at"] is not None
    expected_fields = {
        "attempt_id", "video_id", "quiz_version", "status", "total_questions",
        "score", "percentage", "started_at", "submitted_at",
    }
    assert all(set(item) == expected_fields for item in history)
    serialized_history = json.dumps(history)
    assert "selected_answer" not in serialized_history
    assert "correct_answer" not in serialized_history
    assert "explanation" not in serialized_history
    assert "Private snapshot" not in serialized_history


def test_attempt_history_returns_404_for_unknown_video(client):
    response = client.get("/api/videos/999999/attempts")

    assert response.status_code == 404
    assert response.json()["detail"] == "Video not found."

