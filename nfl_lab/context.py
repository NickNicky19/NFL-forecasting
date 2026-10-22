"""Optional NGS and public observation inputs, separate from the frozen baseline.

No model fits or automatic narrative-to-number changes occur here. Historical
NGS uses a declared seven-day reconstruction assumption; current source files
cannot authenticate their original pregame publication or revision state.
"""
from __future__ import annotations

import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import numpy as np
import pandas as pd

from nfl_lab.data import BASE, VINTAGE, _download, _schedule, _sha, _team, _utc_now, fetch_cached_json

GSIS = re.compile(r"^00-\d{7}$")
NGS_METRICS = {
    "passing": ["avg_time_to_throw", "avg_intended_air_yards", "aggressiveness",
                "expected_completion_percentage", "completion_percentage_above_expectation"],
    "receiving": ["avg_cushion", "avg_separation", "avg_intended_air_yards", "avg_yac_above_expectation"],
    "rushing": ["efficiency", "percent_attempts_gte_eight_defenders", "avg_time_to_los",
                "rush_yards_over_expected_per_att", "rush_pct_over_expected"],
}
CLAIM_TYPES = {"reported_fact", "coach_statement", "reporter_interpretation", "model_hypothesis"}
OBSERVATION_GROUPS = {"news", "injury", "environment", "scheme", "source_feature"}


def load_ngs(cache: Path, seasons: list[int]) -> pd.DataFrame:
    """Load supported weekly public NGS assets from the cached release inventory.

    Only exact source GSIS IDs and schedule bindings are accepted. Week-zero
    season aggregates, unknown identities and unmatched games are excluded with
    counts. No guessed postseason calendar or player-name crosswalk is applied.
    """
    cache = Path(cache)
    raw = cache / "raw"
    inventory = json.loads((raw / "ngs_release.json").read_text())
    assets = {a["name"]: a for a in inventory.get("assets", [])}
    seasons = sorted(set(int(s) for s in seasons))
    if not seasons:
        raise ValueError("at least one NGS season is required")
    schedule = _schedule(raw, seasons)
    registry = set(pd.read_parquet(raw / "players.parquet", columns=["gsis_id"]).gsis_id.dropna())
    jobs, unavailable = [], []
    for season in seasons:
        for kind in NGS_METRICS:
            name = f"ngs_{season}_{kind}.csv.gz"
            asset = assets.get(name)
            if asset is None:
                unavailable.append(name)
                continue
            expected = f"{BASE}/nextgen_stats/{name}"
            if asset.get("browser_download_url") != expected:
                raise ValueError(f"NGS inventory URL is not the exact supported asset: {name}")
            if int(asset.get("size", 0)) > 5 * 1024 * 1024:
                raise ValueError(f"NGS asset exceeds optional 5 MiB budget: {name}")
            jobs.append((season, kind, name, asset))
    with ThreadPoolExecutor(max_workers=2) as pool:
        receipts = list(pool.map(lambda job: _download(raw, job[2], job[3]["browser_download_url"], optional=True), jobs))
    tables, coverage = [], []
    for job, receipt in zip(jobs, receipts):
        season, kind, name, asset = job
        if receipt.get("status") not in ("acquired", "stale_cache"):
            unavailable.append(name)
            continue
        frame = pd.read_csv(raw / name, dtype={"player_gsis_id": str})
        required = {"season", "season_type", "week", "player_gsis_id", "team_abbr", *NGS_METRICS[kind]}
        if required - set(frame):
            raise ValueError(f"NGS {kind} schema missing {sorted(required - set(frame))}")
        if not frame.season.eq(season).all():
            raise ValueError(f"NGS asset contains a different season: {name}")
        summary = {"asset": name, "source_rows": len(frame), "season_aggregates_excluded": int(frame.week.eq(0).sum())}
        frame = frame[frame.week.gt(0)].copy()
        valid_id = frame.player_gsis_id.map(lambda s: isinstance(s, str) and bool(GSIS.fullmatch(s)))
        known_id = frame.player_gsis_id.isin(registry)
        summary["invalid_or_unknown_gsis_excluded"] = int((~(valid_id & known_id)).sum())
        frame = frame[valid_id & known_id].copy()
        frame = frame.rename(columns={"player_gsis_id": "player_id", "team_abbr": "team"})
        frame["team"] = _team(frame.team)
        identity = ["season", "week", "team", "player_id"]
        if frame.duplicated(identity).any():
            raise ValueError(f"duplicate NGS player/week identity in {name}")
        matched = frame.merge(schedule, on=["season", "week", "team"], how="left", validate="many_to_one", indicator=True)
        summary["unmatched_schedule_excluded"] = int(matched._merge.ne("both").sum())
        matched = matched[matched._merge.eq("both")].copy()
        metrics = {metric: f"{kind}_{metric}" for metric in NGS_METRICS[kind]}
        matched = matched.rename(columns=metrics)
        keys = ["player_id", "game_id", "season", "week", "team", "opponent", "kickoff_utc"]
        table = matched[keys + list(metrics.values())].copy()
        table[f"{kind}_source_retrieved_utc"] = receipt["retrieved_utc"]
        # GitHub asset update is a source vintage clock, not weekly publication.
        table[f"{kind}_asset_updated_utc"] = asset.get("updated_at")
        tables.append(table)
        summary["accepted_rows"] = len(table)
        coverage.append(summary)
    keys = ["player_id", "game_id", "season", "week", "team", "opponent", "kickoff_utc"]
    if tables:
        # Concatenate seasons within kind before joining distinct metric groups.
        groups = []
        for kind in NGS_METRICS:
            matching = [t for t in tables if f"{kind}_source_retrieved_utc" in t]
            if matching:
                groups.append(pd.concat(matching, ignore_index=True))
        result = groups[0]
        for group in groups[1:]:
            result = result.merge(group, on=keys, how="outer", validate="one_to_one")
        result = result.sort_values(["kickoff_utc", "player_id"]).reset_index(drop=True)
    else:
        result = pd.DataFrame(columns=keys)
        result["kickoff_utc"] = pd.to_datetime(result.kickoff_utc, utc=True)
    for kind, metrics in NGS_METRICS.items():
        for metric in metrics:
            col = f"{kind}_{metric}"
            if col not in result:
                result[col] = np.nan
            result[col] = pd.to_numeric(result[col], errors="coerce")
    result["available_utc"] = result.kickoff_utc + pd.Timedelta(days=7)
    result["published_utc"] = pd.NaT
    result["updated_utc"] = pd.NaT
    result["availability_basis"] = "reconstructed_7day_lag"
    result["history_vintage"] = VINTAGE
    manifest = {"adapter": "optional-context-ngs-v1", "seasons": seasons,
                "rows": len(result), "inventory_sha256": _sha(raw / "ngs_release.json"),
                "sources": receipts, "coverage": coverage, "unavailable_assets": unavailable,
                "time_semantics": "kickoff+7d assumed reconstruction; authentic original publication/revision unknown",
                "rights": "NFL/NGS upstream rights remain separate; no raw or row-level redistribution",
                "unavailable_groups": ["routes", "premium tracking", "authentic historical weather forecasts", "authenticated historical injury/news snapshots"]}
    processed = cache / "processed"
    processed.mkdir(parents=True, exist_ok=True)
    (processed / "context_ngs_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    result.attrs["manifest"] = manifest
    return result


def merge_ngs_asof(history: pd.DataFrame, ngs: pd.DataFrame) -> pd.DataFrame:
    """Add optional prior NGS means/counts; never alter existing base features.

    Three earlier roster-game slots are used, including missing NGS slots.
    Inputs over 60 days old are stale. Every populated metric must be available
    strictly before cutoff, including a later supplied publication/update clock.
    """
    keys = {"game_id", "player_id", "team", "kickoff_utc"}
    if keys - set(history) or keys - set(ngs):
        raise ValueError("NGS/history identity or kickoff schema missing")
    if history.duplicated(["game_id", "player_id"]).any() or ngs.duplicated(["game_id", "player_id"]).any():
        raise ValueError("duplicate player/game identity")
    if ngs.player_id.map(lambda x: not isinstance(x, str) or not GSIS.fullmatch(x)).any():
        raise ValueError("NGS player_id must be an exact GSIS identifier")
    out = history.copy().reset_index(drop=True)
    out["kickoff_utc"] = pd.to_datetime(out.kickoff_utc, utc=True)
    cutoff = pd.to_datetime(out.get("cutoff_utc", out.kickoff_utc), utc=True).fillna(out.kickoff_utc)
    if cutoff.isna().any() or (cutoff > out.kickoff_utc).any():
        raise ValueError("cutoff must be at or before kickoff")
    source = ngs.copy()
    source["kickoff_utc"] = pd.to_datetime(source.kickoff_utc, utc=True)
    if "availability_basis" not in source or not source.availability_basis.eq("reconstructed_7day_lag").all():
        raise ValueError("this adapter requires explicitly labeled reconstructed NGS history")
    source["available_utc"] = pd.to_datetime(source.available_utc, utc=True)
    floor = source.kickoff_utc + pd.Timedelta(days=7)
    source["available_utc"] = pd.concat([source.available_utc, floor], axis=1).max(axis=1)
    for clock in ("published_utc", "updated_utc"):
        if clock in source:
            source["available_utc"] = pd.concat([source.available_utc, pd.to_datetime(source[clock], utc=True)], axis=1).max(axis=1)
    metric_columns = [f"{kind}_{m}" for kind, ms in NGS_METRICS.items() for m in ms]
    for col in metric_columns:
        if col not in source:
            source[col] = np.nan
    identity = out[["game_id", "player_id", "team", "kickoff_utc"]].merge(
        source[["game_id", "player_id", "team", "kickoff_utc"]], on=["game_id", "player_id"], how="inner", suffixes=("_history", "_ngs"))
    if (identity.team_history != identity.team_ngs).any() or (identity.kickoff_utc_history != identity.kickoff_utc_ngs).any():
        raise ValueError("NGS/history team or kickoff binding conflict")
    grid = out[["game_id", "player_id", "kickoff_utc"]].merge(
        source[["game_id", "player_id", "available_utc"] + metric_columns], on=["game_id", "player_id"], how="left", validate="one_to_one")
    base_available = pd.to_datetime(out.get("outcome_available_utc", out.kickoff_utc + pd.Timedelta(days=7)), utc=True).fillna(out.kickoff_utc + pd.Timedelta(days=7))
    if (base_available <= out.kickoff_utc).any():
        raise ValueError("historical game availability must be after kickoff")
    grid["base_available"] = base_available
    output = {f"f_ngs_{col}_{suffix}": np.full(len(out), np.nan if suffix == "mean3" else 0.0)
              for col in metric_columns for suffix in ("mean3", "n3")}
    max_source = np.full(len(out), np.iinfo(np.int64).min, dtype=np.int64)
    for _, positions in out.groupby("player_id", sort=False).indices.items():
        positions = np.asarray(positions)
        group = grid.iloc[positions].sort_values(["base_available", "kickoff_utc"])
        available = pd.to_datetime(group.base_available, utc=True).astype("int64").to_numpy()
        row_cutoffs = cutoff.iloc[positions].astype("int64").to_numpy()
        right = np.searchsorted(available, row_cutoffs, side="left")
        slots = right[:, None] - np.arange(1, 4)[None, :]
        valid_slots = slots >= 0
        safe_slots = np.maximum(slots, 0)
        metric_available = pd.to_datetime(group.available_utc, utc=True).astype("int64").to_numpy()[safe_slots]
        dates = group.kickoff_utc.astype("int64").to_numpy()[safe_slots]
        eligible = valid_slots & (metric_available != np.iinfo(np.int64).min) & (metric_available < row_cutoffs[:, None])
        eligible &= (row_cutoffs[:, None] - dates) <= pd.Timedelta(days=60).value
        values = group[metric_columns].to_numpy(float)[safe_slots]
        valid = np.isfinite(values) & eligible[:, :, None]
        totals = np.where(valid, values, 0).sum(axis=1)
        counts = valid.sum(axis=1)
        means = np.divide(totals, counts, out=np.full_like(totals, np.nan), where=counts > 0)
        for j, col in enumerate(metric_columns):
            output[f"f_ngs_{col}_mean3"][positions] = means[:, j]
            output[f"f_ngs_{col}_n3"][positions] = counts[:, j]
        used_slots = valid.any(axis=2)
        max_source[positions] = np.where(used_slots, metric_available, np.iinfo(np.int64).min).max(axis=1)
    result = pd.concat([out, pd.DataFrame(output)], axis=1)
    result["ngs_feature_max_available_utc"] = pd.to_datetime(max_source, utc=True)
    result["ngs_history_vintage"] = VINTAGE
    result.index = history.index
    result.attrs["context_profile"] = {"adapter": "optional-context-ngs-v1", "rows": len(result),
                                       "numeric_features": len(output), "window": "3 earlier eligible roster games; missing NGS consumes slots",
                                       "max_age_days": 60, "base_features_changed": False,
                                       "time_semantics": "strictly prior, assumed 7day lag, reconstructed history only"}
    return result


def _clock(value) -> pd.Timestamp:
    if value is None or pd.isna(value):
        return pd.NaT
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None:
        raise ValueError("observation clocks must include an explicit timezone")
    return stamp.tz_convert("UTC")


def _canonical_url(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("public observation source_url must be a URL string")
    parsed = urlsplit(value)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("public observation source_url must be HTTP(S) without credentials")
    query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if not k.lower().startswith("utm_")]
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, urlencode(sorted(query)), ""))


def normalize_observations(records: list[dict]) -> pd.DataFrame:
    """Retain supplied source claims/clocks, classify identity and deduplicate.

    A claim is never fabricated, reworded, interpreted as a private gameplan or
    applied to a numerical forecast here. Unknown publication/retrieval times
    remain missing and are ineligible for cutoff-authenticated observations.
    """
    rows = []
    for supplied in records:
        row = dict(supplied)
        if row.get("claim_type") == "fact":
            row["claim_type"] = "reported_fact"
        if row.get("claim_type") not in CLAIM_TYPES or row.get("group") not in OBSERVATION_GROUPS:
            raise ValueError("unsupported observation claim_type/group")
        if not isinstance(row.get("claim_text"), str) or not row["claim_text"].strip():
            raise ValueError("observation requires exact accessible source claim_text")
        row["canonical_source_url"] = _canonical_url(row.get("source_url", ""))
        if row.get("player_id") is not None and not GSIS.fullmatch(str(row["player_id"])):
            raise ValueError("observation player_id must use exact GSIS, not a player name")
        for key in ("published_utc", "updated_utc", "retrieved_utc"):
            row[key] = _clock(row.get(key))
        reasons = []
        if pd.isna(row["published_utc"]):
            reasons.append("publication_unknown")
        if pd.isna(row["retrieved_utc"]):
            reasons.append("retrieval_unknown")
        known_source_clocks = [row[k] for k in ("published_utc", "updated_utc") if pd.notna(row[k])]
        if pd.notna(row["retrieved_utc"]) and any(c > row["retrieved_utc"] for c in known_source_clocks):
            reasons.append("source_clock_after_retrieval")
        if pd.notna(row["updated_utc"]) and pd.notna(row["published_utc"]) and row["updated_utc"] < row["published_utc"]:
            reasons.append("update_before_publication")
        row["clock_status"] = "eligible_clocks" if not reasons else "|".join(reasons)
        clocks = known_source_clocks + ([row["retrieved_utc"]] if pd.notna(row["retrieved_utc"]) else [])
        row["available_utc"] = max(clocks) if not reasons and clocks else pd.NaT
        row["content_clock_utc"] = max(known_source_clocks) if known_source_clocks else pd.NaT
        identity = [row["canonical_source_url"], row["claim_type"], row["group"], row.get("player_id"), row.get("team"), " ".join(row["claim_text"].split())]
        row["observation_id"] = hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()
        rows.append(row)
    if not rows:
        return pd.DataFrame(columns=["observation_id", "claim_type", "group", "claim_text", "source_url", "player_id", "team",
                                     "published_utc", "updated_utc", "retrieved_utc", "available_utc", "content_clock_utc", "clock_status"])
    frame = pd.DataFrame(rows)
    for col in ("published_utc", "updated_utc", "retrieved_utc", "available_utc", "content_clock_utc"):
        frame[col] = pd.to_datetime(frame[col], utc=True)
    # Earliest authenticated identical snapshot survives repeated stories;
    # changed claim text remains a separate version. Raw source stays cached.
    frame = frame.sort_values(["available_utc", "retrieved_utc", "observation_id"], na_position="last")
    duplicates = frame.groupby("observation_id").size()
    frame = frame.drop_duplicates("observation_id").copy()
    frame["duplicate_count"] = frame.observation_id.map(duplicates)
    return frame.reset_index(drop=True)


def observations_asof(observations: pd.DataFrame, cutoff_utc, *, player_id: str | None = None,
                      team: str | None = None, max_age_hours: float = 168) -> pd.DataFrame:
    """Return timely source claims only; never emit numerical model inputs."""
    cutoff = _clock(cutoff_utc)
    if pd.isna(cutoff) or max_age_hours <= 0:
        raise ValueError("valid cutoff and positive observation age required")
    required = {"clock_status", "available_utc", "published_utc", "retrieved_utc"}
    if required - set(observations):
        raise ValueError("normalize source observations before as-of filtering")
    published = pd.to_datetime(observations.published_utc, utc=True)
    retrieved = pd.to_datetime(observations.retrieved_utc, utc=True)
    updated = pd.to_datetime(observations.get("updated_utc", pd.Series(pd.NaT, index=observations.index)), utc=True)
    content_clock = pd.concat([published, updated], axis=1).max(axis=1)
    available = pd.concat([pd.to_datetime(observations.available_utc, utc=True), content_clock, retrieved], axis=1).max(axis=1)
    keep = observations.clock_status.eq("eligible_clocks") & published.notna() & retrieved.notna() & available.lt(cutoff)
    keep &= content_clock.le(retrieved) & (updated.isna() | updated.ge(published))
    keep &= (cutoff - content_clock).between(pd.Timedelta(0), pd.Timedelta(hours=max_age_hours))
    if player_id is not None:
        keep &= observations.get("player_id", pd.Series(None, index=observations.index, dtype=object)).eq(player_id)
    if team is not None:
        keep &= observations.get("team", pd.Series(None, index=observations.index, dtype=object)).eq(team)
    return observations[keep].copy()


def load_public_news(cache: Path) -> pd.DataFrame:
    """Optional current ESPN public snapshot; not a historical news backfill.

    Source descriptions/headlines remain reporter interpretations unless a
    reviewed structured observation classifies a more specific claim. Only
    exact ESPN/GSIS registry bindings identify players. No name matching occurs.
    """
    cache = Path(cache)
    day = _utc_now()[:10]
    payload, receipt = fetch_cached_json(cache, f"espn_nfl_news_{day}.json",
                                         "https://site.api.espn.com/apis/site/v2/sports/football/nfl/news?limit=50")
    registry = pd.read_parquet(cache / "raw" / "players.parquet", columns=["gsis_id", "espn_id"])
    registry = registry.dropna(subset=["gsis_id", "espn_id"])
    registry["espn_id"] = registry.espn_id.astype(str)
    ambiguous = registry.groupby("espn_id").gsis_id.nunique().loc[lambda x: x > 1].index
    mapping = registry[~registry.espn_id.isin(ambiguous)].drop_duplicates("espn_id").set_index("espn_id").gsis_id.to_dict()
    records = []
    for article in payload.get("articles", []):
        url = article.get("links", {}).get("web", {}).get("href")
        text = article.get("description") or article.get("headline")
        if not url or not text:
            continue
        athlete_ids = [str(c.get("athlete", {}).get("id")) for c in article.get("categories", []) if c.get("type") == "athlete"]
        bound_players = sorted({mapping[i] for i in athlete_ids if i in mapping}) or [None]
        for player in bound_players:
            records.append({"group": "news", "claim_type": "reporter_interpretation", "claim_text": text,
                            "source_url": url, "published_utc": article.get("published"),
                            "updated_utc": article.get("lastModified"), "retrieved_utc": receipt["retrieved_utc"],
                            "player_id": player, "source_article_id": article.get("id"),
                            "source_access": "public_feed_excerpt", "source_article_premium": bool(article.get("premium", False)),
                            "identity_status": "exact_espn_gsis_binding" if player else "no_exact_player_binding"})
    result = normalize_observations(records)
    result.attrs["source_receipt"] = receipt
    result.attrs["limitations"] = "current snapshot only; no inferred injury status, coach intent, private scheme or numerical narrative override"
    return result
