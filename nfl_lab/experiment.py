"""Bounded campaign orchestration and one immutable terminal aggregate receipt."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import signal
import tempfile
import threading
import uuid

from .state import records, save


class ExperimentTerminated(SystemExit):
    def __init__(self, signum):
        self.signum = signum
        super().__init__(128 + signum)


def atomic_checkpoint(path, value):
    """Replace a small/local checkpoint; immutable state is saved only at exit."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".checkpoint-", delete=False, mode="w") as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, default=str, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


@contextmanager
def termination_guard():
    """Convert the hosted timeout's SIGTERM into an unwindable termination."""
    installed = threading.current_thread() is threading.main_thread()
    previous = signal.getsignal(signal.SIGTERM) if installed else None
    def terminate(signum, frame):
        raise ExperimentTerminated(signum)
    if installed:
        signal.signal(signal.SIGTERM, terminate)
    try:
        yield
    finally:
        if installed:
            signal.signal(signal.SIGTERM, previous)


def _receipt(config, attempt, result, error, execution_id):
    document = {"schema_version": "lab-training-run-v1", "registration": config,
                "execution_id": execution_id,
                "state": "INTERRUPTED" if isinstance(error, ExperimentTerminated) else "FAILED" if error else "COMPLETED",
                "result": result, "trials": [],
                "row_level_outputs": "local ignored only; never included in immutable aggregate receipt",
                "receipt_policy": "one terminal aggregate per execution; per-trial checkpoints are local"}
    if error is not None:
        document["error"] = {"type": type(error).__name__, "message": str(error)}
        if isinstance(error, ExperimentTerminated):
            document["error"]["signal"] = error.signum
    if attempt is not None:
        document["attempt_output"] = str(attempt)
        for name in ("manifest", "trials", "campaign", "progress", "selected", "paired", "coherence", "summary"):
            path = attempt / (name + ".json")
            if path.exists():
                try:
                    document[name] = json.loads(path.read_text())
                except (OSError, ValueError) as read_error:
                    document.setdefault("checkpoint_read_errors", []).append({"name": name, "error": type(read_error).__name__})
        if not document["trials"]:
            for path in sorted((attempt / "trial-checkpoints").glob("*.json")):
                try:
                    document["trials"].append(json.loads(path.read_text()))
                except (OSError, ValueError) as read_error:
                    document.setdefault("checkpoint_read_errors", []).append({"name": path.name, "error": type(read_error).__name__})
    return document


def run_experiment(root, cache, state, config, methods=None):
    """Run once, preserve a terminal receipt on failure/termination, then reraise."""
    import pandas as pd
    from .evaluation import campaign
    root, cache, state = map(Path, (root, cache, state))
    attempt = None
    result = None
    execution_id = uuid.uuid4().hex
    terminal_saved = False
    def started(path):
        nonlocal attempt
        attempt = path
    with termination_guard():
        try:
            path = cache / "processed/features.parquet"
            if not path.exists():
                raise RuntimeError("run acquire first")
            features = pd.read_parquet(path)
            with path.open("rb") as source:
                features.attrs["feature_file_sha256"] = hashlib.file_digest(source, "sha256").hexdigest()
            manifest_path = cache / "processed/feature_manifests" / (features.attrs["feature_file_sha256"] + ".json")
            features.attrs["source_snapshot_binding"] = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"state": "legacy feature checksum captured; prematched acquisition snapshot absent; no fabricated source binding"}
            result = campaign(features, root / "runs" / config["registration_id"], config, methods, attempt_callback=started)
            save(state, "training", _receipt(config, attempt, result, None, execution_id))
            terminal_saved = True
            return result
        except BaseException as error:
            if not terminal_saved:
                try:
                    # A signal may arrive after the immutable save committed
                    # but before its success flag was assigned. First receipt
                    # for this execution remains authoritative.
                    committed=any(r.get("execution_id")==execution_id for r in records(state,"training"))
                    if not committed:
                        save(state, "training", _receipt(config, attempt, result, error, execution_id))
                except BaseException as preservation_error:
                    error.add_note(f"Terminal receipt preservation also failed: {preservation_error}")
            raise
