"""One frozen saved-output comparison, using the accepted existing evaluator.

Importing this module reads no NFL records. Execution requires root's exact
published GO, immutable original-byte caches and an already-reconstructed B
source panel. No fits, model loading, network, new ranker or native producer.
"""
from __future__ import annotations

import argparse
import bisect
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
import platform
import resource
import signal
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = 'A-ABC-W1W9-SAVED-COMPARISON-v1'
B_NAMESPACE = 'B-FTN-BALL-QUALITY-COMPLETION-v1'
C_NAMESPACE = 'C-ALL12-LAW-THRESHOLD-v2.1'
C_IDS = {
    'mean': 'C::C-ALL12-LAW-THRESHOLD-v2.1/P2_LEAF/H-MULTI/E0_OP/P1_MEAN::P1_MEAN::P1_MEAN-strict-v6',
    'median': 'C::C-ALL12-LAW-THRESHOLD-v2.1/P2_LEAF/H-MULTI/E0_OP/P1_MEDIAN::P1_MEDIAN::P1_MEDIAN-strict-v6',
}
CATEGORIES = ['pass_yd', 'pass_td', 'pass_cmp', 'pass_att', 'pass_int',
              'rush_yd', 'rush_att', 'rec', 'rec_yd', 'rush_rec_yd']
COUNTS = {'pass_td', 'pass_cmp', 'pass_att', 'pass_int', 'rush_att', 'rec'}
ARMS, B_OUTPUTS = ['B0', 'B1', 'B2'], ['mean', 'lower_median', 'P2']
CAPTURED = {'CAPTURED_SITE_ADJUSTED_POINT_STRICT': 'source_adjusted_point',
            'CAPTURED_SITE_RAW_POINT_STRICT': 'source_raw_point'}
PREVALENCE = 'EARLIER_LINE_PREVALENCE'
PHASE = 'NOT_STARTED'


def encoded(obj):
    return (json.dumps(obj, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def sha(body):
    return hashlib.sha256(body).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def bound_file(path, digest):
    path = Path(path)
    require(not path.is_symlink(), 'Bound code/metadata is a symlink')
    raw = path.read_bytes()
    require(sha(raw) == digest, 'Bound code/metadata bytes differ: ' + path.name)
    return raw


def instant(value):
    if finite(value):
        return datetime.datetime.fromtimestamp(value, datetime.timezone.utc)
    if isinstance(value, datetime.datetime):
        require(value.tzinfo is not None and value.utcoffset() is not None,
                'Naive/unknown clock is not an admitted event clock')
        return value.astimezone(datetime.timezone.utc)
    require(isinstance(value, str), 'Explicit aware clock required')
    stamp = datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(stamp.tzinfo is not None, 'Naive/unknown clock is not an admitted event clock')
    return stamp.astimezone(datetime.timezone.utc)


def team(value):
    # The already-admitted 2026 Rams alias, not a current-team/name remapping.
    return 'LAR' if str(value) == 'LA' else str(value)


def immutable(path, body):
    path = Path(path)
    require(path.parent.is_dir() and not path.parent.is_symlink(), 'Root-owned output stage absent')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as handle:
        handle.write(body)
        handle.flush()
        os.fsync(handle.fileno())


def count_actual(value, category):
    if not finite(value) or value != math.floor(value):
        return None
    if category in COUNTS and value < 0:
        return None
    return float(value)


def identity(row, category=None):
    return (category or row.get('target') or row.get('category'), int(row['season']),
            int(row['week']), row.get('game_id'), row.get('player_id'))


def original_sources(plan):
    """The root abstraction verifies the ORIGINAL body, not only its wrapper."""
    from tools.w1w9_source_cache_v1 import original
    inventory = []

    def read(ref, label):
        raw = original(ref)
        expected = ref.get('original_sha256', ref.get('sha256'))
        size = ref.get('original_bytes', ref.get('bytes'))
        require(expected is not None and size is not None and sha(raw) == expected and len(raw) == size,
                'Original immutable source hash/size differs: ' + label)
        inventory.append(dict(id=label, bytes=len(raw), sha256=sha(raw),
                              source_commit=ref.get('source_commit',ref.get('commit',ref.get('producer_commit')))))
        return raw

    def doc(ref, label):
        raw = read(ref, label)
        body = gzip.decompress(raw) if raw.startswith(b'\x1f\x8b') else raw
        require(len(body) <= 128 * 1024**2, 'Decoded source envelope exceeded')
        return json.loads(body)

    return read, doc, inventory


def source_scalar(value, pd):
    """Retain null, absent/nonfinite and clock representations privately."""
    if value is None or type(value) in (str, int, bool):
        return value
    if type(value) is float:
        return value if finite(value) else dict(source_state='NONFINITE', representation=str(value))
    if value is pd.NA or value is pd.NaT:
        return dict(source_state='MISSING', representation=type(value).__name__)
    if hasattr(value, 'item'):
        return source_scalar(value.item(), pd)
    if hasattr(value, 'isoformat'):
        return dict(source_type=type(value).__name__, value=value.isoformat())
    if type(value).__module__ == 'decimal':
        return dict(source_type='Decimal', value=str(value))
    raise TypeError('Unregistered source scalar: ' + type(value).__name__)


def offer_context(offer):
    cat = offer.get('target', offer.get('category'))
    line = offer.get('line')
    require(finite(float(line)), 'Missing/nonfinite actual line')
    return dict(category=cat, season=int(offer['season']), week=int(offer['week']),
        game_id=offer.get('game_id'), player_id=offer.get('player_id'),
        position=offer.get('position'), team=offer.get('team'), opponent=offer.get('opponent'),
        line=float(line), opportunity_key=str(offer['opportunity_key']),
        kickoff_utc=instant(offer['kickoff_utc']).isoformat(),
        cutoff_utc=instant(offer['cutoff_utc']).isoformat())


def label_for(offer, label):
    """Qualification of existing A labels, no new source-zero assumption."""
    if label is None:
        return None, 'UNKNOWN', 'MISSING_QUALIFIED_LABEL'
    for key in ['season', 'week', 'game_id', 'player_id', 'position', 'target']:
        require(str(label[key]) == str(offer[key]), 'A label identity/role/target differs')
    require(all(team(label[k]) == team(offer[k]) for k in ['team', 'opponent'])
            and instant(str(label['kickoff_utc'])) == instant(str(offer['kickoff_utc'])),
            'A qualified outcome team/event differs')
    state = label.get('participation_state')
    appearance = ('PENDING' if label.get('outcome_state') == 'pending' else
                  'DNP' if str(state).lower() == 'dnp' else 'PLAYED' if state == 'played' else 'UNKNOWN')
    actual = count_actual(label.get('actual'), offer['target']) if appearance == 'PLAYED' else None
    reason = label.get('label_reason')
    if actual is not None:
        allowed = ({'EXPLICIT_BOTH_SIGNED_COMPONENTS', 'EXPLICIT_BOTH_SIGNED_YARD_COMPONENTS'}
                   if offer['target'] == 'rush_rec_yd' else
                   {'EXPLICIT_REPORTED_ZERO', 'EXPLICIT_REPORTED_VALUE'})
        require(reason in allowed and bool(label.get('participation_evidence')),
                'Individual statistic/component presence unsupported')
    return actual, appearance, str(reason)


def match(row, offer, kind):
    if row is None:
        return 'MISSING_' + kind + '_SAVED_FORECAST'
    if not offer.get('game_id') or not offer.get('player_id'):
        return 'UNRESOLVED_CANONICAL_OFFER_IDENTITY'
    if row.get('position') != offer.get('position'):
        return kind + '_ROLE_MISMATCH'
    if any(team(row.get(k)) != team(offer.get(k)) for k in ['team', 'opponent']):
        return kind + '_TEAM_OPPONENT_MISMATCH'
    if kind == 'A':
        clocks = [row.get('kickoff_utc'), row.get('cutoff_utc')]
    elif kind == 'B':
        clocks = [row.get('feature_cutoff')] * 2
    else:
        clocks = [row.get('kickoff_UTC'), row.get('as_of_UTC')]
    try:
        if any(instant(a) != instant(str(offer[b])) for a, b in zip(clocks, ['kickoff_utc', 'cutoff_utc'])):
            return kind + '_EVENT_OR_FORECAST_CUTOFF_MISMATCH'
    except (ValueError, TypeError, OverflowError):
        return kind + '_UNKNOWN_EVENT_OR_FORECAST_CUTOFF'
    return None


def source_name(offer):
    return str(offer.get('source_stream') or 'B_NATIVE_EXTERNAL_PROVIDER')


def book_name(offer, policy):
    value = offer.get('book')
    if value is None or (type(value) is float and not finite(value)):
        value = offer.get('book_id', offer.get('venue_id'))
    if finite(value) and value == int(value):
        value = str(int(value))
    if isinstance(value, str) and value.endswith('.0') and value[:-2].isdigit():
        value = value[:-2]
    return str(policy.get('A_book_dictionary', {}).get(str(value), value or 'UNKNOWN'))


def line_tier(offer):
    value = offer.get('main_alternate_status', offer.get('line_tier', offer.get('line_type')))
    if type(value) is float and not finite(value):
        value = None
    return str(value) if value is not None and not isinstance(value, dict) else 'UNKNOWN'


def declared_ids(plan, category, primary=False):
    controls = plan['A_point_products_by_category'][category]
    require(all(isinstance(r.get('output_procedure_version'),str) and r['output_procedure_version']
                for r in controls), 'Each A saved output needs its frozen exact procedure version')
    ids = ['A::' + r['method'] + '::' + r['output'] for r in controls]
    if category == 'pass_cmp':
        ids += [B_NAMESPACE + ':' + arm + '::' + product for arm in ARMS for product in B_OUTPUTS]
    ids += [C_IDS['mean'], C_IDS['median'], 'ALWAYS_OVER', 'ALWAYS_UNDER']
    if category == 'pass_cmp':
        ids += list(CAPTURED) + [PREVALENCE]
    require(len(ids) == len(set(ids)), 'Frozen candidate identities duplicated')
    expected = plan['primary_candidate_ids'] if primary else plan['early_candidate_ids'][category]
    require(ids == expected, 'Frozen exact procedure/output roster differs')
    return ids


def prevalence_history(raw_rows):
    """Existing B all-QB earlier prevalence, not an own-player fitted model.

    Source: B score_ftn_completion_information.py112--115 and ContextHistory.
    Only official completions and original availability/appearance/parity are
    consumed. Source/query outcomes never define the offered population.
    """
    require(isinstance(raw_rows,list), 'Bound QB_CONTEXT array required')
    seen, rows = set(), []
    for row in raw_rows:
        key = row['game_id'], row['player_id']
        require(key not in seen, 'Duplicate canonical QB-game prevalence input')
        seen.add(key)
        if not row.get('physical_participation') or not row['target_parity'] or row['season'] < 2025:
            continue
        require(finite(row['available']) and finite(row['kickoff']) and row['available'] > row['kickoff'],
                'Prevalence source historical availability unsupported')
        value = count_actual(row.get('official_completions'),'pass_cmp')
        require(value is not None, 'Prevalence eligible individual official completions missing/invalid')
        rows.append(dict(game_id=row['game_id'],player_id=row['player_id'],
                         available=row['available'],kickoff=row['kickoff'],actual=value,season=row['season']))
    rows.sort(key=lambda r:(r['available'],r['kickoff'],r['game_id'],r['player_id']))
    return rows,[r['available'] for r in rows]


def earlier_prevalence(history, cutoff, line):
    rows, times = history
    admitted = rows[:bisect.bisect_left(times,cutoff)]
    n = len(admitted)
    whole = float(line).is_integer()
    den = n + (3 if whole else 2)
    over = (sum(r['actual'] > line for r in admitted)+1)/den
    under = (sum(r['actual'] < line for r in admitted)+1)/den
    push = (sum(r['actual'] == line for r in admitted)+1)/den if whole else 0.
    require(abs(over+under+push-1) <= 1e-12, 'Prevalence relative-line mass invalid')
    return dict(p_over=over,p_under=under,p_push=push),dict(
        unique_earlier_QB_games=n,latest_source_available=admitted[-1]['available'] if admitted else None,
        prior='DIRICHLET_ONE_EACH' if whole else 'LAPLACE_ONE_EACH_O_U',
        source_membership_sha256=sha(encoded([(r['game_id'],r['player_id'])for r in admitted])))


def load_B(plan, doc, shared):
    lookup, cdfs, packets = {}, {}, []
    alias_count = fallback_count = 0
    alias_fields = ['mean', 'lower_median', 'law', 'features', 'fit_cutoff', 'feature_cutoff',
                    'latest_source_available', 'history_regime', 'feature_memory', 'fallback',
                    'own_prior_games', 'position', 'team', 'opponent', 'season', 'week',
                    'game_id', 'player_id', 'target']
    # W1--4 are reused only from the original completed A vector receipt below.
    for ref in plan['B_FTN_forecasts']:
        week = int(ref['week'])
        if week <= 4:
            continue
        require(week in range(5, 10), 'B packet week outside the frozen extension')
        packet = doc(ref, 'B-FTN-W' + str(week))
        require(packet['season'] == 2026 and packet['week'] == week and packet['original_issuance'] is False,
                'B packet period/original issuance differs')
        counts = Counter()
        for row in packet['rows']:
            arm = row['method']
            require(arm in ARMS and row['procedure_id'] == B_NAMESPACE + ':' + arm
                    and row['target'] == 'pass_cmp' and row['position'] == 'QB'
                    and row['season'] == 2026 and row['week'] == week and row['original_issuance'] is False,
                    'B exact saved procedure/role/period differs')
            require(finite(row['fit_cutoff']) and finite(row['feature_cutoff'])
                    and row['fit_cutoff'] <= row['feature_cutoff'], 'B origin cutoff invalid')
            require(row.get('latest_source_available') is None
                    or row['latest_source_available'] < row['feature_cutoff'], 'B source not strictly earlier')
            require(row['history_regime'] == 'H-RECENT' and row['feature_memory'] == '2022_EXPANDING'
                    and row['source_vintage'] == plan['B_source_vintage'], 'B history/vintage identity differs')
            key = arm, str(row['game_id']), str(row['player_id'])
            require(key not in lookup, 'Duplicate B arm/player-game')
            require(all(finite(row[k]) and row[k] >= 0 for k in ['mean', 'lower_median']),
                    'B count point is invalid')
            lookup[key] = {k: v for k, v in row.items() if k not in ['actual', 'appearance']}
            cdfs[key] = shared.law_prepare(row['law'], row['mean'], row['lower_median'])
            counts[arm] += 1
        require(set(counts) == set(ARMS) and len(set(counts.values())) == 1, 'B arm source coverage differs')
        packets.append(dict(week=week, rows=dict(counts)))
    require({p['week'] for p in packets} == set(range(5, 10)), 'Exact B W5--9 packet missing')
    for (arm, game, player), row in lookup.items():
        base = lookup.get(('B0', game, player))
        require(base is not None, 'B0 counterpart unavailable')
        if arm == 'B1':
            require(row.get('support_alias_of') == B_NAMESPACE + ':B0'
                    and all(row.get(k) == base.get(k) for k in alias_fields), 'B1 support alias differs')
            alias_count += 1
        if arm == 'B2' and row.get('fallback') == 'B0_INCOMPLETE_FTN_SOURCE':
            require(all(row.get(k) == base.get(k) for k in ['mean', 'lower_median', 'law', 'fit_cutoff',
                    'feature_cutoff', 'position', 'team', 'opponent']), 'B2 declared fallback changed B0 output')
            fallback_count += 1
    return lookup, cdfs, dict(packets=packets, B1_alias_rows=alias_count,
                             B2_incomplete_source_reference_fallbacks=fallback_count,
                             W1_W4='REUSED_PRIOR_COMPLETE_VECTORS_NO_PACKET_REDECODE')


def load_C(plan, doc):
    lookup, coverage = {}, []
    whitelist = ['version', 'slot', 'target', 'history', 'family', 'arm', 'game_id', 'player_id',
                 'position', 'team', 'opponent', 'season', 'week', 'kickoff_UTC', 'as_of_UTC',
                 'information_tier', 'generated_UTC', 'scoring_contract_id', 'mean', 'median',
                 'product_type', 'fallback']
    for ref in plan['C_legacy_forecasts']:
        cat = ref.get('source_target', ref.get('category'))
        week = int(ref['week'])
        if cat not in CATEGORIES or week not in (range(1, 8) if cat == 'pass_cmp' else range(1, 6)):
            continue
        packet = doc(ref, 'C-' + cat + '-W' + str(week))
        require(isinstance(packet, list), 'C legacy forecast array differs')
        for source in packet:
            row = {k: source.get(k) for k in whitelist}
            require(row['target'] == cat and row['season'] == 2026 and row['week'] == week
                    and row['version'] == C_NAMESPACE and row['history'] == 'H-MULTI'
                    and row['family'] == 'P2_LEAF' and row['arm'] == 'E0_OP', 'C exact legacy version differs')
            require(row['scoring_contract_id'] == 'official-player-fullgame-OT-v1'
                    and row['information_tier'] == 'CURRENT_REVISED_7DAY_RECONSTRUCTION',
                    'C target/information contract differs')
            require(instant(row['kickoff_UTC']) == instant(row['as_of_UTC']), 'C historical query horizon differs')
            require(row['position'] in plan['C_roles_by_category'][cat], 'C role outside producer-code scope')
            require(isinstance(row['player_id'], str) and row['player_id'].startswith('00-')
                    and len(row['player_id']) == 10 and row['player_id'][3:].isdigit()
                    and isinstance(row['game_id'], str) and bool(row['game_id']),
                    'C canonical player/game fields unavailable')
            require(type(row['fallback']) is bool, 'C original model/prior flag unavailable')
            key = cat, str(row['game_id']), str(row['player_id'])
            require(key not in lookup, 'Duplicate C legacy target/player-game')
            lookup[key] = row
        coverage.append(dict(category=cat, week=week, source_rows=len(packet)))
    expected = {(cat, week) for cat in CATEGORIES for week in (range(1, 8) if cat == 'pass_cmp' else range(1, 6))}
    require({(r['category'], r['week']) for r in coverage} == expected, 'An admitted C historical source packet is missing')
    return lookup, dict(packets=coverage, guard_state='LEGACY_POINT_DIAGNOSTIC_ONLY_COHERENCE_CERTIFICATE_NOT_SUPPLIED',
                       probabilities='NOT_EXPORTED_AS_A_COMPLETE_CDF;GRID_PROBABILITIES_NOT_USED',
                       cached_actual_and_appearance='DISCARDED_BEFORE_JOIN')


def summary(rows, common, shared):
    s = common.summary(rows)
    selected = [r for r in rows if r['selected_side'] in ['OVER', 'UNDER']]
    unresolved = [r for r in selected if r['status'] in ['UNKNOWN_PARTICIPATION', 'MISSING_ACTUAL', 'PENDING']]
    w, n, u = s['COMBINED']['wins'] or 0, s['COMBINED']['decided'], len(unresolved)
    states = Counter(r['status'] for r in rows)
    weeks = sorted({r['week'] for r in rows})
    available = [r for r in rows if r['selected_side'] is not None]
    scored_weeks = sorted({r['week'] for r in rows if r['status'] in ['WIN', 'LOSS']})
    selected_weeks = sorted({r['week'] for r in selected})
    contributions = defaultdict(list)
    outcome_masks = Counter()
    for row in rows:
        cid, flag = row['candidate_id'], row.get('fallback')
        if cid in ['ALWAYS_OVER', 'ALWAYS_UNDER']:
            attribution = 'CONSTANT_CONTROL_NOT_MODEL'
        elif cid in CAPTURED:
            attribution = 'CAPTURED_REFERENCE_POINT'
        elif cid == PREVALENCE:
            attribution = 'EARLIER_COMPLETE_PANEL_EMPIRICAL_CONTROL' if flag != 'EMPTY_HISTORY_UNIFORM_ABSTAIN' else 'EMPTY_HISTORY_UNIFORM_CONTROL'
        elif cid in C_IDS.values():
            attribution = 'C_PRIOR_FALLBACK' if flag is True else 'C_LEARNED_FLAG' if flag is False else 'C_ATTRIBUTION_UNAVAILABLE'
        elif cid.startswith(B_NAMESPACE + ':'):
            attribution = ('B_LEARNED_FLAG' if flag == 'none' else 'B_REFERENCE_B0_INCOMPLETE_FTN'
                           if flag == 'B0_INCOMPLETE_FTN_SOURCE' else 'B_REPORTED_FALLBACK'
                           if flag is not None else 'B_ATTRIBUTION_UNAVAILABLE')
        else:
            # A's old empty/null flags do not establish learned-only coverage.
            attribution = 'A_SAVED_ATTRIBUTION_UNSPECIFIED' if flag in [None, ''] or isinstance(flag, dict) else 'A_REPORTED_FALLBACK'
        if row['selected_side'] is None:
            attribution = 'TECHNICALLY_UNAVAILABLE_FORECAST'
        contributions[attribution].append(row)
        actual_state = ('KNOWN_ZERO' if row['appearance'] == 'PLAYED' and row['actual'] == 0 else
                        'KNOWN_NONZERO' if row['appearance'] == 'PLAYED' and row['actual'] is not None else
                        'PLAYED_STATISTIC_UNKNOWN' if row['appearance'] == 'PLAYED' else row['appearance'])
        outcome_masks[('AVAILABLE' if row['selected_side'] is not None else 'UNAVAILABLE', actual_state)] += 1
    contribution_summary = {}
    for tag, group in sorted(contributions.items()):
        own = common.summary(group)
        contribution_summary[tag] = {k: own[k] for k in ['eligible','OVER','UNDER','COMBINED','unavailable','abstentions','states']}
    probability = shared.probscores(rows)
    if rows and rows[0]['candidate_id'] == PREVALENCE:
        probability['conditioning'] = ('Earlier physical/parity-qualified unique QB-games since2025; categorical relative-line probabilities. '
            'Binary Over Brier and three-state log loss; not source half-multiclass Brier parity at integer pushes.')
    elif not probability['events']:
        probability['conditioning'] = 'POINT_ONLY_OR_CONSTANT_NO_PROBABILITY_CLAIM'
    return dict(**s, numerical=shared.numerical(rows), probability=probability,
        available=len(available), unknown_selected=u, DNP_selected=states['DNP'], pushes=states['PUSH'],
        unavailable_reasons=dict(Counter(r.get('unavailability_reason') for r in rows if r.get('unavailability_reason'))),
        fallback_states=dict(Counter(str(r.get('fallback')) for r in rows)),
        learned_prior_reference_contributions=contribution_summary,
        outcome_availability_diagnostic=[dict(forecast_state=a,outcome_state=b,count=n)
            for (a,b),n in sorted(outcome_masks.items())],
        represented_board_weeks=weeks, forecast_available_weeks=sorted({r['week'] for r in available}),
        selected_season_weeks=[[2026,x] for x in selected_weeks],
        scored_season_weeks=[[2026, x] for x in scored_weeks],
        complete_zero_selection_weeks=[w for w in weeks if w not in selected_weeks
            and all(r['selected_side'] is not None for r in rows if r['week'] == w)],
        canonical_games=len({r['game_id'] for r in rows if r['game_id'] is not None}),
        unique_player_games=len({(r['game_id'], r['player_id']) for r in rows
                                 if r['game_id'] is not None and r['player_id'] is not None}),
        selected_unknown_sensitivity=dict(unresolved=u, lower=w/(n+u) if n+u else None,
                                         upper=(w+u)/(n+u) if n+u else None),
        eligible_mask_sha256=shared.mask(rows), decided_mask_sha256=shared.mask(rows, True),
        uncertainty_scope='Summary Wilson is independent-Bernoulli diagnostic only; use named paired game/week intervals.')


def report_panel(panel_id, cat, board, vectors, plan, common, shared, np, *, primary=False):
    ids = list(vectors)
    require(all(len(v) == len(board) for v in vectors.values()), 'Candidate shrank the frozen eligible board')
    key_to_offer = {str(o['opportunity_key']): o for o in board}
    require(len(key_to_offer) == len(board), 'Outer opportunity keys duplicate')
    views = {'FULL_DECLARED_BOARD': set(key_to_offer)}
    for stream in sorted({source_name(o) for o in board}):
        views['SOURCE::'+stream] = {k for k, o in key_to_offer.items() if source_name(o) == stream}
    for book in sorted({book_name(o, plan['source_union_policy']) for o in board}):
        views['BOOK::'+book] = {k for k, o in key_to_offer.items() if book_name(o, plan['source_union_policy']) == book}
    for tier in sorted({line_tier(o) for o in board}):
        views['LINE_TIER::'+tier] = {k for k, o in key_to_offer.items() if line_tier(o) == tier}
    all_modeled = [cid for cid in ids if cid.startswith(('A::', 'B-', 'C::'))]
    if all_modeled:
        views['COMMON_ALL_MODELED_AVAILABLE'] = set.intersection(*[
            {r['opportunity_key'] for r in vectors[cid] if r['selected_side'] is not None} for cid in all_modeled])
    summaries, paired = [], []
    # Every pair is frozen through the candidate order, not selected after gains.
    pair_ids = [(a, b) for i, a in enumerate(ids) for b in ids[i+1:]]
    references = plan['paired_sensitivity_references_by_category'][cat]
    require(len(references)==len(set(references)) and set(references)<=set(ids),
            'Fixed strong-control sensitivity references differ')
    def sensitivity_pair(left,right):
        if left in references or right in references:
            return True
        for output in B_OUTPUTS:
            if (left,right) in [(B_NAMESPACE+':'+arm+'::'+output,B_NAMESPACE+':B2::'+output)
                               for arm in ['B0','B1']]:
                return True
        return False
    for view, mask in views.items():
        vv = {cid: [r for r in rr if r['opportunity_key'] in mask] for cid, rr in vectors.items()}
        for cid, rr in vv.items():
            for week in ['ALL'] + list(range(1, 10)):
                selected = [r for r in rr if week == 'ALL' or r['week'] == week]
                summaries.append(dict(panel_id=panel_id, category=cat, candidate_id=cid, view=view,
                                      week_view=week, **summary(selected, common, shared)))
        # Common and source/line-tier sensitivities retain pairwise masks. Empty
        # views are explicit, and full-board denominators never change.
        for left, right in pair_ids:
            if view not in ['FULL_DECLARED_BOARD','COMMON_ALL_MODELED_AVAILABLE'] and not sensitivity_pair(left,right):
                continue
            paired.append(dict(panel_id=panel_id, category=cat, view=view, left=left, right=right,
                               **shared.paired(vv[left], vv[right], np)))
    full = {q['candidate_id']: q for q in summaries if q['view'] == 'FULL_DECLARED_BOARD' and q['week_view'] == 'ALL'}
    board_weeks = sorted({o['week'] for o in board})
    complete = [cid for cid, q in full.items() if q['unavailable'] == 0 and q['COMBINED']['decided'] > 0
                and (not primary or q['forecast_available_weeks'] == list(range(1,10)))]
    modeled = [cid for cid in complete if cid.startswith(('A::', 'B-', 'C::'))]

    def maxima(candidates, side):
        valid = [cid for cid in candidates if full[cid][side]['decided']]
        best = max((full[cid][side]['rate'] for cid in valid), default=None)
        return [dict(candidate_id=cid, **full[cid][side], scored_season_weeks=full[cid]['scored_season_weeks'])
                for cid in valid if full[cid][side]['rate'] == best]

    coverage = []
    for week in range(1, 10):
        oo = [o for o in board if o['week'] == week]
        coverage.append(dict(week=week, eligible=len(oo),
            canonical_games=len({o.get('game_id') for o in oo if o.get('game_id') is not None}),
            scheduled_games=plan.get('scheduled_games_by_week', {}).get(str(week)),
            source_counts=dict(Counter(source_name(o) for o in oo)),
            book_counts=dict(Counter(book_name(o, plan['source_union_policy']) for o in oo)),
            line_tier_counts=dict(Counter(line_tier(o) for o in oo)),
            source_horizon_counts=dict(Counter(str(o.get('source_horizon','HISTORICAL_LEFT_LIMIT_KICKOFF_RECONSTRUCTION')) for o in oo)),
            quote_timing_counts=dict(Counter(str(o.get('quote_timing_status','UNKNOWN_NOT_RETAINED')) for o in oo)),
            state='COMPLETE_FOR_NAMED_PARTIAL_BOARD' if oo else 'NO_ACTUAL_LINE_IN_THIS_PANEL'))
    status = ('NINE_WEEKS_REPRESENTED_NAMED_BOARD_NOT_LEAGUE_COMPLETE' if primary and board_weeks == list(range(1,10))
              else 'PARTIAL_ACTUAL_WEEK_PANEL')
    return dict(id=panel_id, category=cat, board_weeks=board_weeks, coverage_status=status,
        coverage=coverage, candidate_ids=ids, summaries=summaries, paired=paired,
        complete_product_candidates=complete, complete_modeled_candidates=modeled,
        highest_observed_complete=maxima(complete, 'COMBINED'), highest_observed_modeled=maxima(modeled, 'COMBINED'),
        highest_observed_Over_complete=maxima(complete, 'OVER'), highest_observed_Under_complete=maxima(complete, 'UNDER'),
        partial_product_observed_records=[dict(candidate_id=cid, own_record=full[cid]['COMBINED'],
            scored_season_weeks=full[cid]['scored_season_weeks'], available=full[cid]['available'],
            unavailable=full[cid]['unavailable']) for cid in ids if cid not in complete],
        recommendation='SCOPED_RESEARCH_COMPARISON_ONLY;C_COORDINATES_SUPPORT_TIES;NO_AUTOMATIC_PRIMARY_ADMISSION',
        probability_or_selector_qualification='POINT_VIEWS_HAVE_NONE;B_LAW_HAS_OWN_SCORES;NO_C_GRID_INTERPOLATION_OR_NEW_TOPK')


def run(args):
    global PHASE
    cpu, wall = time.process_time(), time.monotonic()
    sys.dont_write_bytecode = True
    PHASE = 'ROOT_REGISTRATION_AND_RUNTIME_PREFLIGHT'
    raw = bound_file(args.plan, args.plan_sha256)
    plan = json.loads(gzip.decompress(raw) if raw.startswith(b'\x1f\x8b') else raw)
    require(plan['id'] == VERSION and plan['state'] == 'ROOT_REGISTERED_SCORING_GO'
            and plan['registered_by'] == '/root', 'Published exact root comparison GO required')
    require(plan['new_fits'] == plan['new_model_inference'] == plan['network_calls'] == 0,
            'This saved-output procedure does not authorize fitting/model inference/acquisition')
    require(plan['source_union_policy']['state'] == 'ROOT_FROZEN_COMPATIBLE_RETROSPECTIVE_DIAGNOSTIC'
            and plan['source_union_policy']['primary_period_priority'] == {'A_ANNUAL_NAMED_NJ': [1,2,3,4], 'B_NATIVE': [5,6,7,8,9]},
            'No compatible deterministic source/period policy was frozen')
    for path, digest in plan['code_sha256'].items():
        bound_file(ROOT/path, digest)
    for path, digest in plan['metadata_sha256'].items():
        bound_file(ROOT/path, digest)
    budget = plan['resources']
    require(budget['CPU_seconds'] == 900 and budget['wall_seconds'] == 1800
            and budget['RSS_bytes'] == 3*1024**3 and budget['retained_limit_bytes'] == 12*1024**2,
            'Bounded registered resource contract differs')
    resource.setrlimit(resource.RLIMIT_CPU, (850, 900))
    resource.setrlimit(resource.RLIMIT_AS, (budget['RSS_bytes'],)*2)

    def exhausted(sig, _):
        if sig == signal.SIGXCPU:
            signal.signal(signal.SIGXCPU, signal.SIG_IGN)
        raise TimeoutError('Finite saved-output comparison exhausted')

    signal.signal(signal.SIGXCPU, exhausted)
    signal.signal(signal.SIGALRM, exhausted)
    signal.alarm(1750)

    def offline(event, _):
        if event in ('socket.connect', 'socket.connect_ex', 'socket.getaddrinfo'):
            raise RuntimeError('Only root-bound offline source caches are permitted')

    sys.addaudithook(offline)
    for key in ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS']:
        os.environ[key] = '1'
    import numpy as np
    import pandas as pd
    import pyarrow as pa
    runtime = dict(python=platform.python_version(), numpy=np.__version__, pandas=pd.__version__, pyarrow=pa.__version__)
    require(runtime == plan['runtime'], 'Exact existing runtime required')
    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)
    pa.set_memory_pool(pa.system_memory_pool())
    sys.path.insert(0, str(ROOT))
    from tools import timing_confirm_b_completion_join_v1 as shared
    for name, digest in plan['common_code'].items():
        bound_file(args.c_cache/name, digest)
    sys.path.insert(0, str(args.c_cache))
    common = importlib.import_module('abc_championship_v2')
    require(Path(common.__file__).resolve() == (args.c_cache/'abc_championship_v2.py').resolve(), 'Wrong accepted evaluator imported')
    read, doc, source_inventory = original_sources(plan)

    PHASE = 'ORIGINAL_A_OFFERS_LABELS_AND_SAVED_POINTS'
    sources = plan['A_sources']
    with zipfile.ZipFile(io.BytesIO(read(sources['offers'], 'A-OFFERS'))) as archive:
        body = archive.read(sources['offers']['member'])
        require(sha(body) == sources['offers']['member_sha256'], 'A offer member differs')
        offers = pd.read_parquet(io.BytesIO(body))
    with zipfile.ZipFile(io.BytesIO(read(sources['qualified_labels'], 'A-QUALIFIED-LABELS'))) as archive:
        body = archive.read(sources['qualified_labels']['member'])
        require(sha(body) == sources['qualified_labels']['member_sha256'], 'A label member differs')
        labels = pd.read_parquet(io.BytesIO(body))
    with zipfile.ZipFile(io.BytesIO(read(sources['frozen_bundle'], 'A-SAVED-POINTS'))) as archive:
        body = archive.read('FORECASTS.parquet')
        require(sha(body) == plan['A_forecast_member_sha256'], 'A saved point member differs')
        forecasts = pd.read_parquet(io.BytesIO(body))
    aa = offers.loc[offers.season.eq(2026) & offers.week.between(1,5)
                    & offers.target.isin(CATEGORIES) & offers.source_stream.eq('ANNUAL_NAMED_NJ')].copy()
    ll = labels.loc[labels.season.eq(2026) & labels.week.between(1,5) & labels.target.isin(CATEGORIES)].copy()
    ff = forecasts.loc[forecasts.season.eq(2026) & forecasts.week.between(1,7) & forecasts.target.isin(CATEGORIES)].copy()
    require(not aa.duplicated(['target','season','week','game_id','player_id']).any()
            and not aa.opportunity_key.duplicated().any(), 'A actual opportunity/source policy ambiguous')
    require(not ll.duplicated(['target','season','week','game_id','player_id']).any(), 'A qualified label identity ambiguous')
    require(not ff.duplicated(['target','method','product','season','week','game_id','player_id']).any(),
            'A saved procedure identity ambiguous')
    label_lookup = {identity(r): r for r in ll.to_dict('records')}
    a_lookup = {(r['target'], r['method'], r['product'], int(r['season']), int(r['week']), r['game_id'], r['player_id']):r
                for r in ff.to_dict('records')}
    early = aa.to_dict('records')
    for offer in early:
        actual, appearance, reason = label_for(offer, label_lookup.get(identity(offer)))
        offer.update(actual=actual, appearance=appearance, qualified_label_reason=reason,
                     main_alternate_status=offer.get('main_alternate_status', 'UNKNOWN'))
    prior = doc(plan['prior_84_vectors'], 'PRIOR-COMPLETED-84-VECTORS')
    require(prior['id'] == 'A-B-FTN-COMPLETION-W1-W4-SAVED-JOIN-v1'
            and prior['A_source_bindings'] == plan['prior_A_source_bindings']
            and prior['A_forecast_member_sha256'] == plan['A_forecast_member_sha256'], 'Prior original source/grade version changed')
    prior_lookup = {}
    for cid, rr in prior['vectors'].items():
        require(len(rr) == 84, 'Original completed candidate board differs')
        for row in rr:
            key = cid, row['opportunity_key']
            require(key not in prior_lookup, 'Duplicate original completed vector')
            prior_lookup[key] = row

    PHASE = 'ORIGINAL_B_NATIVE_SOURCE_PANEL_AND_SAVED_FORECASTS'
    native = doc(plan['B_native_panel'], 'B-NATIVE-PANEL')
    require(native['id'] == 'A-W1W9-B-NATIVE-CMP-SOURCE-PANEL-v1'
            and native['state'] == 'PASS_EXACT_NATIVE_SOURCE_MEMBERSHIP_RECONSTRUCTION',
            'B original selected offer membership has not passed')
    require(all(r['native_identity_parity'] and not r['missing_lines'] for r in native['coverage']),
            'Unresolved B native source membership/line qualification')
    later = native['rows']
    require(len(later) == 142 and Counter(int(o['week']) for o in later) == {5:28,6:28,7:28,8:28,9:30},
            'B source-selected actual completion panel differs')
    for o in later:
        require(o['target'] == o['category'] == 'pass_cmp' and o['position'] == 'QB'
                and o['eligible_retained_line'], 'B source role/target/line differs')
        require(o['actual'] is None or (o['appearance'] == 'PLAYED' and o['label_reason'] in
                ['EXPLICIT_REPORTED_ZERO','EXPLICIT_REPORTED_VALUE'] and count_actual(o['actual'],'pass_cmp') is not None),
                'Native B individual completion/appearance unsupported')
        o['source_stream'] = 'B_NATIVE_EXTERNAL_PROVIDER'
    bf, cdf, b_proof = load_B(plan, doc, shared)
    cf, c_proof = load_C(plan, doc)
    ph = prevalence_history(doc(plan['B_football_context'],'B-QB-CONTEXT-EARLIER-PREVALENCE'))

    PHASE = 'FROZEN_SOURCE_UNION_AND_SAVED_OUTPUT_APPEND'
    primary = [o for o in early if o['target'] == 'pass_cmp' and int(o['week']) <= 4] + later
    require(len(primary) == 226 and len({str(o['opportunity_key']) for o in primary}) == 226,
            'Frozen nonoverlapping nine-week source union differs')
    require(Counter(int(o['week']) for o in primary) == {1:10,2:25,3:26,4:23,5:28,6:28,7:28,8:28,9:30},
            'Nine requested source weeks are not all represented')
    reuse_checks = []
    private_boards, private_labels = {}, {}
    vectors_by_panel = {}

    def build(panel_id, cat, board, is_primary=False):
        ids = declared_ids(plan, cat, primary=is_primary)
        vectors = {cid: [] for cid in ids}
        control_meta = {'A::'+r['method']+'::'+r['output']:r for r in plan['A_point_products_by_category'][cat]}
        private_boards[panel_id] = [{k:source_scalar(v,pd) for k,v in o.items()} for o in board]
        private_labels[panel_id] = [dict(opportunity_key=str(o['opportunity_key']),
            label=None if int(o['week'])>=5 and source_name(o).startswith('B_NATIVE') else
            {k:source_scalar(v,pd) for k,v in label_lookup.get(identity(o),{}).items()}) for o in board]
        for offer in board:
            context = offer_context(offer)
            key = str(offer.get('game_id')), str(offer.get('player_id'))
            for cid in ids:
                old = prior_lookup.get((cid, str(offer['opportunity_key']))) if cat == 'pass_cmp' and int(offer['week']) <= 4 else None
                if old is not None:
                    require(all(old[k] == context[k] for k in ['season','week','game_id','player_id','category','line'])
                            and old['actual'] == offer['actual'] and old['appearance'] == offer['appearance'],
                            'Completed first84 source/outcome identity changed')
                    vectors[cid].append(old)
                    reuse_checks.append([panel_id,cid,old['opportunity_key'],sha(encoded(old))])
                    continue
                point = probs = side = fallback = reason = None
                prevalence_proof = None
                if cid in control_meta:
                    spec = control_meta[cid]
                    row = a_lookup.get((cat,spec['method'],spec['output'],2026,int(offer['week']),offer.get('game_id'),offer.get('player_id')))
                    reason = match(row, offer, 'A')
                    if reason is None:
                        # The bound member retains its full output-version field;
                        # a root-declared version is enforced where provided.
                        require(str(row.get('output_procedure_version')) == spec['output_procedure_version'],
                                'A exact saved output/corrector version differs')
                        if finite(row.get('prediction')):
                            point = float(row['prediction'])
                            fallback = source_scalar(row.get('fallback'), pd)
                        else:
                            reason = 'A_NONFINITE_OR_MISSING_SAVED_POINT'
                    side = shared.point_side(point, context['line'])
                elif cid.startswith(B_NAMESPACE + ':'):
                    arm, output = cid.removeprefix(B_NAMESPACE+':').split('::')
                    row = bf.get((arm,*key))
                    reason = match(row, offer, 'B')
                    if reason is None:
                        probs = shared.probabilities(cdf[(arm,*key)], context['line'])
                        point = row[output] if output != 'P2' else None
                        side = shared.probability_side(probs) if output == 'P2' else shared.point_side(point,context['line'])
                        fallback = row.get('fallback')
                elif cid in C_IDS.values():
                    output = next(k for k,v in C_IDS.items() if v == cid)
                    row = cf.get((cat,*key))
                    reason = match(row, offer, 'C')
                    if reason is None:
                        value = row.get(output)
                        if finite(value) and (cat not in COUNTS or value >= 0):
                            point, fallback = float(value), row['fallback']
                        else:
                            reason = 'C_NONFINITE_MISSING_OR_INVALID_COUNT_POINT'
                    side = shared.point_side(point,context['line'])
                elif cid in CAPTURED:
                    field = CAPTURED[cid]
                    if source_name(offer).startswith('B_NATIVE') and finite(offer.get(field)):
                        point, fallback = offer[field], 'CAPTURED_REFERENCE_POINT_NOT_LEARNED_ATTRIBUTION'
                        side = shared.point_side(point,context['line'])
                    else:
                        reason = 'CAPTURED_SITE_POINT_NOT_RETAINED_ON_THIS_SOURCE'
                elif cid == PREVALENCE:
                    require(instant(context['cutoff_utc']) == instant(context['kickoff_utc']),
                            'Existing B prevalence requires the registered query-kickoff horizon')
                    probs,prevalence_proof = earlier_prevalence(ph,instant(context['kickoff_utc']).timestamp(),context['line'])
                    side = shared.probability_side(probs)
                    fallback = ('EMPTY_HISTORY_UNIFORM_ABSTAIN' if not prevalence_proof['unique_earlier_QB_games']
                                else 'ELIGIBLE_EARLIER_ALL_QB_COUNTS')
                else:
                    require(cid in ['ALWAYS_OVER','ALWAYS_UNDER'], 'Unregistered candidate')
                    side = cid.removeprefix('ALWAYS_')
                row = dict(season=2026, week=context['week'], game_id=context['game_id'],
                    player_id=context['player_id'], category=cat, comparator='STRICT_OVER_UNDER',
                    line=context['line'], actual=offer['actual'], appearance=offer['appearance'],
                    point=point, selected_side=side, opportunity_key=context['opportunity_key'],
                    source_stream=source_name(offer), candidate_id=cid, fallback=fallback,
                    unavailability_reason=reason, **(probs or {}))
                row['status'] = shared.grade(row)
                if prevalence_proof is not None:
                    row['prevalence_source_support'] = prevalence_proof
                require(common.status(row) == row['status'], 'Existing grade and common evaluator disagree')
                vectors[cid].append(row)
        vectors_by_panel[panel_id] = vectors
        return report_panel(panel_id,cat,board,vectors,plan,common,shared,np,primary=is_primary)

    panels = [build('CMP_A_W1_W4_PLUS_B_NATIVE_W5_W9','pass_cmp',primary,True)]
    for cat in CATEGORIES:
        board = [o for o in early if o['target'] == cat]
        panels.append(build('A_ANNUAL_W1_W5_'+cat,cat,board))

    PHASE = 'COMPATIBILITY_MEMBERSHIP_AND_FINAL_REPORT'
    a5 = [o for o in early if o['target']=='pass_cmp' and int(o['week'])==5]
    b5 = [o for o in later if int(o['week'])==5]
    pg = lambda o:(o.get('game_id'),o.get('player_id'),'pass_cmp')
    overlap = dict(A_W5=len(a5),B_W5=len(b5),
        common_canonical_player_games=len({pg(o)for o in a5}&{pg(o)for o in b5}),
        exact_numeric_line_player_game_intersection=len({(*pg(o),str(o['line']))for o in a5}&{(*pg(o),str(o['line']))for o in b5}),
        primary_source_choice='B_NATIVE_W5_ONLY_FROZEN_BEFORE_SCORING;A_W5_SENSITIVITY_ONLY',
        duplicate_count_addition=0,
        book_horizon_resolution='Distinct retained source contracts remain explicit; numeric line coincidence alone does not prove same offer.')
    private = dict(id=VERSION,plan_sha256=sha(raw),vectors=vectors_by_panel,
        offer_contracts=private_boards,qualified_A_label_proofs=private_labels,
        native_B_outcome_source_receipt=native.get('football_source_sha256'),
        source_inventory=source_inventory,unchanged_prior_rows=reuse_checks,
        prior_original_vector_sha256=plan['prior_84_vectors'].get('original_sha256',plan['prior_84_vectors'].get('sha256')),
        restrictions='PRIVATE_OWNER_LOCAL_ONLY;SOURCE_CACHED_ACTUALS_NOT_USED;NO_RAW_GITHUB_EXPORT')
    private_buffer = io.BytesIO()
    with zipfile.ZipFile(private_buffer,'w',compression=zipfile.ZIP_LZMA) as archive:
        info = zipfile.ZipInfo('COMPLETE_COMPARISON_VECTORS.json',date_time=(1980,1,1,0,0,0))
        info.compress_type = zipfile.ZIP_LZMA
        archive.writestr(info,encoded(private))
    private_body = private_buffer.getvalue()
    result = dict(id=VERSION,state='COMPLETED_FROZEN_SAVED_OUTPUT_COMPARISON',
        completed_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),plan_sha256=sha(raw),
        panels=panels,B_saved_contract_proof=b_proof,C_saved_contract_proof=c_proof,
        native_source_coverage=native['coverage'],source_inventory=source_inventory,
        primary_source_union_policy=plan['source_union_policy'],W5_overlap=overlap,
        prior_84_reuse=dict(rows_reused_across_panels=len(reuse_checks),
            canonical_reuse_commitment_sha256=sha(encoded(reuse_checks)),
            statement='Original19x84 vectors preserved; no original B W1–4 packets reparsed or early decisions regraded.'),
        remaining_cells=plan['unscored_product_cells'],
        all_twelve_categories={cat:('NINE_WEEK_SOURCE_PANEL_EXECUTED;CANDIDATE_COVERAGE_EXPLICIT' if cat=='pass_cmp'
            else 'PARTIAL_A_ANNUAL_ACTUAL_W1_W5_ONLY' if cat in CATEGORIES else 'SOURCE_BLOCKED_EXACT_OFFER_CONTRACT')
            for cat in CATEGORIES+['anytime_td','nick-chart-ppr-v1']},
        probability_scope='Original B marginal completion laws and existing earlier-line prevalence event control; no jointCMP/ATT claim, point-implied probabilities, C-grid interpolation or EV.',
        selector_scope='No newTopK/TopPicks; existing scoped owner records and unscored cells remain separate.',
        C_coherence='Legacy point diagnostics only; matching guarded selector/certificate unprovided; not primary admitted.',
        incumbent='Captured native adjusted/raw strict-point views are not the exact UI/margin/ranking policy or a nine-week incumbent record.',
        exposure='Previously examined current-vintage retrospective outcomes; not untouched confirmation/original issuance.',
        private_vectors=dict(bytes=len(private_body),sha256=sha(private_body),file=args.private_zip.name),
        resources=dict(CPU_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-wall,
                       RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024),
        counts=dict(new_fits=0,new_model_inference=0,model_loading=0,new_source_collection=0,network_calls=0,
                    new_NFL_games=0,original_issued_picks=0,production_writes=0))
    public_body = gzip.compress(encoded(result),mtime=0)
    sizes = ('; private_zip_bytes='+str(len(private_body))+'; public_gzip_bytes='+str(len(public_body))
             +'; combined_bytes='+str(len(private_body)+len(public_body)))
    require(len(private_body)<=budget['private_vectors_max_bytes'],'Private complete-vector cap exceeded'+sizes)
    require(len(public_body)<=budget['public_aggregate_max_bytes'],'Public aggregate envelope exceeded'+sizes)
    require(len(public_body)+len(private_body)<=budget['worker_output_limit_bytes'],'Combined worker outputs exceed reservation'+sizes)
    immutable(args.private_zip,private_body)
    immutable(args.output,public_body)
    signal.alarm(0)
    print(json.dumps(dict(state=result['state'],primary_offers=len(primary),panels=len(panels),
        public_bytes=len(public_body),public_sha256=sha(public_body),private_bytes=len(private_body),
        private_sha256=sha(private_body),resources=result['resources'])))


def main():
    ap = argparse.ArgumentParser()
    for name in ['plan','c-cache','private-zip','output']:
        ap.add_argument('--'+name,type=Path,required=True)
    ap.add_argument('--plan-sha256',required=True)
    args = ap.parse_args()
    require(not args.output.exists() and not args.private_zip.exists(),'Immutable worker output already exists')
    try:
        run(args)
    except BaseException as error:
        signal.alarm(0)
        failure = dict(id=VERSION,state='FAILED_NO_AUTOMATIC_RETRY',phase=PHASE,
            UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),error_type=type(error).__name__,
            error_sha256=sha(str(error).encode()),new_fits=0,new_model_inference=0,model_loading=0,
            network_calls=0,production_writes=0,
            CPU_seconds=resource.getrusage(resource.RUSAGE_SELF).ru_utime+resource.getrusage(resource.RUSAGE_SELF).ru_stime,
            RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
        path=args.output.with_name('FAILED_'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json')
        immutable(path,encoded(failure))
        print(encoded(failure).decode())
        raise


if __name__ == '__main__':
    main()
