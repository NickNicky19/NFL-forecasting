"""Versioned fictional continuation; original source and 23-case pass retained."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=root/'tools/category_topfive_matched12_score_checks_v1.py';source=p.read_text()
source=source.replace("'category_topfive_matched12_score_v1.py'","'category_topfive_matched12_score_v1_1.py'")
source=source.replace("'shortlist_group':'LEAF_CDF'}","'shortlist_group':'LEAF_CDF','products':['mean' if x=='CDF_MEAN' else 'median']}")
source=source.replace('scope=dict(','scope=dict(horizon_id="fictional-primary",')
source=source.replace("'minimum_clusters':2});check", "'minimum_clusters':2},expected_roster=f[m.KEY+['position']].drop_duplicates(),outcomes=f[m.ID+['horizon_id','actual','participation_state']].drop_duplicates());check")
extra='''
 d=m.normalize(pd.DataFrame([row(actual=np.nan,state='DNP')]),scope,{'rec':cfg});check('uppercase_DNP_canonical',d.participation_state.iloc[0]=='dnp' and m.metrics(d,'rec')['DNP']==1)
 rejects('unknown_participation_enum_rejected',lambda:m.normalize(pd.DataFrame([row(actual=np.nan,state='inactive')]),scope,{'rec':cfg}))
 second=f.copy();second['player_id']='fictional-player-2';second['game_id']='fictional-game-2';both=pd.concat([f,second],ignore_index=True)
 expected=both[m.KEY+['position']].drop_duplicates();outcomes=both[m.ID+['horizon_id','actual','participation_state']].drop_duplicates()
 partial=both.copy();partial.loc[(partial.player_id=='fictional-player-2')&partial.method.eq('CDF_MEDIAN'),'prediction']=np.nan
 result,_=m.score_panel(partial,scope,{'rec':cfg},{'seed':1703,'replicates':5,'minimum_clusters':2},expected_roster=expected,outcomes=outcomes)
 core=[x for x in result['records'] if x['scope']=='PREDECLARED_PRIMARY_COMMON_CORE'];check('same_joint_finite_core',len(core)==2 and all(x['metrics']['scored']==1 and x['excluded_core_rows']==1 for x in core))
 missing=both.loc[~((both.player_id=='fictional-player-2')&both.method.eq('CDF_MEDIAN'))];grid=m.materialize_expected(missing,expected,outcomes,scope,{'rec':cfg})
 check('missing_output_materialized',len(grid)==4 and grid.prediction_status.eq('MISSING_DECLARED_OUTPUT').sum()==1)
 bad=f.copy();bad.loc[0,'team']='X';rejects('context_contradiction_not_hidden_in_KEY',lambda:m.normalize(bad,scope,{'rec':cfg}))
 bad=f.copy();bad.loc[0,'participation_state']='unknown';bad.loc[0,'actual']=np.nan;rejects('participation_conflict_across_methods',lambda:m.normalize(bad,scope,{'rec':cfg}))
 bad=f.copy();bad.loc[0,'actual']=3.;rejects('label_conflict_across_methods',lambda:m.normalize(bad,scope,{'rec':cfg}))
 point=pd.DataFrame([row()]);offer=point[m.ID+['cutoff_utc']].copy();offer['line']=1.5;offer['evidence_tier']='FICTIONAL';offer['primary_offer_policy']='FICTIONAL';offer['statistical_contract']='FICTIONAL'
 offer['cutoff_utc']='2026-08-31T20:00:00-04:00';check('equivalent_offer_UTC_joins',m.point_sides(point,offer,contract).iloc[0].statistical_result=='WIN')
 duplicate=pd.concat([offer,offer.assign(cutoff_utc='2026-09-01T00:00:00Z')]);rejects('equivalent_UTC_offer_duplicate_rejected',lambda:m.point_sides(point,duplicate,contract))
 rejects('naive_offer_clock_rejected',lambda:m.point_sides(point,offer.assign(cutoff_utc='2026-09-01T00:00:00'),contract))
 rejects('bool_line_rejected',lambda:m.point_sides(point,offer.assign(line=True),contract))
 rejects('pdNA_line_rejected',lambda:m.point_sides(point,offer.assign(line=pd.NA),contract))
'''
source=source.replace(" out={'version':",extra+" out={'version':")
source=source.replace('resource.RLIMIT_CPU,(10,11)','resource.RLIMIT_CPU,(15,16)').replace('signal.alarm(20)','signal.alarm(30)')
source=source.replace('matched12-score-fictional-v1','matched12-score-fictional-v1.1').replace('FICTIONAL_RESULT_V1_1.json','FICTIONAL_RESULT_V2.json')
source='import hashlib\n'+source.replace("'cases':cases,","'case_ids_sha256':hashlib.sha256(json.dumps(cases).encode()).hexdigest(),")
exec(compile(source,str(p), 'exec'),{'__name__':'__main__','__file__':__file__})
