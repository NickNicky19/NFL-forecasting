"""Immutable permitted NFL history for operational reference methods.

Only schedule metadata, exact identity, weekly rosters and official NFL action
credits enter this namespace. Historical publication remains a seven-day
reconstruction assumption. This adapter never fits or scores a model.
"""
from __future__ import annotations

import hashlib
import io
import json
import tempfile
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from . import data, features, permitted_source_features as permitted
from .operational_storage import OperationalStorage
from .operational_io import operational_io

VERSION = "permitted-operational-nfl-history-v2"
POLICY_ID = "permitted-operational-nfl-history-v2-20261023"
SCHEDULE_COLUMNS = ["game_id", "season", "week", "game_type", "gameday", "gametime", "away_team", "home_team"]
SOURCE_SPECS = {
    "schedules": ("schedules.csv", "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"),
    "players": ("players.parquet", f"{data.BASE}/players/players.parquet"),
    "statistics": ("stats_player_week_{season}.parquet", f"{data.BASE}/stats_player/stats_player_week_{{season}}.parquet"),
    "rosters": ("roster_weekly_{season}.parquet", f"{data.BASE}/weekly_rosters/roster_weekly_{{season}}.parquet"),
    "license": ("nflverse_LICENSE.md", "https://raw.githubusercontent.com/nflverse/nflverse-data/main/LICENSE.md"),
}
CODE_FILES = ("operational_sources.py", "data.py", "features.py", "permitted_source_features.py", "rb_readiness.py", "operational_storage.py", "operational_io.py",
              "operational_models.py", "live.py", "experiment.py", "cli.py")


def _json(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def _digest(value: object) -> str:
    return hashlib.sha256(_json(value)).hexdigest()


def _stamp(value: object) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None or pd.isna(stamp):
        raise ValueError("asof must be an explicit timezone-aware clock")
    return stamp.tz_convert("UTC")


def _actual_now() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC")


def load_source_policy(policy: Path | str | dict) -> dict:
    """Validate the finite whitelist; preserve the exact configuration hash."""
    if isinstance(policy, (str, Path)):
        body = Path(policy).read_bytes()
        result = json.loads(body)
        file_sha = hashlib.sha256(body).hexdigest()
    else:
        result = dict(policy)
        file_sha = result.get("_policy_sha256")
    clean = {k: v for k, v in result.items() if not k.startswith("_")}
    if clean.get("policy_id") != POLICY_ID:
        raise ValueError("unsupported operational source policy")
    if set(clean.get("sources", {})) != set(SOURCE_SPECS):
        raise ValueError("source policy whitelist changed")
    for kind, (name, url) in SOURCE_SPECS.items():
        spec = clean["sources"][kind]
        if spec.get("name") != name or spec.get("url") != url:
            raise ValueError("source policy URL/name changed: " + kind)
    if clean["sources"]["schedules"].get("columns") != SCHEDULE_COLUMNS:
        raise ValueError("schedule metadata columns changed")
    if clean.get("history", {}).get("statistics_lag_days") != 7 or clean["history"].get("season_type") != "REG":
        raise ValueError("unsupported availability/season-type policy")
    predicates = clean["history"].get("parquet_predicates", {})
    if predicates.get("statistics_season_type") != "season_type == REG" or predicates.get("roster_season_type") != "game_type == REG":
        raise ValueError("explicit REG parquet predicates required")
    canonical = _digest(clean)
    if file_sha and not isinstance(policy, (str, Path)) and result.get("_canonical_policy_sha256") != canonical:
        raise ValueError("normalized operational policy body changed")
    return {**clean, "_policy_sha256": file_sha or canonical, "_canonical_policy_sha256": canonical}


def _code_hashes() -> dict:
    return {name: data._sha(Path(__file__).with_name(name)) for name in CODE_FILES}


def _request(seasons: list[int], policy: dict, asof: object, allowed_periods: dict | None) -> dict:
    stamp = _stamp(asof)
    if stamp > _actual_now():
        raise ValueError("asof cannot exceed actual current UTC")
    years = sorted(set(int(year) for year in seasons))
    # An NFL season in January belongs to the preceding calendar year.
    active = stamp.year - (stamp.month < 3)
    if not years or any(year < 2012 or year > active for year in years):
        raise ValueError("seasons must lie between 2012 and supplied active NFL season")
    periods = None
    if allowed_periods is not None:
        periods = {str(int(year)): sorted(set(int(w) for w in weeks)) for year, weeks in allowed_periods.items()}
        if set(periods) != set(map(str, years)) or any(w < 1 or w > 18 for weeks in periods.values() for w in weeks):
            raise ValueError("allowed_periods must explicitly bind every requested season to REG weeks")
    return {"adapter_version": VERSION, "policy_sha256": policy["_policy_sha256"],
            "canonical_policy_sha256": policy["_canonical_policy_sha256"], "asof_utc": stamp.isoformat(),
            "seasons": years, "allowed_periods": periods, "code_sha256s": _code_hashes()}


def _base(cache: Path, policy: dict) -> Path:
    return Path(cache) / "operational-source-v2" / policy["_policy_sha256"]


def _asof_name(request: dict) -> str:
    return _stamp(request["asof_utc"]).strftime("%Y%m%dT%H%M%S%fZ")


def _names(years: list[int]) -> dict:
    result = {}
    for kind, (name, url) in SOURCE_SPECS.items():
        for year in years if "{season}" in name else [None]:
            result[name.format(season=year)] = {"kind": kind, "url": url.format(season=year)}
    return result


def _no_links(path: Path) -> None:
    # Parents matter too: a symlinked raw/sources directory is not isolation.
    for parent in [path, *path.parents]:
        if parent.is_symlink():
            raise ValueError("symlink source/namespace is forbidden: " + str(parent))


def _read_receipt(path: Path, expected_url: str) -> dict:
    _no_links(path)
    receipt_path = path.with_name(path.name + ".receipt.json")
    _no_links(receipt_path)
    receipt = json.loads(receipt_path.read_text())
    if receipt.get("status") not in {"acquired", "stale_cache"} or receipt.get("sha256") != data._sha(path):
        raise ValueError("source body/receipt mismatch: " + path.name)
    if receipt.get("url") != expected_url:
        raise ValueError("non-whitelisted source URL: " + path.name)
    _stamp(receipt["retrieved_utc"])
    return receipt


def _columns(path: Path) -> set[str]:
    return set(pq.ParquetFile(path).schema_arrow.names)


def _filtered_parquet(path: Path, columns: list[str], *, year: int, weeks: list[int], kind: str) -> tuple[pd.DataFrame, list]:
    season_column = "season_type" if kind == "statistics" else "game_type"
    required = {"season", "week", season_column}
    if required - _columns(path):
        raise ValueError("missing parquet predicate schema: " + path.name)
    # Even an empty eligible set is pushed down, never decoded then filtered.
    filters = [[("season", "==", year), ("week", "in", weeks), (season_column, "==", "REG")]]
    frame = pd.read_parquet(path, columns=columns, filters=filters)
    if not (frame.season.eq(year) & frame.week.isin(weeks) & frame[season_column].eq("REG")).all():
        raise ValueError("parquet returned rows outside frozen source window")
    return frame, filters


def _subsets(stage: Path, request: dict) -> tuple[dict, pd.DataFrame]:
    sources, raw = stage / "sources", stage / "raw"
    raw.mkdir()
    schedule = pd.read_csv(sources / "schedules.csv", usecols=SCHEDULE_COLUMNS)
    data._require(schedule, set(SCHEDULE_COLUMNS), "schedule metadata")
    schedule = schedule[schedule.season.isin(request["seasons"]) & schedule.game_type.eq("REG")].copy()
    local = pd.to_datetime(schedule.gameday + " " + schedule.gametime, errors="coerce")
    kickoff = local.dt.tz_localize("America/New_York", ambiguous="NaT", nonexistent="NaT").dt.tz_convert("UTC")
    if kickoff.isna().any() or schedule.duplicated(["season", "week", "game_id"]).any():
        raise ValueError("ambiguous schedule metadata prevents cutoff qualification")
    weekly = pd.DataFrame({"season": schedule.season, "week": schedule.week, "kickoff": kickoff}).groupby(["season", "week"]).kickoff.max()
    eligible = weekly[weekly + pd.Timedelta(days=7) < _stamp(request["asof_utc"])]
    periods = request["allowed_periods"]
    weeks = {year: sorted(int(w) for y, w in eligible.index if y == year and (periods is None or int(w) in periods[str(year)])) for year in request["seasons"]}
    proof = {"allowed_periods": {str(y): w for y, w in weeks.items()}, "files": {},
             "week_rule": "all scheduled REG kickoffs+7days strictly before actual asof"}

    def save(frame: pd.DataFrame, name: str, transformation: dict) -> None:
        frame = frame.copy()
        frame.attrs.clear()
        destination = raw / name
        if name.endswith(".csv"):
            frame.to_csv(destination, index=False)
        else:
            frame.to_parquet(destination, index=False)
        proof["files"][name] = {"path": "raw/" + name, "sha256": data._sha(destination), "rows": len(frame), **transformation}

    save(schedule, "schedules.csv", {"columns_read": SCHEDULE_COLUMNS, "transform": "metadata only; requested seasons and REG; future schedule metadata retained"})
    players_path = sources / "players.parquet"
    data._require(pd.DataFrame(columns=list(_columns(players_path))), {"gsis_id", "display_name"}, "identity")
    players = pd.read_parquet(players_path, columns=["gsis_id", "display_name"])
    # The frozen shared loader expects this unused crosswalk column. No PFR
    # value is read, and no snap source can exist in the derived raw whitelist.
    players["pfr_id"] = None
    save(players, "players.parquet", {"columns_read": ["gsis_id", "display_name"], "transform": "identity only; synthetic missing unused pfr_id schema placeholder"})
    stats_frames = []
    for year in request["seasons"]:
        name = f"stats_player_week_{year}.parquet"
        available = _columns(sources / name)
        required = {"player_id", "season", "week", "position", "season_type"}
        if required - available or not {"team", "recent_team"} & available:
            raise ValueError("official weekly statistics schema incomplete")
        columns = sorted(available & (required | {"team", "recent_team", "player_display_name", "player_name", "passing_interceptions"}
                                      | set(data.STAT_MAP) | set(permitted.PHYSICAL_COUNT_FIELDS) | set(permitted.SIGNED_ACTION_FIELDS)))
        stats, filters = _filtered_parquet(sources / name, columns, year=year, weeks=weeks[year], kind="statistics")
        for field in set(data.STAT_MAP) | {"passing_interceptions"}:
            if field not in stats:
                continue
            numeric = pd.to_numeric(stats[field], errors="coerce")
            invalid = stats[field].notna() & (~np.isfinite(numeric))
            if field not in {"passing_yards", "rushing_yards", "receiving_yards"}:
                invalid |= numeric.notna() & (numeric.lt(0) | numeric.mod(1).ne(0))
            if invalid.any():
                raise ValueError("invalid supported official statistic: " + field)
        save(stats, name, {"columns_read": columns, "parquet_read_filters": filters, "transform": "official statistic and physical-action columns only"})
        stats_frames.append(stats.rename(columns={"recent_team": "team"}) if "team" not in stats else stats)
        name = f"roster_weekly_{year}.parquet"
        columns = ["season", "week", "game_type", "team", "gsis_id", "position", "status", "full_name", "sleeper_id"]
        if set(columns) - _columns(sources / name):
            raise ValueError("weekly roster/identity schema incomplete")
        roster, filters = _filtered_parquet(sources / name, columns, year=year, weeks=weeks[year], kind="rosters")
        save(roster, name, {"columns_read": columns, "parquet_read_filters": filters, "transform": "REG eligibility and exact identity; roster status is not participation evidence"})
    (stage / "subset-manifest.json").write_bytes(_json(proof))
    return proof, pd.concat(stats_frames, ignore_index=True)


def _frame_sha(frame: pd.DataFrame) -> str:
    copy = frame.copy()
    copy.attrs.clear()
    body = io.BytesIO()
    copy.to_parquet(body, index=False)
    return hashlib.sha256(body.getvalue()).hexdigest()


def _snapshot_digest(manifest: dict) -> str:
    return _digest({key: value for key, value in manifest.items() if key not in {"snapshot_sha256", "namespace", "manifest_sha256"}})


def _verify(namespace: Path, request: dict | None = None, *, storage: OperationalStorage) -> dict:
    _no_links(namespace)
    manifest_path = namespace / "source-manifest.json"
    storage.validate_reference(manifest_path)
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("adapter_version") != VERSION:
        raise ValueError("v2 operational source manifest required; v1 replay requires its Git pin")
    if manifest.get("snapshot_sha256") != _snapshot_digest(manifest):
        raise ValueError("operational snapshot manifest digest mismatch")
    if request is not None and manifest["request"] != request:
        raise ValueError("operational snapshot request/code binding mismatch")
    if manifest["code_sha256s"] != _code_hashes():
        raise ValueError("operational transform code changed; new namespace required")
    expected = _names(manifest["seasons"])
    raw_names = {"schedules.csv", "players.parquet"} | {f"{kind}_{y}.parquet" for y in manifest["seasons"] for kind in ("stats_player_week", "roster_weekly")}
    if {p.name for p in (namespace / "raw").iterdir()} != raw_names:
        raise ValueError("forbidden/unexpected derived raw artifact")
    if {p.name for p in (namespace / "sources").iterdir()} != set(expected) | {name + ".receipt.json" for name in expected}:
        raise ValueError("forbidden/unexpected original source artifact")
    for name, spec in expected.items():
        path = namespace / "sources" / name
        storage.validate_reference(path)
        storage.validate_reference(path.with_name(name + ".receipt.json"))
        receipt = _read_receipt(path, spec["url"])
        if receipt != manifest["source_receipts"][name] or data._sha(path.with_name(name + ".receipt.json")) != manifest["sources"][name]["receipt_sha256"]:
            raise ValueError("original receipt binding changed: " + name)
    for relative, sha in manifest["artifact_sha256s"].items():
        path = namespace / relative
        _no_links(path)
        storage.validate_reference(path, expected_sha256=sha)
        if data._sha(path) != sha:
            raise ValueError("operational derived artifact changed: " + relative)
    return {**manifest, "namespace": str(namespace.resolve()), "manifest_sha256": data._sha(manifest_path)}


def acquire_operational_history(cache: Path, seasons: list[int], policy: Path | str | dict, asof: object,
                                *, source_cache: Path | None = None, allowed_periods: dict | None = None,
                                state: Path | None = None, storage: OperationalStorage | None = None) -> dict:
    """Create one immutable request snapshot, or verify and reuse its exact bytes.

    ``source_cache`` adopts only verified named raw files without modifying that
    cache or making HTTP calls. Operational HTTP is confined to a new per-day
    namespace and uses the existing bounded downloader, never legacy acquisition.
    ``allowed_periods`` can narrow acceptance reads, including protected weeks.
    """
    normalized = load_source_policy(policy)
    storage = storage or OperationalStorage(cache, normalized, state=state)
    with operational_io(storage):
        return _acquire_operational_history(cache, seasons, normalized, asof,
            source_cache=source_cache, allowed_periods=allowed_periods, storage=storage)


def _acquire_operational_history(cache, seasons, policy, asof, *, source_cache, allowed_periods, storage):
    started = time.monotonic()
    normalized = load_source_policy(policy)
    request = _request(seasons, normalized, asof, allowed_periods)
    base = _base(cache, normalized)
    _no_links(base)
    request_id = _digest(request)
    binding = base / "requests" / (request_id + ".json")
    if binding.exists():
        storage.validate_reference(binding)
        return _verify(base / json.loads(binding.read_text())["namespace"], request, storage=storage)
    base.mkdir(parents=True, exist_ok=True)
    limit = int(normalized["namespaces"]["private_retention_bytes"])
    if limit <= 0 or limit > 512 * 1024 * 1024:
        raise ValueError("invalid private retention budget")
    stage = Path(tempfile.mkdtemp(prefix=".staging-", dir=base))
    with storage.capture_writes(roots=[stage]):
        try:
            sources = stage / "sources"
            sources.mkdir()
            receipts, source_proof = {}, {}
            specs = _names(request["seasons"])
            if source_cache is None:
                adoption_raw = base / "daily" / request["asof_utc"][:10] / "raw"
                _no_links(adoption_raw)
                for name, spec in specs.items():
                    data._download(adoption_raw, name, spec["url"], refresh_daily=False)
                    storage.import_file(adoption_raw / name, adoption_raw / name)
                    storage.import_file(adoption_raw / (name + ".receipt.json"), adoption_raw / (name + ".receipt.json"))
            else:
                adoption_raw = Path(source_cache) / "raw"
            total = 0
            for name, spec in specs.items():
                path = adoption_raw / name
                receipt = _read_receipt(path, spec["url"])
                if source_cache is not None and _stamp(receipt["retrieved_utc"]) > _stamp(request["asof_utc"]):
                    raise ValueError("source receipt retrieved after supplied actual asof")
                total += path.stat().st_size
                if path.stat().st_size > data.MAX_BYTES or total > 512 * 1024 * 1024:
                    raise ValueError("operational acquisition byte budget exceeded")
                storage.import_file(path, sources / name, expected_sha256=receipt["sha256"])
                storage.import_file(path.with_name(name + ".receipt.json"), sources / (name + ".receipt.json"))
                if data._sha(sources / name) != receipt["sha256"]:
                    raise ValueError("source changed during immutable copy")
                receipts[name] = receipt
                source_proof[name] = {"sha256": receipt["sha256"], "receipt_sha256": data._sha(sources / (name + ".receipt.json")), "bytes": (sources / name).stat().st_size}
            subsets, stats = _subsets(stage, request)
            # Shared normalization can only see this audited finite raw whitelist.
            raw_names = {p.name for p in (stage / "raw").iterdir()}
            expected_raw = {"schedules.csv", "players.parquet"} | {f"{kind}_{y}.parquet" for y in request["seasons"] for kind in ("stats_player_week", "roster_weekly")}
            if raw_names != expected_raw:
                raise ValueError("forbidden/unexpected raw artifact before shared normalizer")
            history, qualification = permitted.qualify_history(data.load_history(stage, request["seasons"]), stats)
            team_proof = stats[["season", "week", "team"]].copy()
            team_proof["team"] = data._team(team_proof.team)
            team_proof["_physical"] = permitted.physical_event_evidence(stats).to_numpy()
            positive_teams = team_proof.groupby(["season", "week", "team"])._physical.any()
            team_keys = pd.MultiIndex.from_frame(history[["season", "week", "team"]])
            team_supported = positive_teams.reindex(team_keys, fill_value=False).to_numpy()
            history.loc[~team_supported, ["team_stat_" + col for col in features.TEAM_STATS]] = np.nan
            qualification["team_context_rows_masked_without_physical_evidence"] = int((~team_supported).sum())
            qualification["roster_status_counts"] = {"missing" if pd.isna(key) else str(key): int(value)
                                                      for key, value in qualification["roster_status_counts"].items()}
            # Replace the private unqualified intermediate before publishing a view.
            history.attrs.clear()
            history_path = stage / "processed" / "history.parquet"
            history.to_parquet(history_path, index=False)
            (stage / "processed" / "history_profile.json").unlink()
            identity = data.load_identity(stage)
            identity.attrs.clear()
            identity_path = stage / "processed" / "identity.parquet"
            identity.to_parquet(identity_path, index=False)
            artifacts = {"subset-manifest.json": data._sha(stage / "subset-manifest.json"),
                         "processed/history.parquet": data._sha(history_path), "processed/identity.parquet": data._sha(identity_path)}
            artifacts.update({item["path"]: item["sha256"] for item in subsets["files"].values()})
            manifest = {"adapter_version": VERSION, "request": request, "policy_sha256": request["policy_sha256"],
                        "canonical_policy_sha256": request["canonical_policy_sha256"], "code_sha256s": request["code_sha256s"],
                        "asof_utc": request["asof_utc"], "seasons": request["seasons"], "allowed_periods": request["allowed_periods"],
                        "effective_periods": subsets["allowed_periods"], "source_receipts": receipts, "sources": source_proof,
                        "source_observed_max_utc": max(_stamp(r["retrieved_utc"]) for r in receipts.values()).isoformat(),
                        "artifact_sha256s": artifacts, "qualified_history_sha256": artifacts["processed/history.parquet"],
                        "training_view_sha256": artifacts["processed/history.parquet"], "history_frame_sha256": _frame_sha(history),
                        "qualification": qualification, "vintage": data.VINTAGE,
                        "availability": "strict kickoff+7days before asof and feature cutoff; assumed historical publication only",
                        "participation_probability": "unavailable: sufficient-positive panel has no complete nonappearance denominator",
                        "exact_ppr": "blocked_incomplete_component_contract", "elapsed_seconds": round(time.monotonic() - started, 6)}
            snapshot = _snapshot_digest(manifest)
            manifest["snapshot_sha256"] = snapshot
            (stage / "source-manifest.json").write_bytes(_json(manifest))
            destination = base / _asof_name(request) / snapshot
            destination.parent.mkdir(parents=True, exist_ok=True)
            stage.rename(destination)
            verified = _verify(destination, request, storage=storage)
            binding.parent.mkdir(exist_ok=True)
            binding.write_bytes(_json({"namespace": str(destination.relative_to(base)), "snapshot_sha256": snapshot}))
            return verified
        except Exception as exc:
            # Failed stages remain private evidence and cannot resolve as snapshots.
            if stage.exists():
                try:
                    storage.write_bytes(stage / "FAILURE.json", _json({"request": request, "exception": type(exc).__name__, "message": str(exc)[:500]}))
                except Exception as marker_error:
                    exc.add_note("Failure marker could not be persisted: " + str(marker_error))
            raise


def resolve_operational_snapshot(cache: Path, seasons: list[int], policy: Path | str | dict, asof: object,
                                 *, allowed_periods: dict | None = None) -> dict:
    """Verify the latest matching cached snapshot at/before asof; never acquire."""
    normalized = load_source_policy(policy)
    request = _request(seasons, normalized, asof, allowed_periods)
    base = _base(cache, normalized)
    storage = OperationalStorage(cache, normalized)
    candidates = []
    for binding in (base / "requests").glob("*.json"):
        storage.validate_reference(binding)
        namespace = base / json.loads(binding.read_text())["namespace"]
        manifest = json.loads((namespace / "source-manifest.json").read_text())
        other = manifest["request"]
        same_policy_code = all(other[key] == request[key] for key in request if key not in {"asof_utc", "seasons", "allowed_periods"})
        seasons_supported = set(request["seasons"]).issubset(other["seasons"])
        # Grading may request one season from a larger already-qualified panel.
        # Explicit narrower restrictions remain authoritative; unrestricted
        # latest lookup may accept a narrower cached view and report its gaps.
        restrictions_supported = request["allowed_periods"] is None or all(
            set(manifest["effective_periods"].get(str(year), [])).issubset(request["allowed_periods"][str(year)])
            for year in request["seasons"])
        if same_policy_code and seasons_supported and restrictions_supported and _stamp(other["asof_utc"]) <= _stamp(request["asof_utc"]):
            candidates.append((_stamp(other["asof_utc"]), namespace))
    if not candidates:
        raise FileNotFoundError("no matching permitted operational snapshot; legacy fallback forbidden")
    return _verify(max(candidates, key=lambda item: item[0])[1], storage=storage)


def _load_manifest(cache: Path, seasons: list[int], policy: Path | str | dict, asof: object,
                   allowed_periods: dict | None, latest: bool) -> dict:
    if latest:
        return resolve_operational_snapshot(cache, seasons, policy, asof, allowed_periods=allowed_periods)
    normalized = load_source_policy(policy)
    request = _request(seasons, normalized, asof, allowed_periods)
    base = _base(cache, normalized)
    storage = OperationalStorage(cache, normalized)
    binding = base / "requests" / (_digest(request) + ".json")
    if not binding.exists():
        raise FileNotFoundError("exact permitted operational snapshot missing; acquisition must be explicit")
    storage.validate_reference(binding)
    return _verify(base / json.loads(binding.read_text())["namespace"], request, storage=storage)


def load_operational_history(cache: Path, seasons: list[int], policy: Path | str | dict, asof: object,
                             *, allowed_periods: dict | None = None, latest: bool = False) -> pd.DataFrame:
    manifest = _load_manifest(cache, seasons, policy, asof, allowed_periods, latest)
    history = pd.read_parquet(Path(manifest["namespace"]) / "processed" / "history.parquet")
    history.attrs["operational_manifest"] = manifest
    return history


def load_operational_identity(cache: Path, seasons: list[int], policy: Path | str | dict, asof: object,
                              *, allowed_periods: dict | None = None, latest: bool = False) -> pd.DataFrame:
    manifest = _load_manifest(cache, seasons, policy, asof, allowed_periods, latest)
    identity = pd.read_parquet(Path(manifest["namespace"]) / "processed" / "identity.parquet")
    identity.attrs["operational_manifest"] = manifest
    return identity


def build_operational_features(history: pd.DataFrame, *, policy: Path | str | dict,
                               queries: pd.DataFrame | None = None) -> pd.DataFrame:
    """Use the shared temporal feature builder on the exact qualified view."""
    normalized = load_source_policy(policy)
    manifest = history.attrs.get("operational_manifest", {})
    if manifest.get("policy_sha256") != normalized["_policy_sha256"] or manifest.get("code_sha256s") != _code_hashes():
        raise ValueError("qualified operational history policy/code binding required")
    if _frame_sha(history) != manifest.get("history_frame_sha256"):
        raise ValueError("qualified operational training view changed")
    rows = history.copy()
    rows.attrs.clear()
    if queries is not None:
        query = queries.copy()
        query.attrs.clear()
        required = {"player_id", "game_id", "team", "opponent", "kickoff_utc", "cutoff_utc"}
        data._require(query, required, "operational feature queries")
        query["kickoff_utc"] = pd.to_datetime(query.kickoff_utc, utc=True)
        query["cutoff_utc"] = pd.to_datetime(query.cutoff_utc, utc=True)
        if query.cutoff_utc.isna().any() or (query.cutoff_utc > query.kickoff_utc).any():
            raise ValueError("query cutoff must be at or before kickoff")
        if (_stamp(manifest["asof_utc"]) > query.cutoff_utc).any():
            raise ValueError("source snapshot asof exceeds query cutoff")
        observed = max(_stamp(receipt["retrieved_utc"]) for receipt in manifest["source_receipts"].values())
        if (observed > query.cutoff_utc).any():
            raise ValueError("source receipt observed after query cutoff")
        for field in [*features.PLAYER_STATS, *("team_stat_" + col for col in features.TEAM_STATS)]:
            query[field] = np.nan
        query["participation_state"] = "unknown"
        query["outcome_available_utc"] = query.kickoff_utc + pd.Timedelta(days=7)
        combined = features.build_features(pd.concat([rows, query], ignore_index=True))
        result = combined.iloc[len(rows):].copy()
        result.index = queries.index
        result["feature_max_assumed_history_available_utc"] = result.feature_max_source_available_utc
        result["feature_max_source_available_utc"] = result.feature_max_source_available_utc.fillna(observed).clip(lower=observed)
    else:
        result = features.build_features(rows)
    # A sufficient-positive panel cannot estimate nonappearance probability.
    result["f_player_play_rate8"] = np.nan
    result["participation_probability_state"] = "unavailable_incomplete_nonappearance_denominator"
    result.attrs["operational_manifest"] = {**manifest, "feature_view_sha256": _frame_sha(result)}
    return result
