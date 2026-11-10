"""Saved reception points on the immutable A733 board; no model execution.

``prepare`` only restores retained bytes and inventories identities/contracts.
``score`` requires a hash-bound root registration. The retained result is a
small lossless view manifest over the original immutable inputs, not a second
copy of forecast vectors. Never use a mutable website line in this procedure.
"""
from __future__ import annotations

import argparse
import collections
from decimal import Decimal
import hashlib
import importlib
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
VERSION = "PLAYER-CONTEXT-COMPLETION-DECISION-01-A-reception-v1"
ALLOCATION = "f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26"
C_NAMESPACE = "PLAYER-CONTEXT-ACCEPTANCE-01-A-peer-overlap-v1"
C_SHA = "6b9839b644490121ee852d230560cf59c95439c09be1ffb1ee1f06a4dd6513bc"
PEER_PROTOCOL_SHA = "c5d48f0cc456f2f07556b54ab15ee173053e9145f07a3db16a5e29c7dad72e88"
A_SHA = "753970f359a5089286dde4c7ace6eeeb02c82b59eed07a50fd8ecc797eec8c33"
OFFER_SHA = "f224f17930e8da7ed5683808de3339d9656cc4b71edb0deefcfb9c48dfd82ffb"
LABEL_SHA = "61da98ad90542b07c6c6664b674086ba4f9474e597325aba62dec44bb2fa72f5"
A_MEMBER_SHA = "7d849d60902a2aa0a4922dd1ba0d09d4e0a21290cb5121e48279c6f54349e23f"
EVIDENCE = "CURRENT_VINTAGE_SEVEN_DAY_FOOTBALL_RECONSTRUCTION;QUOTE_TIMING_UNVERIFIED_ACTUAL_LINE_DIAGNOSTIC;EXPOSED_DEVELOPMENT"
A_PRODUCTS = [
    ("COUNT_A_LEGACY_POINT", "legacy_empirical_point"),
    ("COUNT_A_MEAN", "mean_objective_point"),
    ("HGB_MAE_DIRECT", "mae_objective_point"),
    ("CATBOOST_MEDIUM", "mean_objective_point"),
    ("LEAF_CDF", "mean"), ("LEAF_CDF", "median"),
    ("ORDERED_CDF", "mean"), ("ORDERED_CDF", "median"),
]
C_PRODUCTS = [(m, p) for m in ["P1", "P2"] for p in ["mean", "median"]]
C_IDS = ["C::PLAYER-CONTEXT-MATCHUP-01::v1.1::" + m + "::" + p for m, p in C_PRODUCTS]
A_IDS = ["A::" + m + "::" + p for m, p in A_PRODUCTS]
CONSTANT_IDS = ["ALWAYS_OVER", "ALWAYS_UNDER"]
CANDIDATE_IDS = A_IDS + C_IDS + CONSTANT_IDS


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def checked(value, message):
    if not value:
        raise ValueError(message)


def finite(value):
    return type(value) in [int, float] and math.isfinite(value)


def side(point, line):
    if not finite(point):
        return None
    p, q = Decimal(str(point)), Decimal(str(line))
    return "OVER" if p > q else "UNDER" if p < q else "ABSTAIN"


def grade(row):
    if row["selected_side"] is None:
        return "UNAVAILABLE_FORECAST"
    if row["selected_side"] == "ABSTAIN":
        return "ABSTAIN"
    if row["appearance"] != "PLAYED":
        return {"DNP": "DNP", "PENDING": "PENDING"}.get(row["appearance"], "UNKNOWN_PARTICIPATION")
    if row["actual"] is None:
        return "MISSING_ACTUAL"
    actual, line = Decimal(str(row["actual"])), Decimal(str(row["line"]))
    if actual == line:
        return "PUSH"
    return "WIN" if ((actual > line) == (row["selected_side"] == "OVER")) else "LOSS"


def read_ref(ref):
    raw = Path(ref["path"]).read_bytes()
    checked(len(raw) == ref["bytes"] and sha(raw) == ref["sha256"], "saved source bytes changed")
    return raw


def runtime():
    for name in ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"]:
        os.environ[name] = "1"
    import numpy as np
    import pandas as pd
    import pyarrow as pa
    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)
    pa.set_memory_pool(pa.system_memory_pool())
    return np, pd


def restore(pd):
    """Approved read-only attachments and retained-byte joins; no grading."""
    from tools import abc_a_dynamic_carry_wave_v1 as base
    from tools import category_topfive_matched12_storage_v1 as storage
    store, _ = storage.open_store(ROOT, allocation_sha256=ALLOCATION, root_go=storage.GO, readonly=True)
    _, _, g, _ = base.sources()
    refs = {k: dict(g[k]) for k in ["frozen_bundle", "offers", "qualified_labels"]}
    for name, expected in [("frozen_bundle", A_SHA), ("offers", OFFER_SHA), ("qualified_labels", LABEL_SHA)]:
        checked(refs[name]["sha256"] == expected, "frozen source selector changed")
    with zipfile.ZipFile(io.BytesIO(read_ref(refs["frozen_bundle"]))) as archive:
        raw = archive.read("FORECASTS.parquet")
        checked(sha(raw) == A_MEMBER_SHA, "frozen forecast member changed")
        forecasts = pd.read_parquet(io.BytesIO(raw))
        catalog = json.loads(archive.read("CATALOG_SCOPE.json"))
        member_manifest = json.loads(archive.read("MEMBER_MANIFEST.json"))
        checked(sha(raw) == member_manifest["FORECASTS.parquet"]["sha256"], "forecast member manifest mismatch")
    cpath = store.forward_root / "research" / C_NAMESPACE / "RELATIONAL_SCORECARD.json.xz"
    cbytes = cpath.read_bytes()
    checked(len(cbytes) == 50704 and sha(cbytes) == C_SHA, "retained C733 scorecard changed")
    refs["C_relational"] = {"path": str(cpath), "bytes": len(cbytes), "sha256": C_SHA}
    c = json.loads(lzma.decompress(cbytes))
    cm = c["manifest"]
    checked(cm["A_offers_sha256"] == OFFER_SHA and cm["A_outcomes_sha256"] == LABEL_SHA,
            "C board points to a different A source version")
    checked(cm["products"] == [list(x) for x in C_PRODUCTS], "C product order changed")
    rows = [dict(zip(cm["row_columns"], r)) for r in c["rows"]]
    checked(len(rows) == 733 and len({r["opportunity"] for r in rows}) == 733, "C733 board identity changed")
    with zipfile.ZipFile(io.BytesIO(read_ref(refs["offers"]))) as archive:
        offers = pd.read_parquet(io.BytesIO(archive.read(refs["offers"]["member"])))
    offers = offers.loc[offers.target.eq("rec") & offers.season.eq(2026) & offers.week.between(1, 7)]
    excluded = offers.loc[~offers.position.isin(["WR", "TE"])].groupby(["week", "position"]).size()
    offers = offers.loc[offers.position.isin(["WR", "TE"])].copy()
    checked(not offers.duplicated(["season", "game_id", "player_id"]).any(), "ambiguous A primary offer")
    om = {str(r.opportunity_key): r for r in offers.itertuples()}
    checked(set(om) == {r["opportunity"] for r in rows}, "C733 is not the exact A primary board")
    with zipfile.ZipFile(io.BytesIO(read_ref(refs["qualified_labels"]))) as archive:
        labels = pd.read_parquet(io.BytesIO(archive.read(refs["qualified_labels"]["member"])))
    labels = labels.loc[labels.target.eq("rec") & labels.season.eq(2026) & labels.week.between(1, 7)]
    checked(not labels.duplicated(["season", "game_id", "player_id"]).any(), "ambiguous retained outcome")
    lm = {(str(r.game_id), str(r.player_id)): r for r in labels.itertuples()}
    for r in rows:
        o = om[r["opportunity"]]
        checked((str(o.game_id), str(o.player_id), int(o.week), str(o.line), str(o.source_stream), str(o.source_sha256)) ==
                (r["game"], r["player"], r["week"], r["original_line_exact_text"], r["source_panel"], r["source_sha256"]),
                "retained original offer binding changed")
        r["position"] = str(o.position)
        label = lm.get((r["game"], r["player"]))
        state = getattr(label, "participation_state", None)
        appearance = "PENDING" if getattr(label, "outcome_state", None) == "pending" else "DNP" if str(state).lower() == "dnp" else "PLAYED" if state == "played" else "UNKNOWN"
        val = getattr(label, "actual", None)
        actual = float(val) if appearance == "PLAYED" and finite(val) and val >= 0 and val % 1 == 0 else None
        checked((appearance, actual) == (r["appearance"], r["actual"]), "known retained outcome conflict; halt before scoring")
        if actual is not None:
            checked(getattr(label, "label_reason", None) in ["EXPLICIT_REPORTED_ZERO", "EXPLICIT_REPORTED_VALUE"] and
                    isinstance(getattr(label, "participation_evidence", None), str) and bool(label.participation_evidence),
                    "outcome lacks explicit metric/participation evidence")
    forecasts = forecasts.loc[forecasts.target.eq("rec") & forecasts.season.eq(2026) & forecasts.week.between(1, 7)].copy()
    checked(not forecasts.duplicated(["method", "product", "season", "game_id", "player_id"]).any(), "ambiguous retained forecast")
    fixed = {r["opportunity"] for r in rows if r["statistical_grades"][1] in ["WIN", "LOSS"]}
    checked(len(fixed) == 667, "immutable C P1 median mask changed")
    return store, refs, rows, forecasts, catalog, fixed, [dict(week=int(k[0]), position=str(k[1]), rows=int(v)) for k, v in excluded.items()]


def inventory(refs, board, forecasts, catalog, fixed, excluded):
    provenance = {}
    for cid, (method, product) in zip(A_IDS, A_PRODUCTS):
        f = forecasts.loc[forecasts.method.eq(method) & forecasts["product"].eq(product)]
        fm = {(str(r.game_id), str(r.player_id)): r for r in f.itertuples()}
        matched = [r for r in board if (r["game"], r["player"]) in fm]
        fields = ["output_procedure_version", "source_forecast_sha256", "source_forecast_member_sha256", "source_information_policy", "source_issue_time_UTC"]
        provenance[cid] = dict(method=method, product=product, saved_rows=len(f), board_matched=len(matched),
            fixed667_matched=sum(r["opportunity"] in fixed for r in matched),
            source_versions=f[fields].drop_duplicates().where(f[fields].drop_duplicates().notna(), None).to_dict("records"),
            catalog=catalog["catalog"]["rec"][method])
    history = {
        "LEAF_CDF_and_COUNT_A": "Retained annual fixed2019-2025 relationship; fit cutoff2026-09-01; declared seven-day source reconstruction; prior target-week histories update inputs. COUNT_A legacy mixed empirical point and intended conditional mean remain separate.",
        "ORDERED_CDF": "Retained unchanged annual count-law learner with ordered rec/target lags and explicit played/DNP/unknown slots; same strict earlier kickoff and seven-day availability projection. Saved mean and lower median only; no new inference.",
        "HGB_MAE_DIRECT": "Retained accepted2019-2025 REG-source annual fitted MAE-objective direct point; maximum training availability2026-01-12; no invented count distribution.",
        "CATBOOST_MEDIUM": "Retained fixed13 accepted2019-2025 REG-source annual Cat count-objective point; mean_objective_point is its saved product name, not a saved PMF.",
        "C_P1_P2": "Retained Poisson points from current/revised ordinary facts and reconstructed kickoff+7day history availability; season2022+ earlier history; C query membership requires target-game source-row existence/role, not a qualified pregame roster. P1/P2 conditional mean and lower median of same law remain separate.",
        "B": "No approved B reception forecast-vector export identified in the supplied exact B export index; no aggregate reconstruction.",
    }
    metadata_paths = ["config/category-topfive-matched12-inference-v1.json",
        "config/category-topfive-matched12-inference-followup-v1.json.gz",
        "config/category-topfive-matched12-all-finalists-freeze-v1_2.json.gz",
        "reports/category-topfive-matched-all12-w1w7-20261030/fitting/ACTUAL_HGB_V1_1.json",
        "reports/category-topfive-matched-all12-w1w7-20261030/fitting/FIXED13_SOURCE_V1.py.gz",
        "reports/abc-championship/player-context-acceptance-01/C_QUERY_POPULATION_SCOPE_V1.json"]
    metadata = {p: dict(bytes=len((ROOT / p).read_bytes()), sha256=sha((ROOT / p).read_bytes())) for p in metadata_paths}
    return dict(version=VERSION, state="PREPARED_READ_ONLY_NO_NEW_SCORES", candidate_ids=CANDIDATE_IDS,
        sources=refs, A_forecast_member=dict(member="FORECASTS.parquet", sha256=A_MEMBER_SHA),
        source_scope=catalog["scope"], A_provenance=provenance,
        source_history_contracts=history, source_history_metadata=metadata,
        fixed667_mask_sha256=sha(encode(sorted(fixed))), outer733_mask_sha256=sha(encode(sorted(r["opportunity"] for r in board))),
        outer733=733, fixed667=667, excluded_outside_WRTE=excluded,
        C_original_W2_W3="SEPARATE_UNCHANGED_NOT_PART_OF_THIS_NEW_PANEL",
        excluded_candidates={"B": "NO_APPROVED_RECEPTION_VECTOR_EXPORT_IN_INSPECTED_B_EXPORT_INDEX", "RESPONSE_CDF_rec": "NOT_IN_RETAINED_REC_CATALOG", "new_labels_seeds": "NO_NEW_SELECTION_OR_FITS"},
        new_fits=0, new_inference=0, new_scores=0, private_writes=0)


def numerical(rows):
    err = [r["point"] - r["actual"] for r in rows if finite(r["point"]) and r["actual"] is not None]
    return dict(scored=len(err), MAE=math.fsum(map(abs, err)) / len(err) if err else None,
                MSE=math.fsum(x*x for x in err) / len(err) if err else None,
                bias=math.fsum(err) / len(err) if err else None)


def bootstrap(groups, np, reps, seed):
    if len(groups) < 2:
        return None
    values = np.asarray([groups[k] for k in sorted(groups)], dtype=float)
    rng = np.random.default_rng(seed)
    results = []
    for _ in range(reps):
        x = values[rng.integers(0, len(values), len(values))]
        results.append(float(x[:, 0].sum() / x[:, 1].sum()))
    return [float(x) for x in np.quantile(results, [.025, .975])]


def paired(left, right, np, reps, seed):
    rm = {r["opportunity_key"]: r for r in right}
    pairs = [(a, rm[a["opportunity_key"]]) for a in left if a["opportunity_key"] in rm]
    decided = [(a, b) for a, b in pairs if a["status"] in ["WIN", "LOSS"] and b["status"] in ["WIN", "LOSS"]]
    games = collections.defaultdict(lambda: [0., 0.])
    for a, b in decided:
        games[a["game_id"]][0] += int(a["status"] == "WIN") - int(b["status"] == "WIN")
        games[a["game_id"]][1] += 1
    return dict(common_decided=len(decided), left_wins=sum(a["status"] == "WIN" for a, b in decided),
        right_wins=sum(b["status"] == "WIN" for a, b in decided),
        win_change=sum(int(a["status"] == "WIN") - int(b["status"] == "WIN") for a, b in decided),
        side_disagreements=sum(a["selected_side"] != b["selected_side"] for a, b in decided),
        game_clusters=len(games), week_clusters=len({a["week"] for a, b in decided}),
        common_mask_sha256=sha(encode(sorted(a["opportunity_key"] for a, b in decided))),
        paired_accuracy_change_interval95=bootstrap(games, np, reps, seed))


def score(plan, protocol_sha, prep, board, forecasts, fixed, np, common):
    vectors = {}
    for cid, (method, product) in zip(A_IDS, A_PRODUCTS):
        f = forecasts.loc[forecasts.method.eq(method) & forecasts["product"].eq(product)]
        vectors[cid] = {(str(r.game_id), str(r.player_id)): r for r in f.itertuples()}
    scored = {cid: [] for cid in CANDIDATE_IDS}
    for b in board:
        for cid in CANDIDATE_IDS:
            fallback = None
            why = None
            if cid in A_IDS:
                f = vectors[cid].get((b["game"], b["player"]))
                point = float(f.prediction) if f is not None and finite(f.prediction) else None
                if f is not None and str(f.position) != b["position"]:
                    point, why = None, "POSITION_CONTRACT_MISMATCH"
                elif point is None:
                    why = "MISSING_RETAINED_A_POINT"
                fallback = str(f.fallback) or None if f is not None else None
                selected = side(point, b["original_line_exact_text"])
            elif cid in C_IDS:
                j = C_IDS.index(cid)
                point, fallback, why = b["points"][j], b["fallbacks"][j], b["unavailability_reasons"][j]
                selected = side(point, b["original_line_exact_text"])
            else:
                point, selected = None, cid.removeprefix("ALWAYS_")
            row = dict(season=2026, week=b["week"], game_id=b["game"], player_id=b["player"], category="rec",
                line=float(b["original_line_exact_text"]), actual=b["actual"], appearance=b["appearance"],
                opportunity_key=b["opportunity"], source_panel=b["source_panel"], selected_side=selected,
                point=point, fallback=fallback, unavailability_reason=why, comparator="STRICT_OVER_UNDER")
            row["status"] = grade(row)
            checked(common.status(row) == row["status"], "accepted and independent graders disagree")
            if cid in C_IDS:
                checked((selected, row["status"]) == (b["selected_sides"][C_IDS.index(cid)], b["statistical_grades"][C_IDS.index(cid)]), "retained C decision replay changed")
            scored[cid].append(row)
    summaries, pairs = [], []
    for view in ["FULL_A733", "FIXED_C667"]:
        mask = {r["opportunity"] for r in board} if view == "FULL_A733" else fixed
        viewrows = {cid: [r for r in rr if r["opportunity_key"] in mask] for cid, rr in scored.items()}
        for cid, rr in viewrows.items():
            for panel in ["ALL"] + sorted({r["source_panel"] for r in rr}):
                for week in ["ALL"] + list(range(1, 8)):
                    part = [r for r in rr if (panel == "ALL" or r["source_panel"] == panel) and (week == "ALL" or r["week"] == week)]
                    summaries.append(dict(candidate_id=cid, view=view, source_panel=panel, week_view=week,
                        **common.summary(part), numerical=numerical(part),
                        actual_scored_weeks=sorted({r["week"] for r in part if r["status"] in ["WIN", "LOSS", "PUSH"]}),
                        outer_appearance_states=dict(collections.Counter(r["appearance"] for r in part)),
                        unavailable_reasons=dict(collections.Counter(r["unavailability_reason"] for r in part if r["unavailability_reason"])),
                        fallback_outputs=sum(r["fallback"] not in [None, False, ""] for r in part)))
        # Every learned product compared against both constants and retained C
        # P1median; finite preregistered comparisons, no selection after scoring.
        for left, right in plan["paired_candidate_ids"]:
            pairs.append(dict(view=view, left=left, right=right,
                **paired(viewrows[left], viewrows[right], np, plan["bootstrap_replicates"], plan["bootstrap_seed"])))
    view = dict(version=VERSION, protocol_sha256=protocol_sha, source_refs=prep["sources"],
        A_member=prep["A_forecast_member"], C_relational_columns="ORIGINAL_PINNED_MANIFEST_ROW_COLUMNS",
        candidate_ids=CANDIDATE_IDS, A_products=A_PRODUCTS, C_products=C_PRODUCTS,
        board_selector="Original C733 retained row order; exact A WRTE rec2026W1-7 PRIMARY_FULL identities/lines/qualified outcomes checked byte-for-byte; no changed offer selection",
        fixed667_selector="C original P1median retained statistical_grades in WIN/LOSS; never changed to candidate availability",
        fixed667_mask_sha256=prep["fixed667_mask_sha256"], outer733_mask_sha256=prep["outer733_mask_sha256"],
        decision_rule="Decimal(str(original saved point)) versus Decimal(original retained line text); exact tie ABSTAIN; grade() plus pinned Cstatus",
        source_history_output_contracts=prep["A_provenance"],
        source_history_contracts=prep["source_history_contracts"], source_history_metadata=prep["source_history_metadata"], evidence=EVIDENCE,
        original_C_W2_W3_separate=True, no_original_issuance_claim=True,
        lossless_reconstruction="Hash-verified original vectors+offers+outcomes+C733 relations and this code regenerate every point/side/grade without model loading or vector duplication",
        new_fits=0, new_inference=0, new_sources=0)
    public = dict(version=VERSION, state="SAVED_POINT_REPLAY_COMPLETE", protocol_sha256=protocol_sha,
        source_sha256={k: v["sha256"] for k, v in prep["sources"].items()}, candidate_ids=CANDIDATE_IDS,
        full_outer_offers=733, fixed_mask_offers=667, fixed667_mask_sha256=prep["fixed667_mask_sha256"],
        outer733_mask_sha256=prep["outer733_mask_sha256"], summaries=summaries, paired=pairs,
        evidence=EVIDENCE, excluded_candidates=prep["excluded_candidates"], excluded_outside_WRTE=prep["excluded_outside_WRTE"],
        uncertainty="New paired intervals: nominal500-draw game bootstrap. Inherited pinned C summaries:2000-draw week bootstrap when at least five weeks, Wilson below. Seven exposed week clusters, multiplicity unadjusted; conditional on saved-source coverage/qualified outcomes, no prospective claim.",
        new_fits=0, new_inference=0, new_source_requests=0, production_writes=0)
    return view, public


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["prepare", "score"], required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--protocol", type=Path)
    ap.add_argument("--protocol-sha256")
    ap.add_argument("--c-code-cache", type=Path, default=Path("/tmp/acceptance-c-review/src"))
    args = ap.parse_args()
    start, cpu = time.monotonic(), time.process_time()
    caps = {"CPU_seconds": 250, "wall_seconds": 600, "RSS_bytes": 3*1024**3}
    plan = None
    if args.mode == "score":
        checked(args.protocol is not None and args.protocol_sha256 is not None, "published root protocol required")
        raw = args.protocol.read_bytes()
        checked(sha(raw) == args.protocol_sha256, "root protocol hash changed")
        plan = json.loads(raw)
        checked(plan["state"] == "ROOT_REGISTERED_EXECUTION_GO" and plan["registered_by"] == "/root", "root execution GO required")
        checked(plan["version"] == VERSION and plan["candidate_ids"] == CANDIDATE_IDS, "finite candidate registration changed")
        checked(plan["code_sha256"][str(Path(__file__).relative_to(ROOT))] == sha(Path(__file__).read_bytes()), "worker code not registration bound")
        for path, digest in plan["code_sha256"].items():
            checked(sha((ROOT / path).read_bytes()) == digest, "bound code changed")
        caps = plan["resources"]
        checked(caps["CPU_seconds"] <= 250 and caps["wall_seconds"] <= 600 and caps["RSS_bytes"] <= 3*1024**3, "finite resource cap exceeded")
        checked(0 < caps["private_peak_bytes"] <= 23793, "registered private budget exceeds known headroom")
        checked(0 < plan["bootstrap_replicates"] <= 500 and plan["bootstrap_seed"] == 20261110, "finite bootstrap registration required")
        checked(len(plan["paired_candidate_ids"]) <= 60 and all(a in CANDIDATE_IDS and b in CANDIDATE_IDS for a, b in plan["paired_candidate_ids"]), "finite paired comparisons required")
    resource.setrlimit(resource.RLIMIT_CPU, (caps["CPU_seconds"], caps["CPU_seconds"]+1))
    resource.setrlimit(resource.RLIMIT_AS, (caps["RSS_bytes"],)*2)
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError("registered wall cap")))
    signal.alarm(caps["wall_seconds"])
    def offline(event, _args):
        if event in {"socket.connect", "socket.connect_ex", "socket.getaddrinfo"}:
            raise RuntimeError("retained byte replay is offline")
    sys.addaudithook(offline)
    np, pd = runtime()
    _, refs, board, forecasts, catalog, fixed, excluded = restore(pd)
    prep = inventory(refs, board, forecasts, catalog, fixed, excluded)
    if args.mode == "prepare":
        prep["actual"] = dict(CPU_seconds=time.process_time()-cpu, wall_seconds=time.monotonic()-start,
                              RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
        with args.output.open("xb") as handle:
            handle.write(encode(prep))
        print(json.dumps(dict(state=prep["state"], output=str(args.output), candidate_ids=CANDIDATE_IDS, new_scores=0, private_writes=0)))
        return
    checked(plan["source_sha256"] == {k: v["sha256"] for k, v in refs.items()}, "registered retained sources changed")
    checked(plan["fixed667_mask_sha256"] == prep["fixed667_mask_sha256"] and plan["outer733_mask_sha256"] == prep["outer733_mask_sha256"], "registered masks changed")
    peer_bytes = (ROOT / "reports/abc-championship/player-context-acceptance-01/PEER_PROTOCOL_V2.json").read_bytes()
    checked(sha(peer_bytes) == PEER_PROTOCOL_SHA, "accepted peer protocol changed")
    peer = json.loads(peer_bytes)
    for ref in peer["peer_overlap"]["C_bound_code"]:
        checked(sha((args.c_code_cache / Path(ref["path"]).name).read_bytes()) == ref.get("sha256", ref.get("SHA256")), "accepted C scorer code changed")
    sys.path.insert(0, str(args.c_code_cache))
    common = importlib.import_module("abc_championship_v2")
    view, public = score(plan, args.protocol_sha256, prep, board, forecasts, fixed, np, common)
    payload = lzma.compress(encode(view), preset=9)
    checked(len(payload) <= min(8192,caps["private_peak_bytes"]), "view exceeds registered payload cap; no write performed")
    from tools import category_topfive_matched12_storage_v1 as storage
    store, _ = storage.open_store(ROOT, allocation_sha256=ALLOCATION, root_go=storage.GO)
    dest = store.forward_root / "research" / VERSION
    checked(not dest.exists(), "immutable completion result already exists")
    with store.transaction():
        store._refresh()
        baseline = store._scan()["new_peer_physical_bytes"]
        store._require(caps["private_peak_bytes"])
        store.register_root(dest)
        registered = store._scan()["new_peer_physical_bytes"]
        checked(registered-baseline+len(payload) <= caps["private_peak_bytes"], "namespace/control growth exceeds private envelope")
        path = dest / "LOSSLESS_VIEW_MANIFEST.json.xz"
        store.write_bytes(path, payload)
        store.validate_reference(path, sha(payload))
        usage = store.verify_retained_checkpoint()
        retained_growth = usage["new_peer_physical_bytes"]-baseline
        checked(retained_growth <= caps["private_peak_bytes"], "all-in retained growth exceeds private envelope")
    public["private_view"] = dict(artifact_id=VERSION + "::LOSSLESS_VIEW_MANIFEST", bytes=len(payload), sha256=sha(payload), readback="PASS", all_in_retained_growth=retained_growth, all_in_private_peak_budget=caps["private_peak_bytes"], old96MiB_checkpoint="PASS")
    public["actual"] = dict(CPU_seconds=time.process_time()-cpu, wall_seconds=time.monotonic()-start,
                            RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
    with args.output.open("xb") as handle:
        handle.write(encode(public))
        handle.flush()
        os.fsync(handle.fileno())
    signal.alarm(0)
    print(json.dumps(dict(state=public["state"], output=str(args.output), private_bytes=len(payload), new_fits=0, new_inference=0)))


if __name__ == "__main__":
    main()
