import json, os, subprocess
from pathlib import Path
from dotenv import load_dotenv
from backend.utils.storage import AUDIO_DIR, TRANSCRIPT_DIR
load_dotenv()

def extract_audio(video_path: Path, video_id: int) -> Path:
    output_path = AUDIO_DIR / f"video_{video_id}.wav"
    command = ["ffmpeg", "-y", "-i", str(video_path), "-vn", "-ac", "1", "-ar", "16000",
               "-acodec", "pcm_s16le", str(output_path)]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=3600)
    except FileNotFoundError as exc:
        raise RuntimeError("FFmpeg not found. Install it and ensure ffmpeg.exe is on PATH.") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Audio extraction timed out.") from exc
    if result.returncode != 0 or not output_path.exists():
        raise RuntimeError(f"FFmpeg audio extraction failed: {(result.stderr or 'Unknown error')[-1200:]}")
    return output_path

def transcribe_audio(audio_path: Path, video_id: int) -> dict:
    try:
        import whisper
    except ImportError as exc:
        raise RuntimeError("Whisper is not installed. Run pip install -r requirements.txt.") from exc
    model = whisper.load_model(os.getenv("WHISPER_MODEL", "base"))
    result = model.transcribe(str(audio_path), fp16=False, verbose=False)
    payload = {"video_id": video_id, "language": result.get("language"),
               "text": (result.get("text") or "").strip(),
               "segments": [{"start": round(float(s.get("start", 0)), 2),
                             "end": round(float(s.get("end", 0)), 2),
                             "text": str(s.get("text", "")).strip()} for s in result.get("segments", [])]}
    (TRANSCRIPT_DIR / f"video_{video_id}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload
