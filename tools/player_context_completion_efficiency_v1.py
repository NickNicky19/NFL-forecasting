"""A-owned, fixed-opportunity rush-efficiency wave; no production or HTTP I/O.

Preparation decodes retained source identities and histories only. Execution
requires root's exact published plan, explicit GO and separately bounded guard.
Scoring is a separate saved-vector operation; a scoring failure cannot refit.
"""
from __future__ import annotations

import argparse
import copy
import datetime
import gzip
import hashlib
import io
import json
import lzma
import os
from pathlib import Path
import resource
import signal
import sys
import time
import traceback
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/abc-championship/player-context-completion-decision-01"
sys.path.insert(0, str(ROOT))
VERSION = "PLAYER-CONTEXT-COMPLETION-DECISION-01-A-efficiency-v1"
KEY = ["season", "week", "game_id", "player_id"]
CTX = ["team", "opponent", "position", "kickoff_utc", "cutoff_utc"]
STATE = {"phase": "NOT_STARTED", "fits_attempted": 0, "fits_returned": 0, "artifacts": [], "forecasts": []}
LAW_REF = {"id": "A_RETAINED_FIXED_N_A1_LAWS", "relative_path": "research/ABC-PREDICTIVE-IMPROVEMENT-01-A-runtime-v2/FAILED_PARTIALS_V2.zip", "bytes": 4829248, "sha256": "91121673a47289098f764978fec2cba74b2d156299a1223ea21ce307da5bc208"}
HGB_REF = {"id": "A_RETAINED_ACCEPTED_REG_RUSH_YARD_HGB", "relative_path": "research/matched12-hgb-accepted-reg-v1-1-20261031/rush_yd/MODEL.joblib", "bytes": 486553, "sha256": "8a254a96c76c74349b545a52fe655cfc2ffb28b8f4a7919beacb9034e21b8895"}
W8_REF = {"id": "A_RETAINED_WEEK8_PREGAME_BOARD_SOURCE", "relative_path": "research/week8-original-grade-v2-batch-20261102/SOURCES.zip", "bytes": 1386723, "sha256": "6290b6a501ac5adf33ce693c2c4dc92d5f371ffdc3e6c6ba1da83ca6d1b623c5"}
W8_MEMBER = {"name": "archive_pre_first.bin", "bytes": 365417, "sha256": "e097de9302eb147807c9a35c8c4550600c5686ad7cdc5123664e1db0d11a4ebb"}
AUDIT_FEATURE_SHA = "c3dcc6f3dd3cf019b358ffc86434e2659351c0aeb60c00256ab23be2039a4ade"
AUDIT_EXACT = {"path": str(ROOT / "reports/abc-championship/audit-remediation-20261105/EXACT_PREPARATION_RECEIPT_V1.json"), "bytes": 4389, "sha256": "efca3a30db4a723d1d489a4954c48ad5f9698cd8150d078ac56f05ff3e17ba03"}
AUDIT_TRAINING = {"path": str(ROOT / "reports/abc-championship/audit-remediation-20261105/HISTORY_IMPACT_RECEIPT_V6.json"), "bytes": 28681, "sha256": "8dfc96149eac5900b3e7cdfb3df30b857483c293a2c6f7c48468cadf0612b0ed"}
SOURCE_CONFIGS = ("category-topfive-matched12-new-hgb-v1_1.json", "role-count-full-pbp2024-recovery-gate-network-v2.json",
                  "category-topfive-matched12-current-label-execute-v1.json.gz", "category-topfive-backfield-v1.sealed.json",
                  "category-topfive-matched12-inference-followup-v1.json.gz", "category-topfive-matched12-all-finalists-grade-v1.json.gz")


def enc(x):
    return (json.dumps(x, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def sha(body):
    return hashlib.sha256(body).hexdigest()


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def safe(ref):
    return {k: v for k, v in ref.items() if k not in ("path", "native_root", "relative_path")}


def pin(ref):
    if "path" in ref:
        path = Path(ref["path"])
    else:
        from tools import category_topfive_matched12_storage_v1 as retained
        owner = STATE.get("source_owner")
        if owner is None:
            owner, _ = retained.open_store(ROOT, allocation_sha256="f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26", root_go=retained.GO, readonly=True)
            STATE["source_owner"] = owner
        relative = Path(ref["relative_path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("owned logical artifact path required")
        path = owner.forward_root / relative
        owner.validate_reference(path, ref["sha256"])
    body = path.read_bytes()
    if len(body) != ref["bytes"] or sha(body) != ref["sha256"]:
        raise ValueError("retained input checksum mismatch: " + path.name)
    return body


def doc(name):
    path = ROOT / "config" / name
    body = path.read_bytes()
    return json.loads(gzip.decompress(body) if path.suffix == ".gz" else body)


def runtime(cpu=200, wall=600):
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        os.environ[name] = "1"
    # Keep failure/model retention inside the registered hard CPU envelope.
    retention_cpu = min(100, max(10, cpu // 10))
    resource.setrlimit(resource.RLIMIT_CPU, (max(1, cpu - retention_cpu), cpu))
    resource.setrlimit(resource.RLIMIT_AS, (3 * 1024**3,) * 2)
    def exhausted(signum, _frame):
        if signum == signal.SIGXCPU:
            # Linux repeats SIGXCPU each CPU second beyond the soft limit.
            # Ignore repeats so cleanup can use the reserved CPU interval;
            # the unchanged hard limit still terminates the process at cpu.
            signal.signal(signal.SIGXCPU, signal.SIG_IGN)
        raise TimeoutError("registered finite resource envelope")
    signal.signal(signal.SIGXCPU, exhausted)
    signal.signal(signal.SIGALRM, exhausted)
    signal.alarm(max(1, wall - min(60, max(10, wall // 10))))
    import numpy as np
    import pandas as pd
    import pyarrow as pa
    pa.set_cpu_count(1); pa.set_io_thread_count(1); pa.set_memory_pool(pa.system_memory_pool())
    def no_network(event, _args):
        if event in {"socket.connect", "socket.connect_ex", "socket.getaddrinfo"}:
            raise RuntimeError("zero-network retained-source efficiency wave")
    sys.addaudithook(no_network)
    return np, pd


def public_note(name, payload):
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / name).open("xb") as handle:
        handle.write(enc(payload)); handle.flush(); os.fsync(handle.fileno())


def source_refs():
    hgb = doc("category-topfive-matched12-new-hgb-v1_1.json")
    pbp24 = doc("role-count-full-pbp2024-recovery-gate-network-v2.json")
    pbp26 = doc("category-topfive-matched12-current-label-execute-v1.json.gz")["pbp"]
    return hgb, [{"path": str(Path(pbp24["output"]) / "FULL_PBP2024.parquet"), "bytes": pbp24["asset"]["expected_bytes"], "sha256": pbp24["asset"]["expected_sha256"]}, pbp26]


def pack_profiles(profiles):
    """Lossless schema/clock factorization; every raw/shrunk value is retained."""
    static = {"actor", "group", "value", "metric", "lookback_appearances", "prior_carries"}
    definitions = []
    for tendency in profiles[0]["tendencies"] if profiles else []:
        definitions.append(dict(constants={k: v for k, v in tendency.items() if k in static},
                                fields=sorted(set(tendency) - static)))
    encoded = []
    for profile in profiles:
        if len(profile["tendencies"]) != len(definitions):
            raise ValueError("profile tendency schema mismatch")
        clocks = sorted({v for t in profile["tendencies"] for k, v in t.items() if k.endswith("_clock") and v is not None})
        clockids = {v: i for i, v in enumerate(clocks)}
        values = []
        for definition, tendency in zip(definitions, profile["tendencies"]):
            if {k: v for k, v in tendency.items() if k in static} != definition["constants"]:
                raise ValueError("profile constant definition mismatch")
            values.append([clockids[v] if k.endswith("_clock") and v is not None else v for k in definition["fields"] for v in [tendency[k]]])
        encoded.append(dict(identity={k: v for k, v in profile.items() if k != "tendencies"}, clocks=clocks, values=values))
    packet = dict(codec="LOSSLESS_PROFILE_SCHEMA_CLOCK_FACTORIZATION_V1", definitions=definitions, profiles=encoded)
    return lzma.compress(enc(packet), preset=3)


def unpack_profiles(body):
    packet = json.loads(lzma.decompress(body))
    if packet["codec"] != "LOSSLESS_PROFILE_SCHEMA_CLOCK_FACTORIZATION_V1":
        raise ValueError("unknown profile codec")
    profiles = []
    for p in packet["profiles"]:
        tendencies = []
        for definition, values in zip(packet["definitions"], p["values"]):
            row = dict(definition["constants"])
            for k, value in zip(definition["fields"], values):
                row[k] = p["clocks"][value] if k.endswith("_clock") and value is not None else value
            tendencies.append(row)
        profiles.append(dict(p["identity"], tendencies=tendencies))
    return profiles


def load_inputs(pd):
    from tools import abc_a_dynamic_carry_wave_v1 as base
    from nfl_lab import abc_player_rushing_context_v1 as accepted
    b, c, g, fr, z, oldtrain, history, queries = base.inputs(pd)
    hgb, refs = source_refs()
    # Exact original HGB accepted-REG admission, feature panel and parameters.
    train = pd.read_parquet(io.BytesIO(pin(hgb["training_features"])))
    schedule = pd.read_csv(io.BytesIO(pin(hgb["schedule"])))
    regular = set(schedule.loc[schedule.season.between(2019, 2025) & schedule.game_type.eq("REG"), "game_id"])
    available = pd.to_datetime(train.outcome_available_utc, utc=True)
    kickoff = pd.to_datetime(train.kickoff_utc, utc=True)
    origin = pd.Timestamp("2026-09-01", tz="UTC")
    mask = train.game_id.isin(regular) & available.notna() & (available < origin) & kickoff.notna() & (kickoff < origin)
    train = train.loc[mask].sort_values(["kickoff_utc", "game_id", "player_id"], kind="stable").reset_index(drop=True)
    if len(train) != hgb["expected_training_rows"]:
        raise ValueError("original HGB training population mismatch")
    if pd.to_datetime(history.outcome_available_utc, utc=True).isna().any():
        raise ValueError("explicitly unknown historical clock cannot be filled")
    frames = []
    for year, ref in zip((2024, 2026), refs):
        frame = pd.read_parquet(io.BytesIO(pin(ref)), columns=accepted.COLS)
        frames.append(frame.loc[frame.season_type.eq("REG") & ((frame.week <= 7) if year == 2026 else True)].copy())
    category = json.loads(pin(hgb["categories"]))["categories"]["rush_yd"]
    category = dict(category, target="rush_yd")
    return dict(base=b, continuation=c, grade=g, prepared=fr, train=train, oldtrain=oldtrain, history=history, queries=queries,
                frames=frames, pbp_refs=refs, hgb_plan=hgb, category=category, schedule=schedule)


def cached_laws(queries):
    with zipfile.ZipFile(io.BytesIO(pin(LAW_REF))) as archive:
        records = json.loads(gzip.decompress(archive.read("FORECAST_PARTIALS.json.gz")))
    laws = {}
    coverage = {}
    for year, q in queries.items():
        rows = [r for r in records if r["season"] == year and r["arm"] == "A1_BACKFIELD_CDF_ROLE_INPUTS"]
        lookup = {tuple(r[k] for k in KEY): r for r in rows}
        if len(lookup) != len(rows):
            raise ValueError("duplicate cached A1 count law")
        planned = set(map(tuple, q[KEY].to_numpy()))
        missing = planned - set(lookup)
        if missing:
            raise ValueError(f"cached fixed N law missing {len(missing)} declared {year} queries")
        if any(lookup[k].get("law", {}).get("kind") != "leaf_cdf" for k in planned):
            raise ValueError("cached A1 product lacks genuine count law")
        laws.update({k: lookup[k] for k in planned})
        coverage[str(year)] = dict(rows=len(planned), games=int(q.game_id.nunique()), weeks=sorted(map(int, q.week.unique())), complete=True)
    return laws, coverage


def audited_feature_binding(data):
    """Reuse exact existing source-matched audit; never recertify other inputs."""
    adapter = ROOT / "nfl_lab/player_context_completion_features_v1.py"
    if sha(adapter.read_bytes()) != AUDIT_FEATURE_SHA:
        raise ValueError("exact owned repaired feature adapter required")
    exact = json.loads(pin(AUDIT_EXACT)); training = json.loads(pin(AUDIT_TRAINING))
    if (exact["state"] != "EXACT_RETAINED_TRAINING_QUERY_AND_GUARD_EQUIVALENCE" or exact["changed_rows"] != 0
            or exact["model_feature_columns"] != 97 or exact["repaired_feature_sha256"] != AUDIT_FEATURE_SHA
            or exact["retained_query_sha256"] != data["continuation"]["features"]["sha256"]
            or exact["training_proof_sha256"] != AUDIT_TRAINING["sha256"]):
        raise ValueError("source-matched repaired query evidence differs")
    tref = data["hgb_plan"]["training_features"]
    if any(training["training_input"][k] != tref[k] for k in ("sha256", "bytes")):
        raise ValueError("HGB old training source differs from exact97-field audit")
    if training["history_sources"] != [safe(r) for r in data["continuation"]["history_sources"]]:
        # Only hashes and sizes identify the admitted history; paths are routing.
        actual = [{k: r[k] for k in ("sha256", "bytes")} for r in data["continuation"]["history_sources"]]
        if training["history_sources"] != actual:
            raise ValueError("repaired query audit history sources differ")
    panel = training["panels"][0]
    if panel["fit_eligible_rows"] != len(data["train"]) or any(not panel[k]["exact_finite_and_missing_equivalence"] or panel[k]["columns"] != 97 for k in
            ("original_rebuild", "repair_effect", "fit_scope_original_rebuild", "fit_scope_repair_effect")):
        raise ValueError("unchanged HGB training input equivalence not established")
    return dict(state="REUSED_EXACT_SOURCE_MATCHED_AUDIT_97_FIELDS_AND_GUARDS", adapter_sha256=AUDIT_FEATURE_SHA,
                training_rows=len(data["train"]), query_rows=exact["query_rows"], source_audit=safe(AUDIT_EXACT), training_audit=safe(AUDIT_TRAINING))


def representative_cached_parity(data, pd):
    """One bounded actual-path check; reuse the completed full source audit."""
    import numpy as np
    from nfl_lab import player_context_completion_features_v1 as features
    binding = audited_feature_binding(data)
    saved = pd.read_parquet(io.BytesIO(pin(data["continuation"]["features"])))
    candidates = saved.loc[saved.position.eq("RB") & saved.week.eq(7)]
    order = candidates.sort_values(["f_player_games_prior", "cutoff_utc", "player_id"], kind="stable")
    indices = list(dict.fromkeys(list(order.index[:4]) + list(order.index[-4:])))
    known = saved.loc[indices].copy().reset_index(drop=True)
    columns = [c for c in saved if c.startswith("f_")]
    if len(columns) != 97:
        raise ValueError("exact cached feature-panel scope changed")
    metadata = [c for c in known if not c.startswith(("f_", "feature_")) and c != "participation_probability_state"]
    q = known[metadata].copy()
    # Exactly the audited query-only placeholder contract: it is not an
    # observed outcome clock, every target statistic stays null, and it lies
    # after every query cutoff. Historical unknown clocks are never filled.
    q["outcome_available_utc"] = q.kickoff_utc + pd.Timedelta(days=7)
    q["participation_state"] = "unknown"
    for field in [*features.PLAYER_STATS, *("team_stat_" + x for x in features.TEAM_STATS)]:
        q[field] = np.nan
    source = data["history"].loc[data["history"].season.lt(2026) | data["history"].season.eq(2026) & data["history"].week.lt(7)].copy()
    if pd.to_datetime(source.outcome_available_utc, utc=True).isna().any():
        raise ValueError("representative check cannot fill unknown historical clock")
    source["cutoff_utc"] = pd.to_datetime(source.kickoff_utc, utc=True)
    if (q.outcome_available_utc <= q.cutoff_utc.max()).any():
        raise ValueError("query-only placeholder must remain beyond every query cutoff")
    combined = features.build_features(pd.concat([source, q], ignore_index=True))
    actual = combined.iloc[len(source):].copy().reset_index(drop=True)
    actual["f_player_play_rate8"] = np.nan
    actual["feature_max_assumed_history_available_utc"] = actual.feature_max_source_available_utc
    changed = []
    for name in columns:
        a = pd.to_numeric(known[name], errors="raise").to_numpy(float)
        b = pd.to_numeric(actual[name], errors="raise").to_numpy(float)
        if not np.all((a == b) | (np.isnan(a) & np.isnan(b))):
            changed.append(name)
    guards = {}
    for name in ("feature_max_source_available_utc", "feature_max_assumed_history_available_utc"):
        a = pd.to_datetime(known[name], utc=True); b = pd.to_datetime(actual[name], utc=True)
        guards[name] = int((~(a.eq(b) | (a.isna() & b.isna()))).sum())
    if changed or any(guards.values()):
        raise ValueError("representative repaired feature mismatch: " + repr(changed) + repr(guards))
    return dict(state="PASS_REPRESENTATIVE_REPAIRED_FEATURES_MATCH_CACHED", adapter_sha256=AUDIT_FEATURE_SHA,
        representative_query_rows=len(known), feature_columns=len(columns), changed_columns=changed, guard_changed_rows=guards,
        identity_commitment_sha256=sha(enc(known[KEY].to_dict("records"))), retained_query_sha256=data["continuation"]["features"]["sha256"],
        unknown_external_target_outcome_clock_preserved=True, target_outcomes_read=False, source_binding=binding,
        query_only_internal_clock="kickoff+7day_nonobservation_placeholder_after_all_cutoffs; exact audited recipe; alltargetstatisticsNaN",
        model_loads=0, fits=0, predictive_inference=0, scores=0, private_writes=0)


def week8_queries(data, pd, build_features=False):
    """Captured board defines membership; historical metadata supplies exact IDs.

    No target participants, target statistics, current roster or fuzzy names are
    used. Missing original ID bridges are an explicit source gap.
    """
    with zipfile.ZipFile(io.BytesIO(pin(W8_REF))) as archive:
        raw = archive.read(W8_MEMBER["name"])
    if len(raw) != W8_MEMBER["bytes"] or sha(raw) != W8_MEMBER["sha256"]:
        raise ValueError("original Week8 board mismatch")
    board = json.loads(raw)
    # The captured schema has top-level arrays; do not inspect points or props.
    players = board["players"]
    games = board["games"]
    cut = pd.Timestamp(board["saved_at"])
    original = pd.read_parquet(io.BytesIO(pin(data["continuation"]["features"])), columns=["sleeper_id", "player_id", "position"])
    original["sleeper_id"] = original.sleeper_id.astype(str)
    bridge = {}
    for sid, group in original.groupby("sleeper_id"):
        ids = group.player_id.dropna().astype(str).unique()
        if len(ids) == 1:
            bridge[sid] = ids[0]
    schedule = data["schedule"]
    if "espn" not in schedule:
        raise ValueError("original schedule ESPN event bridge unavailable")
    sched = schedule.loc[schedule.season.eq(2026) & schedule.week.eq(8) & schedule.game_type.eq("REG")].copy()
    sched["website_game_id"] = sched.espn.map(lambda x: str(int(x)) if pd.notna(x) else None)
    game_lookup = {str(g["id"]): g for g in games}
    rows, missing = [], []
    aliases = {"LA": "LAR", "STL": "LAR", "SD": "LAC", "OAK": "LV"}
    for player in players:
        if player["pos"] != "RB":
            continue
        sid = str(player["id"]); event = str(player["game_id"])
        gsis = bridge.get(sid)
        sg = sched.loc[sched.website_game_id.eq(event)]
        team = aliases.get(player["team"], player["team"]); opponent = aliases.get(player["opp"], player["opp"])
        if gsis is None or len(sg) != 1 or event not in game_lookup:
            missing.append(dict(profile_version="A::PLAYER-CONTEXT-COMPLETION-DECISION-01-efficiency-v1", season=2026, week=8,
                game_id=str(sg.iloc[0].game_id) if len(sg) == 1 else None, player_id=None,
                source_identity=dict(player_namespace="SLEEPER", player_id=sid, event_namespace="ESPN", event_id=event),
                historical_team=team, opponent=opponent, cutoff_utc=cut.isoformat(), source_information_max_utc=None,
                lookback_appearances=8, state="UNAVAILABLE_CANONICAL_ID" if gsis is None else "UNAVAILABLE_CANONICAL_EVENT",
                unavailable_reason="canonical GSIS bridge" if gsis is None else "original schedule event bridge",
                eligible_player_games=None, eligible_player_carries=None, historical_teams=[], tendencies=[],
                source_policy="CURRENT_VINTAGE_RECONSTRUCTION_WITH_SEVEN_DAY_PROXY", source_board_sha256=W8_MEMBER["sha256"]))
            continue
        sr = sg.iloc[0]; home = aliases.get(sr.home_team, sr.home_team); away = aliases.get(sr.away_team, sr.away_team)
        if {team, opponent} != {home, away}:
            raise ValueError("Week8 source historical team/opponent mismatch")
        kickoff = pd.Timestamp(game_lookup[event]["kickoff"])
        if kickoff.tzinfo is None or cut.tzinfo is None or not cut < kickoff:
            raise ValueError("captured pregame board clock required")
        rows.append(dict(season=2026, season_type="REG", week=8, game_id=str(sr.game_id), player_id=gsis, sleeper_id=sid,
            team=team, opponent=opponent, position="RB", kickoff_utc=kickoff, cutoff_utc=cut, is_home=team == home,
            participation_state="unknown", outcome_available_utc=pd.NaT, pregame_roster_qualified=True,
            source_board_sha256=W8_MEMBER["sha256"], query_membership="AUTHENTIC_CAPTURED_BOARD_NOT_TARGET_APPEARANCE"))
    q = pd.DataFrame(rows)
    census = dict(state="READY_EXACT_BRIDGED_CAPTURED_BOARD" if not missing else "PARTIAL_EXACT_BRIDGE_SOURCE_GAP", captured_rb_rows=len(rows) + len(missing),
        mapped_rows=len(rows), missing_bridge_rows=len(missing), games=int(q.game_id.nunique()) if len(q) else 0, source=safe(W8_REF), member=W8_MEMBER,
        captured_at=cut.isoformat(), feature_state="RECONSTRUCTION_REGISTERED_NOT_YET_EXECUTED", missing_inputs=sorted(set(r["unavailable_reason"] for r in missing)),
        unavailable_profile_rows=len(missing), original_declared_profile_rows=len(rows)+len(missing))
    if not build_features or not len(q):
        return q, census, missing
    binding = audited_feature_binding(data)
    import numpy as np
    from nfl_lab import player_context_completion_features_v1 as features, category_topfive_backfield_v1 as backfield, abc_dynamic_carry_v1 as dynamic
    history = data["history"].copy()
    for name in ("kickoff_utc", "outcome_available_utc"):
        if pd.to_datetime(history[name], utc=True).isna().any():
            raise ValueError("Week8 feature reconstruction cannot fill unknown historical clocks")
    # Existing deterministic seven-day builder; this new historical query is
    # explicitly reconstruction, never a genuine original model issuance.
    h = history.loc[pd.to_datetime(history.outcome_available_utc, utc=True) < cut].copy()
    h["cutoff_utc"] = pd.to_datetime(h.kickoff_utc, utc=True)
    old_features = [c for c in h if c.startswith("f_")]
    h.drop(columns=old_features, inplace=True)
    internal_q = q.copy()
    internal_q["outcome_available_utc"] = internal_q.kickoff_utc + pd.Timedelta(days=7)
    for field in [*features.PLAYER_STATS, *("team_stat_" + x for x in features.TEAM_STATS)]:
        internal_q[field] = np.nan
    if (internal_q.outcome_available_utc <= internal_q.cutoff_utc.max()).any():
        raise ValueError("query-only placeholder must remain beyond all target cutoffs")
    combined = features.build_features(pd.concat([h, internal_q], ignore_index=True))
    built = combined.iloc[len(h):].copy().reset_index(drop=True)
    built["participation_state"] = "unknown"; built["outcome_available_utc"] = pd.NaT
    built["f_player_play_rate8"] = np.nan
    built["participation_probability_state"] = "unavailable_incomplete_nonappearance_denominator"
    built["feature_max_assumed_history_available_utc"] = built.feature_max_source_available_utc
    built = backfield.augment(built, h)
    built, _, _ = dynamic.augment(built, dynamic.compile_history(h))
    if not set(data["category"]["panels"]["base"]) <= set(built):
        raise ValueError("Week8 original direct-HGB base features missing")
    census["feature_state"] = "EXISTING_EARLIER_ONLY_BUILDER_RECONSTRUCTION"
    census["feature_builder"] = "exact audited c3dcc6 adapter + unchanged backfield/dynamic augment"
    census["feature_adapter_binding"] = binding
    census["history_max_available_utc"] = pd.to_datetime(h.outcome_available_utc, utc=True).max().isoformat()
    return built, census, missing


def prepare():
    start = time.monotonic(); cpu = time.process_time()
    np, pd = runtime()
    from nfl_lab import player_context_rush_efficiency_v1 as core
    data = load_inputs(pd)
    laws, coverage = cached_laws(data["queries"])
    _, w8, _ = week8_queries(data, pd)
    pin(HGB_REF)  # Authenticate own model bytes without deserialization.
    with zipfile.ZipFile(io.BytesIO(pin(data["grade"]["frozen_bundle"]))) as z:
        controls = pd.read_parquet(io.BytesIO(z.read("FORECASTS.parquet")), columns=["target", "method", "product", "season", "week", "position"])
    saved = controls.loc[controls.target.eq("rush_yd") & controls.position.eq("RB")]
    inventory = saved.groupby(["method", "product"], dropna=False).size().reset_index(name="rows").to_dict("records")
    ctx = core.EfficiencyContext(data["frames"], data["history"])
    records = [p for rs in ctx.players.values() for p in rs if p["role"] == "RB" and p["season"] == 2024 and p["attempts"] > 0]
    window_support = []
    for w in (4, 8, 16):
        # Source support only, without features, predictions, scores or target
        # participant-defined query membership for a selection experiment.
        distinct = [min(w, len(core.eligible(ctx.players[p["player"]], p["kickoff"] - pd.Timedelta(hours=1), 16))) for p in records]
        window_support.append(dict(window=w, source_rb_player_games=len(records), earlier_supported_player_games=sum(n > 0 for n in distinct),
            reached_window_player_games=sum(n == w for n in distinct)))
    report = dict(version=VERSION, state="SOURCE_AND_CODE_PREPARATION_NO_FITS_INFERENCE_OR_SCORES", UTC=now(),
        mechanism="direction/gap/down/distance conditional signed-yard+EPApositive efficiency; fixed unchanged external A1 carry law",
        source_ids={"pbp2024": safe(data["pbp_refs"][0]), "pbp2026": safe(data["pbp_refs"][1]), "original_hgb_training": safe(data["hgb_plan"]["training_features"]),
                    "strong_saved_controls": safe(data["grade"]["frozen_bundle"]), "fixed_n_laws": safe(LAW_REF), "own_hgb_model": safe(HGB_REF)},
        original_hgb_training_rows=len(data["train"]), original_hgb_feature_panel=data["category"]["panels"]["base"], conditional_feature_count=len(core.EFFICIENCY_FEATURES),
        consumed_efficiency_features=core.EFFICIENCY_FEATURES, profile_only_features=core.PROFILE_ONLY_FEATURES,
        law_coverage=coverage, strong_control_inventory=inventory, week8=w8, source_player_appearance_lookback_support=window_support,
        withheld_target_source_games=len(ctx.accepted.withheld_future_source_games),
        lookback=dict(value=8, selection_state="INCOMPLETE_END_TO_END_LOOKBACK_SELECTION", reason="No retained earlier2024 A1 count-law binding or qualified pregame2024 universe identified; component-only NLL does not select this total-yard system"),
        fits_planned=["D0_2025 original MAE HGB", "D1_2025 identical HGB+raw earlier conditional profiles", "D1_2026 identical HGB+raw earlier conditional profiles", "S1 shared2024 percarry signed-yard Ridge", "S1 shared2024 percarry EPApositive logistic"],
        frozen_control_policy="Include every available saved rush_yd finalist including HGB, Leaf mean/median, CatBoost; do not select a weaker baseline",
        fitting_rule="annual HGB training years<year, available<September1; S1 uses only2024 source carries, same fitted conditional model reused2025/26; no2026 fit labels",
        tradeoff="Direct MAE and integrated conditional mean optimize different objectives; compare complete systems, not pure architecture causality",
        output_contract="point-only total signed yards; no outcome law, O/U win probability or manufactured distribution; percarry EPApositive is diagnostic",
        executions=dict(new_fits=0, inference=0, new_scores=0, model_loads=0, new_source_HTTP=0, private_writes=0),
        resources=dict(CPU_seconds=time.process_time()-cpu, wall_seconds=time.monotonic()-start, RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024),
        code_sha256={p: sha((ROOT / p).read_bytes()) for p in ("nfl_lab/player_context_rush_efficiency_v1.py", "tools/player_context_completion_efficiency_v1.py")})
    public_note("EFFICIENCY_PREPARATION_V1.json", report)
    print(enc(report).decode(), flush=True)


def fit_direct(train, category, panel):
    """Original MAE-HGB recipe, explicit one-thread runtime for this wave."""
    import numpy as np
    from nfl_lab import cdf_engine as cdf, median_boosting as hgb
    from sklearn.ensemble import HistGradientBoostingRegressor
    from threadpoolctl import threadpool_limits
    cdf.validate_category(category)
    y = cdf.numeric(train, "rush_yd")
    good = (cdf.strings(train, "participation_state") == "played") & cdf.valid_support(y, "signed_integer")
    supported = train.loc[good]
    model = hgb.MedianBoostingModel(category, panel)
    columns = [c for c in cdf.KEYS + ["position", "kickoff_utc", "outcome_available_utc", "rush_yd"] if c in train]
    model.prior_training_binding = supported[columns].copy()
    model.global_prior = cdf.SupportPrior.fit(y[good], "signed_integer")
    model.priors = {str(role): cdf.SupportPrior.fit(cdf.numeric(part, "rush_yd"), "signed_integer") for role, part in supported.groupby("position")}
    modeled = supported.loc[supported.position.isin(category["modeled_roles"])]
    model.training_binding = modeled[columns].copy()
    model.design = cdf.FixedDesign.fit(modeled, category["panels"][panel])
    if len(modeled) < hgb.DESIGN["minimum_modeled_rows"]:
        raise ValueError("insufficient original HGB modeled rows")
    with threadpool_limits(limits=1):
        model.estimator = HistGradientBoostingRegressor(loss="absolute_error", **hgb.PARAMETERS).fit(model.design.transform(modeled), cdf.numeric(modeled, "rush_yd"))
    STATE["pending_model_object"] = model
    model.audit = dict(fit_state="FITTED", version=hgb.VERSION, design=hgb.DESIGN, actual_threads=1, supported_played_training_rows=len(supported),
        modeled_training_rows=len(modeled), global_prior=vars(model.global_prior), role_priors={r: vars(p) for r, p in model.priors.items()},
        original_feature_panel=category["panels"][panel], point_contract="MAE_OBJECTIVE_POINT_NOT_LAW_MEAN_MEDIAN_OR_PROBABILITY")
    return model


def authorize(plan_path, plan_sha, go_path, go_sha):
    planraw = pin(dict(path=str(plan_path), bytes=plan_path.stat().st_size, sha256=plan_sha))
    goraw = pin(dict(path=str(go_path), bytes=go_path.stat().st_size, sha256=go_sha))
    plan, go = json.loads(planraw), json.loads(goraw)
    if go.get("state") != "ROOT_AND_INDEPENDENT_GO" or go.get("registered_by") != "/root" or go.get("protocol_sha256") != plan_sha:
        raise ValueError("exact root protocol GO required before NFL execution")
    if plan["version"] != VERSION or plan["maximum_new_fits"] != 5 or plan["lookback"] != 8:
        raise ValueError("fixed one-mechanism five-fit plan required")
    for name, digest in plan["code_sha256"].items():
        if sha((ROOT / name).read_bytes()) != digest:
            raise ValueError("published code binding changed: " + name)
    if set(plan["source_configuration_sha256"]) != {"config/" + name for name in SOURCE_CONFIGS}:
        raise ValueError("complete fixed source-configuration binding required")
    for name, digest in plan["source_configuration_sha256"].items():
        if sha((ROOT / name).read_bytes()) != digest:
            raise ValueError("published source configuration changed: " + name)
    publication = json.loads(pin(go.get("publication_ref", plan.get("publication"))))
    if publication.get("state") != "PUBLICATION_COMPLETE":
        raise ValueError("public protocol readback required")
    STATE["plan_raw"] = planraw
    return plan


def predict_direct(model, frame):
    """Original signed-HGB prediction/fallback policy, using one thread."""
    import numpy as np
    from nfl_lab import cdf_engine as cdf, median_boosting as hgb
    from threadpoolctl import threadpool_limits
    roles = cdf.strings(frame, "position")
    history = cdf.numeric(frame, "f_player_games_prior")
    points = np.full(len(frame), np.nan)
    reasons = np.full(len(frame), "no_supported_played_training_outcomes", dtype=object)
    for role in np.unique(roles):
        ix = np.flatnonzero(roles == role)
        prior = model.priors.get(str(role), model.global_prior)
        if prior is None:
            continue
        points[ix] = hgb.prior_point(prior); reasons[ix] = ""
        if str(role) not in model.category["modeled_roles"]:
            reasons[ix] = "nonmodeled_role_prior"
        elif model.estimator is None:
            reasons[ix] = "insufficient_modeled_training_role_prior"
        else:
            cold = ~np.isfinite(history[ix]) | (history[ix] <= 0)
            reasons[ix[cold]] = "cold_start_role_prior"
        if str(role) not in model.priors:
            reasons[ix] = "global_prior_unknown_role"
    warm = np.flatnonzero(reasons == "")
    if len(warm):
        with threadpool_limits(limits=1):
            points[warm] = model.estimator.predict(model.design.transform(frame.iloc[warm]))
    if not np.isfinite(points).all():
        raise ValueError("unchanged signed HGB point is nonfinite")
    return points, reasons


def run(plan):
    start = time.monotonic(); cpu = time.process_time()
    np, pd = runtime(plan["resources"]["CPU_seconds"], plan["resources"]["wall_seconds"])
    import joblib
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import Ridge, LogisticRegression
    from threadpoolctl import threadpool_limits
    from nfl_lab import player_context_rush_efficiency_v1 as core, player_context_completion_storage_v1 as guard
    store = guard.CompletionStore(ROOT, Path(plan["allocation"]["path"]), plan["allocation"]["sha256"], root_go=guard.GO)
    STATE.update(store=store, phase="SOURCE_ADMISSION")
    def put(name, body):
        if not name.endswith("FAILURE.json") and "FAILURE" not in name and "RETURNED_PENDING" not in name:
            store.reserve(len(body) + 1024**2)
        ref = store.put(name, body); STATE["artifacts"].append(ref)
        return ref
    def persist_model(name, model):
        # Set pending state immediately after fit return, before optional checks.
        STATE["pending_model_object"] = model
        stream = io.BytesIO(); joblib.dump(model, stream, compress=("xz", 3))
        STATE["pending_model_bytes"] = stream.getvalue()
        ref = put(name, stream.getvalue())
        store.read(name, ref["sha256"])
        STATE.pop("pending_model_bytes", None); STATE.pop("pending_model_object", None)
        return ref
    def fit_started(arm, reserve=800000):
        store.reserve(reserve + 1024**2)
        STATE["fits_attempted"] += 1; STATE["phase"] = "FIT_" + arm
        if STATE["fits_attempted"] > plan["maximum_new_fits"]:
            raise ValueError("consumed five-fit ceiling")
        put(f"events/FIT_{STATE['fits_attempted']}_START.json", enc(dict(arm=arm, UTC=now(), slot=STATE["fits_attempted"], state="CONSUMED_BEFORE_FIT")))
    put("CONSUMED.json", enc(dict(version=VERSION, UTC=now(), state="CONSUMED_BEFORE_SOURCE_MODEL_DECODE", maximum_new_fits=5)))
    put("PRIVATE_EXECUTION_PLAN.json", STATE.pop("plan_raw", enc(plan)))
    try:
        data = load_inputs(pd)
        ctx = core.EfficiencyContext(data["frames"], data["history"])
        queries = data["queries"]
        laws, law_coverage = cached_laws(queries)
        adapter_evidence = audited_feature_binding(data)
        representative = json.loads(pin(plan["feature_adapter_representative_parity"]))
        if (representative["state"] != "PASS_REPRESENTATIVE_REPAIRED_FEATURES_MATCH_CACHED" or representative["adapter_sha256"] != AUDIT_FEATURE_SHA
                or representative["retained_query_sha256"] != data["continuation"]["features"]["sha256"]):
            raise ValueError("bound representative repaired-builder parity required before W8 inference")
        put("REPAIRED_FEATURE_ADAPTER_AUDIT_BINDING.json", enc(adapter_evidence))
        put("REPAIRED_FEATURE_ADAPTER_REPRESENTATIVE_PARITY.json", enc(representative))
        w8, w8_census, unavailable = week8_queries(data, pd, build_features=False)
        put("PROFILES_2026_W8_UNAVAILABLE.json.gz", gzip.compress(enc(unavailable), mtime=0))
        if plan.get("week8_reconstruction", False):
            w8, w8_census, _ = week8_queries(data, pd, build_features=True)
        if plan.get("week8_reconstruction", False) and w8 is not None and len(w8):
            from nfl_lab import cdf_engine as cdf
            # Authenticated own A1 compact model contains every unique learned
            # state; optional W8 inference does not create a new fitted model.
            nmodel = joblib.load(io.BytesIO(pin(plan["week8_count_model"])))
            if not isinstance(nmodel, cdf.LeafCDFModel):
                raise ValueError("own fixed N model type mismatch")
            for ix, law, reasons in nmodel.predict_batches(w8, batch_size=128):
                for j, pos in enumerate(ix):
                    r = w8.iloc[pos]
                    laws[tuple(r[k] for k in KEY)] = dict(law=dict(kind="leaf_cdf", support=law.support.tolist(), weights=law.weights[j].tolist(),
                        prior=vars(law.prior), prior_weight=law.b), source_forecast_sha256=plan["week8_count_model"]["sha256"],
                        source_information_max_UTC=str(r.feature_max_source_available_utc))
            queries[2026] = pd.concat([queries[2026], w8], ignore_index=True)
        put("SOURCE_ADMISSION.json", enc(dict(version=VERSION, law_coverage=law_coverage, week8=w8_census,
            pbp=[safe(r) for r in data["pbp_refs"]], strong_controls=safe(data["grade"]["frozen_bundle"]), original_training_rows=len(data["train"]),
            withheld_source_games=len(ctx.accepted.withheld_future_source_games), window=8, lookback_selection="INCOMPLETE_FIXED8")))
        augmented, _ = ctx.augment(data["train"], rich=False)
        qaug = {}; profile_count = len(unavailable)
        for year, q in queries.items():
            qaug[year], profiles = ctx.augment(q, rich=True)
            profile_count += len(profiles)
            packed = pack_profiles(profiles)
            # Unique profile values are durable before optional codec parity.
            pref = put(f"PROFILES_{year}.json.xz", packed)
            if enc(unpack_profiles(store.read(f"PROFILES_{year}.json.xz", pref["sha256"]))) != enc(profiles):
                raise ValueError("lossless profile factorization roundtrip mismatch")
            del profiles
            # Query targets remain unavailable. Profile hashes commit exact
            # private values without publicly exporting source player histories.
            put(f"QUERY_IDENTITIES_{year}.json.gz", gzip.compress(enc([{k: int(getattr(r, k)) if k in ("season", "week") else str(getattr(r, k)) for k in KEY + CTX} for r in q.itertuples()]), mtime=0))
        from nfl_lab import median_boosting as hgb
        # All available saved finalists remain controls; this prevents choosing a
        # weak comparator after candidate scores are known.
        with zipfile.ZipFile(io.BytesIO(pin(data["grade"]["frozen_bundle"]))) as z:
            old_controls = pd.read_parquet(io.BytesIO(z.read("FORECASTS.parquet")))
        control = old_controls.loc[old_controls.target.eq("rush_yd") & old_controls.position.eq("RB")].copy()
        forecast_rows = STATE["forecasts"]
        for r in control.to_dict("records"):
            point = r.get("prediction", r.get("point"))
            if pd.isna(point):
                continue
            row = {k: int(r[k]) if k in ("season", "week") else str(r[k]) for k in KEY + CTX}
            row.update(arm="SAVED_" + str(r["method"]) + "__" + str(r["product"]), target="rush_yd", point=float(point), probability=None,
                outcome_law=None, point_semantics=str(r["product"]), source_forecast_sha256=data["grade"]["frozen_bundle"]["sha256"])
            forecast_rows.append(row)
            if r["method"] == "HGB_MAE_DIRECT" and r["product"] == "mae_objective_point":
                forecast_rows.append(dict(row, arm="D0_UNCHANGED_HGB_MAE"))
        modelrefs = {}
        for year in (2025, 2026):
            fitcut = pd.Timestamp(f"{year}-09-01", tz="UTC")
            mask = augmented.season.lt(year) & (pd.to_datetime(augmented.outcome_available_utc, utc=True) < fitcut)
            tr = augmented.loc[mask].copy()
            q = qaug[year]
            for arm in ("D0_UNCHANGED_HGB_MAE", "D1_HGB_RAW_CONDITIONAL_PROFILE"):
                if year == 2026 and arm.startswith("D0"):
                    # W1-7 uses exact saved forecasts; only authentic mapped W8
                    # queries require restoring the unchanged own model.
                    q = qaug[year].loc[qaug[year].week.eq(8)]
                    if q.empty:
                        continue
                    model = joblib.load(io.BytesIO(pin(HGB_REF)))
                    modelrefs[f"{year}_{arm}"] = safe(HGB_REF)
                else:
                    category = copy.deepcopy(data["category"])
                    if arm.startswith("D1"):
                        category["panels"]["base"] += core.EFFICIENCY_FEATURES
                        category["panels"]["context"] += core.EFFICIENCY_FEATURES
                    fit_started(f"{year}_{arm}")
                    model = fit_direct(tr, category, "base")
                    STATE["fits_returned"] += 1
                    modelrefs[f"{year}_{arm}"] = persist_model(f"MODEL_{year}_{arm}.joblib", model)
                    q = qaug[year]
                with threadpool_limits(limits=1):
                    points, reasons = predict_direct(model, q)
                rows = []
                for j, r in enumerate(q.itertuples()):
                    row = {k: int(getattr(r, k)) if k in ("season", "week") else str(getattr(r, k)) for k in KEY + CTX}
                    row.update(arm=arm, target="rush_yd", point=float(points[j]), probability=None, outcome_law=None, fallback=str(reasons[j]) or None,
                        point_semantics="MAE_OBJECTIVE_POINT_NOT_MEAN_OR_LAW_MEDIAN", source_information_max_utc=str(r.feature_max_source_available_utc))
                    rows.append(row)
                forecast_rows.extend(rows)
                put(f"FORECAST_{year}_{arm}.json.gz", gzip.compress(enc(rows), mtime=0))
                del model
        # Per-carry fitting uses old credited carry cells, weighted by their
        # exact multiplicity. Both annual systems reuse the same 2024 fit.
        x, y, success, weight = [], [], [], []
        for player, records in ctx.players.items():
            for r in records:
                if r["season"] != 2024 or r["role"] != "RB" or not r["attempts"]:
                    continue
                cut = r["kickoff"] - pd.Timedelta(hours=1)
                f, _, _ = ctx.profile(player, r["team"], r["opponent"], cut, rich=False)
                # Individual EPA-success outcomes, not fractional binomial
                # labels, retain exact cell multiplicity through sample weights.
                for c, cell in r["cells"].items():
                    n, sy, ns, _ = cell
                    design = core.carry_design(f, c, r["bucket"])
                    # Ridge cell-mean weighted fitting is algebraically equal to
                    # individual carries; logistic uses two binary sufficient rows.
                    x.append(design); y.append(sy/n); weight.append(n); success.append(ns)
        xx = np.asarray(x); ww = np.asarray(weight); yy = np.asarray(y); ss = np.asarray(success)
        scaler = StandardScaler().fit(xx, sample_weight=ww)
        xs = scaler.transform(xx)
        percarry = core.ConditionalCarryModel(scaler=scaler, audit=dict(training_source=safe(data["pbp_refs"][0]), season=2024,
            credited_rb_carries=int(ww.sum()), cell_rows=len(xx), parameters=dict(ridge_alpha=32., logistic_C=1/32., logistic_solver="lbfgs", max_iter=1000),
            source_clock="each profile available<its historical kickoff-1hour; fitted relationship before2025 and2026 first block", first_down="SEPARATE_DESCRIPTIVE_PROFILE_ONLY"))
        fit_started("S1_SHARED2024_SIGNED_YARD_RIDGE", 100000)
        with threadpool_limits(limits=1):
            percarry.yards = Ridge(alpha=32., solver="lsqr", tol=1e-8, max_iter=2000).fit(xs, yy, sample_weight=ww)
        STATE["fits_returned"] += 1
        modelrefs["S1_YARDS"] = persist_model("MODEL_S1_YARDS_RETURNED.joblib", percarry)
        lx = np.repeat(xs, 2, axis=0); ly = np.tile([0, 1], len(xs)); lw = np.column_stack([ww-ss, ss]).ravel()
        good = lw > 0
        fit_started("S1_SHARED2024_EPA_POSITIVE_LOGISTIC", 100000)
        with threadpool_limits(limits=1):
            percarry.success = LogisticRegression(C=1/32., solver="lbfgs", max_iter=1000, tol=1e-8, random_state=1703).fit(lx[good], ly[good], sample_weight=lw[good])
        STATE["fits_returned"] += 1
        modelrefs["S1_COMPLETE"] = persist_model("MODEL_S1_COMPLETE_RETURNED.joblib", percarry)
        for year, q in qaug.items():
            rows, diagnostics = [], []
            for r in q.itertuples():
                fixed = laws[tuple(getattr(r, k) for k in KEY)]
                prediction = core.integrated_point(percarry, ctx, r, fixed["law"])
                # The complete system includes the external N-law and original
                # pregame feature clocks, which can be later than PBP profiles.
                clocks = pd.to_datetime([prediction["source_information_max_utc"], r.feature_max_source_available_utc,
                                         fixed.get("source_information_max_UTC")], utc=True)
                full_clock = clocks.max()
                if pd.notna(full_clock) and full_clock >= pd.Timestamp(r.cutoff_utc):
                    raise ValueError("full-system N/profile clock is not earlier")
                prediction["context_information_max_utc"] = prediction["source_information_max_utc"]
                prediction["fixed_n_information_max_utc"] = fixed.get("source_information_max_UTC")
                prediction["source_information_max_utc"] = full_clock.isoformat() if pd.notna(full_clock) else None
                identity = {k: int(getattr(r, k)) if k in ("season", "week") else str(getattr(r, k)) for k in KEY + CTX}
                for arm, name in (("S1_CONDITIONAL_EFFICIENCY_FIXED_N", "point"), ("S0_UNCONDITIONAL_OWN_YPC_FIXED_N", "no_context_fixed_n_point")):
                    rows.append(dict(**identity, arm=arm, target="rush_yd", point=prediction[name], probability=None, outcome_law=None,
                        point_semantics=prediction["point_semantics"] if arm.startswith("S1") else "FIXED_N_MEAN_TIMES_SHRUNK_EARLIER_OWN_YPC", source_information_max_utc=prediction["source_information_max_utc"],
                        fixed_n_source_sha256=LAW_REF["sha256"] if r.week <= 7 or year == 2025 else plan["week8_count_model"]["sha256"]))
                diagnostics.append(dict(**identity, **prediction))
            forecast_rows.extend(rows)
            put(f"FORECAST_{year}_STRUCTURED.json.gz", gzip.compress(enc(rows), mtime=0))
            put(f"DIAGNOSTIC_{year}_STRUCTURED.json.gz", gzip.compress(enc(diagnostics), mtime=0))
        frozen = put("ALL_FORECASTS_BEFORE_LABELS.json.gz", gzip.compress(enc(forecast_rows), mtime=0))
        receipt = dict(version=VERSION, state="FROZEN_FORECASTS_COMPLETE_UNSCORED", UTC=now(), fits_attempted=STATE["fits_attempted"], fits_returned=STATE["fits_returned"],
            models=modelrefs, forecasts=frozen, forecast_rows=len(forecast_rows), profile_rows=profile_count, artifacts=STATE["artifacts"],
            week8=w8_census, counts=dict(new_source_HTTP=0, new_scoring=0, new_original_issuances=0, production_writes=0),
            resources=dict(CPU_seconds=time.process_time()-cpu, wall_seconds=time.monotonic()-start, RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024),
            storage=store.checkpoint(), lookback_selection="INCOMPLETE_FIXED8", evidence="CURRENT_VINTAGE_SEVEN_DAY_RECONSTRUCTION")
        put("EXECUTION_RECEIPT.json", enc(receipt))
        public_note("EFFICIENCY_EXECUTION_RECEIPT_V1.json", receipt)
        print(enc(receipt).decode(), flush=True)
    except BaseException as error:
        fail = dict(version=VERSION, state="FAILED_RETAINED_NO_AUTOMATIC_REFIT", UTC=now(), phase=STATE["phase"], error_type=type(error).__name__,
                    error_sha256=sha(str(error).encode()), fits_attempted=STATE["fits_attempted"], fits_returned=STATE["fits_returned"], artifacts=STATE["artifacts"])
        if STATE.get("pending_model_object") is not None:
            try:
                persist_model("RETURNED_PENDING_MODEL_FAILURE.joblib", STATE["pending_model_object"])
            except BaseException as retention_error:
                fail["returned_model_retention_error_type"] = type(retention_error).__name__
        try:
            put("FAILURE_PRIVATE.json", enc(dict(**fail, traceback=traceback.format_exc())))
            put("FORECAST_PARTIALS_FAILURE.json.gz", gzip.compress(enc(STATE["forecasts"]), mtime=0))
            fail["storage"] = store.checkpoint()
        except BaseException as retention_error:
            fail["failure_retention_error_type"] = type(retention_error).__name__
        public_note("EFFICIENCY_FAILURE_V1.json", fail)
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("prepare", "run"), required=True)
    parser.add_argument("--plan", type=Path); parser.add_argument("--plan-sha256")
    parser.add_argument("--go", type=Path); parser.add_argument("--go-sha256")
    args = parser.parse_args()
    if args.mode == "prepare":
        prepare()
    else:
        if None in (args.plan, args.plan_sha256, args.go, args.go_sha256):
            parser.error("exact published plan and root GO hashes required")
        run(authorize(args.plan, args.plan_sha256, args.go, args.go_sha256))


if __name__ == "__main__":
    main()
