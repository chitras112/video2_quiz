import os
from pathlib import Path
from uuid import uuid4
from dotenv import load_dotenv
load_dotenv()
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("VIDEO2QUIZ_DATA_DIR", str(PROJECT_ROOT / "data")))
if not DATA_DIR.is_absolute():
    DATA_DIR = (PROJECT_ROOT / DATA_DIR).resolve()
VIDEO_DIR, AUDIO_DIR, TRANSCRIPT_DIR = DATA_DIR / "videos", DATA_DIR / "audio", DATA_DIR / "transcripts"
for directory in (VIDEO_DIR, AUDIO_DIR, TRANSCRIPT_DIR):
    directory.mkdir(parents=True, exist_ok=True)

def unique_video_path(extension: str):
    ext = extension.lower()
    if not ext.startswith("."):
        ext = "." + ext
    filename = f"{uuid4().hex}{ext}"
    return filename, VIDEO_DIR / filename
