"""Measurement records and summaries for Video2Quiz benchmark runs."""

from __future__ import annotations

import math
import re
import statistics
from dataclasses import asdict, dataclass
from typing import Iterable


@dataclass
class ExperimentResult:
    experiment_id: str
    input_file: str
    repetition: int
    started_at: str
    ended_at: str
    file_size_bytes: int | None = None
    video_duration_seconds: float | None = None
    transcript_word_count: int | None = None
    ingestion_seconds: float | None = None
    ffmpeg_seconds: float | None = None
    transcription_seconds: float | None = None
    quiz_generation_seconds: float | None = None
    total_seconds: float | None = None
    peak_memory_mb: float | None = None
    status: str = "failed"
    error: str | None = None

    @property
    def file_size_mb(self) -> float | None:
        if self.file_size_bytes is None:
            return None
        return self.file_size_bytes / (1024 * 1024)

    def to_csv_row(self) -> dict[str, object]:
        row = asdict(self)
        row["file_size_mb"] = self.file_size_mb
        return row


SUMMARY_METRICS = (
    "file_size_mb",
    "video_duration_seconds",
    "transcript_word_count",
    "ingestion_seconds",
    "ffmpeg_seconds",
    "transcription_seconds",
    "quiz_generation_seconds",
    "total_seconds",
    "peak_memory_mb",
)


_LANGUAGES_WITHOUT_RELIABLE_WHITESPACE_WORD_BOUNDARIES = {
    "bo", "ja", "km", "lo", "my", "th", "zh",
}


def count_transcript_words(text: str | None, language: str | None = None) -> int | None:
    """Count Unicode word tokens where whitespace/token boundaries are usable.

    Return unavailable for empty text and languages without dependable
    whitespace-delimited word boundaries; do not present a character/token
    count as a linguistic word count for those languages.
    """
    if not text or not text.strip():
        return None
    language_code = (language or "").lower().split("-")[0].split("_")[0]
    if language_code in _LANGUAGES_WITHOUT_RELIABLE_WHITESPACE_WORD_BOUNDARIES:
        return None
    return len(re.findall(r"\b[\w]+(?:[’'-][\w]+)*\b", text, flags=re.UNICODE))


def summarize(results: Iterable[ExperimentResult]) -> list[dict[str, object]]:
    """Summarize observed values only; failed runs remain in experiment CSV."""
    rows = list(results)
    summary: list[dict[str, object]] = []
    for metric in SUMMARY_METRICS:
        values = [
            float(value)
            for result in rows
            if (value := getattr(result, metric)) is not None
            and math.isfinite(float(value))
        ]
        n = len(values)
        summary.append(
            {
                "metric": metric,
                "mean": statistics.mean(values) if n else None,
                "median": statistics.median(values) if n else None,
                "standard_deviation": statistics.stdev(values) if n > 1 else None,
                "sample_count": n,
            }
        )
    return summary

