"""One root-authorized, cached-data-only FTN completion W1--4 join.

No fit, model restoration, source acquisition or native write is implemented.
The accepted scorer and prior timing-confirm arithmetic are reused unchanged.
Original B forecast bytes and A outcomes remain separate immutable evidence.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import datetime
import gzip
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import platform
import resource
import signal
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = 'A-B-FTN-COMPLETION-W1-W4-SAVED-JOIN-v1'
B_NAMESPACE = 'B-FTN-BALL-QUALITY-COMPLETION-v1'
B_COMMIT = 'd79acddf5f094c85001c9b17a525ac7d9e25f9ec'
ARMS = ['B0', 'B1', 'B2']
PRODUCTS = ['mean', 'lower_median', 'P2']
WEEKS = [1, 2, 3, 4]
PHASE = 'NOT_STARTED'


def enc(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def sha(body):
    return hashlib.sha256(body).hexdigest()


def check(value, message):
    if not value:
        raise ValueError(message)


def bound(path, digest, size=None):
    path = Path(path)
    check(not path.is_symlink(), 'Symlink input is not an admitted cache')
    body = path.read_bytes()
    check(sha(body) == digest and (size is None or len(body) == size),
          'Bound input bytes differ: ' + path.name)
    return body


def immutable_write(path, body):
    with Path(path).open('xb') as handle:
        handle.write(body)
        handle.flush()
        os.fsync(handle.fileno())


def run(args):
    global PHASE
    cpu, wall = time.process_time(), time.monotonic()
    sys.dont_write_bytecode = True
    PHASE = 'ROOT_REGISTRATION'
    raw = bound(args.protocol, args.protocol_sha256)
    plan = json.loads(raw)
    check(plan['id'] == VERSION and plan['state'] == 'ROOT_REGISTERED_SCORING_GO'
          and plan['registered_by'] == '/root', 'Exact published scoring GO required')
    check(plan['new_fits'] == plan['new_model_inference'] == plan['native_writes'] == 0,
          'Zero-fit/inference/native-write contract differs')
    check(plan['weeks'] == WEEKS and plan['B_producer_commit'] == B_COMMIT,
          'Exact saved-output comparison differs')
    for path, digest in plan['code_sha256'].items():
        bound(ROOT / path, digest)
    for path, digest in plan['original_source_configs_sha256'].items():
        bound(ROOT / path, digest)
    budget = plan['resources']
    check(budget['CPU_seconds'] == 300 and budget['wall_seconds'] == 600
          and budget['RSS_bytes'] == 3 * 1024**3, 'Finite execution envelope differs')
    resource.setrlimit(resource.RLIMIT_CPU, (280, 300))
    resource.setrlimit(resource.RLIMIT_AS, (budget['RSS_bytes'],) * 2)

    def stop(sig, _):
        if sig == signal.SIGXCPU:
            signal.signal(signal.SIGXCPU, signal.SIG_IGN)
        raise TimeoutError('Bounded saved-output completion comparison')

    signal.signal(signal.SIGXCPU, stop)
    signal.signal(signal.SIGALRM, stop)
    signal.alarm(580)

    def offline(event, _):
        if event in {'socket.connect', 'socket.connect_ex', 'socket.getaddrinfo'}:
            raise RuntimeError('Offline cached evidence only')

    sys.addaudithook(offline)
    for name in ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS']:
        os.environ[name] = '1'
    import numpy as np
    import pandas as pd
    import pyarrow as pa
    runtime = dict(python=platform.python_version(), numpy=np.__version__,
                   pandas=pd.__version__, pyarrow=pa.__version__)
    check(runtime == plan['runtime'], 'Pinned runtime differs')
    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)
    pa.set_memory_pool(pa.system_memory_pool())
    sys.path.insert(0, str(ROOT))
    from tools import timing_confirm_b_completion_join_v1 as shared
    from tools import abc_a_dynamic_carry_wave_v1 as original
    for name, digest in plan['C_bound_code'].items():
        bound(args.c_cache / name, digest)
    sys.path.insert(0, str(args.c_cache))
    common = importlib.import_module('abc_championship_v2')
    check(Path(common.__file__).resolve() == (args.c_cache / 'abc_championship_v2.py').resolve(),
          'Accepted common scorer imported from wrong location')

    PHASE = 'AUTHENTICATED_PRIVATE_SOURCE_CACHE'
    access_raw = bound(args.source_receipt, plan['source_access_receipt_sha256'])
    access = json.loads(access_raw)
    check(access['state'] == 'PASS_EXISTING_A_SOURCE_OWNER_VALIDATION_AND_READBACK'
          and access['registered_by'] == '/root'
          and access['worker_id'] == VERSION,
          'Actual namespace-owner validation/readback receipt required')
    check(access['complete_peer_census_verified'] is True
          and access['all_old_caps_and_reserves_preserved'] is True,
          'Complete shared-lock accounting receipt required')
    _, _, original_refs, _ = original.sources()
    sources = {}
    for name, expected in plan['A_sources'].items():
        check(original_refs[name]['sha256'] == expected['sha256']
              and original_refs[name]['bytes'] == expected['bytes'],
              'Original source metadata differs')
        ref = access['sources'][name]
        check(ref['sha256'] == expected['sha256'] and ref['bytes'] == expected['bytes'],
              'Authenticated cached source differs')
        owner = ref['owner_validation']
        check(owner['owner'] in access['permitted_original_owners']
              and owner['sha256'] == ref['sha256'] and owner['bytes'] == ref['bytes'],
              'Actual source owner did not validate the exact source')
        sources[name] = bound(ref['path'], ref['sha256'], ref['bytes'])

    PHASE = 'PUBLIC_B_SAVED_FORECASTS'
    check(sum(ref['bytes'] for ref in plan['B_forecast_refs']) == 624640,
          'Exact four-packet public-byte envelope differs')
    forecasts, cdfs, inventory = {}, {}, []
    alias_checks, fallback_checks, clock_inventory = 0, 0, []
    alias_fields = ['mean', 'lower_median', 'law', 'features', 'fit_cutoff', 'feature_cutoff',
                    'latest_source_available', 'history_regime', 'feature_memory', 'fallback',
                    'own_prior_games', 'position', 'team', 'opponent', 'season', 'week',
                    'game_id', 'player_id', 'target', 'FTN_information']
    fallback_fields = [field for field in alias_fields if field != 'fallback']
    for ref in plan['B_forecast_refs']:
        body = bound(args.b_cache / ref['id'], ref['sha256'], ref['bytes'])
        packet = json.loads(gzip.decompress(body))
        check(packet['season'] == 2026 and packet['week'] == ref['week']
              and packet['original_issuance'] is False, 'Packet period/issuance differs')
        counts = Counter()
        for row in packet['rows']:
            arm = row['method']
            check(arm in ARMS and row['procedure_id'] == B_NAMESPACE + ':' + arm
                  and row['target'] == 'pass_cmp' and row['position'] == 'QB',
                  'Exact B procedure/target/role differs')
            check(row['season'] == 2026 and row['week'] == ref['week']
                  and row['original_issuance'] is False, 'B row period/issuance differs')
            check(shared.finite(row['fit_cutoff']) and shared.finite(row['feature_cutoff'])
                  and row['fit_cutoff'] <= row['feature_cutoff'], 'B origin clock invalid')
            check(row.get('latest_source_available') is None
                  or row['latest_source_available'] < row['feature_cutoff'],
                  'B source availability is not strictly earlier')
            check(row['history_regime'] == 'H-RECENT' and row['feature_memory'] == '2022_EXPANDING',
                  'B history identity differs')
            check(row['source_vintage'] == plan['B_source_vintage'], 'B source-vintage tier differs')
            if arm == 'B0':
                check(row['reused_original_procedure_id'] == 'B-QB-OPPORTUNITY-PROFILE-INCREMENT-v1:R3'
                      and row['new_inference'] is False, 'B0 is not the exact retained R3 output contract')
            check(all(shared.finite(row[key]) and row[key] >= 0 for key in ['mean', 'lower_median']),
                  'Invalid saved count point')
            key = arm, str(row['game_id']), str(row['player_id'])
            check(key not in forecasts, 'Duplicate B arm/player-game')
            forecasts[key] = row
            cdfs[key] = shared.law_prepare(row['law'], row['mean'], row['lower_median'])
            counts[arm] += 1
        check(len(set(counts.values())) == 1 and set(counts) == set(ARMS), 'B arms have unequal support')
        inventory.append(dict(week=ref['week'], bytes=len(body), sha256=sha(body), arm_rows=dict(counts)))
        clock_inventory.append(dict(week=ref['week'], fit_cutoff=packet['fit_cutoff'],
                                    actual_persisted_UTC=packet['actual_persisted_UTC'],
                                    original_issuance=False))
    for (arm, game, player), row in forecasts.items():
        base = forecasts.get(('B0', game, player))
        check(base is not None, 'B0 counterpart missing')
        if arm == 'B1':
            check(row['support_alias_of'] == B_NAMESPACE + ':B0'
                  and all(row.get(field) == base.get(field) for field in alias_fields),
                  'B1 support alias changed outputs or information contract')
            alias_checks += 1
        if arm == 'B2' and row.get('fallback') == 'B0_INCOMPLETE_FTN_SOURCE':
            check(all(row.get(field) == base.get(field) for field in fallback_fields),
                  'Incomplete FTN source did not preserve exact B0 fallback')
            fallback_checks += 1

    PHASE = 'QUALIFIED_A_OFFERS_OUTCOMES_AND_RETAINED_CONTROLS'
    with zipfile.ZipFile(io.BytesIO(sources['frozen_bundle'])) as archive:
        a_body = archive.read('FORECASTS.parquet')
        check(sha(a_body) == plan['A_forecast_member_sha256'], 'A saved forecast member differs')
        af = pd.read_parquet(io.BytesIO(a_body))
    af = af.loc[af.target.eq('pass_cmp') & af.season.eq(2026) & af.week.isin(WEEKS)].copy()
    check(not af.duplicated(['method', 'product', 'season', 'game_id', 'player_id']).any(),
          'A retained control identity ambiguous')
    with zipfile.ZipFile(io.BytesIO(sources['offers'])) as archive:
        offers = pd.read_parquet(io.BytesIO(archive.read(original_refs['offers']['member'])))
    with zipfile.ZipFile(io.BytesIO(sources['qualified_labels'])) as archive:
        labels = pd.read_parquet(io.BytesIO(archive.read(original_refs['qualified_labels']['member'])))
    board = offers.loc[offers.target.eq('pass_cmp') & offers.season.eq(2026)
                       & offers.week.isin(WEEKS) & offers.source_stream.eq('ANNUAL_NAMED_NJ')].copy()
    check(len(board) == 84 and board.groupby('week').size().to_dict() == {1: 10, 2: 25, 3: 26, 4: 23},
          'Retained early-week completion offer population differs')
    check(not board.duplicated(['season', 'game_id', 'player_id']).any()
          and not board.opportunity_key.duplicated().any(), 'A primary offers ambiguous')
    labels = labels.loc[labels.target.eq('pass_cmp') & labels.season.eq(2026) & labels.week.isin(WEEKS)]
    check(not labels.duplicated(['season', 'game_id', 'player_id']).any(), 'A qualified labels ambiguous')
    label_map = {(str(row.game_id), str(row.player_id)): row for row in labels.itertuples()}
    a_ids = ['A::' + method + '::' + output for method, output in plan['A_products']]
    b_ids = [B_NAMESPACE + ':' + arm + '::' + output for arm in ARMS for output in PRODUCTS]
    ids = a_ids + b_ids + ['ALWAYS_OVER', 'ALWAYS_UNDER']
    check(ids == plan['candidate_ids'], 'Registered product identities differ')
    a_values, provenance = {}, {}
    for cid, (method, output) in zip(a_ids, plan['A_products']):
        subset = af.loc[af.method.eq(method) & af['product'].eq(output)]
        a_values[cid] = {(str(row['game_id']), str(row['player_id'])): row for row in subset.to_dict('records')}
        fields = [key for key in ['output_procedure_version', 'source_forecast_sha256',
                  'source_forecast_member_sha256', 'source_information_policy', 'source_issue_time_UTC'] if key in subset]
        provenance[cid] = dict(method=method, product=output, rows=len(subset),
            state='RETAINED' if len(subset) else 'NOT_RETAINED',
            bindings=[{key: None if pd.isna(value) else str(value) for key, value in row.items()}
                      for row in subset[fields].drop_duplicates().to_dict('records')])
    vectors = {cid: [] for cid in ids}
    common_mask, strict_mask, members = set(), set(), []
    cached_actual_conflicts = Counter()
    conflict_hashes = []
    private_offers, private_labels = [], []

    def source_scalar(value):
        """Keep source-clock representation and exceptional states in private proof."""
        if value is None or type(value) in (str, int, bool):
            return value
        if type(value) is float:
            return value if shared.finite(value) else dict(source_state='NONFINITE', representation=str(value))
        if value is pd.NA or value is pd.NaT:
            return dict(source_state='MISSING', representation=type(value).__name__)
        if hasattr(value, 'item'):
            return source_scalar(value.item())
        if hasattr(value, 'isoformat'):
            return dict(source_type=type(value).__name__, value=value.isoformat())
        if type(value).__module__ == 'decimal':
            return dict(source_type='Decimal', value=str(value))
        raise TypeError('Unsupported source-contract scalar type: ' + type(value).__name__)

    def match(row, offer, owner, canonical=True):
        if row is None:
            return 'MISSING_' + owner + '_RETAINED_CANONICAL_QB_GAME'
        if row['position'] != offer['position']:
            return owner + '_ROLE_MISMATCH'
        normalize = shared.team if canonical else str
        if any(normalize(row[key]) != normalize(offer[key]) for key in ['team', 'opponent']):
            return owner + '_TEAM_OPPONENT_MISMATCH'
        for key in ['kickoff_utc', 'cutoff_utc']:
            offered = pd.Timestamp(offer[key])
            forecast = pd.Timestamp(row[key]) if owner == 'A' else pd.Timestamp(row['feature_cutoff'], unit='s', tz='UTC')
            if offered.tzinfo is None or forecast.tzinfo is None or offered != forecast:
                return owner + '_EXACT_' + key.upper() + '_MISMATCH'
        return None

    PHASE = 'FROZEN_OWN_SIDE_JOIN_AND_ACCEPTED_GRADING'
    for offer in board.to_dict('records'):
        check(offer['position'] == 'QB' and shared.finite(float(offer['line'])), 'Offer role/line differs')
        key = str(offer['game_id']), str(offer['player_id'])
        label = label_map.get(key)
        if label is not None:
            check(all(str(getattr(label, field)) == str(offer[field]) for field in ['season', 'week', 'game_id', 'player_id', 'position', 'target'])
                  and all(shared.team(getattr(label, field)) == shared.team(offer[field]) for field in ['team', 'opponent']),
                  'Qualified label identity/role/team/period differs from offer')
            label_kickoff, offer_kickoff = pd.Timestamp(label.kickoff_utc), pd.Timestamp(offer['kickoff_utc'])
            check(label_kickoff.tzinfo is not None and offer_kickoff.tzinfo is not None
                  and label_kickoff == offer_kickoff, 'Qualified label event clock differs from offer')
        private_offers.append({field: source_scalar(value) for field, value in offer.items()})
        private_labels.append(dict(opportunity_key=str(offer['opportunity_key']),
            label=None if label is None else {field: source_scalar(value) for field, value in label._asdict().items()}))
        participation = getattr(label, 'participation_state', None)
        appearance = ('PENDING' if getattr(label, 'outcome_state', None) == 'pending' else
                      'DNP' if str(participation).lower() == 'dnp' else
                      'PLAYED' if participation == 'played' else 'UNKNOWN')
        actual = getattr(label, 'actual', None)
        actual = (float(actual) if appearance == 'PLAYED' and shared.finite(actual)
                  and actual >= 0 and actual == int(actual) else None)
        if actual is not None:
            check(getattr(label, 'label_reason', None) in ['EXPLICIT_REPORTED_ZERO', 'EXPLICIT_REPORTED_VALUE']
                  and bool(getattr(label, 'participation_evidence', None)), 'Outcome metric presence unsupported')
        b_rows = {arm: forecasts.get((arm, *key)) for arm in ARMS}
        reasons = {arm: match(b_rows[arm], offer, 'B') for arm in ARMS}
        if all(reason is None for reason in reasons.values()):
            common_mask.add(str(offer['opportunity_key']))
        if all(match(b_rows[arm], offer, 'B', canonical=False) is None for arm in ARMS):
            strict_mask.add(str(offer['opportunity_key']))
        for arm, row in b_rows.items():
            if row is not None:
                check(row['week'] == int(offer['week']), 'B forecast target week differs')
                if actual is not None and shared.finite(row.get('actual')) and row['actual'] != actual:
                    cached_actual_conflicts[arm] += 1
                    conflict_hashes.append(sha(enc([arm, *key])))
        for cid in ids:
            point = probability = side = fallback = reason = own_no_history = clock = age = None
            if cid in a_ids:
                row = a_values[cid].get(key)
                reason = match(row, offer, 'A')
                if reason is None:
                    point = float(row['prediction']) if shared.finite(row['prediction']) else None
                    reason = None if point is not None else 'A_POINT_UNAVAILABLE'
                    fallback = None if pd.isna(row['fallback']) else str(row['fallback'])
                    clock = str(row['cutoff_utc'])
                side = shared.point_side(point, offer['line'])
            elif cid in b_ids:
                arm, output = cid.removeprefix(B_NAMESPACE + ':').split('::')
                row, reason = b_rows[arm], reasons[arm]
                if reason is None:
                    probability = shared.probabilities(cdfs[(arm, *key)], float(offer['line']))
                    point = None if output == 'P2' else row[output]
                    side = shared.probability_side(probability) if output == 'P2' else shared.point_side(point, offer['line'])
                    fallback, own_no_history, clock = row.get('fallback'), row.get('own_prior_games') == 0, row['feature_cutoff']
                    age = row.get('source_age_days')
            else:
                side = cid.removeprefix('ALWAYS_')
            result_row = dict(season=2026, week=int(offer['week']), game_id=key[0], player_id=key[1],
                category='pass_cmp', comparator='STRICT_OVER_UNDER', line=float(offer['line']), actual=actual,
                appearance=appearance, point=point, selected_side=side, candidate_id=cid,
                opportunity_key=str(offer['opportunity_key']), source_stream=str(offer['source_stream']),
                fallback=fallback, unavailability_reason=reason, no_own_history=own_no_history,
                source_age_days=age, **(probability or {}))
            result_row['status'] = shared.grade(result_row)
            check(common.status(result_row) == result_row['status'], 'Accepted and independent grades differ')
            vectors[cid].append(result_row)
            members.append([cid, result_row['opportunity_key'], str(offer['line']), str(offer['source_stream']),
                            str(offer['source_sha256']), str(offer['quote_timing_status']), point, probability,
                            appearance, actual, side, result_row['status'], clock])

    PHASE = 'FIXED_FULL_AND_COMMON_POPULATION_AGGREGATES'
    full_mask = set(map(str, board.opportunity_key))
    summaries, contrasts = [], []
    for view, mask in [('FULL_A_EARLY_BOARD', full_mask), ('COMMON_ALL_THREE_B_ARMS', common_mask),
                       ('QUALIFIED_TEAM_ALIAS_SUBGROUP', common_mask - strict_mask)]:
        selected_vectors = {cid: [row for row in rows if row['opportunity_key'] in mask]
                            for cid, rows in vectors.items()}
        for cid, rows in selected_vectors.items():
            for week in ['ALL'] + list(range(1, 10)):
                selected = [row for row in rows if week == 'ALL' or row['week'] == week]
                ages = [row['source_age_days'] for row in selected if shared.finite(row['source_age_days'])]
                summaries.append(dict(candidate_id=cid, view=view, source_panel='ANNUAL_NAMED_NJ',
                    week_view=week, **common.summary(selected), numerical=shared.numerical(selected),
                    probability=shared.probscores(selected),
                    scored_season_weeks=sorted({(row['season'], row['week']) for row in selected if row['status'] in ['WIN', 'LOSS']}),
                    unavailable_reasons=dict(Counter(row['unavailability_reason'] for row in selected if row['unavailability_reason'])),
                    fallback_states=dict(Counter(str(row['fallback']) for row in selected)),
                    no_own_history_queries=sum(row['no_own_history'] is True for row in selected),
                    source_age_known=len(ages), source_age_unknown=sum(row['source_age_days'] is None for row in selected if cid in b_ids),
                    source_age_min_days=min(ages) if ages else None, source_age_max_days=max(ages) if ages else None,
                    eligible_mask_sha256=shared.mask(selected), decided_mask_sha256=shared.mask(selected, True),
                    probability_scope='SAME_STORED_COMPLETION_LAW_AUXILIARY' if cid in b_ids else 'POINT_ONLY_NO_PROBABILITY',
                    source_clock_tier='CURRENT_VINTAGE_SEVEN_DAY_RECONSTRUCTION;QUOTE_TIMING_UNVERIFIED',
                    admission='FOUR_WEEK_EXTENSION_ONLY;NO_AUTOMATIC_PRIMARY_SWITCH'))
        for left, right in plan['paired_candidate_ids']:
            check(left in ids and right in ids and left != right, 'Registered paired product invalid')
            contrasts.append(dict(view=view, source_panel='ANNUAL_NAMED_NJ', left=left, right=right,
                                  **shared.paired(selected_vectors[left], selected_vectors[right], np)))
    source_counts = [dict(week=week, eligible=int((board.week == week).sum()),
        games=int(board.loc[board.week == week, 'game_id'].nunique()),
        state='SCORED_IN_THIS_JOIN' if week in WEEKS else 'NOT_IN_THIS_W1_W4_JOIN',
        source_tier='ANNUAL_ACTUAL_RETAINED_LINE_QUOTE_TIMING_UNVERIFIED' if week in WEEKS else 'NOT_CLAIMED')
        for week in range(1, 10)]
    private_packet = dict(id=VERSION, state='PRIVATE_COMPLETE_JOINED_OWN_SIDE_AND_SOURCE_PROOF',
        protocol_sha256=sha(raw), source_access_receipt_sha256=sha(access_raw),
        A_source_bindings=plan['A_sources'], A_forecast_member_sha256=plan['A_forecast_member_sha256'],
        B_forecast_inventory=inventory, candidate_ids=ids, vectors=vectors,
        original_offer_contracts=private_offers, qualified_label_bindings=private_labels,
        clock_scope='All original retained offer fields and source representations preserved; null/nonfinite/naive-clock states not upgraded.',
        restrictions='PRIVATE_A_OWNER_LOCAL_ONLY; no raw/protected rows or this packet in public GitHub; root-managed original allocation.',
        marginal_law='Standalone completion law only; no new attempt-completion joint coherence claim.')
    private_body = gzip.compress(enc(private_packet), mtime=0)
    check(len(private_body) <= budget['private_vectors_max_bytes'], 'Private vector reservation exceeded')
    private_ref = dict(bytes=len(private_body), sha256=sha(private_body), rows=sum(map(len, vectors.values())),
                       opportunities=len(private_offers), file=args.private_vectors.name,
                       scope='PRIVATE_A_OWNER_LOCAL_ONLY_NOT_PUBLIC')
    result = dict(id=VERSION, state='COMPLETED_OWNER_LOCAL_SAVED_FTN_COMPLETION_JOIN',
        UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(), protocol_sha256=sha(raw),
        B_producer_commit=B_COMMIT, B_current_discovery_HEAD=plan['B_current_discovery_HEAD'],
        B_forecast_inventory=inventory, B_clock_inventory=clock_inventory,
        B1_alias_proof=dict(state='PASS_EXACT_OUTPUT_AND_INPUT_CONTRACT_ALIAS', rows=alias_checks, fields=alias_fields,
                            independent_fitted_procedure=False),
        B2_incomplete_source_fallback_proof=dict(rows=fallback_checks, state='PASS_EXACT_B0_OUTPUT_FALLBACK'),
        B0_reuse_scope='Exact row original-procedure/new-inference flags plus immutable B code/protocol lineage; no duplicate old forecast decode or independent old-law parity claim.',
        A_source_bindings=plan['A_sources'], A_forecast_member_sha256=plan['A_forecast_member_sha256'],
        source_access_receipt_sha256=sha(access_raw), A_product_provenance=provenance,
        candidate_ids=ids, eligible_A_offers=len(board), eligible_A_games=int(board.game_id.nunique()),
        common_all_B_offers=len(common_mask), A_early_source_inventory=source_counts,
        summaries=summaries, paired=contrasts,
        private_vectors=private_ref,
        B_cached_actual_disagreements=dict(cached_actual_conflicts), B_cached_actual_conflict_case_hashes=sorted(set(conflict_hashes)),
        full_A_mask_sha256=sha(enc(sorted(full_mask))), common_B_mask_sha256=sha(enc(sorted(common_mask))),
        strict_team_text_common_mask_sha256=sha(enc(sorted(strict_mask))), membership_sha256=sha(enc(sorted(members))),
        evidence_tier=plan['evidence_tier'], rules=plan['rules'],
        outcome_policy='Frozen forecasts regraded only on original bound presence-qualified A outcomes; original B forecasts/grades preserved; cached conflicts separately counted.',
        uncertainty='Unchanged timing-confirm game/week cluster bootstrap; four exposed week clusters, repeated players and prior model selection limit interpretation.',
        resources=dict(CPU_seconds=time.process_time() - cpu, wall_seconds=time.monotonic() - wall,
                       RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024),
        counts=dict(new_fits=0, new_model_inference=0, model_loading=0, source_acquisition=0,
                    native_writes=0, new_NFL_games=0, original_issued_picks=0, production_writes=0))
    body = gzip.compress(enc(result), mtime=0)
    check(len(body) <= budget['compressed_result_max_bytes'], 'Registered aggregate reservation exceeded')
    check(len(body) + len(private_body) + sum(ref['bytes'] for ref in plan['B_forecast_refs'])
          <= budget['new_private_result_and_receipts_limit_bytes'], 'Result/vector/cache total exceeds declared private cap')
    immutable_write(args.private_vectors, private_body)
    immutable_write(args.output, body)
    signal.alarm(0)
    print(json.dumps(dict(state=result['state'], A_offers=len(board), B_common=len(common_mask),
                          bytes=len(body), sha256=sha(body), resources=result['resources'])))


def main():
    parser = argparse.ArgumentParser()
    for name in ['protocol', 'b-cache', 'c-cache', 'source-receipt', 'output', 'private-vectors']:
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--protocol-sha256', required=True)
    args = parser.parse_args()
    check(not args.output.exists() and not args.private_vectors.exists(), 'Immutable result or vectors already exist')
    try:
        run(args)
    except BaseException as error:
        signal.alarm(0)
        failure = dict(id=VERSION, state='FAILED_NO_AUTOMATIC_RETRY', phase=PHASE,
            UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(), error_type=type(error).__name__,
            error_sha256=sha(str(error).encode()), new_fits=0, model_loading=0, new_model_inference=0,
            source_acquisition=0, native_writes=0,
            CPU_seconds=resource.getrusage(resource.RUSAGE_SELF).ru_utime + resource.getrusage(resource.RUSAGE_SELF).ru_stime,
            RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024)
        immutable_write(args.output.with_name('FAILED_' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json'), enc(failure))
        print(enc(failure).decode())
        raise


if __name__ == '__main__':
    main()
