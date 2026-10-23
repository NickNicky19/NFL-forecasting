"""Fictional identities/values only; never open an actual NFL input."""
import copy
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from nfl_lab import ftn_zero_join as join


def identity(number):
    return f'00-{number:07d}'


def fixtures():
    raw = []
    query = []
    accepted = []
    for number, position in ((1, 'QB'), (2, 'RB'), (3, 'CB')):
        row = dict.fromkeys(join.PRIMITIVES, 0)
        row.update(game_id=join.GAME, season=2024, week=1, season_type='REG',
            player_id=identity(number), team='BAL', opponent_team='KC', position=position)
        raw.append(row)
    raw[1].update(rushing_yards=-4, receiving_yards=4)
    for number, position in ((1, 'QB'), (2, 'RB'), (4, 'WR')):
        row = dict(season=2024, week=1, game_id=join.GAME, player_id=identity(number),
            position=position, team='BAL', opponent='KC')
        query.append(row)
        accepted.append(dict(row, official_physical_event=False, participation_state='unknown',
            participation_evidence='no_game_specific_participation_contract'))
    accepted[1].update(official_physical_event=True, participation_state='played',
        participation_evidence='positive_official_nfl_physical_event')
    players = [identity(i) for i in (1, 2, 3, 5)]
    appearance = pd.DataFrame([dict(nflverse_game_id=join.GAME, play_id=1,
        players_on_play=json.dumps(players), offense_players=json.dumps(players[:2]),
        defense_players=json.dumps(players[2:]), n_offense=2, n_defense=2)], columns=join.APPEARANCE_COLUMNS)
    return (pd.DataFrame(raw, columns=join.RAW_COLUMNS), appearance,
        pd.DataFrame(accepted, columns=join.HISTORY_COLUMNS), pd.DataFrame(query, columns=join.QUERY_COLUMNS))


def selected(records, number, target):
    return records.loc[records.player_id.eq(identity(number)) & records.target.eq(target)].iloc[0]


def test_complete_union_primary_support_components_and_input_preservation():
    frames = fixtures()
    originals = [x.copy(deep=True) for x in frames]
    records, report = join.audit_zero_candidates(*frames, expected_witnesses=4)
    assert len(records) == 5 * 12
    assert report['coverage']['raw_planned_rows'] == 3
    assert report['coverage']['witness_players'] == 4
    assert report['coverage']['offered_players'] == 3
    assert report['coverage']['union_players'] == 5
    assert report['coverage']['witness_without_raw'] == 1
    assert report['coverage']['offered_without_raw_or_witness'] == 1
    assert selected(records, 1, 'pass_int').candidate_new_support
    assert not selected(records, 3, 'pass_int').candidate_new_support
    assert selected(records, 3, 'pass_int').population == 'NOT_OFFERED'
    assert selected(records, 2, 'rush_rec_yd').zero_kind == 'SIGNED_CANCELLATION'
    assert selected(records, 2, 'rush_rec_yd').already_supported_zero
    assert selected(records, 2, 'anytime_td').zero_kind == 'BOTH_COMPONENTS_ZERO'
    assert selected(records, 4, 'rec').target_state == 'NO_RAW_STAT_ROW'
    assert selected(records, 5, 'rec').target_state == 'NO_RAW_STAT_ROW'
    assert records.loc[records.target.eq('fantasy_ppr'), 'target_state'].eq('BLOCKED_EXACT_PPR').all()
    assert report['zeros_applied'] == 0
    encoded = json.dumps(report, allow_nan=False)
    assert not any(identity(i) in encoded for i in range(1, 6))
    for original, frame in zip(originals, frames):
        assert_frame_equal(original, frame, check_exact=True)


@pytest.mark.parametrize('field,value,state', [
    ('rushing_tds', None, 'MISSING_COMPONENT'),
    ('rushing_tds', -1, 'INVALID_COMPONENT'),
    ('receiving_tds', 0.5, 'INVALID_COMPONENT'),
    ('receiving_tds', np.inf, 'INVALID_COMPONENT'),
    ('receiving_tds', '0', 'INVALID_COMPONENT'),
])
def test_both_td_components_required_without_coercion(field, value, state):
    frames = list(fixtures())
    frames[0] = frames[0].astype({field: object})
    frames[0].loc[1, field] = value
    records, _ = join.audit_zero_candidates(*frames)
    row = selected(records, 2, 'anytime_td')
    assert row.target_state == state
    assert not row.known_zero and not row.already_supported_zero


def test_missing_signed_component_is_not_zero_and_signed_yards_remain_valid():
    frames = list(fixtures())
    frames[0].loc[1, 'receiving_yards'] = np.nan
    records, _ = join.audit_zero_candidates(*frames)
    assert selected(records, 2, 'rush_rec_yd').target_state == 'MISSING_COMPONENT'
    assert selected(records, 2, 'rush_yd').target_state == 'KNOWN_NONZERO'


@pytest.mark.parametrize('damage', ['unknown_old_flag', 'unknown_old_state', 'metadata_position_conflict',
    'raw_team_conflict', 'missing_position', 'empty_position', 'nontext_position', 'missing_old_metadata', 'duplicate_raw'])
def test_conflicting_or_ambiguous_evidence_never_becomes_a_candidate(damage):
    frames = list(fixtures())
    if damage == 'unknown_old_flag':
        frames[2]['official_physical_event'] = frames[2].official_physical_event.astype(object)
        frames[2].loc[0, 'official_physical_event'] = pd.NA
    elif damage == 'unknown_old_state':
        frames[2].loc[0, 'participation_state'] = pd.NA
    elif damage == 'metadata_position_conflict':
        frames[2].loc[0, 'position'] = 'RB'
    elif damage == 'raw_team_conflict':
        frames[0].loc[0, ['team', 'opponent_team']] = ['KC', 'BAL']
    elif damage == 'missing_position':
        frames[3].loc[0, 'position'] = pd.NA
    elif damage == 'empty_position':
        frames[3].loc[0, 'position'] = ''
    elif damage == 'nontext_position':
        frames[3].loc[0, 'position'] = 0
    elif damage == 'missing_old_metadata':
        frames[2] = frames[2].iloc[1:].copy()
    elif damage == 'duplicate_raw':
        frames[0] = pd.concat([frames[0], frames[0].iloc[[0]]], ignore_index=True)
    records, report = join.audit_zero_candidates(*frames)
    assert not selected(records, 1, 'pass_int').candidate_new_support
    if damage in ('missing_position', 'empty_position', 'nontext_position'):
        assert selected(records, 1, 'pass_int').population == 'OFFERED_UNKNOWN_POSITION'
    if damage == 'duplicate_raw':
        assert report['coverage']['raw_planned_rows'] == 4
        assert selected(records, 1, 'pass_int').target_state == 'AMBIGUOUS_RAW_ROWS'


@pytest.mark.parametrize('damage', ['extra_column', 'query_duplicate', 'bad_id', 'null_context',
    'wrong_week', 'wrong_game', 'wrong_team', 'wrong_type', 'union_mismatch', 'negative_play', 'witness_count'])
def test_schema_identity_context_and_appearance_fail_closed(damage):
    frames = list(fixtures())
    expected = None
    if damage == 'extra_column':
        frames[0]['unapproved'] = 0
    elif damage == 'query_duplicate':
        frames[3] = pd.concat([frames[3], frames[3].iloc[[0]]])
    elif damage == 'bad_id':
        frames[0].loc[0, 'player_id'] = ' 00-0000001'
    elif damage == 'null_context':
        frames[0].loc[0, 'game_id'] = pd.NA
    elif damage == 'wrong_week':
        frames[0].loc[0, 'week'] = 2
    elif damage == 'wrong_game':
        frames[1].loc[0, 'nflverse_game_id'] = 'OTHER'
    elif damage == 'wrong_team':
        frames[3].loc[0, 'opponent'] = 'OTHER'
    elif damage == 'wrong_type':
        frames[0].loc[0, 'season_type'] = 'POST'
    elif damage == 'union_mismatch':
        frames[1].loc[0, 'players_on_play'] = json.dumps([identity(1)])
    elif damage == 'negative_play':
        frames[1].loc[0, 'play_id'] = -1
    else:
        expected = 92
    with pytest.raises(join.JoinNotReady) as captured:
        join.audit_zero_candidates(*frames, expected_witnesses=expected)
    assert captured.value.diagnostic['planned_rows'] == dict(raw=len(frames[0]), appearance=len(frames[1]),
        accepted=len(frames[2]), query=len(frames[3]))
    assert captured.value.diagnostic['successful_subset_returned'] is False


def test_complete_union_overflow_no_successful_subset():
    frames = list(fixtures())
    base = frames[3].iloc[0].to_dict()
    frames[3] = pd.DataFrame([dict(base, player_id=identity(i)) for i in range(10, 210)])
    with pytest.raises(join.JoinNotReady, match='union exceeds200'):
        join.audit_zero_candidates(*frames)


def test_global_forecast_freeze_exact_query_binding():
    sha = 'a' * 64
    freeze = dict(state='GLOBAL_FORECASTS_FROZEN', bindings={join.QUERY_RELATIVE: sha},
        slots=[dict(year=2024, state='PREDICTION_FROZEN', query=join.QUERY_RELATIVE)])
    join.validate_global_freeze(freeze, sha)
    for change in ('state', 'hash', 'path', 'no_successful_2024'):
        changed = copy.deepcopy(freeze)
        if change == 'state':
            changed['state'] = 'RUNNING'
        elif change == 'hash':
            changed['bindings'][join.QUERY_RELATIVE] = 'b' * 64
        elif change == 'path':
            changed['slots'][0]['query'] = 'other.parquet'
        else:
            changed['slots'][0]['year'] = 2023
        with pytest.raises(join.JoinNotReady):
            join.validate_global_freeze(changed, sha)


def test_unbound_template_rejected_before_any_input_decode(tmp_path, monkeypatch):
    template = json.loads((Path(__file__).parents[1] / 'config/ftn-explicit-zero-join-template-v1.json').read_bytes())
    path = tmp_path / 'fictional-template.json'
    body = json.dumps(template).encode()
    path.write_bytes(body)
    def forbidden(*args, **kwargs):
        raise AssertionError('unbound template must never open inputs')
    monkeypatch.setattr(join, '_read', forbidden)
    monkeypatch.setattr(join, '_fixed_table', forbidden)
    with pytest.raises(join.JoinNotReady, match='unbound template'):
        join.run_join(path, hashlib.sha256(body).hexdigest())


def test_authenticated_regular_binding_and_json_parser(tmp_path):
    path = tmp_path / 'fictional-body'
    path.write_bytes(b'fictional')
    binding = dict(path=str(path), sha256=hashlib.sha256(b'fictional').hexdigest(), bytes=9)
    assert join._read(binding) == b'fictional'
    with pytest.raises(join.JoinNotReady):
        join._read(dict(binding, sha256='0' * 64))
    path.unlink()
    path.symlink_to(tmp_path / 'absent')
    with pytest.raises(ValueError):
        join._read(binding)
    for encoded in ('{"duplicate":1,"duplicate":2}', '{"value":NaN}'):
        with pytest.raises(join.JoinNotReady):
            join._json(encoded)


def test_fictional_arrow_predicate_projection_and_count_before_materialization(tmp_path):
    import pyarrow as pa
    import pyarrow.parquet as pq
    path = tmp_path / 'fictional.parquet'
    pq.write_table(pa.table({'game_id': [join.GAME, 'OTHER', join.GAME],
        'player_id': [identity(1), identity(2), identity(3)], 'unapproved': ['private'] * 3}), path)
    table = join._fixed_table(path, ['game_id', 'player_id'], limit=2)
    assert table.column_names == ['game_id', 'player_id']
    assert table.num_rows == 2
    with pytest.raises(join.JoinNotReady, match='materialization cap'):
        join._fixed_table(path, ['game_id', 'player_id'], limit=1)
    with pytest.raises(join.JoinNotReady, match='columns absent'):
        join._fixed_table(path, ['game_id', 'absent'])
