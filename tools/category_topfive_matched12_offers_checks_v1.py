"""One bounded fictional check; never loads NFL inputs or fitted models."""
from pathlib import Path
import hashlib
import importlib.util
import json
import resource
import signal
import time

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'reports/category-topfive-matched-all12-w1w7-20261030/offers'


def main():
    start, cpu = time.monotonic(), time.process_time()
    resource.setrlimit(resource.RLIMIT_CPU,(20,21))
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('fictional offer check limit')))
    signal.alarm(30)
    target=OUT/'FICTIONAL_RESULT_V1.json'
    assert not target.exists(), 'one registered attempt only'
    source=ROOT/'tools/category_topfive_matched12_offers_v1.py'
    spec=importlib.util.spec_from_file_location('matched12_offer_loader',source)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    import pandas as pd
    checks=[]
    def check(name,value):
        assert value,name
        checks.append(name)
    sha='a'*64
    base={'season':2026,'week':1,'game_id':'2026_01_A_B','player_id':'00-0000001','team':'A','opponent':'B','position':'QB',
      'kickoff_utc':'2026-09-01T17:00:00Z','target':'pass_att','period':'event','side':'over','line':30.5,
      'american_odds':-110,'book_id':68,'book_kind':'named','source_collection_naive':'2026-08-31T12:00:00',
      'source_eligible_exploratory':True,'identity_status':'source_gsis_exact_historical_roster_schedule',
      'duplicate_status':'unique','source_row_number':0,'source_sha256':sha,'source_member':'fictional.parquet','rejection_reasons':''}
    cases=[dict(base),dict(base,side='under',source_row_number=1,american_odds=-110),
      dict(base,week=2,source_row_number=2,american_odds=0,rejection_reasons='invalid_american_odds',source_eligible_exploratory=False),
      dict(base,week=3,source_row_number=3,american_odds=0,rejection_reasons='invalid_american_odds;conflicting_duplicate_versions',source_eligible_exploratory=False),
      dict(base,source_row_number=4,book_id=69,line=29.5,source_collection_naive='2026-08-30T12:00:00'),
      dict(base,week=4,source_row_number=5,source_eligible_exploratory=None),
      dict(base,week=5,target='anytime_td',side='noside',line=0,source_row_number=6),
      dict(base,week=6,source_row_number=7,book_id=15,book_kind='consensus',rejection_reasons='not_individual_sportsbook',source_eligible_exploratory=False),
      dict(base,week=7,source_row_number=8,source_collection_naive='2026-08-31T12:00:00',line=29.5),
      dict(base,week=7,source_row_number=9,source_collection_naive='2026-08-30T12:00:00',line=31.5)]
    status={'state':'FAILED_RETAINED','fixture_only':True,'checks':checks,'new_NFL_decode_fits_inference_scores_HTTP_CAS':0}
    try:
        result=m.prepare_annual_line_only(pd.DataFrame(cases),admitted_source_sha256s={sha})
        primary=result['primary']
        r=primary.loc[primary.week.eq(1)].iloc[0]
        check('named_book_priority_before_alternate_book_clock',r.book_id==68 and r.line==30.5)
        check('same_book_same_clock_pair_retained',r.over_offer_present and r.under_offer_present and r.valid_two_sided_prices)
        r=primary.loc[primary.week.eq(2)].iloc[0]
        check('invalid_price_only_finite_line_retained',r.line==30.5 and bool(r.line_only_price_admitted))
        check('invalid_price_not_replaced_or_market_qualified',pd.isna(r.decimal_over) and not bool(r.market_probability_eligible))
        check('nonprice_conflict_stays_rejected',not primary.week.eq(3).any())
        check('nullable_eligibility_rejected',not primary.week.eq(4).any())
        check('ATD_is_event_not_numeric_line',len(result['event_offers'])==1 and result['event_offers'].iloc[0].target=='anytime_td' and pd.isna(result['event_offers'].iloc[0].line))
        check('consensus_stays_excluded',not primary.week.eq(6).any())
        check('earliest_collector_selected_without_opening_claim',primary.loc[primary.week.eq(7)].iloc[0].line==31.5 and not primary.cutoff_qualified.any())
        b={'season':2026,'week':6,'source_game_id':'event6','source_player_id':'12','game_id':'2026_06_A_B','player_id':'00-0000001',
          'team':'A','opponent':'B','position':'QB','kickoff_utc':'2026-10-01T17:00:00Z','identity_resolution_state':'resolved_source_exact_sleeper',
          'identity_source_sha256':'b'*64,'identity_adapter_version':'source-qualified-query-identity-v1','event_crosswalk_sha256':'c'*64}
        binding=pd.DataFrame([b]);fingerprint=hashlib.sha256(binding.to_json(orient='table',date_format='iso',index=False,force_ascii=True).encode()).hexdigest()
        archive={'season':2026,'week':6,'saved_at':'2026-10-02T12:00:00Z','games':[{'id':'event6','home':'B','away':'A','kickoff':'2026-10-01T17:00:00Z'}],
          'players':[{'id':'12','game_id':'event6','team':'A','opp':'B','pos':'QB','late':True,'props':[
            {'key':'pass_att','line':30.5,'line_from':'dk','lean':None},
            {'key':'pass_cmp','line':20.5,'line_from':'sleeper','lean':'over'},
            {'key':'pass_td','line':1.5,'line_from':'ours','lean':'under'}]}]}
        result2=m.prepare_site_line_only(archive,binding,expected_binding_sha256=fingerprint,source_sha256='d'*64)
        check('unchosen_prop_and_late_flag_do_not_remove_descriptive_line',len(result2['primary_dk'])==1 and bool(result2['primary_dk'].iloc[0].source_late_flag))
        check('contest_separate_from_DK_primary',len(result2['secondary_contest'])==1 and result2['secondary_contest'].iloc[0].target=='pass_cmp')
        check('site_generated_line_excluded',not result2['all_lines'].target.eq('pass_td').any())
        check('site_prices_times_stay_unavailable',result2['primary_dk'].iloc[0].source_quote_time is None and result2['primary_dk'].iloc[0].decimal_over is None)
        combined=m.combine_source_fallback(primary,result2['primary_dk'])
        check('model_independent_primary_unique',not combined.duplicated(list(m.KEY)).any() and combined.opportunity_key.nunique()==len(combined))
        # Exact-context mismatch must abstain instead of rewriting the source team.
        altered=archive.copy();altered['players']=[{**archive['players'][0],'team':'B','opp':'A'}]
        rejected=m.prepare_site_line_only(altered,binding,expected_binding_sha256=fingerprint,source_sha256='d'*64)
        check('context_mismatch_excludes_without_reclassification',len(rejected['primary_dk'])==0 and len(rejected['excluded'])==3)
        try:
            m.prepare_site_line_only(archive,binding,expected_binding_sha256='f'*64,source_sha256='d'*64)
        except ValueError:check('binding_hash_enforced',True)
        else:raise AssertionError('binding hash not enforced')
        status['state']='PASS_FICTIONAL_SOURCE_POLICY_CHECKS_ONLY'
    except BaseException as exc:
        status['error_type']=type(exc).__name__;status['error']=str(exc)
        raise
    finally:
        signal.alarm(0)
        status['source_sha256']=hashlib.sha256(source.read_bytes()).hexdigest()
        status['actual']={'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}
        with target.open('x') as f:json.dump(status,f,indent=2);f.write('\n')
        print(json.dumps(status))

if __name__=='__main__':main()
