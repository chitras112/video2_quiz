"""Sequential CLI runner that isolates Video2Quiz processing in temporary SQLite/data paths."""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import close_all_sessions

from benchmark.measurements import ExperimentResult, count_transcript_words
from benchmark.reporting import read_experiment_csv, write_csvs, write_paper_reports

LOG = logging.getLogger("video2quiz.benchmark")
SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi"}


def probe_duration(path: Path) -> float | None:
    """Read container duration with ffprobe; return unavailable on probe failure."""
    try:
        proc = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, timeout=30, check=True,
        )
        duration = float(proc.stdout.strip())
        return duration if duration >= 0 else None
    except (OSError, subprocess.SubprocessError, ValueError):
        LOG.warning("Duration unavailable for %s (ffprobe failed)", path.name)
        return None


def _load_isolated_runtime(work_dir: Path):
    """Set process configuration before importing modules that capture globals."""
    db_path = (work_dir / "benchmark.sqlite3").resolve()
    data_path = (work_dir / "data").resolve()
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    os.environ["VIDEO2QUIZ_DATA_DIR"] = str(data_path)

    from backend.database.database import Base, SessionLocal
    import backend.models  # noqa: F401
    from backend.utils.storage import VIDEO_DIR
    import backend.services.video_service as video_service

    Base.metadata.create_all(bind=SessionLocal.kw["bind"])
    return SessionLocal, VIDEO_DIR, video_service


def _timed(function, key: str, durations: dict[str, float]):
    def wrapped(*args, **kwargs):
        started = time.perf_counter()
        try:
            return function(*args, **kwargs)
        finally:
            durations[key] = time.perf_counter() - started
    return wrapped


def run_benchmarks(input_dir: Path, repetitions: int, output_dir: Path) -> tuple[list[ExperimentResult], Path, Path, list[Path]]:
    input_dir = input_dir.expanduser().resolve()
    if not input_dir.is_dir():
        raise ValueError(f"Input directory does not exist: {input_dir}")
    files = sorted(path for path in input_dir.iterdir() if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS)
    if not files:
        raise ValueError(f"No supported video files found in {input_dir}")
    if repetitions < 1:
        raise ValueError("Repetitions must be at least 1")

    results: list[ExperimentResult] = []
    run_name = datetime.now().strftime("benchmark_%Y%m%d_%H%M%S_%f")
    output_dir = output_dir.expanduser().resolve()
    with tempfile.TemporaryDirectory(prefix="video2quiz-benchmark-") as temporary:
        work_dir = Path(temporary)
        SessionLocal, video_dir, service = _load_isolated_runtime(work_dir)
        from backend.models.video import Transcript, Video

        originals = {
            "extract_audio": service.extract_audio,
            "transcribe_audio": service.transcribe_audio,
            "persist_questions": service.persist_questions,
        }
        try:
            total_runs = len(files) * repetitions
            for index, (source, repetition) in enumerate(
                ((source, repetition) for source in files for repetition in range(1, repetitions + 1)), 1
            ):
                LOG.info("Experiment %d/%d: %s (repetition %d/%d)", index, total_runs, source.name, repetition, repetitions)
                duration = probe_duration(source)
                started_at = datetime.now(timezone.utc)
                wall_start = time.perf_counter()
                stage_durations: dict[str, float] = {}
                experiment_id = uuid4().hex
                video_id: int | None = None
                status = "failed"
                error: str | None = None
                size_bytes: int | None = None
                transcript_word_count: int | None = None
                service.extract_audio = originals["extract_audio"]
                service.transcribe_audio = originals["transcribe_audio"]
                service.persist_questions = originals["persist_questions"]
                service.extract_audio = _timed(originals["extract_audio"], "ffmpeg_seconds", stage_durations)
                service.transcribe_audio = _timed(originals["transcribe_audio"], "transcription_seconds", stage_durations)
                service.persist_questions = _timed(originals["persist_questions"], "quiz_generation_seconds", stage_durations)
                try:
                    ingest_start = time.perf_counter()
                    destination = video_dir / f"{experiment_id}{source.suffix.lower()}"
                    shutil.copyfile(source, destination)
                    size_bytes = destination.stat().st_size
                    db = SessionLocal()
                    try:
                        video = Video(
                            source_type="upload", original_filename=source.name[:255],
                            stored_filename=destination.name, file_path=str(destination.resolve()), status="uploaded",
                        )
                        db.add(video)
                        db.commit()
                        db.refresh(video)
                        video_id = video.id
                    finally:
                        db.close()
                    stage_durations["ingestion_seconds"] = time.perf_counter() - ingest_start

                    service.process_video(video_id)
                    check = SessionLocal()
                    try:
                        processed = check.query(Video).filter(Video.id == video_id).first()
                        status = "success" if processed and processed.status in {"completed", "completed_no_speech"} else "failed"
                        if processed and processed.status == "failed":
                            error = processed.error_message
                        elif processed and processed.status in {"completed", "completed_no_speech"}:
                            transcript_row = check.query(Transcript.text, Transcript.language).filter(
                                Transcript.video_id == video_id
                            ).first()
                            if transcript_row:
                                transcript_word_count = count_transcript_words(
                                    transcript_row.text, transcript_row.language
                                )
                        elif processed and processed.status == "completed" and processed.error_message:
                            LOG.warning("%s completed with processing warning: %s", source.name, processed.error_message)
                        elif processed is None:
                            error = "Processing finished without a video database row."
                    finally:
                        check.close()
                except Exception as exc:
                    status = "failed"
                    error = f"{type(exc).__name__}: {exc}"
                    LOG.exception("Experiment failed for %s", source.name)
                finally:
                    service.extract_audio = originals["extract_audio"]
                    service.transcribe_audio = originals["transcribe_audio"]
                    service.persist_questions = originals["persist_questions"]

                ended_at = datetime.now(timezone.utc)
                result = ExperimentResult(
                    experiment_id=experiment_id, input_file=source.name, repetition=repetition,
                    started_at=started_at.isoformat(), ended_at=ended_at.isoformat(),
                    file_size_bytes=size_bytes, video_duration_seconds=duration,
                    transcript_word_count=transcript_word_count,
                    ingestion_seconds=stage_durations.get("ingestion_seconds"),
                    ffmpeg_seconds=stage_durations.get("ffmpeg_seconds"),
                    transcription_seconds=stage_durations.get("transcription_seconds"),
                    quiz_generation_seconds=stage_durations.get("quiz_generation_seconds"),
                    total_seconds=time.perf_counter() - wall_start,
                    peak_memory_mb=None, status=status, error=error,
                )
                results.append(result)
                # Persist each completed experiment immediately so an interrupted
                # later run does not discard already completed measurements.
                write_csvs(results, output_dir, run_name)
                LOG.info("Experiment %s: %s (%.2f s)", experiment_id, status, result.total_seconds or 0)
        finally:
            service.extract_audio = originals["extract_audio"]
            service.transcribe_audio = originals["transcribe_audio"]
            service.persist_questions = originals["persist_questions"]
            try:
                close_all_sessions()
            finally:
                # Closing sessions returns connections to the pool. Dispose the
                # pool as well so Windows releases the SQLite file before the
                # TemporaryDirectory context attempts to remove it.
                SessionLocal.kw["bind"].dispose()

    experiments_csv, summary_csv = write_csvs(results, output_dir, run_name)
    graphs, stage_summary, status_summary = write_paper_reports(results, output_dir, run_name)
    LOG.info("Saved stage summary to %s", stage_summary)
    LOG.info("Saved run-status summary to %s", status_summary)
    return results, experiments_csv, summary_csv, graphs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark the existing Video2Quiz processing pipeline.")
    parser.add_argument("--input-dir", type=Path, help="Directory containing supported local video files")
    parser.add_argument("--repetitions", type=int, default=1, help="Sequential runs per input video (default: 1)")
    parser.add_argument("--from-csv", type=Path, help="Generate paper reports from an existing experiment CSV without processing videos")
    parser.add_argument("--output-dir", type=Path, default=Path("benchmark_results_styled"), help="Directory for new styled figures and reports")
    parser.add_argument("--log-level", default="INFO", choices=("DEBUG", "INFO", "WARNING", "ERROR"))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level), format="%(asctime)s %(levelname)s %(message)s")
    try:
        if args.from_csv:
            results = read_experiment_csv(args.from_csv)
            source_stem = args.from_csv.stem.removesuffix("_experiments")
            run_name = f"paper_{source_stem}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
            graphs, stage_summary, status_summary = write_paper_reports(results, args.output_dir, run_name)
            experiments = args.from_csv.resolve()
            summary = stage_summary
            LOG.info("Read existing experiment rows from %s", experiments)
            LOG.info("Saved stage summary to %s", stage_summary)
            LOG.info("Saved run-status summary to %s", status_summary)
        else:
            if args.input_dir is None:
                raise ValueError("Provide --input-dir for a benchmark run or --from-csv for report-only mode")
            results, experiments, summary, graphs = run_benchmarks(args.input_dir, args.repetitions, args.output_dir)
    except (ValueError, RuntimeError) as exc:
        LOG.error("Benchmark stopped: %s", exc)
        return 2
    if not args.from_csv:
        LOG.info("Saved %d experiment rows to %s", len(results), experiments)
        LOG.info("Saved summaries to %s", summary)
    for path in graphs:
        LOG.info("Saved graph to %s", path)
    if all(result.peak_memory_mb is None for result in results):
        LOG.info("Peak memory unavailable: no reliable process memory monitor is configured.")
    return 0 if all(result.status == "success" for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

