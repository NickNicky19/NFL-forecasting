#!/usr/bin/env python3
"""Render authenticated SAFE aggregate results; no row/model/statistic-source decode."""
import gzip
import hashlib
import io
import json
from pathlib import Path
import resource
import time
import zipfile
from zoneinfo import ZoneInfo
from datetime import datetime

resource.setrlimit(resource.RLIMIT_CPU, (12, 12))
resource.setrlimit(resource.RLIMIT_AS, (256 << 20, 256 << 20))
started = time.monotonic()
cpu = time.process_time()
HERE = Path(__file__).resolve().parents[1]
OUT = HERE / 'reports/top-player-cached-20261028'
complete = json.loads((OUT / 'native-v1/COMPLETE.json').read_bytes())


def bound_bytes(ref):
    b = Path(ref['path']).read_bytes()
    assert len(b) == ref['bytes']
    assert hashlib.sha256(b).hexdigest() == ref['sha256']
    return b


compressed = bound_bytes(complete['safe_output'])
body = gzip.decompress(compressed)
assert len(body) == complete['safe_output']['uncompressed_bytes']
assert hashlib.sha256(body).hexdigest() == complete['safe_output']['uncompressed_sha256']
result = json.loads(body)
# Parent explicitly authorized this metadata member, never the row-bearing members.
freeze = bound_bytes(complete['membership_freeze'])
with zipfile.ZipFile(io.BytesIO(freeze)) as z:
    manifest_bytes = z.read('MANIFEST.json')
assert hashlib.sha256(manifest_bytes).hexdigest() == '22a4cf52db96085e786d87778faa829363ad74d3b4520ccdf1ade60eb0c03a23'
manifest = json.loads(manifest_bytes)
assert manifest['rows'] == 15860
assert manifest['target_evaluation_labels_decoded'] == 0
assert complete['state'] == 'TOP_PLAYER_CACHED_COMPARISONS_COMPLETE'
records = result['records']
paired = result['paired']
assert len(records) == 6216 and len(paired) == 747
targets = ['pass_yd','pass_td','pass_cmp','pass_att','pass_int','rush_yd',
           'rush_att','rec','rec_yd','rush_rec_yd','chart_ppr','anytime_td']
names = ['Passing yards','Passing TDs','Completions','Passing attempts','Interceptions',
         'Rushing yards','Carries','Receptions','Receiving yards','Rush + rec yards',
         'Chart PPR (new contract)','Anytime rush/rec TD']
labels = dict(zip(targets,names))
short = {
    'CATBOOST_MEDIUM':'CAT', 'CDF_MEAN':'CDF-e', 'CDF_MEDIAN':'CDF-m',
    'RESPONSE_CDF_MEAN':'RCDF-e', 'CATBOOST_COUNT_MEAN':'CAT-e',
    'COUNT_A_MEAN':'CountA-e', 'LAB_CDF':'CDF-p', 'TD_EQUAL_CDF_CAT':'Mix-p',
    'GLOBAL_CHART_MEDIAN_2024':'Global-m', 'HGB_CHART_MEDIAN_V1':'HGB-m',
    'LEAF_CDF_CHART_MEAN_V1':'Leaf-e', 'LEAF_CDF_CHART_MEDIAN_V1':'Leaf-m',
    'POSITION_CHART_MEAN_2024':'Position-e', 'POSITION_CHART_MEDIAN_2024':'Position-m',
    'ROLE_LAW_CHART_MEAN_V1':'Role-e', 'ROLE_LAW_CHART_MEDIAN_V1':'Role-m'}
products = {'mean':'e', 'mean_objective_point':'eo', 'median':'m',
            'median_objective_point':'mo', 'probability':'p'}
reference = dict(zip(targets, ['CDF_MEDIAN','CDF_MEAN','CDF_MEAN','CDF_MEAN','CDF_MEAN',
                             'CDF_MEDIAN','COUNT_A_MEAN','COUNT_A_MEAN','CATBOOST_MEDIUM',
                             'CATBOOST_MEDIUM','HGB_CHART_MEDIAN_V1','TD_EQUAL_CDF_CAT']))
season = [x for x in records if x['period'] == '2026_W1_6']
original = {t:[x for x in season if x['target']==t and x['position']=='ALL_ORIGINAL_PRIMARY_ROLES']
            for t in targets}
groups = ['full','top10','top15','top20']
bands = ['rank1_10','rank11_15','rank16_20','remainder']
position_order = {'QB':0,'RB':1,'WR':2,'TE':3,'FB':4}
target_positions = [(t,p) for t in targets for p in sorted(
    {x['position'] for x in season if x['target']==t and x['position']!='ALL_ORIGINAL_PRIMARY_ROLES'},
    key=lambda p:position_order[p])]


def loss(x, kind):
    v = x['metrics']['probability_scores']['Brier'] if kind=='Brier' else x['metrics'].get(kind)
    return float('inf') if v is None else v


def best(rows, kind, allowed=None):
    eligible = [x for x in rows if x['metrics']['scored'] and
                (allowed is None or x['product'] in allowed)]
    return min(eligible, key=lambda x:(loss(x,kind),x['method'])) if eligible else None


def display(x, kind='MAE'):
    if x is None:
        return 'unscored'
    return f"{short[x['method']]} {loss(x,kind):.3f} ({x['metrics']['scored']}/{x['metrics']['planned']})"


def pair_for(t,p,g,method,kind):
    return next((v for v in paired if (v['target'],v['position'],v['group'],v['candidate'],v['loss']) ==
                 (t,p,g,method,kind)),None)


full = []
for t in targets:
    rows = original[t]
    counts = {(v['metrics']['planned'],v['metrics']['scored']) for v in rows}
    assert len(counts)==1
    point = best(rows,'Brier' if t=='anytime_td' else 'MAE',None if t=='anytime_td' else ['median','median_objective_point'])
    mean = None if t=='anytime_td' else best(rows,'MSE',['mean','mean_objective_point'])
    ref = next(x for x in rows if x['method']==reference[t])
    full.append({'target':t,'median_or_probability_leader':point,'mean_leader':mean,'reference':ref})

cohorts = []
band_rows = []
for t,p in target_positions:
    for g in groups:
        rows = [x for x in season if (x['target'],x['position'],x['group'])==(t,p,g)]
        assert len({(x['metrics']['planned'],x['metrics']['scored']) for x in rows})==1
        k='Brier' if t=='anytime_td' else 'MAE'
        winner=best(rows,k)
        ref=next(x for x in rows if x['method']==reference[t])
        q=pair_for(t,p,g,winner['method'],k) if winner else None
        m=ref['metrics']
        cohorts.append([t,p,g,None if winner is None else short[winner['method']],
                        None if winner is None else products[winner['product']],
                        k,None if winner is None else loss(winner,k),m['scored'],m['planned'],
                        short[reference[t]],None if not m['scored'] else loss(ref,k),
                        None if q is None else q['improvement_percent'],
                        None if q is None else q['intervals']['game_id']['interval']])
    for g in bands:
        x=next(x for x in season if (x['target'],x['position'],x['group'],x['method']) ==
               (t,p,g,reference[t]))
        m=x['metrics']
        band_rows.append([t,p,g,short[reference[t]],m['MAE'],m['scored'],m['planned'],
                          m.get('share_of_full_position_absolute_error'),m['outcome_states'].get('unknown',0),
                          m['played_missing']])

# Look up the actual retained share key; no new grading or changed population.
def compact_full(v):
    t=v['target']; point=v['median_or_probability_leader']; mean=v['mean_leader']; ref=v['reference']
    def compact_point(x):
        if x is None:return None
        m=x['metrics']
        return [short[x['method']],products[x['product']],m['MAE'],m['MSE'],m['RMSE'],m['bias'],
                m['p90_AE'],m['p95_AE'],m['strict_within'],m['inclusive_within'],
                m['fallback_scored'],m['fallback_planned'],m['original_forecast_clock_unknown']]
    return {'target':t,'n':ref['metrics']['scored'],'planned':ref['metrics']['planned'],
            'median_or_probability':compact_point(point),'mean':compact_point(mean),
            'reference':[short[ref['method']],products[ref['product']],ref['metrics']['MAE'],ref['metrics']['MSE']]}

summary={'version':'top-player-cached-v1-20261028-readable-v1','state':'CACHED_COHORT_DIAGNOSTIC_ONLY',
         'scope':result['scope']['evaluation'],'source':complete['safe_output'],'membership_freeze':complete['membership_freeze'],
         'grade':complete['grade'],'methods':short,'products':products,
         'full_product_columns':['method','product','MAE','MSE_or_Brier','RMSE','bias','p90_AE','p95_AE',
                                 'strict_within','inclusive_within','fallback_scored','fallback_planned','unknown_forecast_clock'],
         'full_category_leaders':[compact_full(x) for x in full],
         'cohort_columns':['target','position','group','method','product','primary','loss','scored','planned',
                           'reference','reference_loss','improvement_percent_vs_reference','nominal_game_CI'],
         'cohorts':cohorts,
         'band_columns':['target','position','band','reference','MAE','scored','planned','AE_share','unknown_participation','played_missing'],
         'bands':band_rows,'ranking_metadata':{k:manifest[k] for k in ['deadlines','rank_source_audit','original_query_clock_census','rows']},
         'diagnostic_columns':['target','position','ranked_player_weeks','unranked_query_rows','unknown_forecast_clock'],
         'diagnostics':[[d[k] for k in ['target','position','ranked_player_weeks','unranked_query_rows','original_forecast_clock_unknown']]
                        for d in result['diagnostics']],'execution':complete['usage'],
         'new_specialization_fits':0,'website_relative_comparison':'UNAVAILABLE_NO_AUTHENTIC_HISTORICAL_SITE_R0',
         'deployment':'NONE_BY_THIS_STUDY','limitations':result['limitations']}

# Readable report keeps all position-specific comparisons, while the full safe gzip retains all weeks/methods.
lines=['# Top-player cached comparison — 2026 Weeks 1–6','',
       'Completed October 28, 2026 (America/Chicago). **This analysis regrades retained predictions; it trains no specialized model.** '
       'It does not establish a new gain against the website. The ranked groups use one shared prior-opportunity ordering per position/category/week.',
       '', '## Full original population: products stay separate','',
       'MAE is the average miss in yards, counts or chart points. MSE selects the mean product; RMSE returns it to original units. '
       'ATD uses Brier loss. These are the lowest recorded losses among this saved candidate set, on the same stated population.', '',
       '| Category | Scored / query rows | Median-product leader: MAE (ATD: Brier) | Mean-product leader: MSE / RMSE |',
       '|---|---:|---|---|']
for v in full:
    t=v['target']; x=v['median_or_probability_leader']; y=v['mean_leader']; m=v['reference']['metrics']
    point=display(x,'Brier' if t=='anytime_td' else 'MAE')
    # Population is already its own column.
    point=point.rsplit(' (',1)[0]
    mean='—' if y is None else f"{short[y['method']]} {y['metrics']['MSE']:.6f} / {y['metrics']['RMSE']:.3f}"
    lines.append(f"| {labels[t]} | {m['scored']}/{m['planned']} | {point} | {mean} |")
lines += ['', '**Chart PPR is `nick-chart-ppr-v1`, not the old exact website-PPR target.** The latter is not validated by these labels. '
          'Median products and means answer different questions. A count-median MAE lead does not qualify replacement of a mean or probability component.',
          '', '## Shared top-10 / 15 / 20 groups by position','',
          'Each cell gives the lowest observed **point MAE** (ATD: Brier), method, and **scored/planned** rows. '
          'Unlike the full typed table, this diagnostic permits all saved point recipes to compete on MAE; product labels are retained in the summary. '
          'Top N means players in each weekly position/category pool, not N independent games. Membership is identical across methods.', '',
          '| Category / position | Full | Top 10 | Top 15 | Top 20 |',
          '|---|---|---|---|---|']
for t,p in target_positions:
    cells=[]
    for g in groups:
        row=next(v for v in cohorts if v[:3]==[t,p,g])
        cells.append(f"{row[3]} {row[6]:.3f} ({row[7]}/{row[8]})" if row[6] is not None else f"unscored (0/{row[8]})")
    lines.append(f"| {t} / {p} | "+' | '.join(cells)+' |')
lines += ['', 'A top-group average can be **larger** than the full-population average because high-volume players have more absolute yardage/count risk. '
          'Neither direction measures the benefit of specialization: every group uses the same original models. Missing-rank players remain in the full population and remainder.',
          '', '## Disjoint rank bands: retained reference error and coverage','',
          'Cells are **reference MAE [scored/planned]**. The four disjoint bands reproduce the full reference population and total absolute error; '
          'the machine summary retains each band’s share. ATD MAE below is a descriptive diagnostic only; Brier above remains primary. '
          'An additional overlapping `unranked` group is retained in the complete safe aggregate.', '',
          '| Category / position | Ranks 1–10 | 11–15 | 16–20 | Remainder incl. unranked |',
          '|---|---|---|---|---|']
for t,p in target_positions:
    cells=[]
    for g in bands:
        row=next(v for v in band_rows if v[:3]==[t,p,g])
        cells.append(f"{row[4]:.3f} [{row[5]}/{row[6]}]" if row[4] is not None else f"— [0/{row[6]}]")
    lines.append(f"| {t} / {p} | "+' | '.join(cells)+' |')
lines += ['', '## Timing, coverage and evidence boundaries','',
          '- Evaluation: **2026 regular-season Weeks 1–6, 93 games**. Exactly **15,860 category-query opportunities** were frozen before target labels; '
          'overlapping categories and model rows are not extra independent NFL outcomes.',
          '- Original generic query pool: **2,999** rows. All original query cutoffs equal kickoff: these are historical **left-limit reconstructions**, '
          'not originally issued pregame forecasts. The old seven-day availability assumption remains unchanged; no live consumer guard was relaxed.',
          '- Rankings admit source records strictly before the shared weekly deadline, then take the last eight eligible game slots by game chronology. '
          'They use pass attempts (QB), carries (RB rushing), targets (receiving), or carries+targets (combined/ATD; position-specific chart rules). '
          'No target-game values, outcomes or model-specific ranking enter membership. Older seasons and potentially prior postseason can enter history.',
          '- History clock audit: no unknown/conflicting clock keys, invalid identities, quarantined rows or conflicting slots in this retained source. '
          'This does not authenticate original publication timestamps. Source availability is still reconstructed.',
          '- Unsupported participation and played-missing labels stay unscored and in planned coverage. Missing rank is never zero. '
          'Chart has **163 unknown-participation queries**; source chart states were retained and unexpected states would stop execution.',
          '- No authentic historical SITE/R0/raw-provider values or sportsbook-offered population in this panel. '
          'No new threshold-probability, correct-side, close-and-correct, market/EV or paper-return result is claimed.',
          '- Six weeks are insufficient for the registered minimum-eight-cluster week interval. Game-cluster intervals (500 resamples) are nominal exposed-development diagnostics, '
          'not adjusted confirmation or durable superiority. Full paired results retain adverse findings.',
          '- This wave does not execute the queued 2025 cohort panel or genuine Week 7 cohort analysis, and deploys nothing. '
          'No subgroup-specific model or irreducible error floor was established.',
          '', '| Week | Common ranking deadline (America/Chicago) | Admitted history rows | Last-8 slot rows |',
          '|---|---|---:|---:|']
for a in manifest['rank_source_audit']:
    d=datetime.fromisoformat(a['deadline']).astimezone(ZoneInfo('America/Chicago')).strftime('%Y-%m-%d %H:%M %Z')
    lines.append(f"| {a['week']} | {d} | {a['eligible_history_rows']} | {a['last8_slot_rows']} |")
lines += ['', '## Reproduction, private evidence and operating status','',
          'The retained private grade includes `COMPARISON_ROWS.parquet` with original prediction, actual, error context, membership, source keys, '
          'fallback and clock status; it is not a public website asset. Membership and grade were each durably frozen and exact-byte read back. '
          'The safe aggregate contains **6,216 complete weekly/season group records and 747 paired contrasts**, with all saved methods, missingness, '
          'bias, tails, tolerances, probability reliability and intervals.',
          '', f"Actual main: **{complete['usage']['CPU_seconds']:.2f} CPU s / {complete['usage']['wall_seconds']:.2f} wall s**, "
          f"peak RSS **{complete['usage']['RSS_bytes']:,} bytes**; **2 CAS writes**, **0 new fits**, **0 model loads**, **0 new forecast inference**, **0 HTTP**. "
          'All failures/unexecuted earlier proposals remain preserved. Actual backend settings are UNATTESTED.',
          '', '- [Complete safe aggregate: all weeks/methods/groups](PUBLIC_RESULTS.json.gz)',
          '- [Compact leaders, bands, diagnostics and exact metadata](SUMMARY.json)',
          '- [Exact-byte persistence and resource receipt](native-v1/COMPLETE.json)',
          '- [Sealed-plan preparation](../../config/top-player-cached-v1.preseal.json)',
          '- [Zero-fit comparison worker](../../tools/top_player_cached_v1.py)',
          '- [Safe aggregate report renderer](../../tools/top_player_cached_report_v1.py)',
          '', '`CDF-m/e`: empirical leaf-CDF median/mean. `RCDF-e`: response-CDF mean. `CAT`: CatBoost median-objective point for yards, '
          'binary probability for ATD. `CAT-e`: count mean-objective point. `CountA-e`: corrected mean-fallback Count A point recipe. '
          '`Mix-p`: equal CDF/CatBoost ATD probability. `Leaf-m/e`: chart leaf-CDF median/mean. '
          '`HGB-m`: chart absolute-error boosting. Remaining chart position/global/role priors retain their own identities in the machine evidence.', '']
report='\n'.join(lines).encode()
assert len(report)<=16384, len(report)
summary['render_usage']={'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-started,
                         'new_NFL_decodes':0,'private_metadata_member':'MANIFEST.json only',
                         'private_row_members_decoded':0,'CAS':0,'network':0}
def presentation(value):
    if isinstance(value,float):return float(f'{value:.8g}')
    if isinstance(value,list):return [presentation(v) for v in value]
    if isinstance(value,dict):return {k:presentation(v) for k,v in value.items()}
    return value
summary['presentation_precision']='Eight significant digits; authenticated PUBLIC_RESULTS.json.gz retains exact numerical values.'
summary['retained_report_format_failure']={'stage':'summary_size_before_any_output_write','proposed_bytes':38959,'cap':32768,'NFL_reads':0,'scoring':0,'CAS':0}
summary_bytes=json.dumps(presentation(summary),separators=(',',':'),allow_nan=False).encode()+b'\n'
assert len(summary_bytes)<=32768,len(summary_bytes)
(OUT/'README.md').write_bytes(report)
(OUT/'SUMMARY.json').write_bytes(summary_bytes)
print(json.dumps({'README':{'bytes':len(report),'sha256':hashlib.sha256(report).hexdigest()},
                  'SUMMARY':{'bytes':len(summary_bytes),'sha256':hashlib.sha256(summary_bytes).hexdigest()},
                  'render_usage':summary['render_usage'],'cohort_records':len(cohorts),'disjoint_band_records':len(band_rows)}))
