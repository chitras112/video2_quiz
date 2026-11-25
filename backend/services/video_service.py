import json, logging
from pathlib import Path
from sqlalchemy.orm import Session
from backend.database.database import SessionLocal
from backend.models.video import Transcript, Video
from backend.services.quiz_service import persist_questions
from backend.services.transcription_service import extract_audio, transcribe_audio
logger = logging.getLogger(__name__)

def process_video(video_id: int):
    db: Session = SessionLocal()
    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            return
        video.status, video.error_message = "extracting_audio", None
        db.commit()
        audio_path = extract_audio(Path(video.file_path), video_id)
        video.status = "transcribing"
        db.commit()
        data = transcribe_audio(audio_path, video_id)
        transcript = db.query(Transcript).filter(Transcript.video_id == video_id).first()
        if transcript is None:
            transcript = Transcript(video_id=video_id, text=data["text"])
            db.add(transcript)
        transcript.text = data["text"]
        transcript.language = data.get("language")
        transcript.segments_json = json.dumps(data.get("segments", []), ensure_ascii=False)
        db.commit()
        video.status = "generating_quiz"
        db.commit()
        count = persist_questions(db, video_id, data, count=5)
        video.status = "completed" if data["text"] else "completed_no_speech"
        if not count and data["text"]:
            video.error_message = "Transcription completed, but baseline generator could not make questions."
        db.commit()
    except Exception as exc:
        logger.exception("Video processing failed for video_id=%s", video_id)
        db.rollback()
        video = db.query(Video).filter(Video.id == video_id).first()
        if video:
            video.status, video.error_message = "failed", str(exc)[:4000]
            db.commit()
    finally:
        db.close()
