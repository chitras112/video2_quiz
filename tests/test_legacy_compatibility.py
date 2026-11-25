import json

from fastapi.testclient import TestClient
from sqlalchemy import Column, Integer, MetaData, String, Table, Text, create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend import main
from backend.api import videos as videos_api
from backend.models.video import Video
from backend.services.quiz_service import QuizVersioningUnavailable, persist_questions


def legacy_client():
    """Build the pre-versioning schema without touching any configured DB."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Video.__table__.create(engine)
    legacy_metadata = MetaData()
    Table(
        "questions",
        legacy_metadata,
        Column("id", Integer, primary_key=True),
        Column("video_id", Integer, nullable=False),
        Column("question_text", Text, nullable=False),
        Column("options_json", Text, nullable=False),
        Column("correct_answer", String(500), nullable=False),
        Column("explanation", Text, nullable=False),
        Column("difficulty", String(20), nullable=False),
        Column("timestamp_seconds", Integer),
    ).create(engine)

    with Session(engine) as db:
        video = Video(
            source_type="upload",
            stored_filename="legacy.mp4",
            file_path="legacy.mp4",
            status="completed",
        )
        db.add(video)
        db.flush()
        video_id = video.id
        db.execute(
            text("""INSERT INTO questions
                (video_id, question_text, options_json, correct_answer, explanation, difficulty, timestamp_seconds)
                VALUES (:video_id, :question, :options, :answer, :explanation, :difficulty, :timestamp)"""),
            {
                "video_id": video_id,
                "question": "Legacy question",
                "options": json.dumps(["A", "B"]),
                "answer": "A",
                "explanation": "Legacy explanation",
                "difficulty": "easy",
                "timestamp": 12,
            },
        )
        db.commit()

    def override_get_db():
        with Session(engine) as db:
            yield db

    main.app.dependency_overrides[videos_api.get_db] = override_get_db
    return TestClient(main.app), engine, video_id


def test_legacy_quiz_retrieval_and_evaluation_work_without_version_column():
    client, engine, video_id = legacy_client()
    try:
        quiz = client.get(f"/api/videos/{video_id}/quiz")
        assert quiz.status_code == 200
        body = quiz.json()
        assert body["video_id"] == video_id
        assert body["quiz_version"] is None
        assert len(body["questions"]) == 1
        assert body["questions"][0]["question"] == "Legacy question"
        assert body["questions"][0]["options"] == ["A", "B"]

        question_id = body["questions"][0]["id"]
        graded = client.post(
            f"/api/videos/{video_id}/evaluate",
            json={"answers": {str(question_id): "a"}},
        )
        assert graded.status_code == 200
        result = graded.json()
        assert result["quiz_version"] is None
        assert result["score"] == 1
        assert result["total"] == 1
        assert result["results"][0]["correct"] is True
    finally:
        main.app.dependency_overrides.pop(videos_api.get_db, None)
        client.close()
        engine.dispose()


def test_persistent_exam_endpoints_report_unavailable_without_writing():
    client, engine, video_id = legacy_client()
    try:
        unavailable = "Persistent exam attempts are temporarily unavailable"
        start = client.post(
            f"/api/videos/{video_id}/attempts",
            json={"idempotency_key": "legacy-test-key"},
        )
        submit = client.post("/api/videos/attempts/1/submit", json={"answers": {}})
        result = client.get("/api/videos/attempts/1")
        history = client.get(f"/api/videos/{video_id}/attempts")
        for response in (start, submit, result, history):
            assert response.status_code == 503
            assert unavailable in response.json()["detail"]
    finally:
        main.app.dependency_overrides.pop(videos_api.get_db, None)
        client.close()
        engine.dispose()


def test_versioned_generation_is_explicitly_unavailable_without_column():
    client, engine, video_id = legacy_client()
    client.close()
    try:
        with Session(engine) as db:
            try:
                persist_questions(db, video_id, {"text": "", "segments": []})
            except QuizVersioningUnavailable as exc:
                assert "questions.quiz_version" in str(exc)
            else:
                raise AssertionError("generation should be unavailable on the legacy schema")
    finally:
        main.app.dependency_overrides.pop(videos_api.get_db, None)
        engine.dispose()
