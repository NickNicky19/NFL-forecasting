"""A-only coverage contribution from existing aggregates; no scorer/native/model access."""
from pathlib import Path
import collections,csv,datetime,gzip,hashlib,io,json
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/abc-championship/category-decision-release-01'
CATS=['pass_yd','pass_td','pass_cmp','pass_att','pass_int','rush_yd','rush_att','rec','rec_yd','rush_rec_yd','anytime_td','nick-chart-ppr-v1']
UNKNOWN='UNKNOWN'
def sha(b):return hashlib.sha256(b).hexdigest()
def encoded(j):return(json.dumps(j,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def load(path):
    p=ROOT/path;b=p.read_bytes();return json.loads(gzip.decompress(b)if p.suffix=='.gz'else b),dict(path=path,bytes=len(b),sha256=sha(b))
def save(name,b):
    p=OUT/name
    if p.exists()and p.read_bytes()!=b:raise ValueError('immutable existing output differs')
    p.write_bytes(b);return dict(path=str(p.relative_to(ROOT)),bytes=len(b),sha256=sha(b))
def fallback(s):
    if 'fallback_outputs'in s:return s['fallback_outputs']
    if 'fallback_states'in s:
        if s['fallback_states']and set(s['fallback_states'])<={'','None','nan'}:return UNKNOWN
        return sum(n for k,n in s['fallback_states'].items()if k not in ['', 'None','none','nan'])
    return UNKNOWN
def counts(s):
    states=s.get('states',{})
    return dict(eligible=s['eligible'],available=s['eligible']-s['unavailable'],selected=s['COMBINED']['selected'],decided=s['COMBINED']['decided'],unknown=sum(n for k,n in states.items()if'UNKNOWN'in k or'MISSING_ACTUAL'in k),unavailable=s['unavailable'],fallback=fallback(s),fallback_states=s.get('fallback_states',UNKNOWN),games=s['games'],unique_player_games=s['player_games'],abstentions=s.get('abstentions',UNKNOWN),states=states)
def main():
    pair,pr=load(str((OUT/'A_POINT_PAIR_RESULTS_V1.json.gz').relative_to(ROOT)))
    head,hr=load(str((OUT/'A_POINT_PAIR_HEADLINES_COMPACT_V1.json').relative_to(ROOT)))
    oldmatrix,omr=load(str((OUT/'A_EVIDENCE_WEEKLY_LEADER_SOURCE_MATRIX_V1.json').relative_to(ROOT)))
    att,ar=load(str((OUT/'B_ATT_ALIAS_RESULTS_V2.json.gz').relative_to(ROOT)))
    bj,br=load('reports/abc-championship/profile-timing-closure-and-confirm-01/B_TIMING_COMPLETION_RESULTS_V1.json.gz')
    cj,cr=load('reports/abc-championship/profile-timing-closure-and-confirm-01/C04_RECEPTION_RESULTS_V1.json.gz')
    w8,w8r=load('reports/abc-championship/audit-remediation-20261105/A_WEEK8_ALL_PANELS_QUALIFICATION_V1.json')
    orig8,o8r=load('reports/abc-championship/audit-remediation-20261105/A_WEEK8_PRESENCE_QUALIFICATION_V1.json')
    book,bkr=load(str((OUT/'A_ANNUAL_BOOK_POLICY_METADATA_V1.json').relative_to(ROOT)))
    sources={'A79':pr,'AHEAD':hr,'OLD_MATRIX':omr,'BATT':ar,'B_CMP':br,'C_REC':cr,'W8_FULL':w8r,'W8_ORIGINAL':o8r,'BOOK_POLICY':bkr}
    rows=[];procedures={};leaders={}
    def proc(cid,session,source,output=UNKNOWN,version=UNKNOWN,role=UNKNOWN,details=None):
        found=next((k for k,v in procedures.items()if v['candidate_id']==cid and v['source_ref']==source),None)
        if found:return found
        ref=f'P{len(procedures)+1:03}'
        procedures[ref]=dict(candidate_id=cid,origin_session=session,source_ref=source,output=output,procedure_version=version,role_scope=role,selection_policy='STRICT_ORIGINAL_UNROUNDED_POINT_VERSUS_EXACT_LINE'if session in ['A','B','C']else'ORIGINAL_CAPTURED_DECISIONS',history_and_model_binding=details or UNKNOWN)
        return ref
    def row(cat,w,panel,pref,s,source,status,tier,missing):
        rows.append(dict(category=cat,season=2026,week=w,panel=panel,procedure_ref=pref,source_ref=source,status=status,evidence_tier=tier,counts=counts(s),OVER=s['OVER'],UNDER=s['UNDER'],COMBINED=s['COMBINED'],numerical=s.get('numerical',s.get('numerical_same_offer_mask',UNKNOWN)),eligible_mask_sha256=s.get('eligible_mask_sha256',UNKNOWN),decided_mask_sha256=s.get('decided_mask_sha256',UNKNOWN),quote_observation_UTC=UNKNOWN,source_vintage_UTC=UNKNOWN,forecast_issue_UTC=UNKNOWN,per_week_training_cutoff_UTC=UNKNOWN,per_week_feature_cutoff_UTC=UNKNOWN,book_venue='BOOK_POLICY'if panel=='A_ANNUAL_NJ'else UNKNOWN,missing_requirement=missing))
    hmap={p['category']:p['highest_observed_nonconstant_complete_procedures']for p in head['panels']}
    for cat in CATS:
        if cat not in hmap:
            for w in range(1,9):rows.append(dict(category=cat,season=2026,week=w,panel='A_ANNUAL_NJ',procedure_ref=None,source_ref='A79',status='NO_COMPATIBLE_OFFER_PRODUCT_IN_THIS_SCOPE',evidence_tier='MISSING_OR_INCOMPATIBLE',counts={k:UNKNOWN for k in ['eligible','available','selected','decided','unknown','unavailable','fallback','games','unique_player_games','abstentions']},OVER=None,UNDER=None,COMBINED=None,quote_observation_UTC=UNKNOWN,source_vintage_UTC=UNKNOWN,forecast_issue_UTC=UNKNOWN,per_week_training_cutoff_UTC=UNKNOWN,per_week_feature_cutoff_UTC=UNKNOWN,book_venue=UNKNOWN,missing_requirement='Qualified inherited rushing-or-receiving TD offered-event/available-side contract'if cat=='anytime_td'else'Exact nick-chart-ppr-v1 offer, scoring contract and necessary qualified outcome primitives'))
            leaders[cat]=dict(candidate=None,status='BLOCKED_NO_MATCHING_PRODUCT');continue
        fixed=hmap[cat][0];cid=fixed['candidate_id'];spec=next(p for p in pair['original_point_products']if p['candidate_id']==cid)
        pref=proc(cid,'A','A79',spec['output'],spec['procedure_version'],UNKNOWN,pair['source_catalog_provenance'].get(cid,UNKNOWN))
        leaders[cat]=dict(procedure_ref=pref,fixed_cumulative_scope='A own full annual offered-player panel; exposed observed score, not an advance-selected router or C master recommendation',tied_candidates=[p['candidate_id']for p in hmap[cat]],record=fixed['COMBINED'],actual_offer_weeks=[1,2,3,4,5],W1_W8_status='PARTIAL',missing_annual_weeks=[6,7,8])
        source='A79';view='FULL_ELIGIBLE_ANNUAL_BOARD';summary=pair['summaries']
        if cat=='pass_att':
            cid='B-player-context-matchup-01-v1:COMMON_EXPOSURE::lower_median';pref=proc(cid,'B','BATT','lower_median','B-player-context-matchup-01-v1:COMMON_EXPOSURE',['QB'],dict(B_source_commit=att['B_source_commit'],B_public_refs=att['B_public_refs'],old_result=att['old_result'],unchanged_model=True,alias_only='2026 LA->LAR team/opponent tokens; LAC unchanged'))
            source='BATT';view='FULL_A_BOARD_ALIAS_QUALIFIED87';summary=att['summaries'];ss=next(s for s in summary if s['candidate_id']==cid and s['week_view']=='ALL'and s['source_panel']=='ALL'and s['view']==view)
            leaders[cat]=dict(procedure_ref=pref,fixed_cumulative_scope='Highest observed nonconstant among compatible A79 and unchanged B ATT outputs on annual87; not superiority or primary admission.',tied_candidates=[cid],record=ss['COMBINED'],strongest_control=dict(candidate_id='ALWAYS_OVER',wins=46,decided=87),actual_offer_weeks=[1,2,3,4,5],W1_W8_status='PARTIAL',missing_annual_weeks=[6,7,8])
        for w in range(1,9):
            ss=next(s for s in summary if s['candidate_id']==cid and s['week_view']==w and s['source_panel']==('ALL'if source=='BATT'else'ANNUAL_NAMED_NJ')and s['view']==view)
            row(cat,w,'A_ANNUAL_NJ',pref,ss,source,'SCORED_ACTUAL_LINES_TIMING_UNVERIFIED'if ss['eligible']else'NO_ANNUAL_ROW_IN_THIS_EXACT_PANEL',ss.get('evidence_tier',att['evidence_tier']),'Original quote/decision clocks, venue settlement and authenticated historical query/feature vintages remain unverified.'if ss['eligible']else'Annual offer/forecast/outcome contract not supplied for this week; separate site/W8 panels do not fill this cell.')
    # Copy older exact A W6-W7 diagnostic counts, preserving the fixed A annual
    # family even when a peer is now the higher-scoring annual ATT candidate.
    for cat in CATS[:10]:
        fixed=hmap[cat][0];parts=fixed['candidate_id'].split('::');method,output=parts[-2:];version=parts[-3]
        mr=next(x for x in oldmatrix['rows']if x['category']==cat and x['method']==method and x['output']==output)
        qq,sref=load(mr['source_binding']);sr='OLD_'+cat;sources[sr]=sref
        rr=next(x for x in qq['records']if x['method_alias']==method and x['key']['output']==output and x['key']['procedure_version']==version and x['key']['selection_policy']=='FULL_PRIMARY_ROSTER_INTERSECTION_RECORDED_BOARD')
        pref=proc(fixed['candidate_id'],'A',sr,output,version,rr['key']['role_scope'],rr['key'])
        for w in [6,7]:
            ww=next(x for x in rr['weekly_support']if x['week']==w);meta=next(x for x in oldmatrix['rows']if x['category']==cat and x['method']==method and x['output']==output and x['week']==w);cc=meta['counts']
            sides={side.upper():dict(wins=ww[side]['wins'],losses=ww[side]['losses'],decided=ww[side]['decided'],rate=ww[side]['hit_rate'],selected=UNKNOWN)for side in ['over','under']}
            sides['COMBINED']=dict(wins=ww['correct'],losses=ww['scored']-ww['correct'],decided=ww['scored'],rate=ww['correct']/ww['scored']if ww['scored']else None,selected=UNKNOWN)
            c=dict(eligible=ww['eligible_or_opportunities'],available=UNKNOWN,selected=UNKNOWN,decided=ww['scored'],unknown=ww['unknown_participation'],unavailable=UNKNOWN,fallback=ww['fallback_rows'],games=ww['games'],unique_player_games=UNKNOWN,abstentions=ww['no_lean'],states=UNKNOWN)
            rows.append(dict(category=cat,season=2026,week=w,panel='A_SITE_DIAGNOSTIC',procedure_ref=pref,source_ref=sr,status='SCORED_UNQUALIFIED_SITE_THRESHOLD_DIAGNOSTIC',evidence_tier=meta['tier'],counts=c,**sides,quote_observation_UTC=UNKNOWN,source_vintage_UTC=UNKNOWN,forecast_issue_UTC=UNKNOWN,per_week_training_cutoff_UTC=UNKNOWN,per_week_feature_cutoff_UTC=UNKNOWN,book_venue='DK/Sleeper labels; jurisdiction and exact threshold semantics unqualified',missing_requirement=meta['missing_requirement']))
    # Existing peer receipts remain separate role/source masks. No repeated join.
    peer_sets=[('pass_cmp','B_CMP',bj,'FULL_A_BOARD',[f'B-QB-ALIGNED-FRESHNESS-v1:F{x}::{v}'for x in range(4)for v in ['mean','lower_median']]),('rec','C_REC',cj,'FULL_A733',[f'C::PLAYER-CONTEXT-MATCHUP-01::v1.1::{p}::{v}'for p in ['P1','P2']for v in ['mean','median']])]
    for cat,sr,j,view,cids in peer_sets:
        for cid in cids:
            pref=proc(cid,'B'if cat=='pass_cmp'else'C',sr,cid.split('::')[-1],cid.rsplit('::',1)[0],['QB']if cat=='pass_cmp'else['WR','TE'],'Exact bound saved-output join; full source/model lineage is retained in source_ref aggregate and original public handoff manifest. No private-row/fit parity inferred.')
            for w in range(1,9):
                panel='ANNUAL_NAMED_NJ'if w<=5 else'SITE_RECORDED_DK_JURISDICTION_UNKNOWN'
                ss=next((s for s in j['summaries']if s['candidate_id']==cid and s['view']==view and s['source_panel']==panel and s['week_view']==w),None)
                if ss is None:
                    if w!=8:raise ValueError('expected nonempty peer weekly aggregate absent')
                    ss=dict(eligible=0,unavailable=0,abstentions=0,games=0,player_games=0,states={},fallback_outputs=0,**{side:dict(selected=0,wins=None,losses=None,decided=0,rate=None)for side in ['OVER','UNDER','COMBINED']})
                row(cat,w,'PEER_ANNUAL_SUBPANEL'if w<=5 else'PEER_SITE_DIAGNOSTIC',pref,ss,sr,'SCORED_PEER_EXACT_PRODUCT'if ss['eligible']else'NO_ROW_IN_THIS_EXACT_PEER_PANEL','ACTUAL_LINES_TIMING_UNVERIFIED_WRTE'if w<=5 and cat=='rec'else'ACTUAL_LINES_TIMING_UNVERIFIED_QB'if w<=5 else'UNQUALIFIED_SITE_THRESHOLD_OR_EMPTY','Keep own role/source masks; quote/decision/source vintages unverified; W6-7 cannot add actual-offer duration; W8 absent. No native B W5 concatenation.')
    # Preserve audited W8 populations; they never fill annual model cells.
    w8sets=[(w8r,'W8_FULL',[x for x in w8['summaries']if x['kind']=='board_comparison'and x['group']in ['FIXED_R0_CAPTURE_20261028T184637Z','CAPTURED_SELECTED_369fec9caec0']]),(o8r,'W8_ORIGINAL',[x for x in orig8['tables']if x['group']=='ORIGINAL_ARCHIVE_PRE_FIRST_KICKOFF'and x['cohort']=='ALL_RECORDED_LEANS'and x['category']in CATS[:10]])]
    for bind,sr,ss in w8sets:
        for s in ss:
            pref=proc('A::'+s['group'],'A'if sr=='W8_FULL'else'INCUMBENT',sr,UNKNOWN,UNKNOWN,UNKNOWN,'Frozen Week8 source population; audit presence-qualified original measurement appended. Not annual candidate identity or primary qualification.')
            comb=s['sides']['combined'];states=comb['states'];c=dict(eligible=s.get('issued_or_board_rows',UNKNOWN),available=UNKNOWN,selected=comb['selected'],decided=comb['decided'],unknown=sum(n for k,n in states.items()if'UNKNOWN'in k or'MISSING_ACTUAL'in k),unavailable=UNKNOWN,fallback=UNKNOWN,games=s['games'],unique_player_games=s['player_games'],abstentions=UNKNOWN,states=states)
            sides={side.upper():dict(wins=s['sides'][side]['wins'],losses=s['sides'][side]['losses'],decided=s['sides'][side]['decided'],rate=s['sides'][side]['hit_rate'],selected=s['sides'][side]['selected'])for side in ['over','under','combined']}
            rows.append(dict(category=s['category'],season=2026,week=8,panel='W8_'+s['group'],procedure_ref=pref,source_ref=sr,status='AUDITED_FROZEN_W8_POPULATION_SEPARATE_PRODUCT',evidence_tier='PRESENCE_QUALIFIED_W8_SOURCE_SNAPSHOT_ORIGINAL_CLOCK_LIMITS',counts=c,**sides,quote_observation_UTC=UNKNOWN,source_vintage_UTC=UNKNOWN,forecast_issue_UTC=UNKNOWN,per_week_training_cutoff_UTC=UNKNOWN,per_week_feature_cutoff_UTC=UNKNOWN,book_venue=UNKNOWN,missing_requirement='Original horizon/output/model/offer clocks and settlement remain source-specific. Do not substitute this population for annual fitted-product evidence. Explicit absence stays unresolved.'))
    if len([r for r in rows if r['panel']=='A_ANNUAL_NJ'])!=96:raise ValueError('twelve-category eight-week contribution incomplete')
    matrix=dict(version='NFL-CATEGORY-DECISION-AND-RELEASE-01-A-WEEKLY-COVERAGE-MATRIX-v1',UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),session='A',scope='A contribution, not C master ranking. Projection of existing aggregates only; fixed annual observed leaders across all weeks, with ties and separate peer/W6-W7/W8 panels. No new NFL scoring, joins or evidence-tier upgrade.',sources=sources,source_objects=pair['source_objects'],source_member_sha256=pair['source_member_sha256'],annual_source_policy=dict(book_policy_ref='BOOK_POLICY',quote_time='UNKNOWN_NOT_RETAINED',cutoff_qualified=False,book_priority=book['book_priority'],source_history='CURRENT_VINTAGE_RECONSTRUCTION; exact per-procedure history bindings retained',prohibited_pooling='Do not add separate masks/panels, repeat offers or count alternate procedure views as new games.'),procedures=procedures,fixed_annual_observed_leaders=leaders,rows=rows,coverage_claim=dict(primary_request='2026 W1-W8',actual_annual_scored_weeks=[1,2,3,4,5],unqualified_site_diagnostic_weeks=[6,7],independent_frozen_source_week=8,primary_status='PARTIAL; no complete comparable W1-W8 champion certified',extra_procedure_coverage_not_new_games=True),peer_join_scope=dict(B_completion='Existing exact F0-F3 saved-output comparison; native B later board remains separate until normalized W5 overlap is reconciled.',C_receptions='Existing C P1/P2 mean/median WRTE replay uses full733 source/annual469 with unavailability retained, not the broad A642 or fixed667 denominator.',limits='Public aggregate parity is not private-row, source-vintage or fitted-model parity.'),field_contract='UNKNOWN means not supplied by the bound aggregate; numeric zero means a retained source count. No missing available/selected/player-game count is invented. Rates are copied or simple aggregate W/N notation; no rows were regraded.',activity=dict(new_fits=0,new_inference=0,new_scoring=0,new_joins=0,native_reads=0,production_changes=0))
    mf=save('A_WEEKLY_COVERAGE_MATRIX_V1.json',encoded(matrix))
    columns=['category','week','panel','procedure_ref','source_ref','eligible','available','selected','decided','unknown','unavailable','fallback','games','unique_player_games','over_wins','over_losses','over_decided','under_wins','under_losses','under_decided','combined_wins','combined_losses','combined_rate','status']
    buf=io.StringIO(newline='');writer=csv.DictWriter(buf,fieldnames=columns,lineterminator='\n');writer.writeheader()
    for r in rows:
        x={k:r.get(k)for k in ['category','week','panel','procedure_ref','source_ref','status']};x.update({k:r['counts'].get(k,UNKNOWN)for k in columns if k in r['counts']})
        for side in ['over','under','combined']:
            for k in ['wins','losses','decided']if side!='combined'else['wins','losses','rate']:
                if side+'_'+k in columns:x[side+'_'+k]=(r.get(side.upper())or{}).get(k)
        writer.writerow(x)
    cf=save('A_WEEKLY_COVERAGE_MATRIX_V1.csv',buf.getvalue().encode())
    print(json.dumps(dict(matrix=mf,CSV=cf,rows=len(rows),annual_cells=96,procedure_bindings=len(procedures),source_bindings=len(sources),new_scoring=0)))

if __name__=='__main__':main()
