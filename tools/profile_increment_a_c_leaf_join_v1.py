"""A owner-local replay of C's retained Leaf points on the frozen rec board.

No fitting, model decoding, predictive inference or collection. Preparation
inventories exact identities and clocks only; scoring requires published root GO.
Public numerical C bytes remain durably recoverable in their original GitHub
commit. The private result is a lossless view over retained immutable evidence.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import datetime
import gzip
import hashlib
import importlib
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
import io

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
VERSION = "PROFILE-INCREMENT-TO-RELEASE-01-A-C-LEAF-JOIN-v1"
C_REF = "06da9bb77c6122d870e18067c8dbdf34813fc4cb"
C_PATH = "reports/player-context-matchup-01/completion-decision-v1/intake/C_RETAINED_LEAF_POINTS_W1_W7.json.gz"
C_SHA = "05a6b8bbad28ce7978c59f1ae026d6fb61fed964db724f41be253e4606119ccc"
C_BYTES = 45935
PREVIOUS_SHA = "b2554448d8d70ee56e3a95b326f92c0344531cc7333a00d4db40cc16545ae119"
PREFIX = "C::C-ALL12-LAW-THRESHOLD-v2.1::rec::H-MULTI::P2_LEAF::E0_OP::"
NEW = [PREFIX + "MEAN_POINT_DIRECTION", PREFIX + "MEDIAN_POINT_DIRECTION"]
OUT = ROOT / "reports/abc-championship/profile-increment-to-release-01/A"
STATE = {"phase": "NOT_STARTED"}


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def check(value, message):
    if not value:
        raise ValueError(message)


def finite(value):
    return type(value) in [int, float] and math.isfinite(value)


def team(value):
    return {"LA": "LAR", "WSH": "WAS", "STL": "LAR", "SD": "LAC", "OAK": "LV"}.get(str(value), str(value))


def aware(value, pd):
    if value is None:
        return None
    stamp = pd.Timestamp(value)
    return None if pd.isna(stamp) or stamp.tzinfo is None else stamp.tz_convert("UTC")


def load_source(path):
    body = path.read_bytes()
    check(len(body) == C_BYTES and sha(body) == C_SHA, "exact public C Leaf export required")
    value = json.loads(gzip.decompress(body))
    check(value["schema"] == "C-RETAINED-LEAF-POINTS-v1" and value["category"] == "rec", "C source schema/target changed")
    check(value["source_archive_SHA256"] == "5262b7bb374c066adf14bfd10e6992a2568eff84943ea11b96218084be4d1f51", "C archive binding changed")
    check(value["source_pin"] == "dbf3170ee1fdce091b7f4de09c780ca2df65ad7e", "C origin source pin changed")
    check(value["actuals_and_offers_excluded"] is True and value["new_fits"] == value["new_inference"] == 0
          and value["unsafe_models_loaded"] is False, "cached-output export contract changed")
    check(["C::" + value["procedures"][p] for p in ["mean", "median"]] == NEW, "exact namespaced C procedures changed")
    return value


def join_inventory(source, board, offers, pd):
    """No side calculation or target-error score occurs in this function."""
    rows = source["rows"]
    check(len(rows) == 2152 and sum(r["position"] in ["WR", "TE"] for r in rows) == 1547, "C export outer population differs")
    lookup = {}
    for r in rows:
        k = (str(r["game_id"]), str(r["player_id"]))
        check(k not in lookup, "ambiguous C canonical player/event")
        check(r["position"] in ["RB", "WR", "TE"] and r["week"] in range(1, 8), "C role/week outside source contract")
        check(finite(r["mean"]) and r["mean"] >= 0 and finite(r["median"]) and r["median"] >= 0
              and r["median"] == math.floor(r["median"]), "retained count point typing invalid")
        check(type(r["fallback"]) is bool, "fallback contract must stay explicit")
        lookup[k] = r
    slots = {}
    for row in source["slots"]:
        suffix = row["slot"].rsplit("-W", 1)
        check(len(suffix) == 2 and suffix[1].isdigit(), "C slot missing exact week binding")
        week = int(suffix[1])
        check(week not in slots, "multiple C slot versions for one week")
        slots[week] = row
        for name in ["model_sha256", "row_sha256", "training_membership_sha256"]:
            check(isinstance(row[name], str) and len(row[name]) == 64, "C exact slot hash missing")
    check(sorted(slots) == list(range(1, 8)), "C weekly model-slot roster differs")
    om = {str(o.opportunity_key): o for o in offers.itertuples()}
    joined, reasons, weekly = {}, Counter(), defaultdict(Counter)
    for b in board:
        o = om[b["opportunity"]]
        f = lookup.get((b["game"], b["player"]))
        reason = None
        g = source["games"].get(b["game"])
        slot = slots[b["week"]]
        if f is None:
            reason = "NO_RETAINED_C_LEAF_POINT"
        elif f["position"] != b["position"]:
            reason = "EXACT_ROLE_MISMATCH"
        elif int(f["week"]) != b["week"] or g is None or int(g["week"]) != b["week"]:
            reason = "EXACT_GAME_WEEK_MISMATCH"
        elif team(f["team"]) != team(o.team) or team(f["opponent"]) != team(o.opponent):
            reason = "EXACT_HISTORICAL_TEAM_OPPONENT_MISMATCH"
        else:
            kickoff, cutoff = aware(o.kickoff_utc, pd), aware(o.cutoff_utc, pd)
            cg, cc, origin = aware(g["kickoff_UTC"], pd), aware(g["as_of_UTC"], pd), aware(slot["origin_UTC"], pd)
            last = slot.get("latest_training_available")
            train = pd.to_datetime(last, unit="s", utc=True) if finite(last) else None
            if any(x is None for x in [kickoff, cutoff, cg, cc, origin, train]):
                reason = "UNQUALIFIED_C_OR_A_CLOCK"
            elif not (kickoff == cg and cutoff == cc and origin <= cc and train < origin):
                reason = "INCOMPATIBLE_INFORMATION_HORIZON_OR_TRAINING_ORIGIN"
        if reason:
            reasons[reason] += 1
            weekly[b["week"]][reason] += 1
        else:
            weekly[b["week"]]["SUPPORTED_CACHED_POINT"] += 1
        joined[b["opportunity"]] = dict(forecast=f if reason is None else None, unavailable_reason=reason)
    return joined, dict(reasons), [{"week": w, "states": dict(n)} for w, n in sorted(weekly.items())]


def source_inputs(pd):
    from tools import player_context_completion_reception_v1 as base
    store, refs, board, forecasts, catalog, fixed, excluded = base.restore(pd)
    with zipfile.ZipFile(io.BytesIO(base.read_ref(refs["offers"]))) as z:
        offers = pd.read_parquet(io.BytesIO(z.read(refs["offers"]["member"])))
    offers = offers.loc[offers.target.eq("rec") & offers.season.eq(2026) & offers.week.between(1, 7) & offers.position.isin(["WR", "TE"])].copy()
    check(len(offers) == 733 and not offers.opportunity_key.duplicated().any(), "original offer identity changed")
    return base, store, refs, board, forecasts, fixed, excluded, offers


def old_vectors(base, board, forecasts):
    byproduct = {}
    for cid, (method, product) in zip(base.A_IDS, base.A_PRODUCTS):
        f = forecasts.loc[forecasts.method.eq(method) & forecasts["product"].eq(product)]
        byproduct[cid] = {(str(r.game_id), str(r.player_id)): r for r in f.itertuples()}
    out = {cid: [] for cid in base.CANDIDATE_IDS}
    for b in board:
        for cid in base.CANDIDATE_IDS:
            fallback, reason = None, None
            if cid in base.A_IDS:
                f = byproduct[cid].get((b["game"], b["player"]))
                point = float(f.prediction) if f is not None and base.finite(f.prediction) else None
                if f is not None and str(f.position) != b["position"]:
                    point, reason = None, "POSITION_CONTRACT_MISMATCH"
                elif point is None:
                    reason = "MISSING_RETAINED_A_POINT"
                fallback = (str(f.fallback) or None) if f is not None else None
                selected = base.side(point, b["original_line_exact_text"])
            elif cid in base.C_IDS:
                j = base.C_IDS.index(cid)
                point, fallback, reason = b["points"][j], b["fallbacks"][j], b["unavailability_reasons"][j]
                selected = base.side(point, b["original_line_exact_text"])
            else:
                point, selected = None, cid.removeprefix("ALWAYS_")
            row = dict(season=2026, week=b["week"], game_id=b["game"], player_id=b["player"], category="rec",
                line=float(b["original_line_exact_text"]), actual=b["actual"], appearance=b["appearance"],
                opportunity_key=b["opportunity"], source_panel=b["source_panel"], selected_side=selected,
                point=point, fallback=fallback, unavailability_reason=reason, comparator="STRICT_OVER_UNDER")
            row["status"] = base.grade(row)
            out[cid].append(row)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["prepare", "score"], required=True)
    ap.add_argument("--c-points", type=Path, default=Path("/tmp/profile-increment-a-c-leaf.json.gz"))
    ap.add_argument("--protocol", type=Path)
    ap.add_argument("--protocol-sha256")
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--c-code-cache", type=Path, default=Path("/tmp/acceptance-c-review/src"))
    args = ap.parse_args()
    check(not args.output.exists(), "immutable output already exists")
    start, cpu = time.monotonic(), time.process_time()
    resources = dict(CPU_seconds=200, wall_seconds=600, RSS_bytes=3*1024**3, private_view_bytes=16384)
    plan = None
    if args.mode == "score":
        check(args.protocol is not None and args.protocol_sha256, "published root protocol required")
        raw = args.protocol.read_bytes()
        check(sha(raw) == args.protocol_sha256, "exact root protocol differs")
        plan = json.loads(raw)
        check(plan["state"] == "ROOT_REGISTERED_EXECUTION_GO" and plan["registered_by"] == "/root" and plan["version"] == VERSION,
              "root registration required")
        for path, digest in plan["code_sha256"].items():
            check(sha((ROOT / path).read_bytes()) == digest, "bound code differs")
        own = str(Path(__file__).resolve().relative_to(ROOT))
        check(plan["code_sha256"].get(own) == sha(Path(__file__).read_bytes()), "executing worker not hash bound")
        check(plan["resources"] == resources and plan["bootstrap_replicates"] == 500 and plan["bootstrap_seed"] == 20261110,
              "finite resource/precision registration differs")
    resource.setrlimit(resource.RLIMIT_CPU, (resources["CPU_seconds"], resources["CPU_seconds"]))
    resource.setrlimit(resource.RLIMIT_AS, (resources["RSS_bytes"],)*2)
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError("registered wall cap")))
    signal.alarm(resources["wall_seconds"])
    for name in ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"]:
        os.environ[name] = "1"
    def offline(event, _args):
        if event in {"socket.connect", "socket.connect_ex", "socket.getaddrinfo"}:
            raise RuntimeError("saved-output replay is offline")
    sys.addaudithook(offline)
    from tools import player_context_completion_reception_v1 as base
    np, pd = base.runtime()
    source = load_source(args.c_points)
    STATE["phase"] = "RETAINED_IDENTITIES_AND_CLOCK_INVENTORY"
    base, oldstore, refs, board, forecasts, fixed, excluded, offers = source_inputs(pd)
    joined, reasons, weekly = join_inventory(source, board, offers, pd)
    oldraw = (ROOT / "reports/abc-championship/player-context-completion-decision-01/RECEPTION_STRONG_CONTROL_RESULTS_V1.json").read_bytes()
    check(sha(oldraw) == PREVIOUS_SHA, "prior completed aggregate changed")
    previous = json.loads(oldraw)
    old_ids, candidates = base.CANDIDATE_IDS, base.CANDIDATE_IDS + NEW
    pairs = [[a, b] for a in NEW for b in old_ids] + [[NEW[0], NEW[1]]]
    receipt = dict(version=VERSION, state="PREPARED_NO_NEW_SCORES", resources=resources, source_sha256={k: v["sha256"] for k, v in refs.items()},
        C_source=dict(repository="NickNicky19/NFL-forecasting-NGS-C", commit=C_REF, path=C_PATH, bytes=C_BYTES, sha256=C_SHA,
                      archive=source["source_archive"], archive_sha256=source["source_archive_SHA256"], origin_source_pin=source["source_pin"]),
        C_procedures=source["procedures"], C_weekly_slots=source["slots"], source_population=dict(rows=2152, WRTE=1547),
        candidate_ids=candidates, paired_candidate_ids=pairs, original_outer=733, fixed667=667,
        outer733_mask_sha256=base.sha(base.encode(sorted(b["opportunity"] for b in board))),
        fixed667_mask_sha256=base.sha(base.encode(sorted(fixed))),
        C_point_join_rows=sum(v["forecast"] is not None for v in joined.values()),
        C_point_join_fixed667=sum(joined[k]["forecast"] is not None for k in fixed),
        join_unavailable_reasons=reasons, per_week_coverage=weekly,
        history_and_output="Distinct C H-MULTI weekly retained Leaf law mean/lower median; exact model/origin/trainingmembership bindings; not A Leaf aliases; no law/probability reconstruction",
        evidence="CURRENT_REVISED_7DAY_FOOTBALL;QUOTE_TIME_UNVERIFIED;EXPOSED_POINT_REPLAY;NO_ORIGINAL_ISSUANCE",
        horizon="C game as_of/kickoff must equal A retained query cutoff/kickoff; weekly model origin <= as_of; latest admitted training availability < model origin. Clock metadata does not authenticate source vintage or issuance.",
        prior_result_sha256=PREVIOUS_SHA, new_fits=0, new_inference=0, new_scores=0, private_writes=0)
    if args.mode == "prepare":
        receipt["actual"] = dict(CPU_seconds=time.process_time()-cpu, wall_seconds=time.monotonic()-start,
                                 RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
        with args.output.open("xb") as f:
            f.write(encoded(receipt))
        print(json.dumps({k: receipt[k] for k in ["state", "C_point_join_rows", "C_point_join_fixed667", "join_unavailable_reasons"]}))
        return
    check(plan["candidate_ids"] == candidates and plan["paired_candidate_ids"] == pairs, "finite roster differs")
    for field in ["source_sha256", "outer733_mask_sha256", "fixed667_mask_sha256", "C_source", "prior_result_sha256"]:
        check(plan[field] == receipt[field], "source/mask registration differs")
    peerraw = (ROOT / "reports/abc-championship/player-context-acceptance-01/PEER_PROTOCOL_V2.json").read_bytes()
    check(sha(peerraw) == base.PEER_PROTOCOL_SHA, "canonical scorer bindings changed")
    for ref in json.loads(peerraw)["peer_overlap"]["C_bound_code"]:
        check(sha((args.c_code_cache / Path(ref["path"]).name).read_bytes()) == ref.get("sha256", ref.get("SHA256")), "pinned common evaluator differs")
    sys.path.insert(0, str(args.c_code_cache))
    common = importlib.import_module("abc_championship_v2")
    vectors = old_vectors(base, board, forecasts)
    for cid, output in zip(NEW, ["mean", "median"]):
        vector = []
        for b in board:
            item = joined[b["opportunity"]]
            f = item["forecast"]
            point = float(f[output]) if f is not None else None
            selected = base.side(point, b["original_line_exact_text"])
            row = dict(season=2026, week=b["week"], game_id=b["game"], player_id=b["player"], category="rec",
                line=float(b["original_line_exact_text"]), actual=b["actual"], appearance=b["appearance"],
                opportunity_key=b["opportunity"], source_panel=b["source_panel"], selected_side=selected, point=point,
                fallback=f["fallback"] if f is not None else None, unavailability_reason=item["unavailable_reason"], comparator="STRICT_OVER_UNDER")
            row["status"] = base.grade(row)
            check(common.status(row) == row["status"], "independent threshold check differs from common scorer")
            vector.append(row)
        vectors[cid] = vector
    old_summary = {(r["candidate_id"], r["view"], r["source_panel"], str(r["week_view"])): r for r in previous["summaries"]}
    summaries, contrasts, validations = [], [], 0
    for view, mask in [("FULL_A733", {b["opportunity"] for b in board}), ("FIXED_C667", fixed)]:
        vv = {cid: [r for r in rows if r["opportunity_key"] in mask] for cid, rows in vectors.items()}
        for cid, rows in vv.items():
            for panel in ["ALL"] + sorted({r["source_panel"] for r in rows}):
                for week in ["ALL"] + list(range(1, 8)):
                    rr = [r for r in rows if (panel == "ALL" or r["source_panel"] == panel) and (week == "ALL" or r["week"] == week)]
                    value = dict(candidate_id=cid, view=view, source_panel=panel, week_view=week,
                        **common.summary(rr), numerical=base.numerical(rr),
                        actual_scored_weeks=sorted({r["week"] for r in rr if r["status"] in ["WIN", "LOSS", "PUSH"]}),
                        outer_appearance_states=dict(Counter(r["appearance"] for r in rr)),
                        unavailable_reasons=dict(Counter(r["unavailability_reason"] for r in rr if r["unavailability_reason"])),
                        fallback_outputs=sum(r["fallback"] not in [None, False, ""] for r in rr))
                    if cid in old_ids:
                        check(encoded(value) == encoded(old_summary[cid, view, panel, str(week)]), "old completed summary changed; stop before publishing")
                        validations += 1
                    summaries.append(value)
        for left, right in pairs:
            for panel in ["ALL"] + sorted({r["source_panel"] for r in vv[left]}):
                ll = [r for r in vv[left] if panel == "ALL" or r["source_panel"] == panel]
                rr = [r for r in vv[right] if panel == "ALL" or r["source_panel"] == panel]
                contrasts.append(dict(view=view, source_panel=panel, left=left, right=right,
                    **base.paired(ll, rr, np, 500, 20261110)))
    check(validations == 672, "expected prior full/source/week cell parity not completed")
    private_view = dict(version=VERSION, protocol_sha256=args.protocol_sha256, source_refs=refs,
        C_source=receipt["C_source"], prior_result_sha256=PREVIOUS_SHA, candidate_ids=candidates,
        fixed667_mask_sha256=receipt["fixed667_mask_sha256"], outer733_mask_sha256=receipt["outer733_mask_sha256"],
        board_selector="Original A733 WRTE primary rec board with unchanged known label/version and fixed667; no candidate-specific primary shrink",
        join="Exact canonical game/GSIS/role/week, historical team/opponent, equal query horizon; training chronology metadata checked; incompatibility unavailable not loss",
        reconstruction="Original retained private vectors/offers/outcomes/C733 relations plus immutable public C Leaf points and this hash-bound code regenerate every point/side/grade. No model decode.",
        no_original_issuance=True, original_C_probability_panel_separate=True, new_fits=0, new_inference=0)
    payload = lzma.compress(encoded(private_view), preset=6)
    check(len(payload) <= resources["private_view_bytes"], "lossless join view exceeds finite16KiB")
    # Retained-source restoration imports older repository packages. Bind this
    # writer to its registered file instead of that process-global package cache.
    guard_path = ROOT / "nfl_lab/player_context_completion_storage_v1.py"
    guard_spec = importlib.util.spec_from_file_location("profile_increment_local_completion_guard", guard_path)
    guard = importlib.util.module_from_spec(guard_spec)
    guard_spec.loader.exec_module(guard)
    store = guard.CompletionStore(ROOT, Path(plan["allocation"]["path"]), plan["allocation"]["sha256"], root_go=guard.GO)
    private = store.put("PROFILE_INCREMENT_C_LEAF_REC_VIEW_V1.json.xz", payload)
    check(store.read(private["id"], private["sha256"]) == payload, "new view native hash/readback differs")
    public = dict(**{k: v for k, v in receipt.items() if k not in ["state", "new_scores", "private_writes", "actual"]},
        state="SAVED_C_LEAF_CONTROL_JOIN_COMPLETE", protocol_sha256=args.protocol_sha256, summaries=summaries, paired=contrasts,
        old_completed_summary_parity_cells=validations, old_completed_summary_parity="PASS", new_summary_cells=96,
        private_scorecard_view=private, storage=store.checkpoint(),
        new_scores="NEW_C_LEAF_PRODUCTS_AND_NEW_PAIRWISE_CONTRASTS_ONLY;OLD672CELLS_RECONCILED_UNCHANGED",
        new_private_writes="ONE_LOSSLESS_VIEW_UNDER_EXISTING8M_GUARD", production_writes=0, new_C_admission="NOT_ASSUMED",
        uncertainty="Nominal500game/bootstrap plus inherited canonical2000week summaries; seven exposed weekclusters/repeatedplayers/multipleviews; conditional own-side subsets differ",
        actual=dict(CPU_seconds=time.process_time()-cpu, wall_seconds=time.monotonic()-start,
                    RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024))
    with args.output.open("xb") as f:
        f.write(encoded(public)); f.flush(); os.fsync(f.fileno())
    signal.alarm(0)
    print(json.dumps(dict(state=public["state"], output=str(args.output), C_join=receipt["C_point_join_rows"], fixed667=receipt["C_point_join_fixed667"], new_fits=0)))


if __name__ == "__main__":
    try:
        main()
    except BaseException as error:
        signal.alarm(0)
        print(json.dumps(dict(version=VERSION, state="FAILED_NO_AUTOMATIC_REFIT", phase=STATE["phase"],
                             error_type=type(error).__name__, error_sha256=sha(str(error).encode()), new_fits=0, new_inference=0)))
        raise
