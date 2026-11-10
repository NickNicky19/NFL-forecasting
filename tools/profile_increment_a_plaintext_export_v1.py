"""Export only completed public aggregate cells; no private/player-row read."""
from __future__ import annotations
import csv,gzip,hashlib,io,json,resource,signal
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'reports/abc-championship/profile-increment-to-release-01/FULL_FOUR_SCORES_V1.json.gz'
OUT=ROOT/'reports/abc-championship/profile-increment-to-release-01/public-full-four-v1'
LIMIT=61440
FILES=[]
COVERED={k:set() for k in ['DIRECTION','NUMERICAL','PROBABILITY','MATCHED_PAIRS']}

def summary_key(r):return tuple(str(r.get(k)) for k in ['period','cohort','candidate_id','population','source_panel','week_view'])
def pair_key(r):return tuple(str(r.get(k)) for k in ['period','cohort','source_panel','left','right'])

def sha(x):return hashlib.sha256(x).hexdigest()
def cell(v):return json.dumps(v,sort_keys=True,separators=(',',':')) if isinstance(v,(dict,list)) else v
def emit(stem,rows,fields):
    rows=list(rows);chunks=[];part=[]
    def render(rr):
        out=io.StringIO(newline='');writer=csv.DictWriter(out,fieldnames=fields,lineterminator='\n',extrasaction='raise')
        writer.writeheader();writer.writerows([{k:cell(r.get(k)) for k in fields} for r in rr]);return out.getvalue().encode()
    for row in rows:
        if len(render(part+[row]))>LIMIT and part:
            chunks.append(part);part=[]
        part.append(row)
    if part or not chunks:chunks.append(part)
    for index,rr in enumerate(chunks,1):
        raw=render(rr);assert len(raw)<=LIMIT
        name=f'{stem}_{index:03d}.csv';(OUT/name).write_bytes(raw)
        FILES.append(dict(path=name,rows=len(rr),bytes=len(raw),sha256=sha(raw),columns=len(fields),kind=stem))

SIDES=['OVER','UNDER','COMBINED']
def direction(r):
    q=dict(category='rush_yd',role_scope='RB',requested_window='2026_W1_W8',period=r['period'],source_panel=r['source_panel'],
        cohort=r['cohort'],week_view=r['week_view'],procedure=r['candidate_id'],execution_state=r['execution_state'],
        actual_recorded_scored_weeks=r['actual_recorded_line_scored_weeks'],diagnostic_scored_weeks=r['diagnostic_scored_weeks'],
        eligible=r['eligible'],selected=r['COMBINED']['selected'],unavailable=r['unavailable'],abstained=r['abstentions'],
        unknown_participation=r['states'].get('UNKNOWN_PARTICIPATION',0),missing_actual=r['states'].get('MISSING_ACTUAL',0),
        pending=r['states'].get('PENDING',0),DNP=r['states'].get('DNP',0),push=r['states'].get('PUSH',0),
        statistical_void_state=r['states'].get('VOID',0),games=r['games'],player_games=r['player_games'],evidence_tiers=r['evidence_tiers'])
    for side in SIDES:
        for k in ['selected','wins','losses','decided','rate']:q[side.lower()+'_'+k]=r[side][k]
    return q

def numeric(r):
    n=r['numerical'];f=n.get('fallback')
    return dict(category='rush_yd',role_scope='RB',period=r['period'],population=r['population'],source_panel=r.get('source_panel','NUMERICAL_ONLY'),
        cohort=r['cohort'],procedure=r['candidate_id'],execution_state=r['execution_state'],state=n.get('state','POINT_PRODUCT'),
        intended=n.get('intended'),available=n.get('available'),scored=n['scored'],unavailable=n.get('unavailable'),unknown_outcome=n.get('unknown_outcome'),
        MAE=n['MAE'],MSE=n['MSE'],RMSE=n['RMSE'],bias=n['bias'],absolute_error_p90=n.get('absolute_error_p90'),
        maximum_absolute_error=n.get('max_absolute_error'),fallback_states=f,unavailability_reasons=n.get('unavailability_reasons'))

def probability(r):
    p=r['probability']
    return dict(category='rush_yd',role_scope='RB',period=r['period'],source_panel=r['source_panel'],cohort=r['cohort'],week_view=r['week_view'],
        procedure=r['candidate_id'],state=p['state'],qualified_law_outcomes=p['qualified_law_outcomes'],decisive_law_outcomes=p['decisive_law_outcomes'],
        binary_Over_event_Brier=p['binary_Over_event_Brier'],three_class_Brier_sum=p['three_class_Brier_sum'],three_class_log_loss=p['three_class_log_loss'],
        infinite_log_loss_cases=p['infinite_log_loss_cases'],finite_three_class_log_loss_mean=p['finite_three_class_log_loss_mean'],
        conditioning=p['binary_event_contract'],actual_recorded_scored_weeks=r['actual_recorded_line_scored_weeks'])

def paired(r):
    p=r['probability'];du=r['decision_uncertainty'];nu=r['MAE_change_uncertainty']
    return dict(category='rush_yd',period=r['period'],source_panel=r['source_panel'],cohort=r['cohort'],left=r['left'],right=r['right'],
        execution_state=r['execution_state'],common_decided=r['common_decided'],left_wins=r['left_wins'],right_wins=r['right_wins'],
        side_disagreements=r['side_disagreements'],accuracy_change=r['accuracy_change'],decided_mask_sha256=r['decided_mask_sha256'],
        decision_game_clusters=du['game_clusters'],decision_week_clusters=du['week_clusters'],decision_game_interval95=du['game_interval95'],decision_week_interval95=du['week_interval95'],
        common_numerical=r['common_numerical'],MAE_change=r['MAE_change'],numerical_mask_sha256=r['numerical_mask_sha256'],
        MAE_game_interval95=nu['game_interval95'],MAE_week_interval95=nu['week_interval95'],common_probability_events=p['common_probability_events'],
        Brier_change=p['binary_Over_event_Brier_change'],Brier_game_interval95=p['game_interval95'],Brier_week_interval95=p['week_interval95'],
        probability_conditioning=p['event_conditioning'])

def player_summary(r):
    q={k:r[k] for k in ['panel','candidate_id','eligible_players_in_global_declared_universe','players_with_panel_rows','players_with_numerical_scores','support_kind']}
    for bucket in ['0','1','2','3-4','5-7','8+']:q['players_support_'+bucket]=r['support_distribution'].get(bucket,0)
    for side in SIDES:
        e=r['equal_player_sides'][side] if r['equal_player_sides'] is not None else {}
        o=r['opportunity_weighted_sides'][side] if r['opportunity_weighted_sides'] is not None else {}
        q[side.lower()+'_players_with_decisions']=e.get('players_with_decisions');q[side.lower()+'_equal_player_rate']=e.get('mean_player_hit_rate')
        for k in ['selected','wins','losses','decided','rate']:q[side.lower()+'_opportunity_'+k]=o.get(k)
    for metric in ['MAE','MSE','bias']:
        q['equal_player_'+metric]=r['equal_player_numerical'][metric];q['opportunity_weighted_'+metric]=r['opportunity_weighted_numerical'][metric]
    q['numerical_scored']=r['opportunity_weighted_numerical']['scored']
    return q

def player_pair(r):
    q={k:r[k] for k in ['panel','left','right','global_players','common_decided_opportunities','opportunity_weighted_accuracy_change','equal_player_accuracy_change',
        'common_numerical_opportunities','opportunity_weighted_MAE_change','equal_player_MAE_change']}
    for k in ['left_more_correct','right_more_correct','tied','no_common_decisions']:q['direction_players_'+k]=r['direction_player_counts'].get(k,0)
    for k in ['left_lower_MAE','right_lower_MAE','tied','no_common_numeric_scores']:q['numerical_players_'+k]=r['numerical_player_counts'].get(k,0)
    return q

def write_rows(stem,rows,mapper):
    rows=list(rows)
    for r in rows:
        if mapper is direction:COVERED['DIRECTION'].add(summary_key(r))
        elif mapper is numeric:COVERED['NUMERICAL'].add(summary_key(r))
        elif mapper is probability:COVERED['PROBABILITY'].add(summary_key(r))
        elif mapper is paired:COVERED['MATCHED_PAIRS'].add(pair_key(r))
    mapped=[mapper(r) for r in rows];assert mapped
    emit(stem,mapped,list(mapped[0]))

def main():
    resource.setrlimit(resource.RLIMIT_CPU,(30,30));resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,)*2);signal.alarm(60)
    body=SOURCE.read_bytes();assert sha(body)=='9007d0dc9b4f8252ecede568d279deb7a38bbe16fa21f6262e25627075efa522'
    raw=gzip.decompress(body);assert sha(raw)=='b69e3684736b86562163ae02e83b4b060854f69b3a4b7055103ed650eca4e4fb'
    result=json.loads(raw);assert result['state']=='FROZEN_POINT_AND_EXACT_LINE_LAW_SCORING_COMPLETE'
    assert result['prior_partial_parity']['state']=='PASS_UNCHANGED_COMPARABLE_OLD_CELLS'
    OUT.mkdir(parents=True,exist_ok=False)
    ss=result['summaries'];bb=[r for r in ss if r['population']=='RETAINED_THRESHOLD_BOARD']
    annual=[r for r in bb if r['period']=='W1_W7' and r['source_panel']=='ANNUAL_NAMED_NJ' and r['cohort']=='ALL_ELIGIBLE' and r['week_view'] in ['ALL',1,2,3,4,5]]
    mixed=[r for r in bb if r['period']=='W1_W7' and r['source_panel']=='ALL' and r['cohort']=='ALL_ELIGIBLE']
    week8=[r for r in bb if r['period']=='W8_REFERENCE_ONLY' and r['source_panel']=='ALL' and r['cohort']=='ALL_ELIGIBLE']
    assert (len(annual),len(mixed),len(week8))==(156,208,52)
    for name,rows in [('DIRECTION_ANNUAL_ACTUAL_W1_W5',annual),('DIRECTION_MIXED_DIAGNOSTIC_W1_W7',mixed),('DIRECTION_W8_REFERENCE_ONLY',week8)]:write_rows(name,rows,direction)
    for cohort in result['cohorts'] if 'cohorts' in result else ['ALL_ELIGIBLE','STABLE_NEW_CORE','DETAILED_PRIORITY','WORKLOAD_TOP20','PBP_OWN_SUPPORTED']:
        rows=[r for r in bb if r['source_panel']=='ALL' and r['week_view']=='ALL' and r['cohort']==cohort]
        write_rows('COHORT_CUMULATIVE_'+cohort,rows,direction)
    numeric_rows=[r for r in ss if r['cohort']=='ALL_ELIGIBLE' and (r['population']=='BROAD_QUERIES' or r['week_view']=='ALL')]
    write_rows('NUMERICAL_BROAD_AND_OFFERED_ALL_SCOPES',numeric_rows,numeric)
    for name,rows in [('PROBABILITY_ANNUAL_ACTUAL_W1_W5',annual),('PROBABILITY_MIXED_DIAGNOSTIC_W1_W7',mixed),('PROBABILITY_W8_REFERENCE_ONLY',week8)]:write_rows(name,rows,probability)
    for period,panel,scope in [('W1_W7','ANNUAL_NAMED_NJ','ANNUAL_W1_W5'),('W1_W7','ALL','MIXED_W1_W7'),
        ('W1_W7','SITE_RECORDED_DK_JURISDICTION_UNKNOWN','SITE_W6_W7_DIAGNOSTIC'),('W8_REFERENCE_ONLY','ALL','W8_REFERENCE_ONLY'),
        ('W1_W8_PARTIAL_ACTUAL','ALL','W1_W8_MIXED_PLUS_REFERENCE_DIAGNOSTIC')]:
        for cohort in ['ALL_ELIGIBLE','STABLE_NEW_CORE','DETAILED_PRIORITY','WORKLOAD_TOP20','PBP_OWN_SUPPORTED']:
            rows=[r for r in result['paired'] if r['period']==period and r['source_panel']==panel and r['cohort']==cohort]
            if rows:
                assert len(rows)==99
                write_rows('PAIRED_'+scope+'_'+cohort,rows,paired)
    pp=result['per_player_diagnostics'];assert pp['public_player_ids_or_rows'] is False and pp['state']=='RETAINED_PROTECTED_CARD_AND_PUBLIC_AGGREGATES'
    assert len(pp['summary'])==130 and len(pp['paired_player_counts'])==495
    for panel in pp['panel_definitions']:
        write_rows('EQUAL_PLAYER_PUBLIC_'+panel,[r for r in pp['summary'] if r['panel']==panel],player_summary)
        write_rows('PLAYER_PAIRED_COUNTS_PUBLIC_'+panel,[r for r in pp['paired_player_counts'] if r['panel']==panel],player_pair)
    # This exporter never opens the protected per-player card, native forecasts,
    # fitted models, offers or labels. Every emitted cell is a public aggregate.
    for item in FILES:
        assert 'player_id' not in (OUT/item['path']).read_text().splitlines()[0]
    guide='''# Full four-arm rushing profile comparison: public aggregate tables

These plaintext CSVs export the completed immutable owner-local score artifact. They contain aggregate procedure cells, never individual player identities or rows. The protected per-player card is not opened by this exporter.

- ANNUAL_ACTUAL_W1_W5: retained actual offers, 2026 Weeks 1–5; quote timing remains unverified. Five-week duration alone is not admission or superiority.
- MIXED_DIAGNOSTIC_W1_W7: combines the preceding annual offers with the separately named site-recorded W6–7 source whose offer status is unqualified here. This is a diagnostic, not seven authenticated offered-line weeks.
- W8_REFERENCE_ONLY: saved internal/reference thresholds, not authentic offered props. This cannot add an actual-offer test week.
- W1_W8_MIXED_PLUS_REFERENCE_DIAGNOSTIC keeps the requested full-window diagnostic visible without converting its reference thresholds into actual props.
- Numerical broad queries and identical threshold-player rows have separate populations. Conditional historical stat-row query membership is not a qualified pregame roster.
- DETAILED_PRIORITY and WORKLOAD_TOP20 are empty under the frozen universe qualification: N/A, not 100%. Their missing qualified pregame universe/reference clocks remain a source dependency. The complete basic board remains scored.
- Equal-player rates average players with decisions; opportunity-weighted rates sum wins/decided. All 203 declared players, including n0/unknown/unavailable, remain represented in support counts and the protected card. Paired improve/regress counts use common opportunities; they are descriptive, not a player-specific model router.
- Empty CSV cells mean N/A/null, not numeric zero. Explicit numeric zero is preserved. Push, unknown participation, DNP, pending, missing and technical unavailability retain separate counts. Bookmaker settlement, prices, returns and profitability are unverified.
- Each published panel retains all 26 procedure views and all 99 preregistered pairs where applicable, including losses. Other field/scope views remain in the unchanged complete source. Exact exported versus unexported counts and scope indexes are in the manifest; no omission was chosen using outcomes. Many views are outputs/controls of the same family, not independent models or extra NFL games. Saved CIs are copied without new resampling.
- No new model, fit, inference, label, grader, selector, calibration, probability guarantee, capture or production release was created by this export. The separate 90% aspiration is not established.

Rates are fractions. Full source and decoded hashes, row counts and exact file hashes are in PUBLIC_TABLES_MANIFEST_V1.json. Files are split only to remain at or below 60 KiB; splitting is never based on scores. Cumulative and weekly views overlap and must not be pooled twice.
'''
    (OUT/'README.md').write_text(guide)
    coverage={};scope_indexes=[]
    for kind,rows,fields,key_fn in [('DIRECTION',bb,['period','cohort','population','source_panel','week_view'],summary_key),
        ('PROBABILITY',bb,['period','cohort','population','source_panel','week_view'],summary_key),
        ('NUMERICAL',ss,['period','cohort','population','source_panel','week_view'],summary_key),
        ('MATCHED_PAIRS',result['paired'],['period','cohort','source_panel'],pair_key)]:
        missing=[r for r in rows if key_fn(r) not in COVERED[kind]]
        grouped={}
        for r in missing:
            key=tuple(str(r.get(k)) for k in fields);grouped[key]=grouped.get(key,0)+1
        scope=io.StringIO(newline='');writer=csv.DictWriter(scope,fieldnames=fields+['aggregate_cells'],lineterminator='\n');writer.writeheader()
        writer.writerows([dict(zip(fields+['aggregate_cells'],list(k)+[n])) for k,n in sorted(grouped.items())])
        scope_body=scope.getvalue().encode();assert len(scope_body)<=LIMIT
        name='UNEXPORTED_'+kind+'_SCOPE_INDEX_V1.csv';(OUT/name).write_bytes(scope_body)
        scope_indexes.append(dict(path=name,scope_groups=len(grouped),bytes=len(scope_body),sha256=sha(scope_body)))
        coverage[kind]=dict(source_cells=len(rows),plaintext_cells=len(COVERED[kind]),not_in_plaintext_cells=len(missing),
            reason='Deterministic named primary/cohort/cumulative panels only; complete unchanged source retains the additional views, with all procedures/pairs and losses. Not an unavailable or failed test.')
    index=io.StringIO(newline='');writer=csv.DictWriter(index,fieldnames=['path','rows','bytes','sha256'],lineterminator='\n')
    writer.writeheader();writer.writerows([{k:r[k] for k in ['path','rows','bytes','sha256']} for r in FILES])
    index_body=index.getvalue().encode();(OUT/'PUBLIC_TABLES_INDEX_V1.csv').write_bytes(index_body)
    manifest=dict(schema='A_FULL_FOUR_PUBLIC_AGGREGATE_TABLES_V1',source=dict(path=str(SOURCE.relative_to(ROOT)),bytes=len(body),sha256=sha(body),decoded_bytes=len(raw),decoded_sha256=sha(raw)),
        exporter=dict(path=str(Path(__file__).relative_to(ROOT)),sha256=sha(Path(__file__).read_bytes())),
        category='rush_yd',role_scope='RB',season=2026,files=FILES,csv_files=len(FILES),csv_rows=sum(x['rows'] for x in FILES),
        largest_csv_bytes=max(x['bytes'] for x in FILES),maximum_csv_bytes=LIMIT,public_player_ids_or_rows=False,
        no_new_scoring=True,all_losses_retained=True,source_gzip_unchanged=sha(SOURCE.read_bytes())==sha(body),
        plaintext_index=dict(path='PUBLIC_TABLES_INDEX_V1.csv',bytes=len(index_body),sha256=sha(index_body)),
        field_view_coverage=coverage,unexported_scope_indexes=scope_indexes,
        public_player_aggregate_coverage=dict(summary_cells=130,summary_exported=130,paired_groups=495,paired_exported=495),
        no_outcome_based_table_filter=True)
    (OUT/'PUBLIC_TABLES_MANIFEST_V1.json').write_text(json.dumps(manifest,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n')
    signal.alarm(0)
    print(json.dumps({k:manifest[k] for k in ['csv_files','csv_rows','largest_csv_bytes','public_player_ids_or_rows','source_gzip_unchanged']}))

if __name__=='__main__':main()
