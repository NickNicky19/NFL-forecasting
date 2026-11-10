"""Prepared A owner-local replay of public B ATT points; no fit or private write.

Run only with the integrator's published, exact-byte protocol and GO. The source
board is the original A base.sources() offers plus qualified labels. All row
identities remain in memory; only aggregates and deterministic hashes are saved.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import datetime
from decimal import Decimal
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
VERSION = 'PLAYER-CONTEXT-COMPLETION-DECISION-01-A-B-ATT-JOIN-v1'
B_COMMIT = '2fa855fc4dd7e9e495126dea93ba90a33fee4be3'
B_PROCEDURE = 'B-player-context-matchup-01-v1:COMMON_EXPOSURE'
ALLOCATION = 'f123cd5ffd6f4a204a76c68bf63817cce63cecd7021543a23503d0233cc3eb26'
A_OFFERS = 'f224f17930e8da7ed5683808de3339d9656cc4b71edb0deefcfb9c48dfd82ffb'
A_LABELS = '61da98ad90542b07c6c6664b674086ba4f9474e597325aba62dec44bb2fa72f5'
A_FROZEN = '753970f359a5089286dde4c7ace6eeeb02c82b59eed07a50fd8ecc797eec8c33'
A_MEMBER = '7d849d60902a2aa0a4922dd1ba0d09d4e0a21290cb5121e48279c6f54349e23f'
PRODUCTS = ['mean', 'lower_median']
A_PRODUCTS = [('COUNT_A_LEGACY_POINT', 'legacy_empirical_point'),
              ('COUNT_A_MEAN', 'mean_objective_point'),
              ('LEAF_CDF', 'mean'), ('LEAF_CDF', 'median'),
              ('HGB_MAE_DIRECT', 'mae_objective_point')]
A_IDS = ['A::' + method + '::' + product for method,product in A_PRODUCTS]
B_IDS = [B_PROCEDURE + '::' + product for product in PRODUCTS]
CONSTANT_IDS = ['ALWAYS_OVER', 'ALWAYS_UNDER']
CANDIDATE_IDS = A_IDS + B_IDS + CONSTANT_IDS
PAIRED_IDS = [[a,b] for a in A_IDS for b in B_IDS] + [[a,b] for a in A_IDS+B_IDS for b in CONSTANT_IDS] + [[B_IDS[1], B_IDS[0]]]
REQUESTED = list(range(1, 9))
SCORED_SCOPE = list(range(1, 6))
EVIDENCE = 'CURRENT_VINTAGE_STRICT_7DAY_RECONSTRUCTION;QUOTE_TIMING_UNVERIFIED_ACTUAL_LINE_DIAGNOSTIC;EXPOSED_DEVELOPMENT'
POINT_TYPES = {'mean': 'GAMMA_POISSON_CONDITIONAL_EXPECTED_COUNT',
               'lower_median': 'LOWER_MEDIAN_OF_SAME_GAMMA_POISSON_LAW'}
B_REFS = [
    (1, 169479, 'de568cc6242b1469056737311fd86fea4888893e864b977c97935a41234eef96'),
    (2, 179736, '4216ed10c2817dc6c1d47ebcfbfd086b522c556da1df53cd07281a4e9f1b2bce'),
    (3, 168616, '6482e01fc170205af25a0d0b599016636ef29858afd637a57c317ec1368ad073'),
    (4, 156735, '40dc188593ecce049eb51b48cd7fdb1ce9ed972f93e697d3085ef3f4f22176f1'),
    (5, 166434, '4c916ef15c8ea47d998087c76ab44cb10b94508c1024f61219ea720b7769b7fc'),
    (6, 138634, '5a996056a1e6addef104549534f33b142d93cf32968fe4476a04e90b64ec6db8'),
    (7, 147302, 'ba96c0a93573039fe8c83f72d9e478d3531087de51f0b6571b280b688dc21e19'),
    (8, 162215, 'e2c0b595c9f84ff91067b2f516ec30e9549b6868f84fbadc03f5eb5b11c0a2e8'),
]
STATE = {'phase': 'NOT_STARTED'}


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def digest(body):
    return hashlib.sha256(body).hexdigest()


def pin(path, expected, size=None):
    body = Path(path).read_bytes()
    if digest(body) != expected or (size is not None and len(body) != size):
        raise ValueError('exact bound artifact bytes differ')
    return body


def finite(value):
    return type(value) in [int, float] and math.isfinite(value)


def point_side(point, line):
    if point is None:
        return None
    a, b = Decimal(str(point)), Decimal(str(line))
    return 'OVER' if a > b else 'UNDER' if a < b else 'ABSTAIN'


def independent_status(row):
    side = row['selected_side']
    if side is None:
        return 'UNAVAILABLE_FORECAST'
    if side == 'ABSTAIN':
        return 'ABSTAIN'
    appearance = row['appearance']
    if appearance != 'PLAYED':
        return {'DNP': 'DNP', 'PENDING': 'PENDING'}.get(appearance, 'UNKNOWN_PARTICIPATION')
    if row['actual'] is None:
        return 'MISSING_ACTUAL'
    a, line = Decimal(str(row['actual'])), Decimal(str(row['line']))
    if a == line:
        return 'PUSH'
    return 'WIN' if (a > line) == (side == 'OVER') else 'LOSS'


def mask(rows, decided=False):
    return digest(encoded(sorted(r['opportunity_key'] for r in rows
                                 if not decided or r['status'] in ['WIN', 'LOSS'])))


def paired(left, right, np):
    lookup = {r['opportunity_key']: r for r in right}
    if len(lookup) != len(right):
        raise ValueError('ambiguous paired opportunity')
    pairs = [(r, lookup[r['opportunity_key']]) for r in left
             if r['status'] in ['WIN', 'LOSS'] and lookup[r['opportunity_key']]['status'] in ['WIN', 'LOSS']]
    games = defaultdict(list)
    for a, b in pairs:
        games[a['game_id']].append(int(a['status'] == 'WIN') - int(b['status'] == 'WIN'))
    weeks = defaultdict(list)
    for a, b in pairs:
        weeks[a['week']].append(int(a['status'] == 'WIN') - int(b['status'] == 'WIN'))
    def block_interval(groups):
        if len(groups) < 2:
            return None
        gg = [groups[k] for k in sorted(groups)]
        sizes = np.array([len(x) for x in gg]); changes = np.array([sum(x) for x in gg])
        rng = np.random.default_rng(20261110)
        ix = rng.integers(0, len(gg), (500, len(gg)))
        return list(map(float, np.quantile(changes[ix].sum(axis=1) / sizes[ix].sum(axis=1), [.025, .975])))
    interval = block_interval(games)
    return {'common_decided': len(pairs), 'left_wins': sum(a['status'] == 'WIN' for a,b in pairs),
            'right_wins': sum(b['status'] == 'WIN' for a,b in pairs),
            'win_change': sum(int(a['status'] == 'WIN') - int(b['status'] == 'WIN') for a,b in pairs),
            'side_disagreements': sum(a['selected_side'] != b['selected_side'] for a,b in pairs),
            'game_clusters': len(games), 'week_clusters': len({a['week'] for a,b in pairs}),
            'paired_accuracy_change_interval95': interval,
            'paired_week_block_accuracy_change_interval95': block_interval(weeks),
            'common_mask_sha256': mask([a for a,b in pairs]),
            'uncertainty': 'Nominal game bootstrap500 seed20261110; few exposed weeks and multiplicity unadjusted'}


def run(args):
    started, cpu = time.monotonic(), time.process_time()
    resource.setrlimit(resource.RLIMIT_CPU, (250, 250))
    resource.setrlimit(resource.RLIMIT_AS, (3 * 1024**3, 3 * 1024**3))
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('registered600secondwallcap')))
    signal.alarm(600)
    STATE['phase'] = 'REGISTRATION'
    protocol_raw = pin(args.protocol, args.protocol_sha256)
    plan = json.loads(protocol_raw)
    if plan.get('assignment_id') != 'PLAYER-CONTEXT-COMPLETION-DECISION-01':
        raise ValueError('incorrect assignment registration')
    spec = plan['qb_join']
    if spec.get('enabled') is not True or spec.get('GO') != VERSION:
        raise ValueError('exact published A ATT join GO required')
    if spec.get('private_writes') != 0 or spec.get('new_fits') != 0 or spec.get('new_inference') != 0:
        raise ValueError('zero fit/inference/private-write scope required')
    if spec.get('scored_weeks') != SCORED_SCOPE or spec.get('requested_weeks') != REQUESTED:
        raise ValueError('registered week scope differs')
    if spec.get('candidate_ids') != CANDIDATE_IDS or spec.get('paired_candidate_ids') != PAIRED_IDS:
        raise ValueError('finite candidate/comparison registration differs')
    if spec.get('A_frozen_bundle_sha256') != A_FROZEN or spec.get('A_forecast_member_sha256') != A_MEMBER:
        raise ValueError('registered A retained controls source differs')
    if spec.get('bootstrap_replicates') != 500 or spec.get('bootstrap_seed') != 20261110:
        raise ValueError('registered finite bootstrap differs')
    own = str(Path(__file__).resolve().relative_to(ROOT))
    bindings = plan['code_sha256']
    if own not in bindings:
        raise ValueError('executed code is not registration-bound')
    for path, sha in bindings.items():
        pin(ROOT / path, sha)
    if sys.executable != '/workspace/nfl-venv/bin/python':
        raise ValueError('approved existing runtime required')
    for name in ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS']:
        os.environ[name] = '1'
    import numpy as np
    import pandas as pd
    import pyarrow as pa
    pa.set_cpu_count(1); pa.set_io_thread_count(1); pa.set_memory_pool(pa.system_memory_pool())
    cache = Path(args.c_code_cache)
    for ref in spec['C_bound_code']:
        pin(cache / Path(ref['path']).name, ref['sha256'])
    sys.path.insert(0, str(cache))
    common = importlib.import_module('abc_championship_v2')
    STATE['phase'] = 'PUBLIC_RETAINED_OUTPUT_VALIDATION'
    forecasts = {}; public_inventory = []
    if sum(size for week,size,sha in B_REFS) > 8 * 1024**2:
        raise ValueError('public derived cache cap exceeded')
    for week, size, sha in B_REFS:
        raw = pin(Path(args.b_public_cache) / f'2026-W{week:02}.json.gz', sha, size)
        packet = json.loads(gzip.decompress(raw))
        if packet['season'] != 2026 or packet['week'] != week or packet['original_issuance'] is not False:
            raise ValueError('B origin identity/issuance contract differs')
        rows = [r for r in packet['rows'] if r['target'] == 'pass_att']
        for r in rows:
            if r['method'] != 'COMMON_EXPOSURE' or r['procedure_id'] != B_PROCEDURE or r['position'] != 'QB':
                raise ValueError('unexpected B attempt procedure or role')
            if r['season'] != 2026 or r['week'] != week or r['original_issuance'] is not False:
                raise ValueError('B row origin differs')
            if not finite(r['fit_cutoff']) or not finite(r['feature_cutoff']) or r['fit_cutoff'] > r['feature_cutoff']:
                raise ValueError('B fit/query horizon order differs')
            if r['latest_source_available'] is not None and not r['latest_source_available'] < r['feature_cutoff']:
                raise ValueError('B retained source reaches target horizon')
            if any(not finite(r[p]) or r[p] < 0 for p in PRODUCTS):
                raise ValueError('B count points unavailable or invalid')
            law = r['law']
            if law['kind'] != 'gamma_poisson_count' or law['mean'] != r['mean'] or not finite(law['shape']) or law['shape'] <= 0:
                raise ValueError('B output law contract differs')
            key = (2026, str(r['game_id']), str(r['player_id']))
            if key in forecasts:
                raise ValueError('duplicate B retained ATT player-game')
            forecasts[key] = r
        public_inventory.append({'week': week, 'ATT_saved_player_games': len(rows), 'sha256': sha, 'bytes': size})
    STATE['phase'] = 'ORIGINAL_STORE_READONLY_GATE'
    import nfl_lab
    from tools import abc_a_dynamic_carry_wave_v1 as base
    from tools import category_topfive_matched12_storage_v1 as storage
    store, _ = storage.open_store(ROOT, allocation_sha256=ALLOCATION, root_go=storage.GO, readonly=True)
    # Attaching the original read-only guarded store precedes private source reads.
    # No constructor, transaction, _require, recovery, root registration or write.
    b, c, g, fr = base.sources()
    if g['offers']['sha256'] != A_OFFERS or g['qualified_labels']['sha256'] != A_LABELS or g['frozen_bundle']['sha256'] != A_FROZEN:
        raise ValueError('original approved A source binding differs')
    STATE['phase'] = 'ORIGINAL_QUALIFIED_SOURCE_READ'
    with zipfile.ZipFile(io.BytesIO(base.pin(g['frozen_bundle']))) as z:
        ar = z.read('FORECASTS.parquet')
        if digest(ar) != A_MEMBER or json.loads(z.read('MEMBER_MANIFEST.json'))['FORECASTS.parquet']['sha256'] != A_MEMBER:
            raise ValueError('original A retained forecast member differs')
        a_forecasts = pd.read_parquet(io.BytesIO(ar))
    a_forecasts = a_forecasts.loc[a_forecasts.target.eq('pass_att') & a_forecasts.season.eq(2026)
                                  & a_forecasts.week.isin(SCORED_SCOPE)].copy()
    if a_forecasts.duplicated(['method', 'product', 'season', 'game_id', 'player_id']).any():
        raise ValueError('original A retained ATT product identity ambiguous')
    avectors = {}; aprovenance = {}
    provenance_fields = ['output_procedure_version', 'source_forecast_sha256', 'source_forecast_member_sha256',
                         'source_information_policy', 'source_issue_time_UTC']
    for cid, (method, product) in zip(A_IDS, A_PRODUCTS):
        af = a_forecasts.loc[a_forecasts.method.eq(method) & a_forecasts['product'].eq(product)]
        avectors[cid] = {(int(r['season']), str(r['game_id']), str(r['player_id'])): r for r in af.to_dict('records')}
        present = [f for f in provenance_fields if f in af.columns]
        aprovenance[cid] = {'method': method, 'product': product, 'retained_source_rows': len(af),
            'state': 'RETAINED_PRODUCT' if len(af) else 'NOT_RETAINED_IN_THIS_EXACT_SOURCE',
            'source_bindings': [{k: None if pd.isna(v) else str(v) for k,v in r.items()}
                                for r in af[present].drop_duplicates().to_dict('records')]}
    with zipfile.ZipFile(io.BytesIO(base.pin(g['offers']))) as z:
        offers = pd.read_parquet(io.BytesIO(z.read(g['offers']['member'])))
    with zipfile.ZipFile(io.BytesIO(base.pin(g['qualified_labels']))) as z:
        labels = pd.read_parquet(io.BytesIO(z.read(g['qualified_labels']['member'])))
    inventory = []
    for target in ['pass_att', 'pass_cmp']:
        for week in REQUESTED:
            rr = offers.loc[offers.target.eq(target) & offers.season.eq(2026) & offers.week.eq(week)]
            inventory.append({'target': target, 'week': week, 'retained_A_primary_offers': len(rr),
                'games': int(rr.game_id.nunique()), 'source_panels': dict(Counter(map(str, rr.source_stream))),
                'state': 'RETAINED_A_BOARD' if len(rr) else 'NO_ROW_IN_THIS_EXACT_A_BUNDLE_NOT_PROOF_OF_SOURCE_ABSENCE'})
    board = offers.loc[offers.target.eq('pass_att') & offers.season.eq(2026) & offers.week.isin(SCORED_SCOPE)].copy()
    if board.duplicated(['season', 'game_id', 'player_id']).any() or board.opportunity_key.isna().any() or board.opportunity_key.duplicated().any():
        raise ValueError('original A primary board ambiguous')
    ll = labels.loc[labels.target.eq('pass_att') & labels.season.eq(2026) & labels.week.isin(SCORED_SCOPE)]
    if ll.duplicated(['season', 'game_id', 'player_id']).any():
        raise ValueError('A qualified label identity ambiguous')
    lm = {(int(r.season), str(r.game_id), str(r.player_id)): r for r in ll.itertuples()}
    rows = []; memberships = []; missing = Counter(); b_available = set()
    def source_match_reason(forecast, offer, producer):
        if forecast is None:
            return 'MISSING_' + producer + '_RETAINED_CANONICAL_QB_GAME'
        if str(forecast['position']) != str(offer['position']):
            return producer + '_POSITION_CONTRACT_MISMATCH'
        for field in ['team', 'opponent']:
            if field in offer and str(forecast[field]) != str(offer[field]):
                return producer + '_TEAM_OPPONENT_CONTRACT_MISMATCH'
        for field in ['kickoff_utc', 'cutoff_utc']:
            if field not in offer or pd.isna(offer[field]):
                return 'A_ORIGINAL_QUERY_CLOCK_MISSING'
            oq = pd.Timestamp(offer[field])
            fq = pd.Timestamp(forecast[field]) if producer == 'A' else pd.Timestamp(forecast['feature_cutoff'], unit='s', tz='UTC')
            if oq.tzinfo is None or fq.tzinfo is None or oq != fq:
                return producer + '_EXACT_QUERY_' + field.upper() + '_MISMATCH'
        return None
    STATE['phase'] = 'ATT_POINT_REPLAY'
    for o in board.to_dict('records'):
        if o['position'] != 'QB' or not finite(float(o['line'])):
            raise ValueError('original ATT role/threshold contract differs')
        key = (int(o['season']), str(o['game_id']), str(o['player_id']))
        label, forecast = lm.get(key), forecasts.get(key)
        state = getattr(label, 'participation_state', None)
        appearance = ('PENDING' if getattr(label, 'outcome_state', None) == 'pending' else
                      'DNP' if str(state).lower() == 'dnp' else 'PLAYED' if state == 'played' else 'UNKNOWN')
        actual = getattr(label, 'actual', None)
        actual = float(actual) if appearance == 'PLAYED' and finite(actual) and actual >= 0 and actual % 1 == 0 else None
        if actual is not None and (getattr(label, 'label_reason', None) not in ['EXPLICIT_REPORTED_ZERO', 'EXPLICIT_REPORTED_VALUE']
                                   or not getattr(label, 'participation_evidence', None)):
            raise ValueError('explicit metric-presence/participation witness missing')
        if forecast and forecast['week'] != int(o['week']):
            raise ValueError('A/B game-week identity differs')
        if forecast and actual is not None and finite(forecast.get('actual')) and actual != forecast['actual']:
            raise ValueError('known A/B outcome conflict;case_SHA256=' + digest(encoded(list(key))))
        # A board and B PropLine panel remain distinct source opportunities. This
        # script never concatenates their rows or calls shared W5 a new game/week.
        b_reason = source_match_reason(forecast, o, 'B')
        if b_reason is None:
            b_available.add(str(o['opportunity_key']))
        for cid in CANDIDATE_IDS:
            point = None; selected = None; fallback = None; horizon = None; fit_horizon = None
            if cid in A_IDS:
                af = avectors[cid].get(key)
                why = source_match_reason(af, o, 'A')
                product = A_PRODUCTS[A_IDS.index(cid)][1]
                procedure = 'A::' + A_PRODUCTS[A_IDS.index(cid)][0]
                if why is None:
                    point = float(af['prediction']) if finite(af['prediction']) else None
                    why = 'A_RETAINED_POINT_UNAVAILABLE' if point is None else None
                    fallback = str(af['fallback']) if not pd.isna(af['fallback']) else None
                    horizon = str(pd.Timestamp(af['cutoff_utc']))
                selected = point_side(point, o['line'])
            elif cid in B_IDS:
                product = PRODUCTS[B_IDS.index(cid)]; procedure = B_PROCEDURE
                why = b_reason
                if why is None:
                    point = forecast[product]; fallback = forecast['fallback']
                    horizon = forecast['feature_cutoff']; fit_horizon = forecast['fit_cutoff']
                selected = point_side(point, o['line'])
            else:
                product = 'constant_side'; procedure = cid; why = None
                selected = cid.removeprefix('ALWAYS_')
            if why:
                missing[why] += 1
            row = {'season': 2026, 'week': int(o['week']), 'game_id': key[1], 'player_id': key[2],
                'category': 'pass_att', 'line': float(o['line']), 'actual': actual, 'appearance': appearance,
                'selected_side': selected, 'point': point, 'product': product, 'candidate_id': cid,
                'comparator': 'STRICT_OVER_UNDER', 'procedure_id': procedure,
                'source_stream': str(o['source_stream']), 'opportunity_key': str(o['opportunity_key']),
                'fallback': fallback, 'unavailability_reason': why,
                'outer_outcome_state': 'KNOWN_ACTUAL' if actual is not None else 'MISSING_ACTUAL' if appearance == 'PLAYED' else appearance}
            row['status'] = independent_status(row)
            if common.status(row) != row['status']:
                raise ValueError('canonical and independent grades disagree')
            rows.append(row)
            memberships.append([cid, str(o['opportunity_key']), key[1], key[2], str(o['line']), str(o['source_stream']),
                str(o['source_sha256']), str(o['source_quote_time']), str(o['quote_timing_status']),
                point, appearance, actual, row['selected_side'], row['status'],
                horizon, fit_horizon])
    scores = []; contrasts = []; cases = []
    STATE['phase'] = 'CANONICAL_AGGREGATE_AND_PAIRED_CONTROLS'
    panels = ['ALL'] + sorted({r['source_stream'] for r in rows})
    full_mask = {str(o) for o in board.opportunity_key}
    for view, viewmask in [('FULL_A_BOARD', full_mask), ('SHARED_B_AVAILABLE', b_available)]:
        vectors = {cid: [r for r in rows if r['candidate_id'] == cid and r['opportunity_key'] in viewmask] for cid in CANDIDATE_IDS}
        for cid, cr in vectors.items():
            for panel in panels:
                for week in ['ALL'] + REQUESTED:
                    rr = [r for r in cr if (panel == 'ALL' or r['source_stream'] == panel) and (week == 'ALL' or r['week'] == week)]
                    errors = [r['point'] - r['actual'] for r in rr if r['point'] is not None and r['actual'] is not None]
                    actual_weeks = sorted({r['week'] for r in rr if r['status'] in ['WIN', 'LOSS', 'PUSH']})
                    product = rr[0]['product'] if rr else A_PRODUCTS[A_IDS.index(cid)][1] if cid in A_IDS else PRODUCTS[B_IDS.index(cid)] if cid in B_IDS else 'constant_side'
                    point_type = POINT_TYPES[product] if cid in B_IDS else 'RETAINED_' + product.upper() if cid in A_IDS else 'CONSTANT_SIDE'
                    scores.append({'candidate_id': cid, 'view': view, 'product': product, 'point_type': point_type, 'source_panel': panel, 'week_view': week,
                        'actual_scored_weeks': actual_weeks, 'requested_weeks': REQUESTED, 'scoring_scope_weeks': SCORED_SCOPE,
                        'state': 'SCORED_RETAINED_A_BOARD' if rr else 'NO_ELIGIBLE_ROW_IN_REGISTERED_JOIN_SCOPE',
                        **common.summary(rr), 'outer_outcomes': dict(Counter(r['outer_outcome_state'] for r in rr)),
                        'forecast_outcome_cross_counts': [{'forecast_available': a, 'outcome_state': s, 'rows': n}
                            for (a,s),n in sorted(Counter((r['selected_side'] is not None, r['outer_outcome_state']) for r in rr).items())],
                        'unavailable_reasons': dict(Counter(r['unavailability_reason'] for r in rr if r['unavailability_reason'])),
                        'fallback_outputs': sum(r['fallback'] not in [None, '', 'none'] for r in rr),
                        'numerical_same_offer_mask': {'scored': len(errors), 'MAE': math.fsum(map(abs, errors))/len(errors) if errors else None,
                            'MSE': math.fsum(e*e for e in errors)/len(errors) if errors else None,
                            'bias': math.fsum(errors)/len(errors) if errors else None},
                        'eligible_mask_sha256': mask(rr), 'decided_mask_sha256': mask(rr, True),
                        'five_week_duration_floor': len(actual_weeks) >= 5, 'admission': 'DURATION_ONLY_NOT_PRIMARY_ADMISSION'})
        for left, right in PAIRED_IDS:
            contrasts.append({'view': view, 'left': left, 'right': right, **paired(vectors[left], vectors[right], np)})
        for cid, cr in vectors.items():
            ordered = sorted(cr, key=lambda r: digest(encoded(r['opportunity_key'])))
            for state in ['WIN', 'LOSS', 'UNKNOWN_PARTICIPATION', 'UNAVAILABLE_FORECAST', 'ABSTAIN', 'PUSH']:
                case = next((r for r in ordered if r['status'] == state), None)
                if case is not None:
                    cases.append({'view': view, 'candidate_id': cid, 'status': state,
                        'case_sha256': digest(encoded([cid, case['opportunity_key']])),
                        'rule': 'Exact original point/line threshold and qualified outcome, recomputable from lossless view; no raw offer/identity published'})
    lossless_view = {'version': VERSION, 'protocol_sha256': digest(protocol_raw),
        'source_selector': 'Original tools.abc_a_dynamic_carry_wave_v1.sources()[2]; unchanged g offers/qualified_labels/frozen_bundle',
        'source_sha256': {'offers': A_OFFERS, 'qualified_labels': A_LABELS, 'frozen_bundle': A_FROZEN},
        'A_forecast_member': {'member': 'FORECASTS.parquet', 'sha256': A_MEMBER},
        'B_public_prediction_refs': [{'week': w, 'bytes': n, 'sha256': h} for w,n,h in B_REFS],
        'B_public_commit': B_COMMIT, 'candidate_ids': CANDIDATE_IDS, 'A_products': A_PRODUCTS, 'B_products': PRODUCTS,
        'board_selector': 'target pass_att; season2026; weeks1-5; original A PRIMARY_FULL source panels/lines/qualified outcomes unchanged',
        'join': 'Exact canonical game/GSIS player/QB role/team/opponent/query cutoff/kickoff; no source-panel concatenation',
        'full_A_mask_sha256': digest(encoded(sorted(full_mask))),
        'shared_B_available_mask_sha256': digest(encoded(sorted(b_available))),
        'membership_sha256': digest(encoded(sorted(memberships))),
        'decision_and_grading': 'This hash-bound code point_side/independent_status plus pinned canonical status; exact ties abstain, unknown/push distinct',
        'reconstruction': 'Hash-verified original source vectors/board/outcomes plus public B packets and this code regenerate every point/side/grade without model loads or another private vector copy',
        'source_history_contracts': {'A': 'Retained A accepted annual2019-2025 fits, fixed2026-09-01 parameter cutoff, reconstructed seven-day input history; actual procedure/source versions preserved in A_source_product_provenance',
            'B': 'Own last8 earlier games and season>=queryseason-1 eligible physical/parity rows for exposure prior; target kickoff feature horizon; weekly fit origin; retrospective official-QB-source query membership'},
        'comparison': 'Complete saved systems on exact same A offer board; history/learner/population differ; no isolated context increment or originalR0 claim',
        'private_writes': 0}
    signal.alarm(0)
    public = {'id': VERSION, 'state': 'OWNER_LOCAL_ZERO_REFIT_READONLY_REPLAY_COMPLETE',
        'protocol_sha256': digest(protocol_raw), 'B_commit': B_COMMIT, 'candidate_ids': CANDIDATE_IDS,
        'B_retained_output_inventory': public_inventory, 'A_original_source_bindings': {'offers': A_OFFERS, 'qualified_labels': A_LABELS,
            'frozen_bundle': A_FROZEN, 'forecast_member': A_MEMBER}, 'A_source_product_provenance': aprovenance,
        'A_ATT_CMP_source_inventory_all_requested_weeks': inventory,
        'eligible_A_ATT_offers': len(board), 'eligible_A_games': int(board.game_id.nunique()),
        'eligible_A_weeks': sorted(map(int, board.week.unique())), 'shared_B_available_offers': len(b_available),
        'scores': scores, 'paired_controls': contrasts, 'representative_recomputation_cases': cases,
        'private_scorecard': {'kind': 'LOSSLESS_VIEW_OVER_ORIGINAL_IMMUTABLE_SOURCES', 'persisted_new_private_bytes': 0,
            'view_sha256': digest(encoded(lossless_view)), 'view': lossless_view,
            'offhost_original_source_restoration': 'NOT_NEWLY_VERIFIED; originals remain governed by existing recovery receipts'},
        'deterministic_replay_membership_sha256': digest(encoded(sorted(memberships))),
        'missing_product_rows': dict(missing), 'evidence_tier': EVIDENCE,
        'rules': {'point_direction': 'Unrounded point > line OVER; < line UNDER; exact tie ABSTAIN',
            'outcomes': 'Original A explicit metric-present qualified values; unknown/DNP/pending/missing distinct; pushes not wins/losses',
            'B_query_population': 'RETROSPECTIVE_OFFICIAL_QB_STAT_ROWS_NOT_EXANTE_ROSTER; missing canonical QB-games remain unavailable',
            'clock': 'B feature_cutoff is target kickoff; fit_cutoff is weekly origin. Neither is authenticated issuance or source publication.',
            'complete_systems': 'A/B source/history/learner/population differ; exact same-board replay is a complete-system comparison, not isolated context ablation or original R0 performance.',
            'W5': 'A annual and B PropLine offers are separate source panels on overlapping physical player-games. No concatenation or added physical observation/week claim.',
            'CMP': 'Inventory only; no CMP replay or absence claim beyond this exact A source bundle'},
        'qualification': 'Owner-local diagnostic only; actual five-week duration alone does not establish improvement, probability, TopPicks or operational readiness',
        'private_writes': 0, 'private_rows_published': 0, 'new_fits': 0, 'new_inference': 0, 'new_source_collection': 0,
        'production_writes': 0, 'C_shared_admission': 'NOT_REQUESTED_OR_ASSUMED',
        'actual': {'CPU_seconds': time.process_time()-cpu, 'wall_seconds': time.monotonic()-started,
                   'RSS_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024},
        'recorded_UTC': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    with args.output.open('xb') as f:
        f.write(encoded(public)); f.flush(); os.fsync(f.fileno())
    print(json.dumps({'state': public['state'], 'eligible_A_ATT_offers': len(board), 'public_result': str(args.output.relative_to(ROOT)),
                      'private_writes': 0, 'new_fits': 0, 'new_inference': 0}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--protocol', type=Path, required=True)
    parser.add_argument('--protocol-sha256', required=True)
    parser.add_argument('--b-public-cache', default='/tmp/completion-b-public')
    parser.add_argument('--c-code-cache', default='/tmp/acceptance-c-review/src')
    parser.add_argument('--output', type=Path, default=ROOT/'reports/abc-championship/player-context-completion-decision-01/B_ATT_ON_A_EARLIER_BOARD_V1.json')
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit('immutable result exists; no overwrite')
    try:
        run(args)
    except BaseException as error:
        signal.alarm(0)
        import re
        found = re.search(r'case_SHA256=([0-9a-f]{64})', str(error))
        receipt = {'id': VERSION, 'state': 'FAILED', 'phase': STATE['phase'], 'error_type': type(error).__name__,
            'case_sha256': found.group(1) if found else None, 'protocol_sha256': args.protocol_sha256,
            'new_fits': 0, 'new_inference': 0, 'private_writes': 0, 'automatic_retry': False}
        failure = args.output.with_name('B_ATT_ON_A_EARLIER_BOARD_FAILURE_' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json')
        with failure.open('xb') as f:
            f.write(encoded(receipt)); f.flush(); os.fsync(f.fileno())
        print(json.dumps(receipt))
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
