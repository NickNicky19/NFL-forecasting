"""Four new fictional missingness contracts; no original test-suite imports."""
from collections import defaultdict
from copy import deepcopy
import math
import unittest

from nfl_lab import dynamic_opportunity_source as source
from nfl_lab import dynamic_opportunity_source_helpers as helpers
from nfl_lab import dynamic_opportunity_study as study


def fixture():
    calendar = [dict(game_id="fictional-missingness-game", season=2019, week=1,
        season_type="REG", team=own, opponent=other,
        kickoff_utc="2019-08-01T17:00:00+00:00", available_utc="2019-08-08T17:00:00+00:00")
        for own, other in (("FICTIONAL_A", "FICTIONAL_B"), ("FICTIONAL_B", "FICTIONAL_A"))]
    raw = dict(player_id="fictional-missingness-player", season=2019, week=1, season_type="REG",
        team="FICTIONAL_A", carries=2, targets=2, receptions=1, receiving_yards=-3,
        source_row_id="fictional:row:0", source_body_sha256="1"*64)
    history = dict(player_id=raw['player_id'], season=2019, week=1, game_id=calendar[0]['game_id'],
        team="FICTIONAL_A", opponent="FICTIONAL_B", position="RB",
        kickoff_utc=calendar[0]['kickoff_utc'], outcome_available_utc=calendar[0]['available_utc'],
        participation_state="played", source_policy="fictional-qualified-policy",
        rush_att=2, rec_tgt=2, rec=1, rec_yd=-3)
    return calendar, raw, history


def qualified(raw, history, calendar, task):
    return source.qualified_player_rows([raw], [history], calendar, task=task,
        cutoff="2019-08-09T17:00:00+00:00")[0]


def efficiency(raw, history):
    owner = helpers.AnnualInputs.__new__(helpers.AnnualInputs)
    owner.raw_by_key = defaultdict(list, {helpers._key(history): [raw]})
    return owner._efficiency_row(history)


class SourceMissingnessV2Contracts(unittest.TestCase):
    def test_01_normalized_null_or_nan_keeps_played_slot_without_raw_fill(self):
        calendar, original_raw, original_history = fixture()
        for task, rawfield, normalized in (('rush_att', 'carries', 'rush_att'), ('rec_tgt', 'targets', 'rec_tgt')):
            for absent in (None, float('nan')):
                for raw_count in (0, 2):
                    raw = {**original_raw, rawfield: raw_count}
                    history = {**original_history, normalized: absent}
                    result = qualified(raw, history, calendar, task)
                    self.assertIsNone(result['count'])
                    self.assertEqual(result['count_support'], 'missing')
                    self.assertEqual(result['support_reason'], 'missing_qualified_normalized_count')
                    self.assertEqual(result['participation_state'], 'played')
                    self.assertTrue(result['source_qualified'])
                    self.assertEqual(result['source_row_ids'], [raw['source_row_id']])
                    self.assertEqual(result['game_id'], history['game_id'])
                    self.assertEqual(raw[rawfield], raw_count)
                    self.assertTrue(history[normalized] is None or math.isnan(history[normalized]))

    def test_02_raw_missing_is_not_filled_and_explicit_zero_stays_supported(self):
        calendar, raw, history = fixture()
        for absent in (None, float('nan')):
            result = qualified({**raw, 'carries': absent}, history, calendar, 'rush_att')
            self.assertIsNone(result['count'])
            self.assertEqual(result['support_reason'], 'missing_explicit_raw_count')
            credits, orphan = source.credit_rows([{**raw, 'carries': absent}], calendar,
                task='rush_att', cutoff="2019-08-09T17:00:00+00:00", statistics_sha256_by_season={'2019': '1'*64})
            self.assertEqual(len(credits), 1)
            self.assertIsNone(credits[0]['count'])
            self.assertEqual(credits[0]['count_support'], 'missing')
            self.assertEqual(orphan, [])
        raw_zero = {**raw, 'carries': 0}; history_zero = {**history, 'rush_att': 0}
        result = qualified(raw_zero, history_zero, calendar, 'rush_att')
        self.assertEqual(result['count'], 0)
        self.assertEqual(result['count_support'], 'explicit_value')
        for state in ('unknown', 'DNP'):
            result = qualified(raw_zero, {**history_zero, 'participation_state': state}, calendar, 'rush_att')
            self.assertIsNone(result['count'])
            self.assertEqual(result['participation_state'], state)
            self.assertEqual(result['support_reason'], 'unknown_or_DNP_never_becomes_zero')

    def test_03_present_invalid_counts_and_finite_disagreements_still_reject(self):
        calendar, raw, history = fixture()
        for invalid in (True, -1, .5, float('inf'), float('-inf'), 'NaN', '2'):
            self.assertFalse(source.missing_value(invalid))
            for other in (None, 2):
                with self.assertRaisesRegex(ValueError, 'raw/qualified count support conflict'):
                    qualified({**raw, 'carries': invalid}, {**history, 'rush_att': other}, calendar, 'rush_att')
                with self.assertRaisesRegex(ValueError, 'raw/qualified count support conflict'):
                    qualified({**raw, 'carries': other}, {**history, 'rush_att': invalid}, calendar, 'rush_att')
        with self.assertRaisesRegex(ValueError, 'raw/qualified count support conflict'):
            qualified(raw, {**history, 'rush_att': 1}, calendar, 'rush_att')
        self.assertTrue(source.missing_value(None))
        self.assertTrue(source.missing_value(float('nan')))
        self.assertFalse(source.missing_value(0))

    def test_04_efficiency_missing_pairs_preserve_signed_yards_and_strict_conflicts(self):
        _, raw, history = fixture()
        fields = (('targets', 'rec_tgt'), ('receptions', 'rec'), ('receiving_yards', 'rec_yd'))
        selected = []
        for rawfield, normalized in fields:
            for absent in (None, float('nan')):
                for raw_side in (True, False):
                    changed_raw = {**raw, rawfield: absent} if raw_side else deepcopy(raw)
                    changed_history = deepcopy(history) if raw_side else {**history, normalized: absent}
                    result = efficiency(changed_raw, changed_history)
                    self.assertIsNone(result[rawfield])
                    self.assertTrue(result['source_qualified'])
                    self.assertEqual(result['participation_state'], 'played')
                    for other, _ in fields:
                        if other != rawfield:
                            self.assertEqual(result[other], raw[other])
                    selected.append(result)
        # The fixed converter retains its elapsed-slot audit; no omitted slot
        # or missing target becomes an observation of zero production.
        converted = study.fixed_efficiency({'state': 'READY', 'catch_rate': .5, 'YPT': -1}, selected[:8])
        self.assertEqual(len(converted['slots']), 8)
        self.assertIn('missing_targets_no_update', converted['slots'])
        zero = efficiency({**raw, 'targets': 0, 'receptions': 0}, {**history, 'rec_tgt': 0, 'rec': 0})
        self.assertEqual((zero['targets'], zero['receptions'], zero['receiving_yards']), (0, 0, -3))
        for rawfield, normalized in fields:
            with self.assertRaisesRegex(ValueError, 'efficiency raw/qualified field conflict'):
                efficiency(raw, {**history, normalized: raw[rawfield]+1})
            for invalid in (True, float('inf'), 'NaN'):
                with self.assertRaisesRegex(ValueError, 'efficiency raw/qualified field conflict'):
                    efficiency({**raw, rawfield: invalid}, {**history, normalized: None})
                with self.assertRaisesRegex(ValueError, 'efficiency raw/qualified field conflict'):
                    efficiency({**raw, rawfield: None}, {**history, normalized: invalid})


if __name__ == '__main__':
    unittest.main()
