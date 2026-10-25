"""Export reviewed aggregate shapes only; no NFL rows, models or inference."""
import hashlib
import json
from pathlib import Path

SOURCE = Path('/workspace/website-methods-research/resumed/direct-xgboost-binary-scoring-v3-20261023')
DESTINATION = Path(__file__).resolve().parents[1] / 'reports/direct-xgboost-binary-recovery-v2'
PINS = {
    'report.json': '3f97fa78ce4dd43229dc0089c97a70888f71d7341678300ca5512ca9f97d9847',
    'scoring-supervisor-completion.json': 'df6fda65d148c1336b5709419f49dea603bbb254c17395527c8622899676aac9',
    'SCORING_V3_FINISHED.json': '6b78006aa4ef59110e460a1761231b51f67048921f9cdd410443da7f969bcf6b',
    'scored-freeze.json': 'd87173cfd82945e2df5d1539fc821e0381907ca29b100b7ac6731bf0975f3370',
}


def main():
    values = {}
    for name, expected in PINS.items():
        body = (SOURCE / name).read_bytes()
        if hashlib.sha256(body).hexdigest() != expected:
            raise ValueError('saved aggregate/receipt changed: ' + name)
        values[name] = json.loads(body)
    saved, terminal = values['report.json'], values['scoring-supervisor-completion.json']
    report = saved['report']
    if (terminal['state'] != 'COMPLETED' or terminal['returncode'] != 0
            or terminal['limit_reason'] is not None
            or values['SCORING_V3_FINISHED.json']['state'] != 'COMPLETED'
            or values['scored-freeze.json']['state'] != 'SCORED_ROWS_FROZEN'
            or len(values['scored-freeze.json']['slots']) != 6
            or report['target'] != 'anytime_td' or len(report['summaries']) != 16
            or len(report['pairs']) != 80 or len(report['research_nominations']) != 2
            or terminal['new_fits_predictions_model_unpickles_HTTP'] != 0
            or terminal['retention']['charged_bytes'] > 16 * 1024**2):
        raise ValueError('unexpected terminal, coverage or aggregate contract')
    output = dict(
        schema_version='binary-scoring-v3-public-aggregates-v1',
        evidence=saved['evidence'], prior_executions=saved['prior_executions'],
        version=saved['version'], promotion=saved['promotion'],
        future_confirmation=saved['future_confirmation'],
        forecasts=6, scored_forecast_rows=51744,
        new_fits_predictions_model_unpickles_HTTP=0,
        context='Nine original persisted fields exact; season_type absent on both frozen legacy projections; no invented values.',
        source_receipt_SHA256=PINS,
        resources={key: terminal[key] for key in (
            'state', 'returncode', 'limit_reason', 'wall_seconds', 'CPU_seconds',
            'peak_sampled_combined_RSS_bytes', 'child_ru_maxrss_bytes', 'threads')},
        retention=dict(actual_admission_limit_bytes=16777216,
                       inherited_serialized_helper_label_bytes=terminal['retention']['limit_bytes'],
                       new_unique_CAS_bytes=terminal['retention']['new_unique_CAS_bytes'],
                       charged_bytes=terminal['retention']['charged_bytes']),
        report=report,
        limitations=['Exposed reconstructed 2022–2024, not future confirmation.',
                     'Same participation gaps and seven-day historical availability assumption.',
                     'Historical raw Sleeper and SITE unavailable.',
                     'Independent aggregate checks are not additional NFL observations.'])
    DESTINATION.mkdir(parents=True, exist_ok=True)
    (DESTINATION / 'aggregate-report.json').write_text(
        json.dumps(output, sort_keys=True, indent=2, allow_nan=False) + '\n')
    print(json.dumps(dict(state='AGGREGATES_EXPORTED', summary_cells=16, paired_cells=80,
                         NFL_rows_models_source_access_new_scores=0)))


if __name__ == '__main__':
    main()
