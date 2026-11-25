# Video2Quiz — 50% implementation milestone

## Included
- FastAPI backend with Swagger docs and Postman-ready endpoints
- MySQL persistence via SQLAlchemy (tables are created at startup)
- Video upload with extension and size validation
- Public YouTube URL ingestion via yt-dlp
- FFmpeg audio extraction
- Whisper transcription with timestamped segments
- Baseline transcript-derived MCQs stored in MySQL
- Small React/Vite frontend to upload, track status, and view transcript/quiz

## Still to build
Authentication, durable task queue, advanced LLM-based question generation and quality verification,
timed exam/submission, topic analytics, adaptive difficulty, migrations, deployment, and production UI.
The MCQ generator here is an extractive baseline and must be reviewed before formal use.

## Requirements
Windows 10/11, Python 3.11, MySQL Server + Workbench, FFmpeg on PATH, Node.js 20+ for frontend.
Run `ffmpeg -version` to verify FFmpeg.

## 1. Create database in MySQL Workbench
Run:
```sql
CREATE DATABASE video2quiz CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```
The app creates the tables on startup.

## 2. Configure
Copy `.env.example` to `.env` in the project root and edit the MySQL credentials.
Do not commit `.env` or share your database password.

## 3. Backend setup (PowerShell, project root)
```powershell
py -3.11 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```
If PowerShell blocks activation, run once:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```
Reopen the terminal and activate the environment.

## 4. Start backend
Ensure MySQL Server is running and FFmpeg works, then:
```powershell
uvicorn backend.main:app --reload
```
Open http://127.0.0.1:8000/ and http://127.0.0.1:8000/docs

## 5. Start frontend (second terminal)
```powershell
cd frontend
npm install
npm run dev
```
Open the Vite URL, normally http://localhost:5173.

## 6. Test with Postman
Upload:
- POST `http://127.0.0.1:8000/api/videos/upload`
- Body > form-data; key `file` set to File; select a supported video.

YouTube:
- POST `http://127.0.0.1:8000/api/videos/youtube`
- Body > raw > JSON: `{"url":"https://www.youtube.com/watch?v=VIDEO_ID"}`

Status/results:
- GET `/api/videos`
- GET `/api/videos/1`
- GET `/api/videos/1/transcript`
- GET `/api/videos/1/quiz`
Use the actual video ID returned by the API. Keep the backend running while processing.

## Troubleshooting
- MySQL connection refused: start MySQL Server and check port 3306.
- Access denied: check username/password and grants.
- `ffmpeg` not recognized: add the folder containing `ffmpeg.exe` (e.g. `C:\\ffmpeg\\bin`) to Windows PATH and restart VS Code.
- Whisper can be slow. Set `WHISPER_MODEL=tiny` in `.env` for an initial test.
- YouTube downloads require yt-dlp's JavaScript challenge solver and a supported JavaScript runtime. Install the project requirements in the backend venv with `python -m pip install -r requirements.txt`; Node.js 22+ is enabled automatically when it is on PATH. Restart the backend after installing or updating dependencies. The app retries transient requests and shows a shorter troubleshooting message; technical details remain in the backend terminal.
- If YouTube requires you to sign in, close the browser first, then set `YOUTUBE_COOKIES_FROM_BROWSER=chrome` in `.env` (or `edge` / `firefox`) and restart the backend. This reads your browser's YouTube session; keep `.env` private. Cookie access is not a workaround for content you are not authorized to access.
- YouTube can still block automated downloads based on video restrictions, account checks, or network/firewall rules. In that case, upload a video file you have permission to use. Follow YouTube's terms.

## Database migrations

Alembic is the schema lifecycle mechanism. The API startup no longer calls `Base.metadata.create_all()`. Set `DATABASE_URL` in the local environment or `.env` file; credentials are not stored in `alembic.ini` or migration scripts.

For a **fresh database**, create an empty database, then run from the project root:

```powershell
.\venv\Scripts\alembic.exe upgrade head
```

The baseline creates the existing `videos`, `transcripts`, and `questions` schema, then the next migration adds `questions.quiz_version`. The following additive revision creates `exam_attempts` and `exam_responses`.

Quiz generation now preserves earlier question rows and assigns each successful non-empty generation the next per-video version. Quiz retrieval and grading use only the latest stored version; grading rejects submitted IDs from older versions. The quiz response adds a top-level `quiz_version` integer (or `null` when no quiz exists) while retaining its existing fields. Existing questions become version 1 through the migration; the first successful regeneration after migration will therefore be version 2.

For the **existing MySQL database**, do not run `upgrade` against it until its live schema has been compared with `0001_existing_schema_baseline.py` and all tables, columns, types, nullability, keys, and indexes match. Resolve any differences with a reviewed migration or a separately reviewed schema change. Only after reconciliation should an operator explicitly stamp the baseline revision (`0001_existing_schema`) and then apply later migrations. Stamping is not automatic and does not inspect or modify the schema. This repository does not run `stamp` as part of startup.

MySQL may commit DDL implicitly. If a migration fails, inspect the schema and data before retrying or downgrading; do not assume automatic rollback. The question-version downgrade removes only its index and column, while the baseline downgrade is deliberately blocked because dropping its tables would delete application data.
