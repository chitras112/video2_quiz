"""CSV and publication-style plot exports for benchmark measurements."""

from __future__ import annotations

import csv
import logging
import math
import random
import statistics
from pathlib import Path
from typing import Iterable

from benchmark.measurements import ExperimentResult, summarize

LOG = logging.getLogger("video2quiz.benchmark")


def write_csvs(results: Iterable[ExperimentResult], output_dir: Path, run_name: str) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = list(results)
    experiments_path = output_dir / f"{run_name}_experiments.csv"
    summary_path = output_dir / f"{run_name}_summary.csv"

    fields = list(rows[0].to_csv_row()) if rows else [
        "experiment_id", "input_file", "repetition", "started_at", "ended_at",
        "file_size_bytes", "video_duration_seconds", "ingestion_seconds",
        "transcript_word_count", "ffmpeg_seconds", "transcription_seconds", "quiz_generation_seconds",
        "total_seconds", "peak_memory_mb", "status", "error", "file_size_mb",
    ]
    with experiments_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(result.to_csv_row() for result in rows)

    with summary_path.open("w", newline="", encoding="utf-8") as handle:
        fields = ["metric", "mean", "median", "standard_deviation", "sample_count"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(summarize(rows))
    return experiments_path, summary_path


def read_experiment_csv(path: Path) -> list[ExperimentResult]:
    """Load existing experiment rows for report-only graph generation."""
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not {"experiment_id", "input_file", "status"}.issubset(reader.fieldnames):
            raise ValueError("CSV must contain experiment_id, input_file, and status columns")

        def optional_int(row: dict[str, str], key: str) -> int | None:
            value = row.get(key, "")
            return int(value) if value not in (None, "") else None

        def optional_float(row: dict[str, str], key: str) -> float | None:
            value = row.get(key, "")
            return float(value) if value not in (None, "") else None

        results = []
        for row in reader:
            results.append(ExperimentResult(
                experiment_id=row["experiment_id"], input_file=row["input_file"],
                repetition=optional_int(row, "repetition") or 1,
                started_at=row.get("started_at", ""), ended_at=row.get("ended_at", ""),
                file_size_bytes=optional_int(row, "file_size_bytes"),
                video_duration_seconds=optional_float(row, "video_duration_seconds"),
                transcript_word_count=optional_int(row, "transcript_word_count"),
                ingestion_seconds=optional_float(row, "ingestion_seconds"),
                ffmpeg_seconds=optional_float(row, "ffmpeg_seconds"),
                transcription_seconds=optional_float(row, "transcription_seconds"),
                quiz_generation_seconds=optional_float(row, "quiz_generation_seconds"),
                total_seconds=optional_float(row, "total_seconds"),
                peak_memory_mb=optional_float(row, "peak_memory_mb"),
                status=row["status"], error=row.get("error") or None,
            ))
    return results


def write_paper_reports(
    results: Iterable[ExperimentResult], output_dir: Path, run_name: str
) -> tuple[list[Path], Path, Path]:
    """Write four consistent research-style PNG/PDF figures and summaries.

    A graph is omitted when its required real measurements are unavailable.
    Failed experiments are counted in the status report and excluded from all
    time plots.
    """
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError("Paper figure generation requires Matplotlib.") from exc

    rows = list(results)
    output_dir.mkdir(parents=True, exist_ok=True)
    successful = [row for row in rows if row.status == "success"]
    outputs: list[Path] = []
    theme = {
        "font.family": "DejaVu Sans",
        "font.size": 9.5,
        "axes.titlesize": 13,
        "axes.labelsize": 10,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "axes.labelcolor": "#263746",
        "text.color": "#142b43",
        "axes.edgecolor": "#cbd5df",
        "axes.linewidth": 0.8,
        "axes.facecolor": "#ffffff",
        "figure.facecolor": "#f7f9fc",
        "savefig.facecolor": "#f7f9fc",
        "grid.color": "#dce4eb",
        "grid.linewidth": 0.7,
        "grid.alpha": 0.75,
        "savefig.dpi": 300,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    }
    navy, teal, orange, muted = "#142b43", "#087e8b", "#df7b35", "#536779"

    status_path = output_dir / f"{run_name}_status_summary.csv"
    status_counts: dict[str, int] = {}
    for row in rows:
        status_counts[row.status] = status_counts.get(row.status, 0) + 1
    with status_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["status", "experiment_count"])
        writer.writeheader()
        writer.writerows({"status": key, "experiment_count": value} for key, value in sorted(status_counts.items()))
    failed_count = sum(value for key, value in status_counts.items() if key != "success")
    LOG.info("Styled timing figures use %d successful runs; %d failed/non-successful runs excluded.",
             len(successful), failed_count)

    stages = (
        ("ingestion_seconds", "Video ingestion"),
        ("ffmpeg_seconds", "FFmpeg extraction"),
        ("transcription_seconds", "Whisper transcription"),
        ("quiz_generation_seconds", "Quiz generation"),
    )
    stage_stats: list[dict[str, object]] = []
    for field, label in stages:
        values = [
            float(value) for row in successful
            if (value := getattr(row, field)) is not None and math.isfinite(float(value))
        ]
        stage_stats.append({
            "stage": label,
            "mean_seconds": statistics.mean(values) if values else None,
            "standard_deviation_seconds": statistics.stdev(values) if len(values) > 1 else None,
            "sample_count": len(values),
        })
    stage_path = output_dir / f"{run_name}_stage_summary.csv"
    with stage_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["stage", "mean_seconds", "standard_deviation_seconds", "sample_count"])
        writer.writeheader()
        writer.writerows(stage_stats)

    slow_transcript_ids: set[str] = set()

    def scatter(metric: str, xlabel: str, title: str, suffix: str) -> None:
        grouped: dict[str, list[ExperimentResult]] = {}
        for row in successful:
            x, y = getattr(row, metric), row.total_seconds
            if x is not None and y is not None and math.isfinite(float(x)) and math.isfinite(float(y)):
                grouped.setdefault(row.input_file, []).append(row)
        if len(grouped) < 2:
            LOG.warning(
                "Omitting %s: only %d distinct video(s) have both successful measurements; "
                "at least two videos are needed for a relationship plot.",
                title, len(grouped),
            )
            return
        if metric == "transcript_word_count":
            words = [int(row.transcript_word_count) for samples in grouped.values() for row in samples]
            ordered = sorted(words)
            q1 = statistics.median(ordered[:len(ordered) // 2])
            q3 = statistics.median(ordered[(len(ordered) + 1) // 2:])
            times = [float(row.total_seconds) for samples in grouped.values() for row in samples]
            time_fence = None
            if len(times) >= 4:
                ordered_times = sorted(times)
                tq1 = statistics.median(ordered_times[:len(ordered_times) // 2])
                tq3 = statistics.median(ordered_times[(len(ordered_times) + 1) // 2:])
                time_fence = tq3 + 1.5 * (tq3 - tq1)
            for samples in grouped.values():
                for row in samples:
                    if row.total_seconds is not None and time_fence is not None and row.total_seconds > time_fence:
                        slow_transcript_ids.add(row.experiment_id)
        fig, ax = plt.subplots(figsize=(7.2, 5.0), constrained_layout=False)
        points: list[tuple[float, float]] = []
        all_x = [float(getattr(row, metric)) for samples in grouped.values() for row in samples]
        span = max(all_x) - min(all_x)
        trial_palette = [teal, "#58a5aa", "#9bc8c5", "#df7b35", "#657aab"]
        repetition_values = sorted({row.repetition for samples in grouped.values() for row in samples})
        for samples in grouped.values():
            xs = [float(getattr(item, metric)) for item in samples]
            ys = [float(item.total_seconds) for item in samples]
            x_mean, y_mean = statistics.mean(xs), statistics.mean(ys)
            points.append((x_mean, y_mean))
            max_rep = max(item.repetition for item in samples)
            for item, x, y in zip(samples, xs, ys):
                jitter = ((item.repetition - 1) - (max_rep - 1) / 2) * span * 0.003
                slow = item.experiment_id in slow_transcript_ids
                ax.scatter(x + jitter, y, s=54 if slow else 39, marker="D" if slow else "o",
                           facecolor=(orange if slow else trial_palette[(item.repetition - 1) % len(trial_palette)]),
                           edgecolor=navy, linewidth=0.65, alpha=0.9, zorder=4)
            sd = statistics.stdev(ys) if len(ys) > 1 else None
            if sd is not None:
                ax.errorbar(x_mean, y_mean, yerr=[[min(sd, y_mean)], [sd]], fmt="D", markersize=6,
                            markerfacecolor=navy, markeredgecolor="white", ecolor=navy,
                            elinewidth=1, capsize=3, zorder=5)
        # Fit across video-level means, not repeated trials, so repeated runs
        # do not masquerade as independent videos in the trend line.
        x_values = [point[0] for point in points]
        y_values = [point[1] for point in points]
        trend_p = None
        if len(points) >= 5 and len(set(x_values)) >= 3:
            import numpy as np

            slope, intercept = np.polyfit(x_values, y_values, deg=1)
            observed = abs(float(np.corrcoef(x_values, y_values)[0, 1]))
            rng = random.Random(80421)
            exceed = 0
            for _ in range(4999):
                shuffled = list(y_values)
                rng.shuffle(shuffled)
                exceed += abs(float(np.corrcoef(x_values, shuffled)[0, 1])) >= observed
            trend_p = (exceed + 1) / 5000
            if trend_p < 0.05 / 3:
                trend_x = np.linspace(min(x_values), max(x_values), 120)
                ax.plot(trend_x, slope * trend_x + intercept, color=orange,
                        linewidth=2.0, label="Linear fit to video means", zorder=2)
                ax.legend(frameon=False, loc="best", fontsize=8.5)
        ax.set_xlabel(xlabel)
        ax.set_ylabel("Total processing time (seconds)")
        ax.set_title(title, loc="left", color=navy, fontweight="bold", pad=13)
        ax.grid(axis="y", zorder=0)
        ax.grid(axis="x", visible=False)
        ax.spines[["top", "right"]].set_visible(False)
        ax.spines[["left", "bottom"]].set_color("#cbd5df")
        from matplotlib.lines import Line2D
        legend_handles = [Line2D([0], [0], marker="o", color="none",
                                 markerfacecolor=trial_palette[(rep - 1) % len(trial_palette)],
                                 markeredgecolor=navy, label=f"Repetition {rep}", markersize=6)
                          for rep in repetition_values]
        legend_handles.append(Line2D([0], [0], marker="D", color="none", markerfacecolor=navy,
                                     markeredgecolor="white", label="Video mean ±1 SD", markersize=6))
        if legend_handles:
            ax.legend(handles=legend_handles, frameon=False, loc="best", fontsize=7.5, ncols=2)
        fig.text(
            0.12, 0.025,
            f"Individual trials; navy diamonds show video means with ±1 SD. "
            f"{len(successful)} successful runs across {len(grouped)} videos; "
            f"{failed_count} failed/incomplete runs excluded. Trend line only if video-level permutation test passes p<0.0167.",
            color=muted, fontsize=8, ha="left",
        )
        fig.subplots_adjust(left=0.13, right=0.97, top=0.88, bottom=0.17)
        for extension in ("png", "pdf"):
            path = output_dir / f"{run_name}_{suffix}.{extension}"
            fig.savefig(path, bbox_inches="tight", dpi=300 if extension == "png" else None)
            outputs.append(path)
        plt.close(fig)

    with plt.rc_context(theme):
        scatter(
            "file_size_mb", "Video file size (MiB)",
            "File size and total processing time", "01_file_size_vs_total_time",
        )
        scatter(
            "video_duration_seconds", "Video duration (seconds)",
            "Duration and total processing time", "02_video_duration_vs_total_time",
        )
        scatter(
            "transcript_word_count", "Transcript length (words)",
            "Transcript length and total processing time", "03_transcript_words_vs_total_time",
        )

    measured_stages = [item for item in stage_stats if item["sample_count"]]
    if measured_stages:
        with plt.rc_context(theme):
            fig, ax = plt.subplots(figsize=(7.2, 5.0), constrained_layout=False)
            labels = [str(item["stage"]) for item in measured_stages]
            means = [float(item["mean_seconds"]) for item in measured_stages]
            errors = [float(item["standard_deviation_seconds"] or 0.0) for item in measured_stages]
            positions = list(range(len(labels)))
            colors = [teal, teal, orange, teal][:len(labels)]
            lower_errors = [min(error, mean) for error, mean in zip(errors, means)]
            bars = ax.barh(
                positions, means, xerr=[lower_errors, errors], height=0.62,
                color=colors, edgecolor="white", linewidth=1,
                error_kw={"ecolor": navy, "elinewidth": 1.2, "capsize": 3},
                zorder=3,
            )
            ax.set_yticks(positions, labels)
            ax.invert_yaxis()
            # Stage durations span milliseconds through minutes. A symmetric
            # log axis keeps short stages visible while retaining a true zero
            # baseline for the horizontal bars.
            ax.set_xscale("symlog", linthresh=0.01)
            ax.set_xlabel("Mean processing time (seconds; symmetric log scale)")
            ax.set_ylabel("Pipeline stage")
            ax.set_title("Mean time by pipeline stage", loc="left", color=navy,
                         fontweight="bold", pad=13)
            ax.grid(axis="x", zorder=0)
            ax.grid(axis="y", visible=False)
            ax.spines[["top", "right", "left"]].set_visible(False)
            ax.spines["bottom"].set_color("#cbd5df")
            max_mean = max(means) if means else 0.0
            max_error = max(errors) if errors else 0.0
            ax.set_xlim(0, max_mean + max_error + max(0.08 * (max_mean + max_error), 0.05))
            for bar, item, error in zip(bars, measured_stages, errors):
                label_x = bar.get_width() + error
                ax.annotate(
                    f"{bar.get_width():.3g}s; n={item['sample_count']}",
                    (label_x, bar.get_y() + bar.get_height() / 2),
                    xytext=(7, 0), textcoords="offset points", va="center", ha="left",
                    color=muted, fontsize=8.5,
                )
            fig.text(0.13, 0.025,
                     f"Bars show mean ±1 SD across available observations (n shown); lower bounds are clipped at zero. "
                     f"{len(successful)} successful runs; {failed_count} failed/incomplete runs excluded.",
                     color=muted, fontsize=8, ha="left")
            fig.subplots_adjust(left=0.31, right=0.96, top=0.88, bottom=0.17)
            for extension in ("png", "pdf"):
                path = output_dir / f"{run_name}_04_pipeline_stage_mean_times.{extension}"
                fig.savefig(path, bbox_inches="tight", dpi=300 if extension == "png" else None)
                outputs.append(path)
            plt.close(fig)
    else:
        LOG.warning("Omitting pipeline-stage graph: no successful stage timings were recorded.")

    # Keep a concise, machine-readable account of the source set and any
    # unusually slow transcript-plot observations. Outliers remain plotted.
    run_summary_path = output_dir / f"{run_name}_run_summary.csv"
    with run_summary_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["total_runs", "successful_runs", "failed_or_incomplete_runs",
                                                    "distinct_videos", "repetition_values", "slow_observations"])
        writer.writeheader()
        writer.writerow({
            "total_runs": len(rows), "successful_runs": len(successful),
            "failed_or_incomplete_runs": failed_count,
            "distinct_videos": len({row.input_file for row in successful}),
            "repetition_values": ";".join(map(str, sorted({row.repetition for row in successful}))),
            "slow_observations": len(slow_transcript_ids),
        })
    completeness_path = output_dir / f"{run_name}_measurement_completeness.csv"
    metric_fields = (
        "file_size_mb", "video_duration_seconds", "transcript_word_count", "total_seconds",
        "ingestion_seconds", "ffmpeg_seconds", "transcription_seconds", "quiz_generation_seconds",
    )
    with completeness_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["metric", "successful_rows", "measured_rows", "missing_rows"])
        writer.writeheader()
        for field in metric_fields:
            measured = sum(
                getattr(row, field) is not None and math.isfinite(float(getattr(row, field)))
                for row in successful
            )
            writer.writerow({"metric": field, "successful_rows": len(successful),
                             "measured_rows": measured, "missing_rows": len(successful) - measured})
    slow_path = output_dir / f"{run_name}_slow_observations.csv"
    with slow_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["experiment_id", "input_file", "repetition", "transcript_word_count", "total_seconds"])
        writer.writeheader()
        for row in successful:
            if row.experiment_id in slow_transcript_ids:
                writer.writerow({"experiment_id": row.experiment_id, "input_file": row.input_file,
                                 "repetition": row.repetition, "transcript_word_count": row.transcript_word_count,
                                 "total_seconds": row.total_seconds})

    return outputs, stage_path, status_path


def write_graphs(results: Iterable[ExperimentResult], output_dir: Path, run_name: str) -> list[Path]:
    """Compatibility wrapper returning the four redesigned PNG files."""
    outputs, _, _ = write_paper_reports(results, output_dir, run_name)
    return [path for path in outputs if path.suffix.lower() == ".png"]

