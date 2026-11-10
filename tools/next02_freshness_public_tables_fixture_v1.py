"""Fictional export-only checks; never read NFL/native/model evidence."""
from __future__ import annotations
import copy,csv,gzip,hashlib,importlib.util,io,json,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    source=ROOT/'tools/next02_freshness_public_tables_v1.py'
    spec=importlib.util.spec_from_file_location('fictional_public_export',source);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    first=dict(period='W1_W7',cohort='ALL_ELIGIBLE',candidate_id='F0_ORIGINAL_BASE::MEAN_P1',execution_state='FROZEN_OR_CONTROL',population='RETAINED_THRESHOLD_BOARD',source_panel='ANNUAL_NAMED_NJ',week_view=1,eligible=3,unavailable=1,abstentions=0,states={'WIN':0,'LOSS':1,'UNKNOWN_PARTICIPATION':1,'UNAVAILABLE_FORECAST':1},games=3,player_games=3,weeks=[1],uncertainty={'kind':'N/A_NO_DECIDED_RESULTS','low':None,'high':None,'dependence_aware':False},coverage=2/3,actual_recorded_line_scored_weeks=[1],five_actual_week_duration_floor=False,diagnostic_scored_weeks=[1],evidence_tiers={'ACTUAL_RECORDED_QUOTE_TIMING_UNVERIFIED':3},admission='DURATION_ONLY_NOT_PRIMARY_ADMISSION',OVER={'selected':1,'wins':0,'losses':1,'decided':1,'rate':0.},UNDER={'selected':1,'wins':None,'losses':None,'decided':0,'rate':None},COMBINED={'selected':2,'wins':0,'losses':1,'decided':1,'rate':0.},numerical={'intended':3,'available':2,'scored':1,'unavailable':1,'unknown_outcome':1,'MAE':2.,'MSE':4.,'RMSE':2.,'bias':-2.,'absolute_error_p90':2.,'max_absolute_error':2.,'fallback':{'LEARNED_EXPLICIT_NO_FALLBACK':1,'FALLBACK:prior':1,'UNAVAILABLE_FORECAST':1},'unavailability_reasons':{'MISSING_FROZEN_FORECAST':1}},probability={'qualified_law_outcomes':1,'decisive_law_outcomes':1,'binary_Over_event_Brier':.81,'binary_event_contract':'I(actual>original_line), conditional_on_played','three_class_Brier_sum':1.62,'three_class_log_loss':2.3,'infinite_log_loss_cases':0,'finite_three_class_log_loss_mean':2.3,'selected_probability_not_validated_confidence':True,'state':'SCORED_VALID_CACHED_LAWS'},player_id='FICTIONAL_PRIVATE_ID_NOT_FOR_EXPORT')
    summaries=[]
    for i in range(90):
        row=copy.deepcopy(first);row['week_view']=1+i%8;row['cohort']=['ALL_ELIGIBLE','WORKLOAD_TOP20','PBP_OWN_SUPPORTED'][i%3];row['period']=['W1_W7','W8_REFERENCE_ONLY','W1_W8_PARTIAL_ACTUAL'][i%3];summaries.append(row)
    pairs=[]
    for left,right in sorted(m.PRIMARY):
        pairs.append(dict(period='W1_W7',cohort='ALL_ELIGIBLE',source_panel='ANNUAL_NAMED_NJ',left=left,right=right,execution_state='SCORING_EXECUTED',common_decided=1,left_wins=0,right_wins=1,accuracy_change=-1.,side_disagreements=1,decision_uncertainty={'game_clusters':1,'week_clusters':1,'game_interval95':None,'week_interval95':None},common_numerical=2,MAE_change=-.2,MAE_change_uncertainty={'game_clusters':2,'week_clusters':2,'game_interval95':[-.3,.1],'week_interval95':[-.4,.2]},decided_mask_sha256='a'*64,numerical_mask_sha256='b'*64,probability={'common_probability_events':2,'binary_Over_event_Brier_change':-.03,'game_interval95':[-.1,.04],'week_interval95':[-.2,.1],'event_conditioning':'conditional_on_played'}))
    transitions=[dict(panel='ANNUAL_W1_W5',left=pairs[0]['left'],right=pairs[0]['right'],group=group,cases=1,unique_games=1,left_status_counts={'LOSS':1},right_status_counts={'WIN':1},common_decided=1,left_wins=0,right_wins=1,accuracy_change=-1.,common_numerical=1,MAE_change=-.2,common_probability_events=1,Brier_change=-.03,full_mask_sha256='c'*64)for group in ['FULL_SYSTEM','LEARNED_TO_LEARNED','FALLBACK_TO_LEARNED']]
    result=dict(state=m.SOURCE_STATE,score_scope_version='ALIGNED_TIMING_FOUR_ALIASES_V1',completed_arms=m.ARMS,pending_arms=[],protocol_sha256='d'*64,execution_receipt_sha256='e'*64,summaries=summaries,paired=pairs,fallback_attribution={'records':transitions},source_refs={'fictional_source':'PRIVATE_SOURCE_NOT_FOR_EXPORT'},forecasts=[{'player_id':'FICTIONAL_PRIVATE_ID_NOT_FOR_EXPORT'}])
    raw=gzip.compress(m.encoded(result),mtime=0);before=bytes(raw)
    with tempfile.TemporaryDirectory()as temporary:
        base=Path(temporary);destination=base/'public';manifest=m.export(raw,m.sha(raw),destination)
        assert raw==before and manifest['exported_summary_cells']==90 and manifest['exported_paired_cells']==12 and manifest['exported_fallback_transition_cells']==3
        assert len([x for x in manifest['files']if x['path'].startswith('ALL_SUMMARIES')])>=2
        tables=[]
        for ref in manifest['files']:
            body=(destination/ref['path']).read_bytes();assert len(body)==ref['bytes']<=m.LIMIT and m.sha(body)==ref['sha256'];tables.extend(csv.DictReader(io.StringIO(body.decode())))
        assert len(tables)==105
        for file in destination.iterdir():
            text=file.read_text();assert 'FICTIONAL_PRIVATE_ID_NOT_FOR_EXPORT'not in text and'PRIVATE_SOURCE_NOT_FOR_EXPORT'not in text
        firstout=next(r for r in tables if r.get('candidate_id')==first['candidate_id'])
        assert firstout['over_wins']=='0'and firstout['under_wins']==''and firstout['numerical_bias']=='-2.0'
        assert json.loads(firstout['states'])==first['states'] and json.loads(firstout['numerical_fallback'])==first['numerical']['fallback']
        # Location/hash failures must not be silently redacted or reinterpreted.
        try:m.export(raw,'0'*64,base/'wrong-hash')
        except ValueError:pass
        else:raise AssertionError('wrong source hash accepted')
        bad=copy.deepcopy(result);bad['summaries'][0]['candidate_id']=chr(47)+'fictional-locator'
        badraw=gzip.compress(m.encoded(bad),mtime=0)
        try:m.export(badraw,m.sha(badraw),base/'private-locator')
        except ValueError:pass
        else:raise AssertionError('private locator accepted')
        try:m.export(raw,m.sha(raw),destination)
        except ValueError:pass
        else:raise AssertionError('existing export overwritten')
        fixture=dict(state='PASS_FICTIONAL_PLAINTEXT_AGGREGATE_EXPORT',source_summary_cells=90,source_paired_cells=12,source_fallback_cells=3,exported_cells=105,data_shards=len(manifest['files']),all_shards_within_60KiB=True,all_file_hashes_verified=True,loss_zero_unknown_and_fallback_values_preserved=True,source_bytes_unchanged=True,private_extra_fields_not_exported=True,wrong_hash_private_locator_and_overwrite_rejected=True,NFL_rows_read=0,native_store_constructions=0,model_loads=0,fits=0,inference=0,grading=0,score_calculations=0,code_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in [source,Path(__file__)]})
        print(json.dumps(fixture,sort_keys=True))
if __name__=='__main__':main()
