"""Audit retained as-of profiles after a hash-bound profile receipt/root GO.

Reads profile JSON only. No outcomes, PBP, models, fitted-object deserialization,
profile generation, inference, source acquisition or current-week capture.
Actual examples stay in the existing completion guard; public output aggregates.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import gc
import gzip
import hashlib
import inspect
import json
import lzma
import math
import os
from pathlib import Path
import resource
import signal
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
VERSION = "PLAYER-CONTEXT-COMPLETION-DECISION-01-A-profile-review-v1"
OUT = ROOT / "reports/abc-championship/player-context-completion-decision-01"
PUBLIC_PATH = OUT / "PROFILE_INDEX_V1.json"
PRIVATE_NAME = "PROFILE_REVIEW/EXAMPLES_INDEX_V1.json.xz"
PROFILE_NAMES = ["PROFILES_2025.json.xz", "PROFILES_2026.json.xz", "PROFILES_2026_W8_UNAVAILABLE.json.gz"]
EXPECTED_ROWS = {"PROFILES_2025.json.xz": 923, "PROFILES_2026.json.xz": 1364, "PROFILES_2026_W8_UNAVAILABLE.json.gz": 2}
EXPECTED_VERSION = "A::PLAYER-CONTEXT-COMPLETION-DECISION-01-efficiency-v1"
GROUPS = {"direction": ("left", "middle", "right", "UNKNOWN"),
          "gap": ("end", "guard", "tackle", "UNKNOWN"),
          "down": ("1", "2", "3", "4", "UNKNOWN"),
          "distance": ("short", "medium", "long", "UNKNOWN")}
METRICS = {"own": {"yards", "epa_positive", "first_down", "own_carry_mix", "player_share_given_team_run"},
           "team": {"yards", "epa_positive", "first_down", "team_runs_per_offensive_opportunity"},
           "opp": {"yards_earlier_offense_residual", "epa_positive_earlier_offense_residual", "first_down_earlier_offense_residual"}}
FORBIDDEN_KEYS = {"actual", "outcome", "actual_n", "target_outcome", "target_context_mix", "target_participation"}
STATE = {"phase": "NOT_STARTED"}


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def check(value, message):
    if not value:
        raise ValueError(message)


def number(value):
    return type(value) in [int, float] and math.isfinite(value)


def clock(value):
    if value is None:
        return None
    check(isinstance(value, str), "source clock must be explicit text or null")
    result = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    check(result.tzinfo is not None and result.utcoffset() is not None, "source clock timezone unknown")
    return result


def pin(path, expected):
    path = Path(path)
    raw = path.read_bytes()
    check(sha(raw) == expected, "registered metadata/code hash changed")
    return raw


def strict_decode(body):
    """Independent lossless decoder; reject zip truncation and bad clock indices."""
    packet = json.loads(lzma.decompress(body))
    check(packet.get("codec") == "LOSSLESS_PROFILE_SCHEMA_CLOCK_FACTORIZATION_V1", "unknown profile codec")
    check(set(packet) == {"codec", "definitions", "profiles"}, "unregistered codec packet fields")
    definitions = packet["definitions"]
    check(len(definitions) == 196, "unexpected tendency schema cardinality")
    for definition in definitions:
        check(set(definition) == {"constants", "fields"}, "unexpected tendency definition")
        fields = definition["fields"]
        check(isinstance(fields, list) and len(fields) == len(set(fields)) and
              not (set(fields) & set(definition["constants"])), "lossy tendency field definition")
    for ordinal, packed in enumerate(packet["profiles"]):
        check(set(packed) == {"identity", "clocks", "values"}, "unexpected packed profile fields")
        check(len(packed["values"]) == len(definitions), "lossy tendency row count")
        check(len(packed["clocks"]) == len(set(packed["clocks"])), "duplicate clock-table identity")
        for value in packed["clocks"]:
            clock(value)
        tendencies = []
        for definition, values in zip(definitions, packed["values"]):
            check(len(values) == len(definition["fields"]), "lossy tendency column count")
            row = dict(definition["constants"])
            for field, value in zip(definition["fields"], values):
                if field.endswith("_clock") and value is not None:
                    check(type(value) is int and 0 <= value < len(packed["clocks"]), "invalid local clock reference")
                    value = packed["clocks"][value]
                row[field] = value
            tendencies.append(row)
        check("tendencies" not in packed["identity"], "duplicate profile tendency identity")
        yield ordinal, dict(packed["identity"], tendencies=tendencies)


def percentile(values, q):
    if not values:
        return None
    values = sorted(values)
    pos = (len(values) - 1) * q
    a, b = int(math.floor(pos)), int(math.ceil(pos))
    return values[a] + (values[b] - values[a]) * (pos - a)


def distribution(values):
    return dict(known=len(values), minimum=min(values) if values else None,
                median=percentile(values, .5), p90=percentile(values, .9),
                maximum=max(values) if values else None,
                mean=math.fsum(values) / len(values) if values else None)


def group_state():
    return dict(rows=0, canonical_rows=0, unavailable_rows=0, states=collections.Counter(),
                support_games=[], support_carries=[], source_age_days=[], source_clock_null=0,
                raw_source_age_days={a: [] for a in ["own", "team", "opp"]},
                raw_source_clock_null=collections.Counter(), denominator_zero=0,
                known_zero_numerator=0, tendency_rows=0, metrics=collections.Counter(),
                sparse_support_le1=0, row_hashes=[], artifact_rows=collections.defaultdict(list))


def no_outcome_fields(value):
    """Profiles/identities only; refuse unexpected target-label fields."""
    if isinstance(value, dict):
        check(not (set(value) & FORBIDDEN_KEYS), "target-outcome field present in profile artifact")
        for item in value.values():
            no_outcome_fields(item)
    elif isinstance(value, list):
        for item in value:
            no_outcome_fields(item)


def validate_profile(profile, aggregate):
    no_outcome_fields(profile)
    required = {"profile_version", "season", "week", "game_id", "player_id", "historical_team", "opponent",
                "cutoff_utc", "source_information_max_utc", "lookback_appearances", "state", "tendencies"}
    check(required <= set(profile), "as-of profile schema incomplete")
    check(profile["profile_version"] == EXPECTED_VERSION and profile["lookback_appearances"] == 8,
          "profile version/lookback changed")
    check(type(profile["season"]) is int and type(profile["week"]) is int and 1 <= profile["week"] <= 18,
          "invalid profile period")
    cutoff, latest = clock(profile["cutoff_utc"]), clock(profile["source_information_max_utc"])
    check(latest is None or latest < cutoff, "profile source not strictly earlier than cutoff")
    unavailable = profile["player_id"] is None
    if unavailable:
        check(profile["state"] in ["UNAVAILABLE_CANONICAL_ID", "UNAVAILABLE_CANONICAL_EVENT"] and
              isinstance(profile.get("source_identity"), dict) and profile.get("unavailable_reason") and
              profile["tendencies"] == [] and profile.get("eligible_player_games") is None and
              profile.get("eligible_player_carries") is None and latest is None,
              "unavailable source identity was fabricated or dropped")
        check({"player_namespace", "player_id", "event_namespace", "event_id"} <= set(profile["source_identity"]),
              "missing original source identity")
    else:
        check(profile["state"] in ["SUPPORTED_CARRIES", "SUPPORTED_PLAYED_ZERO_ONLY", "NO_ELIGIBLE_SOURCE_PLAYER_HISTORY"],
              "unsupported canonical profile state")
        check(len(profile["tendencies"]) == 196, "canonical profile tendency population differs")
        for field in ["eligible_player_games", "eligible_player_carries"]:
            check(type(profile[field]) is int and profile[field] >= 0, "invalid profile support count")
        check(profile["eligible_player_games"] <= 8, "appearance lookback exceeded")
    identities, own_mix = set(), collections.defaultdict(list)
    raw_mix = collections.defaultdict(list)
    known_zero = False
    raw_actor_clocks = collections.defaultdict(list)
    for tendency in profile["tendencies"]:
        actor, group, value, metric = (tendency[k] for k in ["actor", "group", "value", "metric"])
        check(actor in METRICS and group in GROUPS and value in GROUPS[group] and metric in METRICS[actor],
              "conditional tendency semantics changed")
        check(not (metric == "team_runs_per_offensive_opportunity" and group not in ["down", "distance"]),
              "offensive-opportunity denominator attached to wrong group")
        identity = (actor, group, value, metric)
        check(identity not in identities, "duplicate conditional tendency")
        identities.add(identity)
        numerator, denominator, raw, shrunk = (tendency[k] for k in ["numerator", "denominator", "raw", "shrunk"])
        check(number(numerator) and number(denominator) and denominator >= 0 and number(shrunk),
              "nonfinite raw/shrunk tendency value")
        # Signed yards and defense residuals may be negative. Ordinary
        # frequency/success numerators use their own finite opportunity counts.
        if actor != "opp" and metric != "yards":
            check(0 <= numerator <= denominator and 0 <= shrunk <= 1,
                  "frequency/success quantity outside its declared denominator")
        if denominator == 0:
            check(raw is None, "zero denominator must remain null")
            aggregate["denominator_zero"] += 1
        else:
            check(number(raw) and math.isclose(raw, numerator / denominator, rel_tol=1e-12, abs_tol=1e-12),
                  "raw ratio differs from retained numerator/denominator")
            if numerator == 0:
                check(raw == 0, "known zero numerator must produce zero")
                aggregate["known_zero_numerator"] += 1
                known_zero = known_zero or actor == "own"
        check(tendency["state"] == ("SUPPORTED" if denominator else "UNSUPPORTED_SHRUNK_PRIOR"),
              "raw support state differs from denominator")
        for support in ["support_carries", "support_games"]:
            check(type(tendency[support]) is int and tendency[support] >= 0, "invalid tendency support")
        for field in ["raw_latest_eligible_clock", "latest_eligible_clock"]:
            value_clock = clock(tendency.get(field))
            check(value_clock is None or value_clock < cutoff, "conditional source clock not strictly earlier")
            check(value_clock is None or latest is not None and value_clock <= latest,
                  "conditional source clock exceeds profile source maximum")
            if field == "raw_latest_eligible_clock" and value_clock is not None:
                raw_actor_clocks[actor].append(value_clock)
        if metric == "own_carry_mix":
            own_mix[group].append(shrunk)
            raw_mix[group].append(raw)
        aggregate["metrics"][metric] += 1
        aggregate["tendency_rows"] += 1
    if not unavailable:
        for group, values in GROUPS.items():
            check(len(own_mix[group]) == len(values) and math.isclose(math.fsum(own_mix[group]), 1., abs_tol=1e-12),
                  "own shrunken context mixture does not sum to one")
            check(all(x is None for x in raw_mix[group]) or
                  all(number(x) for x in raw_mix[group]) and math.isclose(math.fsum(raw_mix[group]), 1., abs_tol=1e-12),
                  "own observed context mixture is neither unsupported nor normalized")
        aggregate["support_games"].append(profile["eligible_player_games"])
        aggregate["support_carries"].append(profile["eligible_player_carries"])
        aggregate["sparse_support_le1"] += profile["eligible_player_games"] <= 1
        for actor in ["own", "team", "opp"]:
            if raw_actor_clocks[actor]:
                aggregate["raw_source_age_days"][actor].append((cutoff - max(raw_actor_clocks[actor])).total_seconds() / 86400.)
            else:
                aggregate["raw_source_clock_null"][actor] += 1
    aggregate["rows"] += 1
    aggregate["canonical_rows"] += not unavailable
    aggregate["unavailable_rows"] += unavailable
    aggregate["states"][profile["state"]] += 1
    if latest is None:
        aggregate["source_clock_null"] += 1
    else:
        aggregate["source_age_days"].append((cutoff - latest).total_seconds() / 86400.)
    return known_zero


def row_summary(period, aggregate):
    return dict(season=period[0], week=period[1], rows=aggregate["rows"], canonical_rows=aggregate["canonical_rows"],
        unavailable_rows=aggregate["unavailable_rows"], states=dict(aggregate["states"]),
        support_games=distribution(aggregate["support_games"]), support_carries=distribution(aggregate["support_carries"]),
        sparse_support_le1=aggregate["sparse_support_le1"], source_age_days=distribution(aggregate["source_age_days"]),
        source_clock_null=aggregate["source_clock_null"], raw_source_age_days={k: distribution(v) for k, v in aggregate["raw_source_age_days"].items()},
        raw_source_clock_null=dict(aggregate["raw_source_clock_null"]), tendency_rows=aggregate["tendency_rows"],
        raw_denominator_zero=aggregate["denominator_zero"], raw_known_zero_numerator=aggregate["known_zero_numerator"],
        metric_names_preserved=dict(aggregate["metrics"]),
        decoded_rows_sha256=sha(b"".join(bytes.fromhex(x) for x in sorted(aggregate["row_hashes"]))))


def run(args):
    started, cpu = time.monotonic(), time.process_time()
    STATE["phase"] = "REGISTRATION"
    raw = pin(args.protocol, args.protocol_sha256)
    plan = json.loads(raw)
    check(plan["state"] == "ROOT_REGISTERED_EXECUTION_GO" and plan["registered_by"] == "/root" and plan["version"] == VERSION,
          "published root profile-review GO required")
    own = str(Path(__file__).resolve().relative_to(ROOT))
    check(plan["code_sha256"].get(own) == sha(Path(__file__).read_bytes()), "executing worker not bound")
    for name, digest in plan["code_sha256"].items():
        pin(ROOT / name, digest)
    caps = plan["resources"]
    # Postexecution budget amendment accounts for the measured mandatory
    # full-stack integrity/quota scans; all existing storage guards still run.
    check(0 < caps["CPU_seconds"] <= 500 and 0 < caps["wall_seconds"] <= 900 and
          0 < caps["AS_bytes"] <= 1610612736 and 0 < caps["private_extra_bytes"] <= 65536,
          "finite profile review resource allocation required")
    cleanup_cpu = min(50, max(10, caps["CPU_seconds"] // 10))
    resource.setrlimit(resource.RLIMIT_CPU, (max(1, caps["CPU_seconds"] - cleanup_cpu), caps["CPU_seconds"]))
    resource.setrlimit(resource.RLIMIT_AS, (caps["AS_bytes"], caps["AS_bytes"]))
    def exhausted(signum, _frame):
        if signum == signal.SIGXCPU:
            signal.signal(signal.SIGXCPU, signal.SIG_IGN)
        raise TimeoutError("registered profile review envelope; cleanup reserve remains inside hard cap")
    signal.signal(signal.SIGXCPU, exhausted)
    signal.signal(signal.SIGALRM, exhausted)
    signal.alarm(max(1, caps["wall_seconds"] - min(60, max(10, caps["wall_seconds"] // 10))))
    for name in ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"]:
        os.environ[name] = "1"
    def offline(event, _args):
        if event in {"socket.connect", "socket.connect_ex", "socket.getaddrinfo", "pickle.find_class"}:
            raise RuntimeError("profile review permits retained JSON only")
    sys.addaudithook(offline)
    STATE["phase"] = "COMPLETED_RECEIPT_GATE"
    completed_bytes = pin(args.completed_receipt, args.completed_receipt_sha256)
    check(plan["completed_receipt_sha256"] == args.completed_receipt_sha256, "completed receipt not registration bound")
    completed = json.loads(completed_bytes)
    model_complete = completed["state"] == "FROZEN_FORECASTS_COMPLETE_UNSCORED"
    profile_only = completed["state"] == "PROFILES_COMPLETE_MODEL_WAVE_INFERENCE_INCOMPLETE"
    check((model_complete or profile_only) and completed["profile_rows"] == 2289,
          "expected immutable profile population not established")
    failure_ref = None
    if profile_only:
        failure_ref = completed["model_wave_failure"]
        check(failure_ref["sha256"] == plan["model_wave_failure_sha256"],
              "original failed model-wave receipt not registration bound")
        failure_bytes = pin(OUT / "EFFICIENCY_FAILURE_V1.json", failure_ref["sha256"])
        check(len(failure_bytes) == failure_ref["bytes"], "failed model-wave receipt byte count differs")
        failure = json.loads(failure_bytes)
        check(failure["state"] == "FAILED_RETAINED_NO_AUTOMATIC_REFIT" and
              failure["fits_attempted"] == 5 and failure["fits_returned"] == 5,
              "original failed model-wave state or consumed fits differ")
        failed_profiles = {r["id"]: r for r in failure["artifacts"] if r.get("id") in PROFILE_NAMES}
        admitted_profiles = {r["id"]: r for r in completed["artifacts"] if r.get("id") in PROFILE_NAMES}
        check(failed_profiles == admitted_profiles, "profile-only receipt changed failed-wave artifact bindings")
    refs = {ref["id"]: ref for ref in completed["artifacts"] if ref.get("id") in PROFILE_NAMES}
    check(set(refs) == set(PROFILE_NAMES) and len([r for r in completed["artifacts"] if r.get("id") in PROFILE_NAMES]) == 3,
          "exact retained profile artifact references required")
    check(plan["profile_artifact_sha256"] == {name: refs[name]["sha256"] for name in PROFILE_NAMES},
          "profile artifact admission differs from completed receipt")
    from tools import player_context_completion_efficiency_v1 as owner
    from nfl_lab import player_context_rush_efficiency_v1 as core
    from nfl_lab import player_context_completion_storage_v1 as guard
    from tools import category_topfive_matched12_storage_v1 as legacy
    # Refuse allocation creation or a second root registration. The completed
    # owner's guard must already exist before its normal constructor is used.
    outer, _ = legacy.open_store(ROOT, allocation_sha256=guard.ALLOCATION, root_go=legacy.GO, readonly=True)
    existing = outer.complete_peer.prior_forward.forward_root / "research" / guard.VERSION / "ALLOCATION_STATE.json"
    check(existing.is_file(), "completed owner allocation state must already exist")
    store = guard.CompletionStore(ROOT, Path(plan["allocation"]["path"]), plan["allocation"]["sha256"], root_go=guard.GO)
    store.reserve(caps["private_extra_bytes"])
    check(not store._path(PRIVATE_NAME).exists() and not PUBLIC_PATH.exists(), "immutable profile review already exists")
    check(len(core.FEATURES) == 168 and len(core.EFFICIENCY_FEATURES) == 142 and len(core.PROFILE_ONLY_FEATURES) == 26 and
          set(core.EFFICIENCY_FEATURES).isdisjoint(core.PROFILE_ONLY_FEATURES) and
          set(core.EFFICIENCY_FEATURES) | set(core.PROFILE_ONLY_FEATURES) == set(core.FEATURES),
          "declared feature consumption changed")
    signature = inspect.signature(core.EfficiencyContext.profile)
    check(list(signature.parameters) == ["self", "player", "team", "opponent", "cutoff", "window", "rich"],
          "generic as-of profile interface changed or requires outcomes")
    STATE["phase"] = "PROFILE_ONLY_DECODE_AND_INVARIANTS"
    periods = collections.defaultdict(group_state)
    seen, candidates, missing_examples = set(), {}, []
    artifact_rows, decoded_hashes = {}, {}
    def choose(role, digest, example):
        if role not in candidates or digest < candidates[role]["profile_sha256"]:
            candidates[role] = example
    for name in PROFILE_NAMES:
        ref = refs[name]
        body = store.read(name, ref["sha256"])
        check(len(body) == ref["bytes"], "profile artifact byte count differs")
        if name.endswith(".xz"):
            original = owner.unpack_profiles(body)
            decoded = strict_decode(body)
        else:
            original = json.loads(gzip.decompress(body))
            decoded = enumerate(original)
        check(len(original) == EXPECTED_ROWS[name], "retained profile count differs")
        artifact_hashes, count = [], 0
        for ordinal, profile in decoded:
            check(encode(profile) == encode(original[ordinal]), "strict and owner decoder differ")
            period = (profile["season"], profile["week"])
            aggregate = periods[period]
            known_zero = validate_profile(profile, aggregate)
            identity = (profile["season"], profile["week"], profile["game_id"], profile["player_id"],
                        None if profile["player_id"] is not None else encode(profile["source_identity"]).decode())
            check(identity not in seen, "duplicate intended profile identity")
            seen.add(identity)
            digest = sha(encode(profile))
            aggregate["row_hashes"].append(digest)
            aggregate["artifact_rows"][name].append(ordinal)
            artifact_hashes.append(digest)
            example = dict(profile_sha256=digest, artifact_id=name, artifact_row_ordinal=ordinal, profile=profile)
            if profile["player_id"] is None:
                missing_examples.append(example)
            else:
                games = profile["eligible_player_games"]
                if games > 1 and profile["state"] == "SUPPORTED_CARRIES":
                    choose("ordinary_supported_history", digest, example)
                if games <= 1:
                    choose("sparse_zero_or_one_supported_appearance", digest, example)
                if known_zero:
                    choose("known_zero_numerator_positive_denominator", digest, example)
            count += 1
        check(count == EXPECTED_ROWS[name], "strict decoder row population differs")
        artifact_rows[name] = count
        decoded_hashes[name] = sha(b"".join(bytes.fromhex(x) for x in artifact_hashes))
        del original, decoded, body
        gc.collect()
    check(len(seen) == 2289 and artifact_rows == EXPECTED_ROWS and len(missing_examples) == 2 and
          all(x["profile"]["state"] == "UNAVAILABLE_CANONICAL_ID" for x in missing_examples),
          "expected923+1364+2 intended profile population differs")
    check(set(candidates) == {"ordinary_supported_history", "sparse_zero_or_one_supported_appearance", "known_zero_numerator_positive_denominator"},
          "a required actual example class is absent; do not fabricate an example")
    examples = [dict(example_role=role, **candidates[role]) for role in sorted(candidates)]
    examples += [dict(example_role="missing_canonical_id_" + str(i + 1), **row)
                 for i, row in enumerate(sorted(missing_examples, key=lambda x: x["profile_sha256"]))]
    index = [dict(season=period[0], week=period[1], artifacts=dict(aggregate["artifact_rows"]))
             for period, aggregate in sorted(periods.items())]
    private = dict(version=VERSION, completed_receipt_sha256=args.completed_receipt_sha256,
        profile_input_receipt_state=completed["state"], model_wave_inference_complete=model_complete,
        original_model_wave_failure=failure_ref,
        source_artifacts={name: {k: refs[name][k] for k in ["id", "bytes", "sha256"]} for name in PROFILE_NAMES},
        selection="Lexicographic SHA256(canonical sorted-key profile JSON); outcome-independent predicates; both missing-ID rows included in hash order",
        examples=examples, private_ordinal_index=index,
        readable_examples="Actual examples are complete decoded JSON profiles in examples; source artifacts and exact row ordinals recover every other profile without copying vectors.")
    payload = lzma.compress(encode(private), preset=3)
    check(len(payload) <= caps["private_extra_bytes"], "actual examples/index exceed finite private allocation; no write performed")
    STATE["phase"] = "GUARDED_PRIVATE_EXAMPLES_AND_READBACK"
    private_ref = store.put(PRIVATE_NAME, payload)
    check(store.read(PRIVATE_NAME, private_ref["sha256"]) == payload, "private example readback mismatch")
    usage = store.checkpoint()
    public = dict(version=VERSION, state="RETAINED_PROFILE_SCHEMA_CLOCK_SUPPORT_REVIEW_COMPLETE", protocol_sha256=args.protocol_sha256,
        completed_receipt_sha256=args.completed_receipt_sha256,
        profile_input_receipt_state=completed["state"], model_wave_inference_complete=model_complete,
        original_model_wave_failure=failure_ref,
        receipt_field_note="completed_receipt is a legacy field/CLI name for the exact profile-input receipt; it does not assert complete model-wave inference",
        rows=2289, canonical_rows=2287, unavailable_canonical_id_rows=2,
        artifact_rows=artifact_rows, profile_artifacts={name: {k: refs[name][k] for k in ["id", "bytes", "sha256"]} for name in PROFILE_NAMES},
        ordered_decoded_artifact_rows_sha256=decoded_hashes, per_week=[row_summary(p, a) for p, a in sorted(periods.items())],
        invariants=dict(strict_codec_shape_and_clock_indices="PASS", exact_owner_decoder_parity="PASS", raw_ratio_and_null_zero_semantics="PASS",
            finite_shrinkage="PASS", own_mix_sums_one_per_group="PASS", every_source_clock_strictly_before_cutoff="PASS",
            original_population_and_two_source_identity_gaps_preserved="PASS", opponent_conditional_residual_metric_names="PRESERVED_UNCHANGED"),
        field_consumption=dict(all_feature_fields=168, consumed_efficiency_fields=142, profile_only_fields=26,
            consumed_names=core.EFFICIENCY_FEATURES, profile_only_names=core.PROFILE_ONLY_FEATURES,
            first_down_tendencies="DESCRIPTIVE_PROFILE_ONLY; NOT EPA_POSITIVE_AND_NOT_A_NEW_PROBABILITY_MODEL"),
        generic_asof_interface=dict(callable="nfl_lab.player_context_rush_efficiency_v1.EfficiencyContext.profile",
            signature=str(signature), inputs=["player", "team", "opponent", "timezone-aware cutoff"],
            prerequisites="Existing context built from admitted source rows with qualified availability clocks; selection requires source availability strictly before cutoff; missing support retains explicit shrinkage prior",
            target_game_outcomes_required=False, profile_calls_in_this_review=0, current_week10_capture_executed=False),
        examples=dict(selection=private["selection"], example_roles=[x["example_role"] for x in examples],
            artifact=private_ref, raw_values_and_real_identities="OWNER_PRIVATE_ONLY",
            readable_public_fixtures=["EFFICIENCY_FICTIONAL_PROFILE_EXAMPLE_V1.json", "EFFICIENCY_FICTIONAL_UNAVAILABLE_PROFILE_EXAMPLE_V2.json"],
            actual_examples_are_not_public_fixtures=True),
        storage=usage, actual=dict(CPU_seconds=time.process_time()-cpu, wall_seconds=time.monotonic()-started,
                                  RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024),
        outcomes_read=0, source_histories_read=0, fitted_models_loaded=0, new_fits=0, new_inference=0,
        new_profile_generation=0, new_source_HTTP=0, production_writes=0)
    STATE["phase"] = "PUBLIC_SAFE_AGGREGATE_INDEX"
    with PUBLIC_PATH.open("xb") as handle:
        handle.write(encode(public)); handle.flush(); os.fsync(handle.fileno())
    signal.alarm(0)
    print(json.dumps(dict(state=public["state"], public_index=str(PUBLIC_PATH.relative_to(ROOT)), rows=2289,
                         private_example_bytes=private_ref["bytes"], new_fits=0, new_inference=0)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--completed-receipt", type=Path, required=True)
    parser.add_argument("--completed-receipt-sha256", required=True)
    args = parser.parse_args()
    try:
        run(args)
    except BaseException as error:
        signal.alarm(0)
        # Never serialize exception text, profile values, identities or histories.
        failure = dict(version=VERSION, state="PROFILE_REVIEW_FAILED_NO_AUTOMATIC_RETRY", phase=STATE["phase"],
                       error_type=type(error).__name__, protocol_sha256=args.protocol_sha256,
                       completed_receipt_sha256=args.completed_receipt_sha256, new_fits=0, new_inference=0,
                       new_source_HTTP=0, target_outcomes_read=0)
        path = OUT / "PROFILE_REVIEW_FAILURE_V1.json"
        if not path.exists():
            with path.open("xb") as handle:
                handle.write(encode(failure)); handle.flush(); os.fsync(handle.fileno())
        print(json.dumps(failure))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
