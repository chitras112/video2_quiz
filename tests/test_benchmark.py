"""Synthetic unit tests for benchmark math and exports; no experiment data is used."""

import csv
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from benchmark.measurements import ExperimentResult, count_transcript_words, summarize
from benchmark.reporting import read_experiment_csv, write_csvs, write_paper_reports
from benchmark import runner
from backend.database.database import Base
from backend.models import Video


def synthetic_result(name, *, total=None, size=None, status="success", ffmpeg=None):
    return ExperimentResult(
        experiment_id=name, input_file="synthetic-video.mp4", repetition=1,
        started_at="2026-01-01T00:00:00+00:00", ended_at="2026-01-01T00:00:01+00:00",
        file_size_bytes=size, video_duration_seconds=None, transcript_word_count=None, ingestion_seconds=0.2,
        ffmpeg_seconds=ffmpeg, transcription_seconds=None, quiz_generation_seconds=None,
        total_seconds=total, peak_memory_mb=None, status=status,
        error="synthetic failure" if status == "failed" else None,
    )


def test_summary_uses_only_observed_values_and_reports_sample_count():
    rows = [synthetic_result("a", total=2.0, size=1024), synthetic_result("b", total=4.0, size=2048)]
    summary = {row["metric"]: row for row in summarize(rows)}
    assert summary["total_seconds"]["mean"] == 3.0
    assert summary["total_seconds"]["median"] == 3.0
    assert summary["total_seconds"]["standard_deviation"] is not None
    assert summary["total_seconds"]["sample_count"] == 2
    assert summary["peak_memory_mb"]["mean"] is None
    assert summary["peak_memory_mb"]["sample_count"] == 0


def test_failed_runs_and_missing_stage_measurements_are_not_dropped(tmp_path):
    rows = [
        synthetic_result("ok", total=3.0, ffmpeg=1.1),
        synthetic_result("failed", total=1.0, status="failed", ffmpeg=None),
    ]
    experiments_path, summary_path = write_csvs(rows, tmp_path, "synthetic")
    with experiments_path.open(newline="", encoding="utf-8") as handle:
        experiments = list(csv.DictReader(handle))
    with summary_path.open(newline="", encoding="utf-8") as handle:
        summary = {row["metric"]: row for row in csv.DictReader(handle)}
    assert len(experiments) == 2
    assert [row["status"] for row in experiments] == ["success", "failed"]
    assert experiments[1]["ffmpeg_seconds"] == ""
    assert experiments[1]["error"] == "synthetic failure"
    assert summary["total_seconds"]["sample_count"] == "2"
    assert summary["ffmpeg_seconds"]["sample_count"] == "1"
    assert summary["peak_memory_mb"]["sample_count"] == "0"


@pytest.mark.parametrize("processing_fails", [False, True])
def test_runner_disposes_sqlite_engine_before_temporary_directory_cleanup(
    tmp_path, monkeypatch, processing_fails
):
    input_dir = tmp_path / "inputs"
    input_dir.mkdir()
    (input_dir / "synthetic.mp4").write_bytes(b"synthetic test input; no video processing is run")
    runtime = {}

    def load_runtime(work_dir):
        db_path = work_dir / "benchmark.sqlite3"
        data_dir = work_dir / "data"
        video_dir = data_dir / "videos"
        video_dir.mkdir(parents=True)
        engine = create_engine(f"sqlite:///{db_path}", pool_pre_ping=True)
        Base.metadata.create_all(bind=engine)
        local_sessions = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        runtime["work_dir"] = work_dir
        runtime["db_path"] = db_path

        def process_video(video_id):
            if processing_fails:
                raise RuntimeError("synthetic processing failure")
            with local_sessions() as db:
                video = db.get(Video, video_id)
                video.status = "completed"
                db.commit()

        service = SimpleNamespace(
            extract_audio=lambda *_args, **_kwargs: None,
            transcribe_audio=lambda *_args, **_kwargs: None,
            persist_questions=lambda *_args, **_kwargs: 0,
            process_video=process_video,
        )
        return local_sessions, video_dir, service

    monkeypatch.setattr(runner, "_load_isolated_runtime", load_runtime)
    monkeypatch.setattr(runner, "probe_duration", lambda _path: None)
    monkeypatch.setattr(runner, "write_paper_reports", lambda *_args, **_kwargs: ([], tmp_path / "stages.csv", tmp_path / "status.csv"))

    results, *_ = runner.run_benchmarks(input_dir, repetitions=1, output_dir=tmp_path / "out")

    assert results[0].status == ("failed" if processing_fails else "success")
    assert not runtime["db_path"].exists()
    assert not runtime["work_dir"].exists()


def test_transcript_word_count_only_reports_supported_real_text():
    assert count_transcript_words("Whisper's result has 7 words.", "en") == 5
    assert count_transcript_words("   ", "en") is None
    assert count_transcript_words("你好世界", "zh") is None


def test_paper_reports_use_successful_rows_and_report_stage_sample_counts(tmp_path):
    first = synthetic_result("ok-1", total=4.0, size=1024, ffmpeg=1.0)
    first.video_duration_seconds = 20
    first.transcript_word_count = 100
    second = synthetic_result("ok-2", total=6.0, size=2048, ffmpeg=3.0)
    second.input_file = "second-synthetic-video.mp4"
    second.video_duration_seconds = 40
    second.transcript_word_count = 200
    failed = synthetic_result("bad", total=99.0, size=3072, status="failed", ffmpeg=99.0)
    failed.video_duration_seconds = 60
    failed.transcript_word_count = 300

    graphs, stages_path, statuses_path = write_paper_reports(
        [first, second, failed], tmp_path, "synthetic-paper"
    )
    assert len(graphs) == 8
    expected_stems = {
        "synthetic-paper_01_file_size_vs_total_time",
        "synthetic-paper_02_video_duration_vs_total_time",
        "synthetic-paper_03_transcript_words_vs_total_time",
        "synthetic-paper_04_pipeline_stage_mean_times",
    }
    assert {path.stem for path in graphs} == expected_stems
    assert {path.suffix for path in graphs} == {".png", ".pdf"}
    assert all(path.exists() and path.stat().st_size > 0 for path in graphs)
    with stages_path.open(newline="", encoding="utf-8") as handle:
        stages = {row["stage"]: row for row in csv.DictReader(handle)}
    assert stages["FFmpeg extraction"]["mean_seconds"] == "2.0"
    assert stages["FFmpeg extraction"]["sample_count"] == "2"
    with statuses_path.open(newline="", encoding="utf-8") as handle:
        statuses = {row["status"]: row["experiment_count"] for row in csv.DictReader(handle)}
    assert statuses == {"failed": "1", "success": "2"}


def test_paper_report_omits_transcript_graph_when_measurement_is_missing(tmp_path):
    result = synthetic_result("old-row", total=2.0, size=1024, ffmpeg=0.5)
    result.video_duration_seconds = 10
    second = synthetic_result("old-row-2", total=3.0, size=2048, ffmpeg=0.7)
    second.input_file = "another-synthetic-video.mp4"
    second.video_duration_seconds = 20
    graphs, *_ = write_paper_reports([result, second], tmp_path, "old-paper")
    assert len(graphs) == 6
    assert not any("transcript_words" in path.name for path in graphs)


def test_paper_report_preserves_repetitions_and_writes_run_audit(tmp_path):
    rows = []
    for video_index in range(2):
        for repetition, seconds in enumerate((2.0, 4.0, 8.0), start=1):
            row = synthetic_result(f"v{video_index}-r{repetition}", total=seconds,
                                   size=1024 * (video_index + 1), ffmpeg=seconds / 4)
            row.input_file = f"video-{video_index}.mp4"
            row.repetition = repetition
            row.video_duration_seconds = 10 + video_index
            row.transcript_word_count = 100 + video_index
            rows.append(row)
    failed = synthetic_result("failed", total=90, status="failed", ffmpeg=90)
    failed.input_file = "failed-video.mp4"
    rows.append(failed)

    outputs, _, _ = write_paper_reports(rows, tmp_path, "repeat-paper")
    assert len(outputs) == 8
    summary_path = tmp_path / "repeat-paper_run_summary.csv"
    with summary_path.open(newline="", encoding="utf-8") as handle:
        summary = next(csv.DictReader(handle))
    assert summary["total_runs"] == "7"
    assert summary["successful_runs"] == "6"
    assert summary["failed_or_incomplete_runs"] == "1"
    assert summary["distinct_videos"] == "2"
    assert summary["repetition_values"] == "1;2;3"
    assert all(path.stat().st_size > 0 for path in outputs)


def test_relationship_graphs_require_two_distinct_videos(tmp_path):
    first = synthetic_result("repeat-1", total=2.0, size=1024, ffmpeg=0.5)
    first.video_duration_seconds = 10
    second = synthetic_result("repeat-2", total=3.0, size=1024, ffmpeg=0.7)
    second.repetition = 2
    second.video_duration_seconds = 10
    graphs, *_ = write_paper_reports([first, second], tmp_path, "one-video")
    assert {path.stem for path in graphs} == {"one-video_04_pipeline_stage_mean_times"}
    assert {path.suffix for path in graphs} == {".png", ".pdf"}


def test_existing_csv_without_transcript_measurement_loads_as_unavailable(tmp_path):
    csv_path, _ = write_csvs([synthetic_result("legacy", total=1.0, size=1024)], tmp_path, "legacy")
    loaded = read_experiment_csv(csv_path)
    assert len(loaded) == 1
    assert loaded[0].transcript_word_count is None

