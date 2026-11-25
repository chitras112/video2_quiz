from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from backend.database.database import Base

class Video(Base):
    __tablename__ = "videos"
    id = Column(Integer, primary_key=True, index=True)
    source_type = Column(String(20), nullable=False, default="upload")
    original_filename = Column(String(255), nullable=True)
    stored_filename = Column(String(255), nullable=False)
    file_path = Column(String(1000), nullable=False)
    source_url = Column(String(2000), nullable=True)
    status = Column(String(40), nullable=False, default="uploaded", index=True)
    error_message = Column(Text, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    transcript = relationship("Transcript", back_populates="video", uselist=False, cascade="all, delete-orphan")
    questions = relationship("Question", back_populates="video", cascade="all, delete-orphan")
    exam_attempts = relationship("ExamAttempt", back_populates="video", passive_deletes="all")

class Transcript(Base):
    __tablename__ = "transcripts"
    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    text = Column(Text, nullable=False)
    language = Column(String(30), nullable=True)
    segments_json = Column(Text, nullable=False, default="[]")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    video = relationship("Video", back_populates="transcript")

class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (Index("ix_questions_video_id_quiz_version", "video_id", "quiz_version"),)
    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    quiz_version = Column(Integer, nullable=False, default=1)
    question_text = Column(Text, nullable=False)
    options_json = Column(Text, nullable=False)
    correct_answer = Column(String(500), nullable=False)
    explanation = Column(Text, nullable=False)
    difficulty = Column(String(20), nullable=False, default="medium")
    timestamp_seconds = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    video = relationship("Video", back_populates="questions")
    responses = relationship("ExamResponse", back_populates="question", passive_deletes="all")


class ExamAttempt(Base):
    __tablename__ = "exam_attempts"
    __table_args__ = (
        Index("ix_exam_attempts_video_quiz_version", "video_id", "quiz_version"),
        UniqueConstraint("idempotency_key", name="uq_exam_attempts_idempotency_key"),
    )

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id", ondelete="RESTRICT"), nullable=False, index=True)
    quiz_version = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="in_progress", index=True)
    total_questions = Column(Integer, nullable=False, default=0)
    score = Column(Integer, nullable=True)
    percentage = Column(Integer, nullable=True)
    feedback = Column(Text, nullable=True)
    idempotency_key = Column(String(128), nullable=False)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    submitted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    video = relationship("Video", back_populates="exam_attempts")
    responses = relationship("ExamResponse", back_populates="attempt", passive_deletes="all")


class ExamResponse(Base):
    __tablename__ = "exam_responses"
    __table_args__ = (
        UniqueConstraint("attempt_id", "question_id", name="uq_exam_responses_attempt_question"),
        Index("ix_exam_responses_question_id", "question_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(Integer, ForeignKey("exam_attempts.id", ondelete="RESTRICT"), nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="RESTRICT"), nullable=False)
    selected_answer = Column(String(500), nullable=True)
    is_correct = Column(Boolean, nullable=False, default=False)
    answered_at = Column(DateTime, nullable=True)
    question_text = Column(Text, nullable=False)
    options_json = Column(Text, nullable=False)
    correct_answer = Column(String(500), nullable=False)
    explanation = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    attempt = relationship("ExamAttempt", back_populates="responses")
    question = relationship("Question", back_populates="responses")
