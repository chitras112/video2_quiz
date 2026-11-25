# Video2Quiz performance benchmark

This standalone benchmark measures the existing local-video processing services. It does not use the application's configured database: each CLI invocation sets `DATABASE_URL` to a temporary SQLite file and `VIDEO2QUIZ_DATA_DIR` to a temporary working tree **before importing backend modules**. Its benchmark video rows, transcripts, questions, audio files, and transcript artifacts are isolated and removed with that temporary directory when the run exits. Source videos are read only. No application migration or schema change is performed.

## Setup

Run commands from the `Video2Quiz` project root, with the project's virtual environment activated. Python requirements already used by the application provide FastAPI, SQLAlchemy, Whisper, and the services. FFmpeg and `ffprobe` must be on `PATH`.

PNG graphs require Matplotlib. Install it into the active virtual environment if it is not already present:

```powershell
python -m pip install matplotlib
```

The benchmark does not currently report peak memory: no reliable peak-memory monitor is configured. CSV memory cells remain empty and the memory graph is omitted. Do not interpret unavailable memory as zero.

## Run

Put the real input videos in a directory. Supported extensions are `.mp4`, `.mov`, `.mkv`, `.webm`, and `.avi`. The default is one sequential run per video; specify repetitions to measure repeat variation.

```powershell
python -m benchmark.runner --input-dir "C:\path\to\benchmark-videos" --repetitions 3 --output-dir "benchmark_results_styled"
```

The runner processes one video at a time. It logs each experiment, continues after per-video failures, records failed experiments and errors in the results, and returns a non-zero exit code if any experiment failed. CSV files are updated after every completed experiment. To stop safely, press **Ctrl+C** in the benchmark terminal; completed rows remain in the output CSV, while an interrupted in-progress experiment may not have a result row or final graphs.

## Outputs and measurements

Each invocation writes timestamped files under the requested output directory. The default styled output folder is `benchmark_results_styled`. It contains these four figures when required measurements exist, each as a 600-DPI PNG and vector PDF:

- `*_experiments.csv`: one row per video/repetition, including status, error, timestamps, source file size, probed duration, measured transcript word count, ingestion, FFmpeg, Whisper, quiz-generation, and total wall times. Unavailable measurements are blank.
- `*_summary.csv`: mean, median, sample standard deviation (blank for fewer than two observations), and sample count for each available metric. Measurements are not silently filled or inferred.
- `*_01_file_size_vs_total_time.*`: file size in MiB versus total time in seconds.
- `*_02_video_duration_vs_total_time.*`: video duration in seconds versus total time in seconds.
- `*_03_transcript_words_vs_total_time.*`: persisted transcript word count versus total time. Omitted if no supported, non-empty transcript measurement is available.
- `*_04_pipeline_stage_mean_times.*`: mean seconds per measured pipeline stage, with sample counts shown on the plot.
- `*_stage_summary.csv` and `*_status_summary.csv`: stage means, standard deviations, sample counts, and successful/failed experiment counts. Failed/non-successful runs are retained in CSV and excluded from timing figures.

File size is reported in MiB (bytes divided by 1,048,576); duration and times are in seconds. Duration comes from `ffprobe`; if probing fails it is unavailable. Ingestion includes copying the source into the isolated data directory and creating its SQLite video record. Stage durations wrap the existing FFmpeg extraction, Whisper transcription, and quiz persistence service calls. Total time includes ingestion, service processing, and status/result inspection. Whisper model loading is included because the existing service loads its model inside transcription. Word count is derived from the transcript persisted by the existing pipeline using Unicode word-token boundaries; it is left unavailable for empty text and languages without dependable whitespace word boundaries (including Chinese, Japanese, Thai, Khmer, Lao, Burmese, and Tibetan).

Relationship plots require at least two distinct videos with valid measurements and show per-video means; error bars show ±1 standard error only when repeated runs exist for that video. Trend lines are fitted to video-level means only when at least three videos have distinct X values. Stage bars use successful measurements only, show mean values and sample counts, and use ±1 standard error when repeated observations exist. Their symmetric-log X axis preserves a zero baseline while keeping sub-second stages visible next to long transcription times. The status summary reports failed/non-successful runs separately. A single observation per video is not represented as repeated trials.

To make figures from an existing experiment CSV without processing videos again:

```powershell
python -m benchmark.runner --from-csv "benchmark_results_repeated\benchmark_RUN_experiments.csv" --output-dir "benchmark_results_styled"
```

Older CSVs without `transcript_word_count` can produce only the figures whose required measured columns exist. The transcript figure is deliberately omitted; it is never backfilled from unrelated data.

## Reproducibility and limitations

Record the source video filenames and hashes, Python/package versions, OS, CPU/GPU, FFmpeg/ffprobe versions, Whisper model setting, and benchmark command with any paper results. Keep the same machine, power mode, model, and warm/cold-cache conditions across compared runs. The first Whisper run may include model loading or other one-time effects; report repetitions rather than removing inconvenient runs. The CLI never modifies source video files or the configured application MySQL database.

The runner benchmarks local-file ingestion and the pipeline after ingestion; it does not measure browser/network upload latency or YouTube download time. SQLite is used only for isolated benchmark persistence, and experiments are sequential. Results describe the tested hardware, software, videos, and settings; do not generalize them without additional trials. Synthetic data in `tests/test_benchmark.py` validates calculations and CSV handling only and is never written to experimental result outputs.

