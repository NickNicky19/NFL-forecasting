"""A acceptance: one pinned Ridge reproduction and retained inference checks.

No new predictive recipe, source retrieval, grade version, or production write.
Execution requires the exact preregistration hash and a published GO receipt.
NFL rows and fitted state remain in the inherited guarded private store.
"""
from __future__ import annotations

import argparse
import collections
import datetime
from decimal import Decimal
import gzip
import hashlib
import io
import json
import lzma
import math
import os
from pathlib import Path
import resource
import signal
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
OUT = ROOT / "reports/abc-championship/player-context-acceptance-01"
ALLOCATION = "f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26"
KEY = ["season", "week", "game_id", "player_id"]
STATE = {"phase": "NOT_STARTED", "NFL_fit_attempts": 0, "NFL_fits_returned": 0,
         "software_fits": 0, "private_artifacts": []}
REFS = {
    "p1_model": ("PLAYER-CONTEXT-MATCHUP-01-A-runtime-v3", "MODEL_P1_POOLED_RIDGE.joblib", 4860,
                 "5e8a2eb3c31f3079d8fb35b08449f88dc01e7d9d0ec2af93d48d4408754a22cb"),
    "cdf_container": ("PLAYER-CONTEXT-MATCHUP-01-A-runtime-v2", "FAILED_PARTIALS_V1.zip", 495537,
                      "230bf9d0b7be1f735906102d21d7936278ff83e31222bb5ed662726243e598a9"),
    "context": ("PLAYER-CONTEXT-MATCHUP-01-A-v1", "CONTEXT_FEATURES.parquet", 2155837,
                "d61b578e15515fbf600dacdfcf0b1c87c384917cd591857197c2e867816c97dc"),
    "E1_OWN_CONTEXT": ("PLAYER-CONTEXT-MATCHUP-01-A-runtime-v3", "FORECAST_E1_OWN_CONTEXT.json.xz", 249816,
                       "4ccdfcc5608f1c7ffd08c175f23e401deb817d262dcdfe0a0317ea99ffbdaefa"),
    "R1_OWN_CONTEXT_RIDGE": ("PLAYER-CONTEXT-MATCHUP-01-A-runtime-v3", "FORECAST_R1_OWN_CONTEXT_RIDGE.json.xz", 27896,
                             "3982c7368149ae0080b3975742a82fedec0fc93e490d10140f261a37b2e13b6f"),
    "P1_POOLED_RIDGE": ("PLAYER-CONTEXT-MATCHUP-01-A-runtime-v3", "FORECAST_P1_POOLED_RIDGE.json.xz", 27448,
                        "ef8968ea76d979290d882f2384bcca610949c1bd9e84b346d497f92713ea871d"),
    "R3_CONTEXT_INTERACTION_RIDGE": ("PLAYER-CONTEXT-MATCHUP-01-A-runtime-v3", "FORECAST_R3_CONTEXT_INTERACTION_RIDGE.json.xz", 27500,
                                     "9f63578b9b234e63df560f7aeddd93557f5d49d54f83c0dcf50081f2f8efe8f0"),
    "P2_PARTIAL_PLAYER_TEAM_RIDGE": ("PLAYER-CONTEXT-MATCHUP-01-A-completion-v4", "FORECAST_P2.json.xz", 27988,
                                     "bcc7989628f42f31f392db2c7f84adc6f090fb75f3c2d6d166c00c2adfb3b81b"),
    "P3_PLAYER_ONLY_8_WITH_P1_FALLBACK": ("PLAYER-CONTEXT-MATCHUP-01-A-completion-v4", "FORECAST_P3.json.xz", 24172,
                                         "d7fd0bfc2e5a960ff21ee9efc1e92eb984bf06806c4d7d4d6a5c64275e46e46a"),
    "scorecard": ("PLAYER-CONTEXT-MATCHUP-01-A-completion-v4", "GRADED_SCORECARD_V1.zip", 54469,
                  "d2c980a3bc87093ffa38246b70a4faf4c3493c31e85753f826ede05b79f56343"),
    "controls": ("ABC-PREDICTIVE-IMPROVEMENT-01-A-runtime-v2", "FAILED_PARTIALS_V2.zip", 4829248,
                 "91121673a47289098f764978fec2cba74b2d156299a1223ea21ce307da5bc208"),
    "structured": ("ABC-PREDICTIVE-IMPROVEMENT-01-A-runtime-v2", "POST_WAVE_A3_FORECASTS_V1.json.gz", 1289159,
                   "d4ea148b44c6005cd2cfbee59bd142fb257002a1bdcb22ecc33c2beb97cb6f0a"),
}
CDF_MEMBER = {"bytes": 495075, "sha256": "c90c0fbf3469d3884c1c0a105083e63aae117b5afeb80b9a4b94deb2916a6a4e"}


def enc(obj):
    return (json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def note(name, obj):
    with (OUT / name).open("xb") as stream:
        stream.write(enc(obj)); stream.flush(); os.fsync(stream.fileno())


def key(row):
    return tuple(row[k] for k in KEY)


def fail_timeout(*_):
    raise TimeoutError("registered verification runtime exhausted")


def run(protocol_sha):
    started, cpu = time.monotonic(), time.process_time()
    plan_raw = (OUT / "PROTOCOL_V1.json").read_bytes()
    if sha(plan_raw) != protocol_sha:
        raise ValueError("protocol digest mismatch")
    plan = json.loads(plan_raw)
    publication = json.loads((OUT / "PUBLICATION_V1.json").read_bytes())
    if publication.get("state") != "PUBLICATION_COMPLETE" or publication.get("protocol_sha256") != protocol_sha:
        raise ValueError("published exact protocol GO required")
    for path, digest in plan["code_bindings"].items():
        if sha((ROOT / path).read_bytes()) != digest:
            raise ValueError("bound verification implementation changed")
    if plan["resource_preservation"]["allocation_SHA256"] != ALLOCATION or plan["verification_fit"]["private_peak_bytes"] != 60000:
        raise ValueError("original allocation and finite verification envelope required")
    resource.setrlimit(resource.RLIMIT_CPU, (180, 190))
    resource.setrlimit(resource.RLIMIT_AS, (3 * 1024 ** 3,) * 2)
    signal.signal(signal.SIGALRM, fail_timeout); signal.alarm(300)
    signal.signal(signal.SIGXCPU, fail_timeout)
    for name in ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"]:
        os.environ[name] = "1"
    import numpy as np
    import pandas as pd
    import pyarrow as pa
    import joblib
    from sklearn.linear_model import Ridge
    from sklearn.preprocessing import StandardScaler
    from threadpoolctl import threadpool_limits
    # All own model classes/helpers must precede the frozen inherited loader.
    from nfl_lab import cdf_engine as cdf, abc_dynamic_carry_v1 as dynamic
    from nfl_lab import abc_player_rushing_context_v1 as context
    from nfl_lab import category_topfive_backfield_v1 as backfield
    from tools import abc_a_dynamic_carry_wave_v1 as base
    from tools import category_topfive_matched12_storage_v1 as storage
    pa.set_cpu_count(1); pa.set_io_thread_count(1); pa.set_memory_pool(pa.system_memory_pool())
    # Runtime-only thread limit; saved model recipe/state and arithmetic unchanged.
    cdf.threadpool_limits = lambda *args, **kwargs: threadpool_limits(limits=1)
    STATE["phase"] = "ORIGINAL_STORAGE_GATE"
    store, _ = storage.open_store(ROOT, allocation_sha256=ALLOCATION, root_go=storage.GO)
    STATE["store"] = store
    destination = store.forward_root / "research/PLAYER-CONTEXT-ACCEPTANCE-01-A-inference-v1"
    if destination.exists():
        raise ValueError("immutable verification root already exists")
    with store.transaction():
        store._refresh(); store._require(60000)
    store.register_root(destination)
    STATE["destination"] = destination
    note("INFERENCE_START_V1.json", {"UTC": now(), "protocol_sha256": protocol_sha,
         "selected_origin": "2026 annual P1_POOLED_RIDGE; cutoff 2026-09-01T00:00:00Z",
         "selection_before_new_scores": True, "private_reservation_bytes": 60000,
         "NFL_fits_budget": 1, "software_fit_budget": 2, "source_HTTP": 0})

    def read_ref(name):
        root_id, member, count, digest = REFS[name]
        path = store.forward_root / "research" / root_id / member
        store.validate_reference(path, digest)
        raw = path.read_bytes()
        if len(raw) != count or sha(raw) != digest:
            raise ValueError("immutable evidence mismatch: " + name)
        return raw

    def persist(name, raw):
        if sum(x["bytes"] for x in STATE["private_artifacts"]) + len(raw) > 60000:
            raise ValueError("finite private verification reservation exceeded")
        path = destination / name
        store.write_bytes(path, raw); store.validate_reference(path, sha(raw))
        ref = {"id": name, "bytes": len(raw), "sha256": sha(raw)}
        STATE["private_artifacts"].append(ref)
        return ref

    STATE["phase"] = "AUTHENTICATE_SAVED_MODELS"
    p1_raw = read_ref("p1_model")
    p1 = joblib.load(io.BytesIO(p1_raw))
    assert p1["point_contract"] == "nonnegative regression point; probability/median unsupported"
    with zipfile.ZipFile(io.BytesIO(read_ref("cdf_container"))) as archive:
        cdf_raw = archive.read("RETURNED_PENDING_MODEL.joblib")
        manifest = json.loads(archive.read("MEMBER_MANIFEST.json"))["RETURNED_PENDING_MODEL.joblib"]
    assert manifest == CDF_MEMBER and len(cdf_raw) == CDF_MEMBER["bytes"] and sha(cdf_raw) == CDF_MEMBER["sha256"]
    saved_cdf = joblib.load(io.BytesIO(cdf_raw))
    assert isinstance(saved_cdf, cdf.LeafCDFModel) and saved_cdf.audit["fit_state"] == "FITTED"
    saved_cdf.forest.n_jobs = 1  # Runtime concurrency only; fitted trees unchanged.
    # Authenticate archived scorecard members independently of the summary code.
    with zipfile.ZipFile(io.BytesIO(read_ref("scorecard"))) as archive:
        score_raw = archive.read("RELATIONAL_SCORECARD.json")
        sm = json.loads(archive.read("MEMBER_MANIFEST.json"))["RELATIONAL_SCORECARD.json"]
    assert sm == {"bytes": len(score_raw), "sha256": sha(score_raw)}
    scorecard = json.loads(score_raw)
    forecasts = []
    for arm in ["E1_OWN_CONTEXT", "R1_OWN_CONTEXT_RIDGE", "P1_POOLED_RIDGE",
                "R3_CONTEXT_INTERACTION_RIDGE", "P2_PARTIAL_PLAYER_TEAM_RIDGE", "P3_PLAYER_ONLY_8_WITH_P1_FALLBACK"]:
        retained = json.loads(lzma.decompress(read_ref(arm)))
        assert len(retained) == 1244 and {r["arm"] for r in retained} == {arm}
        forecasts.extend(retained)
    with zipfile.ZipFile(io.BytesIO(read_ref("controls"))) as archive:
        controls = json.loads(gzip.decompress(archive.read("FORECAST_PARTIALS.json.gz")))
    for original, arm in [("A1_BACKFIELD_CDF_ROLE_INPUTS", "E0_A1_UNCHANGED"),
                           ("A0_BACKFIELD_CDF", "S_DIRECT_BACKFIELD_UNCHANGED")]:
        forecasts.extend(dict(r, arm=arm) for r in controls if r["season"] == 2026 and r["arm"] == original)
    structured = json.loads(gzip.decompress(read_ref("structured")))["forecasts"]
    forecasts.extend(dict(r, arm="S_STRUCTURED_A3_UNCHANGED") for r in structured if r["season"] == 2026)
    by_arm = collections.defaultdict(dict)
    for row in forecasts:
        assert key(row) not in by_arm[row["arm"]]
        by_arm[row["arm"]][key(row)] = row
    assert len(by_arm) == 9 and all(len(rows) == 1244 for rows in by_arm.values())

    STATE["phase"] = "RECONSTRUCT_ORIGINAL_FIT_DESIGN"
    _, _, _, _, _, train, history, queries = base.inputs(pd)
    records = dynamic.compile_history(history)
    train, _, _ = dynamic.augment(train, records)
    query, _, _ = dynamic.augment(queries[2026], records)
    feature_frame = pd.read_parquet(io.BytesIO(read_ref("context")))
    assert not feature_frame.duplicated(KEY).any()
    for frame_id, frame in [("train", train), ("query", query)]:
        before = frame[KEY].reset_index(drop=True)
        joined = frame.merge(feature_frame, on=KEY, how="left", sort=False, validate="one_to_one", indicator=True)
        assert joined["_merge"].eq("both").all() and joined[KEY].reset_index(drop=True).equals(before)
        joined.drop(columns="_merge", inplace=True)
        if frame_id == "train": train = joined
        else: query = joined
    origin = pd.Timestamp("2026-09-01", tz="UTC")
    mask = train.season.lt(2026) & pd.to_datetime(train.outcome_available_utc, utc=True).lt(origin)
    eligible = train.loc[mask]
    modeled = eligible.loc[eligible.position.eq("RB") & eligible.participation_state.eq("played")
                           & cdf.valid_support(cdf.numeric(eligible, "rush_att"), "count")]
    assert pd.to_datetime(modeled.outcome_available_utc, utc=True).lt(origin).all()
    assert p1["onehot"] is None
    assert p1["design"].names == saved_cdf.category["panels"]["context"] + context.DEF
    design = cdf.FixedDesign.fit(modeled, p1["design"].names)
    scale = StandardScaler().fit(design.transform(modeled))
    x = scale.transform(design.transform(modeled)); xq = scale.transform(design.transform(query))
    y = cdf.numeric(modeled, "rush_att")
    # Reserve before fitting; retain returned state BEFORE comparative checks.
    with store.transaction(): store._refresh(); store._require(60000)
    STATE.update(phase="ONE_PINNED_RIDGE_FRESH_FIT", NFL_fit_attempts=1)
    with threadpool_limits(limits=1):
        fresh_model = Ridge(alpha=32., solver="lsqr", tol=1e-8, max_iter=2000).fit(x, y)
    STATE["NFL_fits_returned"] = 1
    fresh_object = {"design": design, "scale": scale, "onehot": None, "model": fresh_model,
                    "point_contract": p1["point_contract"]}
    STATE["pending_object"] = fresh_object
    stream = io.BytesIO(); joblib.dump(fresh_object, stream, compress=("xz", 3))
    STATE["pending_model"] = stream.getvalue()
    if STATE["pending_model"] == p1_raw:
        fresh_ref = {"state": "EXACT_BYTES_REUSE_ORIGINAL", "bytes": len(p1_raw), "sha256": sha(p1_raw)}
    else:
        fresh_ref = {"state": "RETURNED_UNIQUE_STATE_SAVED_READBACK", **persist("FRESH_P1_POOLED_RIDGE.joblib", STATE["pending_model"])}
    STATE.pop("pending_model"); STATE.pop("pending_object")
    note("FRESH_FIT_RETENTION_V1.json", {"UTC": now(), "fit_attempts": 1, "returned_fits": 1,
         "state_retained_before_comparative_checks": True, "artifact": fresh_ref})
    STATE["phase"] = "FRESH_FIT_PARITY_CHECKS"
    assert vars(design) == vars(p1["design"])
    scaler_max = {}
    for name in ["mean_", "scale_", "var_"]:
        a, b = getattr(scale, name), getattr(p1["scale"], name)
        np.testing.assert_allclose(a, b, rtol=0, atol=1e-12)
        scaler_max[name] = float(np.max(np.abs(a-b)))
    np.testing.assert_allclose(fresh_model.coef_, p1["model"].coef_, rtol=0, atol=1e-10)
    np.testing.assert_allclose(fresh_model.intercept_, p1["model"].intercept_, rtol=0, atol=1e-10)
    original_points = np.asarray([by_arm["P1_POOLED_RIDGE"][tuple(k)]["mean"] for k in query[KEY].itertuples(index=False, name=None)])
    predictions = np.maximum(0., fresh_model.predict(xq))
    restored = np.maximum(0., p1["model"].predict(p1["scale"].transform(p1["design"].transform(query))))
    np.testing.assert_allclose(predictions, original_points, rtol=0, atol=1e-10)
    np.testing.assert_allclose(restored, original_points, rtol=0, atol=1e-12)
    fit_receipt = {"state": "PASS", "origin": "2026 annual; prior-season RB played supported labels before September 1 UTC",
        "training_rows": len(modeled), "query_rows": len(query), "scaler_max_difference": scaler_max,
        "coefficient_max_difference": float(np.max(np.abs(fresh_model.coef_-p1["model"].coef_))),
        "intercept_difference": float(fresh_model.intercept_-p1["model"].intercept_),
        "forecast_max_difference": float(np.max(np.abs(predictions-original_points))),
        "saved_inference_max_difference": float(np.max(np.abs(restored-original_points))),
        "training_MSE": float(np.mean((fresh_model.predict(x)-y)**2)),
        "n_iter": np.asarray(fresh_model.n_iter_).tolist(), "fit_state": fresh_ref,
        "latest_training_label_availability_UTC": pd.to_datetime(modeled.outcome_available_utc, utc=True).max().isoformat(),
        "historical_source_tier": "CURRENT_VINTAGE_SEVEN_DAY_RECONSTRUCTION_EXPOSED_DEVELOPMENT",
        "median_probability": "UNSUPPORTED_POINT_ONLY; none invented"}

    STATE["phase"] = "SAVED_CDF_COMPLETE_INFERENCE_BOUNDARIES"

    def infer(model, frame, batch=128):
        point = np.full((len(frame), 3), np.nan); fallback = np.empty(len(frame), dtype=object)
        for ix, law, reasons in model.predict_batches(frame, batch_size=batch):
            assert law is not None
            point[ix, 0] = law.mean; point[ix, 1] = law.quantile(.5); point[ix, 2] = law.variance
            fallback[ix] = reasons
        return point, fallback

    baseline, fallback = infer(saved_cdf, query)
    frozen = by_arm["E1_OWN_CONTEXT"]
    frozen_values = np.asarray([[frozen[tuple(k)]["mean"], frozen[tuple(k)]["median"]]
                               for k in query[KEY].itertuples(index=False, name=None)])
    np.testing.assert_allclose(baseline[:, :2], frozen_values, rtol=0, atol=1e-12)
    assert all(str(fallback[i]) == (frozen[tuple(k)]["fallback"] or "")
               for i, k in enumerate(query[KEY].itertuples(index=False, name=None)))
    permutation = np.random.default_rng(20261110).permutation(len(query))
    shuffled, sf = infer(saved_cdf, query.iloc[permutation].reset_index(drop=True), 7)
    np.testing.assert_allclose(shuffled, baseline[permutation], rtol=0, atol=1e-12)
    np.testing.assert_array_equal(sf, fallback[permutation])
    sample_indices = sorted(set([0, len(query)-1] + [int(np.flatnonzero(fallback == value)[0]) for value in np.unique(fallback)]))
    sample = query.iloc[sample_indices].reset_index(drop=True)
    singles, sfb = infer(saved_cdf, sample, 1)
    np.testing.assert_allclose(singles, baseline[sample_indices], rtol=0, atol=1e-12)
    np.testing.assert_array_equal(sfb, fallback[sample_indices])
    serialization = io.BytesIO(); joblib.dump(saved_cdf, serialization, compress=("xz", 3))
    roundtrip = joblib.load(io.BytesIO(serialization.getvalue()))
    round_values, round_fb = infer(roundtrip, sample, 1)
    np.testing.assert_array_equal(round_values, singles); np.testing.assert_array_equal(round_fb, sfb)
    reordered, _ = infer(saved_cdf, sample[list(reversed(sample.columns))], 1)
    np.testing.assert_array_equal(reordered, singles)
    mutated = sample.copy(); mutated["rush_att"] = 999; mutated["participation_state"] = "DNP"
    changed_outcomes, _ = infer(saved_cdf, mutated, 1)
    np.testing.assert_array_equal(changed_outcomes, singles)
    unseen = sample.copy(); unseen["player_id"] = "SYNTHETIC_UNSEEN_ID_NOT_AN_NFL_ROW"
    unseen_values, _ = infer(saved_cdf, unseen, 1)
    np.testing.assert_array_equal(unseen_values, singles)
    boundary = sample.iloc[:1].copy()
    boundary["f_player_games_prior"] = 0
    cold_values, cold_fb = infer(saved_cdf, boundary, 1)
    assert cold_fb[0] == "cold_start_role_prior" and np.isfinite(cold_values).all()
    boundary["position"] = "UNSEEN_SYNTHETIC_ROLE"
    _, unknown_fb = infer(saved_cdf, boundary, 1)
    assert unknown_fb[0] == "global_prior_unknown_role"
    absent = sample.drop(columns=saved_cdf.design.names, errors="ignore")
    absent["f_player_games_prior"] = float("nan")
    absent_values, absent_fb = infer(saved_cdf, absent, 1)
    assert np.isfinite(absent_values).all() and all(str(f) for f in absent_fb)
    law_count, threshold_count, max_mass_error, median_tie_count = 0, 0, 0., 0
    for ix, law, _ in saved_cdf.predict_batches(query, batch_size=128):
        assert law.prior.support == "count"
        assert np.isfinite(law.weights).all() and (law.weights >= 0).all()
        assert np.isfinite(law.mean).all() and np.isfinite(law.variance).all()
        assert (law.support >= 0).all() and (law.support == np.floor(law.support)).all()
        np.testing.assert_allclose(law.weights.sum(axis=1), 1., rtol=0, atol=1e-12)
        previous = np.zeros(len(ix))
        for threshold in [-1, 0, 1, 2, 4, 8, 16, 32, 64, 256, 4096]:
            cumulative = law.cdf(threshold)
            assert np.isfinite(cumulative).all() and (cumulative >= previous-1e-12).all()
            assert (cumulative >= -1e-12).all() and (cumulative <= 1+1e-12).all()
            previous = cumulative
        np.testing.assert_array_equal(law.cdf(-1), np.zeros(len(ix)))
        # PMF sum on finite range plus exact declared upper tail; no truncation.
        total = sum(np.exp(law.logpmf(k)) for k in range(513)) + 1 - law.cdf(512)
        max_mass_error = max(max_mass_error, float(np.max(np.abs(total-1))))
        np.testing.assert_allclose(total, 1., rtol=0, atol=2e-12)
        median = law.quantile(.5)
        assert (median == np.floor(median)).all() and (median >= 0).all()
        assert (law.cdf(median) >= .5-1e-12).all() and (law.cdf(median-1) < .5+1e-12).all()
        for line in [-.5, 0., .5, 1., 1.5, 4., 4.5, 19.5, 32.5]:
            under = law.cdf(math.ceil(line)-1)
            over = 1-law.cdf(math.floor(line))
            push = 1-under-over
            assert (push >= -1e-12).all() and (under >= 0).all() and (over >= -1e-12).all()
            if line % 1 == .5:
                np.testing.assert_allclose(push, 0., rtol=0, atol=1e-12)
                ties = np.abs(over-under) <= 1e-12
                median_tie_count += int(ties.sum())
                assert ((median > line) == (over > under))[~ties].all()
            else:
                np.testing.assert_allclose(push, np.exp(law.logpmf(line)), rtol=0, atol=1e-12)
            threshold_count += len(ix)
        law_count += len(ix)
    cdf_receipt = {"state": "PASS", "restored_original_model_sha256": CDF_MEMBER["sha256"],
        "inference_rows": len(query), "saved_mean_median_max_difference": float(np.max(np.abs(baseline[:, :2]-frozen_values))),
        "single_batch_cases": len(sample), "shuffled_identity_rows": len(query), "serialization_roundtrip": "EXACT_PREDICTIONS",
        "feature_order": "NAMED_COLUMN_EXTRACTION_VERIFIED", "target_outcome_mutation": "UNCHANGED",
        "unseen_player": "POOLED_MODEL_ID_NOT_A_FEATURE; UNCHANGED", "cold_start": str(cold_fb[0]),
        "unknown_role": str(unknown_fb[0]), "missing_features": "FINITE_PRIOR_FALLBACK",
        "law_rows_checked": law_count, "exact_threshold_cases": threshold_count,
        "pmf_plus_exact_tail_max_error": max_mass_error, "half_line_50_50_ties": median_tie_count,
        "conditioning": "conditional_on_played; unknown future participation is not supplied",
        "fresh_CDF_fit": "UNKNOWN_RESOURCE_SCOPE: a mismatching ~500KB returned fit cannot be retained in the 60000B envelope"}

    STATE["phase"] = "INDEPENDENT_OFFERED_SUBSET_NUMERICAL_ARITHMETIC"
    labels = {tuple(k): a for k, a in zip(scorecard["numeric_keys"], scorecard["numeric_actuals"])}
    assert len(labels) == 1244
    full = {k: a["actual"] for k, a in labels.items() if a["actual"] is not None}
    assert len(full) == 586
    groups = scorecard["decision_groups"]
    primary = next(g for g in groups if g["arm"] == "P1_POOLED_RIDGE" and g["policy"] == "P1_OTHER_POINT")
    offered, decimal_checks = {}, 0
    for j, index in enumerate(primary["opportunities"]):
        event = scorecard["offer_universe"][index]
        if primary["status"][j] not in ["WIN", "LOSS"]:
            continue
        identity = key(event)
        assert identity not in offered and full[identity] == event["actual"]
        offered[identity] = event["actual"]
        actual, line = Decimal(str(event["actual"])), Decimal(str(event["line"]))
        side = primary["selected_side"][j]
        assert side in {"OVER", "UNDER"} and actual != line
        won = actual > line if side == "OVER" else actual < line
        assert ("WIN" if won else "LOSS") == primary["status"][j]
        decimal_checks += 1
    assert len(scorecard["offer_universe"]) == 239 and len(offered) == 231
    numeric = []
    for arm, rows in sorted(by_arm.items()):
        assert set(rows) == set(labels)
        for product in ["mean", "median"]:
            for population, actuals in [("FULL_SUPPORTED_NUMERIC", full), ("SAME_DECIDED_OFFERED_PLAYER_GAMES", offered)]:
                pairs = [(rows[k][product], actual) for k, actual in actuals.items() if rows[k].get(product) is not None]
                errors = np.asarray([p-a for p, a in pairs], dtype=float)
                displayed = "other_point" if product == "mean" and arm.startswith(("R1_", "R3_", "P1_", "P2_", "P3_")) else product
                numeric.append({"arm": arm, "product": displayed, "population": population,
                    "eligible_numeric_cases": len(actuals), "scored": len(errors),
                    "MAE": float(np.abs(errors).mean()) if len(errors) else None,
                    "MSE": float(np.mean(errors**2)) if len(errors) else None,
                    "RMSE": float(np.sqrt(np.mean(errors**2))) if len(errors) else None,
                    "bias": float(errors.mean()) if len(errors) else None,
                    "p95_absolute_error": float(np.quantile(np.abs(errors), .95)) if len(errors) else None,
                    "fallback_cases": sum(bool(rows[k].get("fallback")) for k in actuals if rows[k].get(product) is not None),
                    "null_reason": None if len(errors) else "UNSUPPORTED_POINT_PRODUCT"})
    note("OFFERED_SUBSET_NUMERICAL_V1.json", {"state": "COMPLETE_INDEPENDENT_ERRORS_NO_NEW_GRADE_VERSION",
        "outer_queries": 1244, "full_supported_numeric": 586, "primary_offers": 239,
        "same_decided_offer_player_games": 231, "unknown_participation_offers": 8,
        "decimal_existing_grade_checks": decimal_checks, "scores": numeric,
        "offer_source_timing": "TIMING_UNVERIFIED_ACTUAL_LINE_DIAGNOSTIC", "venue_settlement": "UNVERIFIED"})

    STATE["phase"] = "SEPARATE_SYNTHETIC_SOFTWARE_POSITIVE_CONTROLS"
    # Artificial rows contain no NFL observations or identities. No new law recipe.
    toy_x = np.linspace(-1, 1, 256).reshape(-1, 1)
    toy_y = 5 + 4*toy_x.ravel()
    toy_ridge = Ridge(alpha=.001, solver="lsqr", tol=1e-8, max_iter=2000).fit(toy_x, toy_y)
    STATE["software_fits"] += 1
    assert np.mean((toy_ridge.predict(toy_x)-toy_y)**2) < 1e-6
    toy = pd.DataFrame({"season": 2000, "week": 1, "game_id": ["SYNTHETIC"+str(i) for i in range(256)],
        "player_id": ["SYNTHETIC"+str(i) for i in range(256)], "position": "RB", "participation_state": "played",
        "f_signal": np.repeat([0., 1.], 128), "rush_att": np.repeat([0., 20.], 128), "f_player_games_prior": 1.})
    toy_category = {"state": "READY", "target": "rush_att", "support": "count", "modeled_roles": ["RB"],
                    "primary_roles": ["RB"], "panels": {"base": ["f_signal"], "context": ["f_signal"]}}
    tree_parameters = dict(cdf.TREE_PARAMETERS)
    cdf.TREE_PARAMETERS = dict(tree_parameters, n_jobs=1)
    try:
        toy_model = cdf.LeafCDFModel.fit(toy, toy_category, "context")
    finally:
        cdf.TREE_PARAMETERS = tree_parameters
    STATE["software_fits"] += 1
    toy_values, _ = infer(toy_model, toy)
    assert toy_values[:128, 0].mean() < 1 and toy_values[128:, 0].mean() > 19
    software = {"state": "PASS", "fits": 2, "NFL_observations": 0,
                "Ridge_signal_MSE": float(np.mean((toy_ridge.predict(toy_x)-toy_y)**2)),
                "CDF_signal_mean_separation": float(toy_values[128:, 0].mean()-toy_values[:128, 0].mean()),
                "meaning": "software can learn an intentionally strong eligible artificial signal; no football performance inference"}
    usage = store.verify_retained_checkpoint()
    note("INFERENCE_RECEIPT_V1.json", {"state": "COMPLETE_BOUNDED_VERIFICATION", "UTC": now(),
        "protocol_sha256": protocol_sha, "fresh_fit": fit_receipt, "saved_model_inference": cdf_receipt,
        "software_positive_control": software, "NFL_fit_attempts": STATE["NFL_fit_attempts"],
        "NFL_fits_returned": STATE["NFL_fits_returned"], "new_predictive_methods": 0,
        "new_football_opportunities": 0, "new_pregame_forecasts": 0, "production_writes": 0,
        "private_artifacts": STATE["private_artifacts"], "private_new_bytes": sum(r["bytes"] for r in STATE["private_artifacts"]),
        "resource_usage": {"CPU_seconds": time.process_time()-cpu, "wall_seconds": time.monotonic()-started,
            "RSS_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
            "wave_retained_headroom_bytes": usage["wave_retained_headroom_bytes"]},
        "limits": {"CDF_fresh_fit": "NOT_PERFORMED_RESOURCE_SCOPE", "full_source_semantics": "SEPARATE_INDEPENDENT_RAW_REVIEW",
            "authentic_historical_publication": "NOT_ESTABLISHED_CURRENT_VINTAGE_RECONSTRUCTION",
            "production_parity": "NOT_IN_SCOPE_NO_WEBSITE_AUTHORITY"}})
    signal.alarm(0)
    print(json.dumps({"state": "COMPLETE", "fresh_NFL_fits": 1, "software_fits": 2,
                      "saved_CDF_rows": len(query), "offered_decided_cases": len(offered),
                      "private_new_bytes": sum(r["bytes"] for r in STATE["private_artifacts"])}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol-sha256", required=True)
    arguments = parser.parse_args()
    try:
        run(arguments.protocol_sha256)
    except BaseException as error:
        # No private paths, NFL identities, raw rows, or tracebacks in public errors.
        failure = {k: v for k, v in STATE.items() if k not in ["store", "destination", "pending_object", "pending_model"]}
        failure.update(state="FAILED", error_type=type(error).__name__, UTC=now())
        try:
            if STATE.get("pending_object") and not STATE.get("pending_model"):
                import joblib
                stream = io.BytesIO(); joblib.dump(STATE["pending_object"], stream, compress=("xz", 3))
                STATE["pending_model"] = stream.getvalue()
            if STATE.get("pending_model"):
                raw = STATE["pending_model"]
                if len(raw)+sum(r["bytes"] for r in STATE["private_artifacts"]) > 60000:
                    raise ValueError("bounded returned-state reservation")
                path = STATE["destination"] / "FAILED_RETURNED_P1_MODEL.joblib"
                STATE["store"].write_bytes(path, raw); STATE["store"].validate_reference(path, sha(raw))
                failure["returned_state"] = {"bytes": len(raw), "sha256": sha(raw)}
        except BaseException as retention:
            failure["retention_error_type"] = type(retention).__name__
        note("INFERENCE_FAILURE_V1.json", failure)
        print(json.dumps({"state": "FAILED", "phase": STATE["phase"], "error_type": type(error).__name__}), flush=True)
        sys.exit(1)
