"""Retained C P1/P2 Week8 points on A's original recorded threshold board.

Prepare inventories membership only. Score requires a separate exact root GO.
No model loading, inference, HTTP, private writes, fuzzy joins or changed labels.
"""
from __future__ import annotations
import argparse
import collections
import gzip
import hashlib
import importlib
import io
import json
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
VERSION = "PLAYER-CONTEXT-COMPLETION-DECISION-01-A-reception-W8-v1"
ALLOCATION = "f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26"
C_ROWS_SHA = "398957af85dbd55444a88725397b91060599ebb6e008771f35a9399d8f4af4c8"
C_FEATURES_SHA = "63f9853f19042bb3e4af691ce46001920d9df28830d1c6a34abfb5f1eab75ed0"
SOURCES_SHA = "6290b6a501ac5adf33ce693c2c4dc92d5f371ffdc3e6c6ba1da83ca6d1b623c5"
GRADED_SHA = "be9c13b0f42f5e164b29d00cce69fbe1c30acce703d1b33a8103a057888ac2c1"
OVERLAY_SHA = "2f8df2a10dcbba9074a04e9d2477fb76490311e2fedcbf70fa54c17dfec1f5fa"
R0 = "FIXED_R0_CAPTURE_20261028T184637Z"
SELECTED = "CAPTURED_SELECTED_369fec9caec0"
C_PRODUCTS = [(m, p) for m in ["P1", "P2"] for p in ["mean", "median"]]
C_IDS = ["C::PLAYER-CONTEXT-MATCHUP-01::v1.1::" + m + "::" + p for m, p in C_PRODUCTS]
IDS = C_IDS + ["A::R0_ISSUED_POINT", "A::CAPTURED_SELECTED_ISSUED_POINT", "A::ORIGINAL_ARCHIVE_SIDE", "ALWAYS_OVER", "ALWAYS_UNDER"]


def encode(x):
    return (json.dumps(x, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def check(x, message):
    if not x:
        raise ValueError(message)


def finite(x):
    return type(x) in [int, float] and math.isfinite(x)


def normid(x):
    s = str(x) if x is not None else ""
    return s[:-2] if s.endswith(".0") else s


def team(x):
    return {"LA": "LAR", "WSH": "WAS", "OAK": "LV", "SD": "LAC", "STL": "LAR"}.get(x, x)


def pin(path, expected, refs, key):
    path = Path(path)
    raw = path.read_bytes()
    check(sha(raw) == expected, "retained source hash changed")
    refs[key] = dict(path=str(path), bytes=len(raw), sha256=expected)
    return raw


def restore(croot):
    from tools import category_topfive_matched12_storage_v1 as storage
    import pyarrow as pa
    import pyarrow.parquet as pq
    pa.set_cpu_count(1); pa.set_io_thread_count(1); pa.set_memory_pool(pa.system_memory_pool())
    store, _ = storage.open_store(ROOT, allocation_sha256=ALLOCATION, root_go=storage.GO, readonly=True)
    refs = {}
    base = store.forward_root / "research/week8-original-grade-v2-batch-20261102"
    raw = pin(base / "SOURCES.zip", SOURCES_SHA, refs, "A_original_sources")
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        archive_bytes = z.read("archive_pre_first.bin")
        fixed = json.loads(archive_bytes)
    check((fixed["season"], fixed["week"]) == (2026, 8), "wrong original A board period")
    raw = pin(base / "A_LOCAL_WEEK8_REGRADING_V2_20261103.zip", GRADED_SHA, refs, "A_final_graded")
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        members = {n: z.read(n) for n in z.namelist()}
    manifest = json.loads(members["MANIFEST.json"])
    for name, ref in manifest.items():
        check(sha(members[name]) == ref["sha256"] and len(members[name]) == ref["bytes"], "original graded member changed")
    grades = json.loads(gzip.decompress(members["GRADED_ROWS.json.gz"]))
    report = json.loads(members["REPORT.json"])
    check(len(report["schedule"]) == 14 and all(g["final"] for g in report["schedule"]), "original frozen finality differs")
    raw = pin(store.forward_root / "research/ABC-PREDICTIVE-IMPROVEMENT-01-A-runtime-v2/AUDIT_WEEK8_MEASUREMENT_OVERLAY_V1.json.gz", OVERLAY_SHA, refs, "A_Nov5_qualification_overlay")
    overlay = json.loads(gzip.decompress(raw))
    check(overlay["source_archive"]["sha256"] == GRADED_SHA and overlay["source_member"] == manifest["GRADED_ROWS.json.gz"], "Nov5 qualification version mismatch")
    check(len(overlay["row_overlays"]["numerical"]) == len(grades["numerical"]), "qualification ordinal population differs")
    numerics = {}
    for i, row in enumerate(grades["numerical"]):
        q = overlay["row_overlays"]["numerical"][i]
        check(q["member_row"] == i and q["original_measurement_state"] == row["status"], "qualification ordinal mismatch")
        if row["category"] == "rec" and row["group"] in [R0, SELECTED]:
            key = (row["group"], normid(row["player_id"]), normid(row["game_id"]))
            check(key not in numerics, "ambiguous saved A reference")
            numerics[key] = dict(row, qualification=q)
    prep = json.loads((ROOT / "config/category-topfive-matched12-primary-preparation-v1.json").read_bytes())["inputs"]
    feature_ref = json.loads((ROOT / "config/category-topfive-matched12-inference-v1.json").read_bytes())["features"]
    check(feature_ref["sha256"] == "5450041c91f3c5dce3a4078c81b861f388e4682dd5cc57d3f1e6b250338f5b0e", "canonical identity feature panel changed")
    sched_ref = prep["schedule"]
    roster = pq.read_table(io.BytesIO(pin(feature_ref["path"], feature_ref["sha256"], refs, "A_saved_feature_identity_bridge")), columns=["season", "week", "team", "sleeper_id", "player_id"]).to_pylist()
    import csv
    schedule = list(csv.DictReader(io.StringIO(pin(sched_ref["path"], sched_ref["sha256"], refs, "A_historical_schedule_bridge").decode())))
    players = collections.defaultdict(set)
    for p in roster:
        if p.get("sleeper_id") and p.get("player_id"):
            players[normid(p["sleeper_id"])].add(p["player_id"])
    games = {}
    for g in schedule:
        if g["season"] == "2026" and g["week"] == "8" and g["game_type"] == "REG" and g["espn"]:
            k = normid(g["espn"])
            check(k not in games, "ambiguous canonical schedule")
            games[k] = g
    crows = json.loads(gzip.decompress(pin(croot / "NUMERICAL_ROWS.json.gz", C_ROWS_SHA, refs, "C_points")))
    cf = json.loads(gzip.decompress(pin(croot / "FEATURE_EXPORT.json.gz", C_FEATURES_SHA, refs, "C_features")))
    features = {(r["game_id"], r["player_id"]): r for r in cf if r["origin"] == "2026-W08"}
    cm = {}
    for r in crows:
        if r["origin"] == "2026-W08" and r["procedure"] in ["P1", "P2"]:
            k = (r["game_id"], r["player_id"], r["procedure"])
            check(k not in cm, "ambiguous saved C point")
            cm[k] = r
    # Raw source qualification matches Nov5: explicit target value plus positive
    # GP/offense-snap participation witness; absence is never filled with zero.
    stats, source_events = {}, {}
    for s in json.loads(members["sleeper_stats.json"]):
        check(s["season"] in [2026, "2026"] and s["week"] == 8 and s["season_type"] == "regular" and s["category"] == "stat", "raw outcome period differs")
        matches = [g["game_id"] for g in report["schedule"] if {team(g["home"]), team(g["away"])} == {team(s["team"]), team(s["opponent"])}]
        check(len(matches) == 1, "raw outcome event ambiguous")
        k = (normid(s["player_id"]), normid(matches[0]))
        check(k not in stats or stats[k] == s, "raw outcome duplicate conflict")
        check(source_events.setdefault(str(s["game_id"]), k[1]) == k[1], "raw provider event crosswalk conflict")
        stats[k] = s
    rows, excluded = [], collections.Counter()
    seen = set()
    for p in fixed["players"]:
        for offer in p["props"]:
            if offer["key"] != "rec":
                continue
            if p.get("late"):
                excluded["ORIGINAL_LATE_PLAYER_REC_PROP"] += 1; continue
            if offer.get("line_from") not in ["dk", "sleeper"] or not finite(offer.get("line")):
                excluded["SITE_GENERATED_REFERENCE_THRESHOLD" if offer.get("line_from") == "ours" else "NO_ORIGINAL_ELIGIBLE_RECORDED_REC_LINE"] += 1; continue
            if p["pos"] not in ["WR", "TE"]:
                excluded["OUTSIDE_WRTE"] += 1; continue
            sid, event = normid(p["id"]), normid(p["game_id"])
            identity = (sid, event, "rec")
            check(identity not in seen, "ambiguous original primary reception offer")
            seen.add(identity)
            g, ids = games.get(event), players.get(sid, set())
            reason = None
            if g is None or team(p["team"]) not in {team(g["home_team"]), team(g["away_team"])}:
                reason = "NO_CANONICAL_EVENT_TEAM_BRIDGE"
            elif len(ids) != 1:
                reason = "NO_UNIQUE_RETAINED_FEATURE_SLEEPER_GSIS_BRIDGE"
            game, player = (g["game_id"] if g else None), next(iter(ids)) if len(ids) == 1 else None
            feature = features.get((game, player))
            if reason is None and feature is not None:
                if (feature["position"], team(feature["team"]), team(feature["opponent"])) != (p["pos"], team(p["team"]), team(p["opp"])):
                    reason = "C_CONTEXT_ROLE_TEAM_OPPONENT_CONFLICT"
            raw = stats.get((sid, event), {}).get("stats")
            presence = "MISSING_SOURCE_ROW" if not isinstance(raw, dict) else "ABSENT_REQUIRED_COMPONENT" if "rec" not in raw else "EXPLICIT_UNKNOWN" if not finite(raw["rec"]) else "EXPLICIT_FINITE_REQUIRED_COMPONENTS"
            played = isinstance(raw, dict) and ((finite(raw.get("gp")) and raw["gp"] > 0) or (finite(raw.get("off_snp")) and raw["off_snp"] > 0))
            actual = float(raw["rec"]) if played and presence == "EXPLICIT_FINITE_REQUIRED_COMPONENTS" else None
            check(actual is None or (actual >= 0 and actual % 1 == 0), "invalid explicit reception count")
            for group in [R0, SELECTED]:
                n = numerics.get((group, sid, event))
                if n is not None:
                    q = n["qualification"]
                    check(q["source_presence"] == presence, "Nov5 source-presence parity differs")
                    check((q["qualified_measurement_state"] == "SUPPORTED") == (actual is not None), "Nov5 participation/measurement state differs")
                    check(actual is None or n["actual"] == actual, "A explicit qualified outcome conflict")
            for method in ["P1", "P2"]:
                c = cm.get((game, player, method)) if reason is None else None
                check(c is None or feature is not None, "C point lacks bound context export")
                if c is not None and actual is not None and finite(c.get("actual")):
                    check(actual == float(c["actual"]), "A/C known outcome conflict; halt")
            rows.append(dict(sleeper_id=sid, espn_event=event, game_id=game, player_id=player,
                position=p["pos"], team=team(p["team"]), line=offer["line"], line_from=offer["line_from"],
                offer_source_status="SITE_REFERENCE_THRESHOLD", actual_prop_eligible=False,
                original_side=offer.get("lean"), identity_reason=reason, presence=presence,
                appearance="PLAYED" if played else "UNKNOWN", actual=actual,
                opportunity=sha(encode([2026, 8, event, sid, "rec", offer["line_from"], str(offer["line"])]))))
    return refs, rows, cm, numerics, excluded, report


def inventory(refs, rows, cm, numerics, excluded, report):
    def available(r, method):
        return r["identity_reason"] is None and (r["game_id"], r["player_id"], method) in cm
    coverage = dict(outer_original_A_WRTE_rec_recorded_thresholds=len(rows), actual_offered_props_qualified=0,
        source_status_counts=dict(collections.Counter(r["offer_source_status"] for r in rows)),
        recorded_line_from_counts=dict(collections.Counter(r["line_from"] for r in rows)),
        games=len({r["espn_event"] for r in rows}),
        canonical_bridge_matched=sum(r["identity_reason"] is None for r in rows), identity_gaps=dict(collections.Counter(r["identity_reason"] for r in rows if r["identity_reason"])),
        qualified_known_actual=sum(r["actual"] is not None for r in rows), source_presence=dict(collections.Counter(r["presence"] for r in rows)),
        appearance=dict(collections.Counter(r["appearance"] for r in rows)), excluded=dict(excluded),
        C_available={m:sum(available(r,m) for r in rows) for m in ["P1","P2"]},
        C_known_qualified={m:sum(available(r,m) and r["actual"] is not None for r in rows) for m in ["P1","P2"]},
        C_missing_forecasts={m:sum(not available(r,m) for r in rows) for m in ["P1","P2"]},
        C_available_unqualified={m:sum(available(r,m) and r["actual"] is None for r in rows) for m in ["P1","P2"]},
        A_reference_available={g:sum((g,r["sleeper_id"],r["espn_event"]) in numerics for r in rows)for g in [R0,SELECTED]},
        original_side_selected=sum(r["original_side"] in ["over","under"] for r in rows))
    return dict(version=VERSION, state="PREPARED_MEMBERSHIP_ONLY_NO_SCORES", candidate_ids=IDS,
        sources=refs, coverage=coverage, outer_mask_sha256=sha(encode(sorted(r["opportunity"] for r in rows))),
        C_known_mask_sha256=sha(encode(sorted(r["opportunity"] for r in rows if available(r,"P1") and r["actual"] is not None))),
        source_outcome_asof_UTC=report["asof_UTC"], fixed_period="2026_W8_ONLY", source_tier="SITE_RECORDED_THRESHOLD_STATISTICAL_DIRECTION_DIAGNOSTIC_ONLY;C_CURRENT_REVISED_SEVEN_DAY_RECONSTRUCTION;NO_AUTHENTICATED_ACTUAL_PROP_CLAIM",
        threshold_provenance="Pinned original archive has only line,line_from(dk/sleeper/ours),source(model/average),proj and forecast fields. No bookID/quoteID/provider response/quoteclock retained in this binding. dk/sleeper are unverified recorded labels; ours is a site-generated reference threshold excluded from the board. No threshold is admitted as an authenticated actual offered prop.",
        A_reference_horizons="R0issued2026-10-28T18:46:25Z;selectedissued17:01Z,different105minutehorizon;descriptivecompleteprocedurecomparison",
        A_reference_product_labels={g:sorted({str(n.get("product","UNKNOWN_UNRETAINED_PRODUCT_LABEL")) for k,n in numerics.items() if k[0]==g}) for g in [R0,SELECTED]},
        A_W1_W7_finalists="NOT_PRESENT_FOR_W8_NO_VALUES_FABRICATED", C_original_W2_W3="SEPARATE_UNCHANGED",
        identity_rule="Unique SleeperID to GSIS across exact retained feature panel5450041c; identity facts only, no W8pregame eligibility claim. Exact ESPN to canonical schedule; reciprocal team/opponent and recorded position; no name join or fuzzy matching",
        outcome_rule="Pinned Nov5 row-ordinal qualification overlays checked for existing A reference rows; exact frozen raw GP/offensive-snap positive participation plus explicit finite reception metric; omitted rec remains missing",
        new_scores=0,new_fits=0,new_inference=0,new_source_requests=0,private_writes=0)


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--mode",choices=["prepare","score"],required=True);ap.add_argument("--output",type=Path,required=True)
    ap.add_argument("--protocol",type=Path);ap.add_argument("--protocol-sha256");ap.add_argument("--c-root",type=Path,default=Path("/tmp/acceptance-c-review/artifacts/player-context-matchup-01/v1.1"));a=ap.parse_args()
    started,cpu=time.monotonic(),time.process_time()
    resource.setrlimit(resource.RLIMIT_CPU,(120,120));resource.setrlimit(resource.RLIMIT_AS,(1610612736,)*2);signal.alarm(180)
    for n in ["OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","NUMEXPR_NUM_THREADS"]:os.environ[n]="1"
    def offline(event,_args):
        if event in {"socket.connect","socket.connect_ex","socket.getaddrinfo"}:raise RuntimeError("saved byte work is offline")
    sys.addaudithook(offline)
    plan=None
    if a.mode=="score":
        check(a.protocol is not None and a.protocol_sha256 is not None,"root protocol required")
        raw=a.protocol.read_bytes();check(sha(raw)==a.protocol_sha256,"root protocol changed");plan=json.loads(raw)
        check(plan["state"]=="ROOT_REGISTERED_EXECUTION_GO" and plan["registered_by"]=="/root" and plan["version"]==VERSION and plan["candidate_ids"]==IDS,"exact root finite registration required")
        check(plan["study_kind"]=="SITE_RECORDED_THRESHOLD_STATISTICAL_DIRECTION_DIAGNOSTIC" and plan["actual_offered_props_qualified"]==0,"source gate admits diagnostic thresholds only")
        check(plan["resources"]["CPU_seconds"]<=120 and plan["resources"]["wall_seconds"]<=180 and plan["resources"]["RSS_bytes"]<=1610612736 and plan["resources"]["private_peak_bytes"]==0,"bounded zero private write registration required")
        resource.setrlimit(resource.RLIMIT_CPU,(plan["resources"]["CPU_seconds"],plan["resources"]["CPU_seconds"]))
        resource.setrlimit(resource.RLIMIT_AS,(plan["resources"]["RSS_bytes"],)*2)
        signal.alarm(plan["resources"]["wall_seconds"])
        check(0<plan["bootstrap_replicates"]<=500 and plan["bootstrap_seed"]==20261110 and len(plan["paired_candidate_ids"])<=32,"finite paired registration required")
        for p,h in plan["code_sha256"].items():check(sha((ROOT/p).read_bytes())==h,"bound code changed")
        check(plan["code_sha256"].get(str(Path(__file__).relative_to(ROOT)))==sha(Path(__file__).read_bytes()),"worker not bound")
    refs,rows,cm,numerics,excluded,report=restore(a.c_root);result=inventory(refs,rows,cm,numerics,excluded,report)
    if a.mode=="score":
        check(plan["source_sha256"]=={k:v["sha256"]for k,v in refs.items()} and plan["outer_mask_sha256"]==result["outer_mask_sha256"] and plan["C_known_mask_sha256"]==result["C_known_mask_sha256"],"registered sources/membership changed")
        from tools import player_context_completion_reception_v1 as helper
        peer=(ROOT/"reports/abc-championship/player-context-acceptance-01/PEER_PROTOCOL_V2.json").read_bytes();check(sha(peer)==helper.PEER_PROTOCOL_SHA,"accepted scorer protocol changed")
        cache=Path("/tmp/acceptance-c-review/src")
        for ref in json.loads(peer)["peer_overlap"]["C_bound_code"]:check(sha((cache/Path(ref["path"]).name).read_bytes())==ref.get("sha256",ref.get("SHA256")),"accepted scorer code changed")
        sys.path.insert(0,str(cache));common=importlib.import_module("abc_championship_v2")
        scored={cid:[]for cid in IDS}
        for b in rows:
            for cid in IDS:
                point=None;selected=None;fallback=None;missing_reason=None
                if cid in C_IDS:
                    method,product=C_PRODUCTS[C_IDS.index(cid)];f=cm.get((b["game_id"],b["player_id"],method))if b["identity_reason"] is None else None;point=f.get(product)if f else None;selected=helper.side(point,b["line"]);fallback=f.get("fallback")if f else None;missing_reason=(b["identity_reason"]or"NO_SAVED_C_PLAYER_GAME_POINT")if point is None else None
                elif cid in ["A::R0_ISSUED_POINT","A::CAPTURED_SELECTED_ISSUED_POINT"]:
                    g=R0 if cid=="A::R0_ISSUED_POINT"else SELECTED;f=numerics.get((g,b["sleeper_id"],b["espn_event"]));point=f.get("point")if f else None;selected=helper.side(point,b["line"])
                elif cid=="A::ORIGINAL_ARCHIVE_SIDE":selected=b["original_side"].upper()if b["original_side"]in["over","under"]else None
                else:selected=cid.removeprefix("ALWAYS_")
                r=dict(season=2026,week=8,category="rec",game_id=b["game_id"]or b["espn_event"],player_id=b["player_id"]or b["sleeper_id"],opportunity_key=b["opportunity"],line=b["line"],actual=b["actual"],appearance=b["appearance"],selected_side=selected,point=point,fallback=fallback,unavailability_reason=missing_reason,comparator="STRICT_OVER_UNDER")
                r["status"]=helper.grade(r);check(common.status(r)==r["status"],"accepted and independent graders disagree");scored[cid].append(r)
        import numpy as np
        masks={"FULL_ORIGINAL_A_WRTE_RECORDED_THRESHOLD_BOARD":{r["opportunity"]for r in rows},"FIXED_C_AVAILABLE_KNOWN":{r["opportunity"]for r in rows if r["actual"]is not None and r["identity_reason"]is None and(r["game_id"],r["player_id"],"P1")in cm}}
        summaries,pairs=[],[]
        for view,mask in masks.items():
            vv={cid:[r for r in rr if r["opportunity_key"]in mask]for cid,rr in scored.items()}
            summaries.extend(dict(candidate_id=cid,view=view,**common.summary(rr),numerical=helper.numerical(rr),fallback_outputs=sum(r["fallback"]not in[None,False,""]for r in rr),unavailable_reasons=dict(collections.Counter(r["unavailability_reason"]for r in rr if r["unavailability_reason"])))for cid,rr in vv.items())
            for left,right in plan["paired_candidate_ids"]:
                check(left in IDS and right in IDS,"unregistered pair")
                pairs.append(dict(view=view,left=left,right=right,**helper.paired(vv[left],vv[right],np,plan["bootstrap_replicates"],plan["bootstrap_seed"])))
        result.update(state="SAVED_WEEK8_POINT_REPLAY_COMPLETE",protocol_sha256=a.protocol_sha256,scores=summaries,paired=pairs,new_scores=len(rows)*len(IDS),uncertainty="Nominal game bootstrap on one exposed Week8; not independent week confirmation. Multiple products of one fitted procedure are not independent learners.")
    result["actual"]=dict(CPU_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-started,RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
    if a.mode=="score":result["source_sha256"]={k:v["sha256"]for k,v in result.pop("sources").items()}
    with a.output.open("xb")as f:f.write(encode(result));f.flush();os.fsync(f.fileno())
    signal.alarm(0);print(json.dumps(dict(state=result["state"],coverage=result["coverage"],output=str(a.output),private_writes=0,new_fits=0,new_inference=0)))


if __name__=="__main__":main()
