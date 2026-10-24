"""One frozen cached-CDF interval comparison; no point model or acquisition.

The externally guarded caller owns the sole invocation. All source/query/model
lineage stays attached to the original saved CDF files. Only interval products
and descriptive interval reports are new.
"""
from contextlib import ExitStack
import json
from pathlib import Path
import time
from unittest.mock import patch

import numpy as np
import pandas as pd

from . import conformal_intervals as core
from .cdf_engine import KEYS, numeric
from .cdf_evaluation import _observed
from .owned_reference_batch import validate_owned_references
from .state import digest, utc

CONTEXT = tuple(dict.fromkeys(KEYS + ['team', 'opponent', 'position', 'kickoff_utc', 'cutoff_utc']))
PREDICTION = (*CONTEXT, 'target', 'method', 'primary_role', 'fallback', 'history_state', 'p10', 'p90')
LABELS = (*KEYS, 'actual', 'participation_state', 'outcome_state')
INTERVAL_CODES = {'RADIUS_FROZEN': 0, 'UNCALIBRATED_FALLBACK_INSUFFICIENT_N': 1,
    'ABSTAIN_MISSING_BASE_INTERVAL': 2}


def subgroup_table(frame, target):
    """Compact derived player/team/opponent/role summaries, never extra games."""
    y, lo, hi, lower, upper = (numeric(frame, name) for name in
        ('actual', 'p10', 'p90', 'interval_lower', 'interval_upper'))
    observed = _observed(frame, core.SUPPORTS[target])
    paired = observed & np.isfinite(lo) & np.isfinite(hi) & np.isfinite(lower) & np.isfinite(upper)
    work = frame[['position', 'team', 'opponent', 'player_id', 'primary_role', 'history_state', 'fallback']].copy()
    flags = dict(planned_rows=np.ones(len(frame), dtype=np.int32), paired_rows=paired,
        unknown_participation=frame.participation_state.eq('unknown'), DNP=frame.participation_state.eq('DNP'),
        played_missing_or_invalid=frame.participation_state.eq('played') & ~observed,
        supported_zero=observed & (y == 0), supported_negative=observed & (y < 0),
        original_fallback_rows=frame.fallback.fillna('').ne(''))
    for name, values in flags.items():
        work[name] = values
    for prefix, a, b in (('saved_cdf', lo, hi), ('candidate', lower, upper)):
        values = dict(width=b-a, coverage=((y >= a) & (y <= b)).astype(float),
            interval_score=(b-a)+(2/core.ALPHA)*(np.maximum(0, a-y)+np.maximum(0, y-b)))
        for name, values in values.items():
            work[prefix+'_'+name] = np.where(paired, values, np.nan)
    aggregations = {name:'sum' for name in flags}
    aggregations.update({prefix+'_'+name:'mean' for prefix in ('saved_cdf', 'candidate')
        for name in ('width', 'coverage', 'interval_score')})
    tables = []
    for population, subset in (('all_offered', work), ('primary_roles', work.loc[work.primary_role])):
        for dimension in ('position', 'team', 'opponent', 'player_id', 'history_state', 'fallback'):
            grouped = subset.groupby(dimension, dropna=False, observed=True).agg(aggregations).reset_index()
            grouped = grouped.rename(columns={dimension:'dimension_value'})
            grouped['dimension_value'] = grouped.dimension_value.fillna('<missing>').astype(str)
            grouped['dimension'], grouped['population'], grouped['target'] = dimension, population, target
            grouped['evidence'] = 'EXPOSED_DESCRIPTIVE; small groups unqualified; main game/week intervals only'
            tables.append(grouped)
    return pd.concat(tables, ignore_index=True)


def exact_clock_context(query, saved, *, year, target):
    """No sorting/coercion, inferred period, identity repair or changed clocks."""
    if not query.columns.is_unique or not saved.columns.is_unique:
        raise ValueError('duplicate context columns')
    if query.duplicated(KEYS).any() or saved.duplicated(KEYS).any():
        raise ValueError('duplicate original offered player-game')
    if any(name not in query or name not in saved for name in CONTEXT):
        raise ValueError('all nine original persisted context columns required')
    pd.testing.assert_frame_equal(query[list(CONTEXT)].reset_index(drop=True),
        saved[list(CONTEXT)].reset_index(drop=True), check_dtype=True, check_exact=True)
    if not query.season.eq(year).all() or not saved.target.eq(target).all() or not saved.method.eq('leaf_cdf').all():
        raise ValueError('original CDF year/target/method differs')
    if ('season_type' in query) != ('season_type' in saved):
        raise ValueError('one-sided original period metadata is not repairable')
    if 'season_type' in query:
        pd.testing.assert_series_equal(query.season_type.reset_index(drop=True), saved.season_type.reset_index(drop=True))
    return dict(rows=len(query), exact_context_columns=list(CONTEXT), optional_period='exact' if 'season_type' in query
        else 'absent_both_no_period_invented', ordered_identity_clock_match=True)


class LabelGate:
    """Only earlier calibration or an already persisted evaluation year."""
    def __init__(self):
        self.frozen_years = set()

    def freeze_year(self, year, completed_targets):
        if year not in (2023, 2024) or year in self.frozen_years or set(completed_targets) != set(core.SUPPORTS):
            raise ValueError('all ten target interval products must freeze once')
        self.frozen_years.add(year)

    def before_labels(self, year):
        if year != 2022 and year not in self.frozen_years:
            raise ValueError('evaluation labels forbidden before complete year interval freeze')


class Session:
    def __init__(self, spec, *, guard):
        # Reuse unchanged owned storage and the accepted effective16MiB wrapper.
        from direct_xgboost_binary_recovery import storage
        self.spec, self.guard = spec, guard
        self.storage, self.output = storage(spec)
        self.bindings = {}
        self.owned = {r['path']: r['sha256'] for r in spec['owned_inputs']}
        self.entry_refs, self.entry = validate_owned_references(self.storage, self.owned)
        self.gate = LabelGate()
        self.queries, self.predictions, self.labels, self.intervals = {}, {}, {}, {}
        self.radii, self.reports = {}, {}
        self.projections = []
        self.rows_read = 0

    def write(self, relative, value):
        from .source_matched_benchmark import clean, sha
        path = self.output / relative
        self.storage.atomic_json(path, clean(value), replace=False)
        self.bindings[relative] = sha(path)
        return path

    def frame(self, relative, value):
        from .source_matched_benchmark import sha
        path = self.output / relative
        value = value.copy(); value.attrs.clear()
        self.storage.write_dataframe(value, path, index=False, compression='zstd')
        self.bindings[relative] = sha(path)
        return path

    def read(self, reference, columns, *, lane):
        self.guard()
        if lane not in {'query_clock', 'prediction_only', 'saved_label'}:
            raise ValueError('undeclared semantic projection lane')
        if reference['path'] not in self.entry_refs or self.owned[reference['path']] != reference['sha256']:
            raise ValueError('interval read outside authenticated originals')
        allowed = set(CONTEXT) | {'outcome_available_utc', 'season_type'} if lane == 'query_clock' else set(PREDICTION) | {'season_type'}
        if lane == 'saved_label':
            self.gate.before_labels(reference['year'])
            allowed = set(LABELS)
        if not set(columns) <= allowed or len(columns) != len(set(columns)):
            raise ValueError('undeclared interval projection')
        frame = pd.read_parquet(reference['path'], columns=columns)
        if len(frame) != reference['rows']:
            raise ValueError('footer and original complete row inventory differ')
        self.rows_read += len(frame)
        if self.rows_read > 600000:
            raise RuntimeError('registered semantic projection row cap')
        self.projections.append(dict(path=reference['path'], sha256=reference['sha256'], columns=list(columns),
            lane=lane, rows=len(frame)))
        self.guard()
        return frame

    def prepare(self):
        if (self.output/'CONSUMED.json').exists():
            raise RuntimeError('sole interval invocation already consumed')
        self.write('CONSUMED.json', dict(invocations=1, retries=0, version=core.VERSION,
            new_base_fits_predictions_model_unpickles_source_HTTP=0))
        planned = 10*sum(self.spec['queries'][str(year)]['rows'] for year in (2023, 2024))
        # Estimate is fixed before values, not an assertion of compression size.
        estimated = 32*planned + 6*1024**2
        usage = self.storage.snapshot()
        if estimated > 16777216 or usage['physical_bytes']+estimated > usage['limit_bytes']:
            raise RuntimeError('pre-value whole interval packet retention estimate does not fit')
        self.write('retention-preflight.json', dict(planned_interval_rows=planned, estimated_bytes=estimated,
            estimate='32B per compact numeric ordinal/bounds/status row plus6MiB subgroup/manifest/report/failure reserve; not guaranteed compression',
            global_usage=usage, actual_admission='unchanged effective16MiB/new and512MiB/global storage checks'))
        for year in (2022, 2023, 2024):
            ref = self.spec['queries'][str(year)]
            columns = [*CONTEXT, 'outcome_available_utc']
            if 'season_type' in ref['columns']:
                columns.append('season_type')
            query = self.read(ref, columns, lane='query_clock')
            if query.empty or query.duplicated(KEYS).any() or not query.season.eq(year).all():
                raise ValueError('full original query inventory required')
            if not (pd.to_datetime(query.cutoff_utc, utc=True) <= pd.to_datetime(query.kickoff_utc, utc=True)).all():
                raise ValueError('original historical cutoff exceeds kickoff')
            earliest = min(utc(v) for v in query.cutoff_utc)
            audit = self.spec['partition_audits'][str(year)]['training']
            if utc(audit['fit_before_utc']) != earliest or audit['predicate'] != f'((season >= 2019) and (season < {year}))':
                raise ValueError('authenticated earlier-only CDF training boundary differs')
            self.queries[year] = query

    def prediction(self, year, target):
        key = year, target
        if key not in self.predictions:
            ref = self.spec['cdf'][str(year)][target]
            columns = list(PREDICTION)
            if 'season_type' in ref['columns']:
                columns.append('season_type')
            saved = self.read(ref, columns, lane='prediction_only')
            receipt = exact_clock_context(self.queries[year], saved, year=year, target=target)
            category = self.spec['categories'][target]
            if not saved.primary_role.equals(saved.position.isin(category['primary_roles'])):
                raise ValueError('original category primary role differs')
            self.predictions[key] = saved
            self.write(f'private/context/{year}/{target}.json', receipt)
        return self.predictions[key]

    def label(self, year, target):
        self.gate.before_labels(year)
        key = year, target
        if key not in self.labels:
            original = self.read(self.spec['cdf'][str(year)][target], list(LABELS), lane='saved_label')
            pd.testing.assert_frame_equal(self.prediction(year, target)[KEYS].reset_index(drop=True),
                original[KEYS].reset_index(drop=True), check_dtype=True, check_exact=True)
            if not original.participation_state.isin(['played', 'DNP', 'unknown']).all():
                raise ValueError('original participation state outside qualified contract')
            self.labels[key] = original
        return self.labels[key]

    def calibrate_year(self, calibration, evaluation):
        start = min(utc(v) for v in self.queries[evaluation].cutoff_utc).isoformat()
        for target in core.SUPPORTS:
            self.guard()
            prediction, labels = self.prediction(calibration, target), self.label(calibration, target)
            merged = prediction.copy()
            for name in ('actual', 'participation_state', 'outcome_state'):
                merged[name] = labels[name].to_numpy()
            merged['outcome_available_utc'] = self.queries[calibration].outcome_available_utc.to_numpy()
            eligible = _observed(merged, core.SUPPORTS[target]).tolist()
            records = merged.to_dict('records')
            for row, flag in zip(records, eligible):
                row['eligible'] = bool(flag)
                for name in ('cutoff_utc', 'kickoff_utc', 'outcome_available_utc'):
                    value = row[name]
                    row[name] = None if pd.isna(value) else value.isoformat() if hasattr(value, 'isoformat') else value
            radius = core.fit_radius(records, target=target, calibration_season=calibration,
                evaluation_season=evaluation, evaluation_start_utc=start, binding=self.spec['core_binding'])
            self.radii[evaluation, target] = radius
            self.write(f'private/radii/{evaluation}/{target}.json', radius)
            self.guard()

    def freeze_year(self, year):
        completed = []
        for target in core.SUPPORTS:
            prediction = self.prediction(year, target)
            issued = core.apply_radius(prediction.to_dict('records'), self.radii[year, target])
            compact = pd.DataFrame(dict(ordinal=np.arange(len(issued), dtype=np.int32),
                interval_lower=[r['interval_lower'] for r in issued], interval_upper=[r['interval_upper'] for r in issued],
                status=np.asarray([INTERVAL_CODES[r['interval_status']] for r in issued], dtype=np.uint8)))
            self.frame(f'private/intervals/{year}/{target}.parquet', compact)
            self.intervals[year, target] = compact
            self.write(f'private/intervals/{year}/{target}-view.json', dict(version=core.VERSION,
                original_cdf=self.spec['cdf'][str(year)][target], original_query=self.spec['queries'][str(year)],
                radius_artifact=f'private/radii/{year}/{target}.json', rows=len(issued),
                ordinal='exact unchanged original query/CDF order', status_codes=INTERVAL_CODES,
                point_CDF_and_original_fallback_changes=0, paired_losses='replay from unchanged labels and frozen ordinal/bounds/status'))
            completed.append(target)
        # Persistence precedes unlocking label reads, including insufficient-N fallbacks.
        self.write(f'INTERVALS_FROZEN_{year}.json', dict(version=core.VERSION, evaluation_year=year,
            targets=completed, bindings=dict(self.bindings), all_original_offers_retained=True))
        self.gate.freeze_year(year, completed)

    def comparison_view(self, year, target):
        reverse = {value:key for key,value in INTERVAL_CODES.items()}
        frame = self.prediction(year, target).copy()
        labels, intervals = self.label(year, target), self.intervals[year, target]
        if not np.array_equal(intervals.ordinal.to_numpy(), np.arange(len(frame))):
            raise ValueError('compact interval consumer order differs')
        for name in ('actual', 'participation_state', 'outcome_state'):
            frame[name] = labels[name].to_numpy()
        frame['interval_lower'] = intervals.interval_lower.to_numpy()
        frame['interval_upper'] = intervals.interval_upper.to_numpy()
        frame['interval_status'] = intervals.status.map(reverse)
        return frame

    def score_year(self, year):
        for target in core.SUPPORTS:
            frame = self.comparison_view(year, target)
            report = core.evaluate_interval_frame(frame, target=target, guard=self.guard)
            report['evaluation_year'], report['calibration_year'] = year, year-1
            report['radius_artifact'] = f'private/radii/{year}/{target}.json'
            self.reports[year, target] = report
            self.write(f'reports/{year}/{target}.json', report)
            self.guard()

    def pooled_report(self):
        pooled = {}
        for target in core.SUPPORTS:
            frame = pd.concat([self.comparison_view(year, target) for year in (2023, 2024)], ignore_index=True)
            report = core.evaluate_interval_frame(frame, target=target, guard=self.guard)
            report['evaluation_years'] = [2023, 2024]
            groups = subgroup_table(frame, target)
            self.frame(f'private/subgroups/{target}.parquet', groups)
            report['private_subgroup_view'] = dict(path=f'private/subgroups/{target}.parquet', rows=len(groups),
                dimensions=['position', 'team', 'opponent', 'player_id', 'history_state', 'fallback'],
                interpretation='same original rows; derived descriptive groups, no independent observations or subgroup qualification')
            self.write(f'reports/pooled/{target}.json', report)
            pooled[target] = report
        return pooled


def run(spec, *, guard, final_verify):
    if spec['registration_id'] != core.VERSION or spec['state'] != 'ROOT_REGISTERED_SEALED':
        raise ValueError('separate frozen interval registration required')
    session = Session(spec, guard=guard)
    try:
        session.prepare()
        session.calibrate_year(2022, 2023)
        session.freeze_year(2023)
        # Only memory is released; every original/calibration artifact stays
        # retained and authenticated. These rows are never decoded a second time.
        for cache in (session.predictions, session.labels):
            for key in [key for key in cache if key[0] == 2022]:
                del cache[key]
        # These labels also calibrate the next block; no 2023 score can tune it.
        session.calibrate_year(2023, 2024)
        session.freeze_year(2024)
        session.score_year(2023)
        session.score_year(2024)
        pooled = session.pooled_report()
        _, exit_receipt = validate_owned_references(session.storage, session.owned)
        final_verify(); guard()
        matrix = {target:dict(state='EXPOSED_INTERVAL_COMPARISON_COMPLETE', product='80_percent_interval_only',
            reports=[f'reports/{year}/{target}.json' for year in (2023, 2024)], point_change=False,
            confirmation=False, release_ready=False) for target in core.SUPPORTS}
        matrix.update(fantasy_ppr=dict(state='BLOCKED_EXACT_LABEL_CONTRACT'),
            anytime_td=dict(state='NOT_AN_INTERVAL_TARGET_RETAINED_PROBABILITY_REFERENCE'))
        session.write('report.json', dict(version=core.VERSION, state='COMPLETE', radii=20, matrix=matrix,
            reports=[report for _,report in sorted(session.reports.items())], original_points_laws_sources_unchanged=True,
            pooled_exposed_reports=pooled,
            individual_player_role_team_opponent_subgroups='COMPACT_PRIVATE_DERIVED_SUMMARIES; main game/week uncertainty, small groups unqualified',
            owned_entry=session.entry, owned_exit=exit_receipt, projections=session.projections,
            new_base_fits_predictions_models_sources_HTTP=0, confirmation_or_coverage_guarantee=False,
            retention=session.storage.report_retention(), frozen_bindings=dict(session.bindings)))
    except BaseException as error:
        session.write('FAILED.json', dict(version=core.VERSION, exception=type(error).__name__,
            message=str(error)[:500], radii_completed=len(session.radii), full_reports_completed=len(session.reports),
            frozen_years=sorted(session.gate.frozen_years), original_artifacts_unchanged=True))
        raise
