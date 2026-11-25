from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator

class YouTubeRequest(BaseModel):
    url: str

class VideoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    source_type: str
    original_filename: str | None
    stored_filename: str
    source_url: str | None
    status: str
    error_message: str | None
    duration_seconds: int | None
    created_at: datetime
    updated_at: datetime

class TranscriptOut(BaseModel):
    video_id: int
    text: str
    language: str | None
    segments: list[dict[str, Any]]

class ExamSubmission(BaseModel):
    answers: dict[int, str]


class ExamAttemptStartRequest(BaseModel):
    idempotency_key: str = Field(min_length=1, max_length=128)

    @field_validator("idempotency_key")
    @classmethod
    def normalize_idempotency_key(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Idempotency key must not be blank.")
        return value


class ExamAttemptSubmission(BaseModel):
    answers: dict[int, str] = Field(default_factory=dict)

    @field_validator("answers")
    @classmethod
    def validate_answers(cls, answers: dict[int, str]) -> dict[int, str]:
        if any(question_id <= 0 for question_id in answers):
            raise ValueError("Question IDs must be positive integers.")
        if any(len(answer) > 500 for answer in answers.values()):
            raise ValueError("Answers must be at most 500 characters.")
        return answers


class ExamStartQuestion(BaseModel):
    id: int
    video_id: int
    question: str
    options: list[str]
    difficulty: str
    timestamp_seconds: int | None


class ExamAttemptStartResponse(BaseModel):
    attempt_id: int
    video_id: int
    quiz_version: int
    status: str
    total_questions: int
    started_at: datetime
    questions: list[ExamStartQuestion]
    notice: str


class ExamAttemptResultQuestion(BaseModel):
    question_id: int
    question: str
    options: list[str]
    selected_answer: str | None
    correct_answer: str
    correct: bool
    explanation: str
    feedback: str


class ExamAttemptResultResponse(BaseModel):
    attempt_id: int
    video_id: int
    quiz_version: int
    status: str
    submitted_at: datetime
    score: int
    total: int
    percentage: int
    feedback: str
    results: list[ExamAttemptResultQuestion]


class ExamAttemptHistoryItem(BaseModel):
    attempt_id: int
    video_id: int
    quiz_version: int
    status: str
    total_questions: int
    score: int | None
    percentage: int | None
    started_at: datetime
    submitted_at: datetime | None
