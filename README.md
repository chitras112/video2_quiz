# Video2Quiz

Video2Quiz turns learning videos into transcripts and practice quizzes. Upload a video or submit a public YouTube URL, review the transcript and generated questions, then take a quiz and review saved results.

## Live website

**Open the app:** [https://video2quiz-5roj.onrender.com](https://video2quiz-5roj.onrender.com)

The frontend and API are deployed together on Render. The API documentation is available at [https://video2quiz-5roj.onrender.com/docs](https://video2quiz-5roj.onrender.com/docs).

## Features implemented

- React and Vite interface for video upload, YouTube URL submission, processing status, transcripts, quizzes, and quiz history.
- FastAPI API with endpoints documented in Swagger at `/docs`.
- Video upload validation for MP4, MOV, MKV, WebM, and AVI files. The default upload limit is 500 MB and can be changed with `MAX_UPLOAD_MB`.
- Public YouTube video download using yt-dlp.
- Audio extraction using FFmpeg and transcription using OpenAI Whisper, including timestamped transcript segments.
- Transcript-based multiple-choice question generation. This is an extractive baseline, so review questions before using them for formal assessment.
- Versioned quizzes, exam attempts, saved scores, answer explanations, and historical results.
- SQLAlchemy database support with Alembic migrations. The hosted Render deployment uses PostgreSQL; the example local configuration uses MySQL.

## Run locally on Windows

### Requirements

- Python 3.11
- Node.js 20 or newer
- FFmpeg available on `PATH`
- A MySQL database (or another database supported by the configured SQLAlchemy URL)

Check FFmpeg with:

```powershell
ffmpeg -version
```

### 1. Configure the database

Create the local database in MySQL Workbench:

```sql
CREATE DATABASE video2quiz CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

From the project root, copy `.env.example` to `.env` and set `DATABASE_URL` to your local database credentials. Keep `.env` private; it is ignored by Git.

### 2. Install backend dependencies and migrate the database

Run these commands from the project root in PowerShell:

```powershell
py -3.11 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
.\venv\Scripts\alembic.exe upgrade head
```

For an existing database, review the migration guidance below before applying migrations.

### 3. Start the API

Keep MySQL and FFmpeg available, then run from the project root:

```powershell
uvicorn backend.main:app --reload
```

The API runs at `http://127.0.0.1:8000`; API docs are at `http://127.0.0.1:8000/docs`.

### 4. Start the frontend

Open a second terminal at the project root, then:

```powershell
cd frontend
npm install
npm run dev
```

Open the Vite URL, normally `http://localhost:5173`. Keep the backend terminal running as well; the Vite development server forwards `/api` requests to it.

## API endpoints

All endpoints are under `/api`:

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/videos/upload` | Upload a video file |
| `POST` | `/videos/youtube` | Submit a public YouTube URL |
| `GET` | `/videos` | List recent videos |
| `GET` | `/videos/{video_id}` | Get video status and details |
| `GET` | `/videos/{video_id}/transcript` | Get transcript and timestamped segments |
| `GET` | `/videos/{video_id}/quiz` | Get the latest generated quiz |
| `POST` | `/videos/{video_id}/evaluate` | Grade quiz answers |
| `POST` | `/videos/{video_id}/attempts` | Start and save a quiz attempt |
| `POST` | `/videos/attempts/{attempt_id}/submit` | Submit and save an attempt |
| `GET` | `/videos/{video_id}/attempts` | List saved attempts for a video |
| `GET` | `/videos/attempts/{attempt_id}` | View a saved attempt result |

## Deployment on Render

The repository includes a `render.yaml` Blueprint and a Dockerfile. The Blueprint deploys the app and a PostgreSQL database in Singapore; database migrations run when the service starts.

- **Live app:** [video2quiz-5roj.onrender.com](https://video2quiz-5roj.onrender.com)
- **GitHub repository:** [chitras112/video2_quiz](https://github.com/chitras112/video2_quiz)

The current deployment uses Render's free plans for demonstration. Free web services can sleep when idle, and their local files are temporary. The free PostgreSQL database expires after 30 days. Whisper processing can also exceed the free web service's memory limit. See [Render's free plan limitations](https://render.com/docs/free.md).

The app currently has no sign-in or user accounts. Anyone with the public link can submit videos or YouTube URLs. Do not upload sensitive videos.

YouTube may block automated downloads from cloud servers with a sign-in or bot check, even when a video is public. If this happens, try another public video, run the app locally with an authorized browser session, or upload a video file you are allowed to use. Do not share browser cookies.

## Configuration

The project root `.env` file supports:

| Variable | Purpose | Default |
| --- | --- | --- |
| `DATABASE_URL` | SQLAlchemy database connection | Set in `.env` |
| `VIDEO2QUIZ_DATA_DIR` | Directory for uploaded videos and generated files | `./data` |
| `MAX_UPLOAD_MB` | Maximum uploaded file size in MB | `500` |
| `WHISPER_MODEL` | Whisper model size (`tiny`, `base`, etc.) | `base` |
| `YOUTUBE_COOKIES_FROM_BROWSER` | Optional local browser cookie source for YouTube | Unset |

Set `WHISPER_MODEL=tiny` for a quicker local first run. Model speed and transcription quality vary by model size and available hardware.

## Database migrations

Alembic manages the schema; the API does not create tables automatically. For a fresh database, run:

```powershell
.\venv\Scripts\alembic.exe upgrade head
```

The migrations create the initial video, transcript, and question tables, add quiz versioning, and add exam attempt and response tables.

For an existing MySQL database, do not run the baseline migration until the live schema has been compared with `migrations/versions/0001_existing_schema_baseline.py`. The existing schema must match before an operator stamps the baseline and applies later migrations. Review the migration files and back up the database before making schema changes; MySQL may commit DDL implicitly.

## Current work and next steps

Implemented work includes the application UI and API, local video and YouTube ingestion, transcription, quiz generation, saved quiz attempts, migrations, and a public Render deployment.

Possible next improvements include user authentication, a durable job queue for long video processing, persistent object storage for uploaded media, and more advanced question generation and quality checks.
