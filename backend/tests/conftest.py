"""All regression tests use a disposable SQLite database, never the user's trips."""
import os
import tempfile
from pathlib import Path

_test_database = tempfile.TemporaryDirectory(prefix="yuntu-tests-", ignore_cleanup_errors=True)
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///" + (Path(_test_database.name) / "trips.db").as_posix()
os.environ["RUN_METRICS_PATH"] = str(Path(_test_database.name) / "runs.jsonl")
