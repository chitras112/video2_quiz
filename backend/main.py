from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.videos import router as videos_router
from backend.database.database import engine  # noqa: F401; retained for app/test integrations

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = FastAPI(title="Video2Quiz API", description="Turn educational videos into timestamped practice quizzes.",
              version="0.5.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(videos_router, prefix="/api")

@app.get("/", tags=["Health"])
def root():
    return {"message": "Video2Quiz API is running", "status": "healthy", "version": "0.5.0"}
