"""Fictional source transport, real retained original public code, no network/fits.

Parent CI must stage the complete public 895 Git objects and set
NFL_R0_SOURCE_REPOSITORY. Only code blobs are read in these tests; bootstrap
cache/output data are wholly fictional, never protected outcome artifacts.
"""
from copy import deepcopy
from datetime import timedelta
import gzip,json,os
from pathlib import Path
import socket,subprocess,sys,tempfile,unittest
from unittest.mock import patch
from urllib.parse import urlsplit

from nfl_lab import audit_reference_capture_v1 as ref, weekly_adaptive as selector
from nfl_lab.operational_storage import OperationalStorage
from nfl_lab.state import canonical,digest,now_utc,utc

ROOT=Path(__file__).resolve().parents[1]
GAME='2099_02_BBB_AAA'
ESPN='400000001'
KICKOFF='2099-10-25T17:00:00+00:00'
PLAYERS={
 '1001':dict(full_name='FICTIONAL Home RB',position='RB',team='AAA',active=True),
 '1002':dict(full_name='FICTIONAL Away WR',position='WR',team='BBB',active=True)}
ROWS=[dict(player_id=pid,team=team,opponent='BBB'if team=='AAA'else'AAA',stats=stats)
 for pid,team,stats in [('1001','AAA',dict(gp=1,rush_att=10,rush_yd=40,rec=0,rec_yd=0,rush_td=.5,pts_ppr=8)),
                       ('1002','BBB',dict(gp=1,rush_att=0,rush_yd=0,rec=4,rec_yd=60,rec_td=.5,pts_ppr=13))]]


def fixture_value(url,params):
 path=urlsplit(url).path
 if path=='/v1/state/nfl':return dict(season='2099',week=2,season_type='regular')
 if path=='/v1/players/nfl':return deepcopy(PLAYERS)
 if '/stats/nfl/'in path or '/projections/nfl/'in path:return deepcopy(ROWS)
 if path.endswith('/scoreboard'):
  return dict(events=[dict(id=ESPN,date=KICKOFF,status=dict(type=dict(state='pre',completed=False,shortDetail='Scheduled')),
   competitions=[dict(status=dict(type=dict(state='pre',completed=False,shortDetail='Scheduled')),
    competitors=[dict(homeAway=side,score='',team=dict(id=str(i),abbreviation=team))for i,side,team in [(1,'home','AAA'),(2,'away','BBB')]])])])
 if path.endswith('/lines/available'):return []
 if path.endswith('/injuries'):return dict(injuries=[])
 if path.endswith('/teams'):return dict(sports=[])
 if path.endswith('/odds')or path.endswith('/propBets'):return dict(items=[])
 if path.endswith('/depthcharts'):return {}
 raise AssertionError('FICTIONAL_UNSUPPORTED_ENDPOINT')


def install_transport():
 import requests
 def denied(*a,**k):raise AssertionError('REFERENCE_AGENT_TEST_NETWORK_DENIED')
 socket.socket.connect=socket.socket.connect_ex=socket.create_connection=denied
 def response(session,method,url,**kwargs):
  body=fixture_value(url,kwargs.get('params'))
  counter=os.environ.get('REFERENCE_FIXTURE_COUNTER')
  if counter:
   with Path(counter).open('a')as stream:stream.write('FICTIONAL_HTTP\n')
  return type('FixtureResponse',(),dict(status_code=200,raise_for_status=lambda self:None,json=lambda self:deepcopy(body)))()
 requests.sessions.Session.request=response


class ReferenceChecks(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.base=Path(self.temp.name)
  policy=json.loads((ROOT/'config/operational-source-policy-v2.json').read_text())
  self.store=OperationalStorage(self.base/'cache',policy,state=self.base/'state')
  self.repo=Path(os.environ.get('NFL_R0_SOURCE_REPOSITORY','/workspace/nfl-system-audit/website-caption'))
  self.assertTrue(self.repo.exists(),'Parent must stage original public Git objects via NFL_R0_SOURCE_REPOSITORY')
  now=now_utc();self.slate=dict(season=2099,week=2,season_type='REG',slate_id='2099-REG-W02-future-v1',
   game_cutoffs={GAME:'2099-10-25T16:00:00+00:00'},scheduled_first_kickoff_utc=KICKOFF)
  self.control=dict(ref.control_spec(),registered_at=(now-timedelta(minutes=2)).isoformat())
  self.permit=dict(schema_version='audit-weekly-correction-epoch-v1-capture-permit',epoch_sha256=digest('fictional-epoch'),
   choice_sha256=digest('fictional-choice'),selected_versions_sha256=digest('fictional-versions'),catalog_sha256=digest('fictional-catalog'),
   metadata_completion_sha256=digest('fictional-completion'),actual_capture_authorized_at=(now-timedelta(minutes=1)).isoformat(),
   qualified_artifact_restore_proof_sha256=digest('fictional-models-only-proof'),metadata_cas_readback_sha256=digest('fictional-CAS'),
   metadata_remote_durability_qualified=False,captured_bundle_remote_durability_qualified=False,
   game_cutoffs=self.slate['game_cutoffs'],fits=0,reselect=False)
  self.bridge=[];self.offers=[]
  for gsis,sid,own,opp,pos,targets in [('00-0000001','1001','AAA','BBB','RB',['rush_att','rush_yd','rec','anytime_td']),
                                     ('00-0000002','1002','BBB','AAA','WR',['rec','rec_yd','anytime_td'])]:
   item=dict(gsis_id=gsis,gsis_game_id=GAME,sleeper_id=sid,website_player_id=sid,website_game_id=ESPN,
    team=own,opponent=opp,kickoff_utc=KICKOFF,query_source_sha256=digest('fictional-query'),schedule_source_sha256=digest('fictional-schedule'),
    identity_bridge_kind='EXACT_ORIGINAL_WEEKLY_ROSTER_AND_SCHEDULE_NOT_NAMES',actual_visible_board_compatibility='NOT_YET_CHECKED')
   item['identity_binding_sha256']=digest(item);self.bridge.append(item)
   for target in targets:
    offer=dict(season=2099,week=2,game_id=GAME,player_id=gsis,category=target,slate_id=self.slate['slate_id'],
     horizon='player_game',position=pos,team=own,opponent=opp,kickoff_utc=KICKOFF,cutoff_utc=self.slate['game_cutoffs'][GAME])
    offer['offered_id']=selector.offered_id(offer);self.offers.append(offer)
  self.bootstrap_calls=0
  self.transport=self.base/'transport';self.transport.mkdir()
  (self.transport/'sitecustomize.py').write_text('from test_audit_reference_capture_v1 import install_transport\ninstall_transport()\n')
  self.counter=self.base/'http-counter.txt'

 def bootstrap(self,storage,stage,repository):
  self.bootstrap_calls+=1
  old={r['player_id']:dict(team=r['team'],opp=r['opponent'],stats={k:v for k,v in r['stats'].items()if k!='fgm'})for r in ROWS}
  storage.write_bytes(stage/'data/cache/stats_2098_01.json',canonical(old))
  storage.write_bytes(stage/'output/data/track_record.json',b'{"fictional_old_record":true}')

 def prepare(self,name='first',previous=None,aliases=None):
  with patch.object(ref,'_bootstrap',side_effect=self.bootstrap):
   return ref.prepare_reference(self.store,self.base/name,repository=self.repo,permit=self.permit,slate=self.slate,
    control=self.control,offers=self.offers,bridge=self.bridge,previous_state=previous,previous_state_aliases=aliases)

 def capture(self,prepared):
  env=dict(PYTHONPATH=str(self.transport)+os.pathsep+str(ROOT)+os.pathsep+str(ROOT/'tests'),REFERENCE_FIXTURE_COUNTER=str(self.counter))
  with patch.dict(os.environ,env):return ref.capture_reference(self.store,prepared)

 def full(self):
  prepared=self.prepare();finished=self.capture(prepared);result=ref.read_owned(self.store,finished)
  return prepared,result,ref.read_owned(self.store,result['control_forecast_rows'])

 def test_real_original_default_code_native_and_legacy_control_semantics(self):
  prepared,result,doc=self.full()
  self.assertEqual(result['state'],'ORIGINAL_R0_CAPTURE_COMPLETE_PRIVATE')
  self.assertEqual(len(doc['rows']),len(self.offers));self.assertEqual(doc['unavailable'],[])
  worker=ref.read_owned(self.store,ref.binding(self.base/'first/WORKER_COMPLETE.json'))
  original_native=Path(ref.read_owned(self.store,prepared)['worker'])/'data/forward/2099/w02'
  saved=next(original_native.glob('*.json.gz')).read_bytes();self.assertEqual(Path(result['native']['path']).read_bytes(),saved)
  payload=json.loads(gzip.decompress(saved))['payload']
  self.assertEqual(payload['model'],ref.ORIGINAL_MODEL);self.assertEqual(payload['code_commit'],ref.SOURCE)
  self.assertEqual(payload['engine_files'],ref.ENGINE)
  self.assertTrue(all(not ev['refresh']for ev in worker['cache_events']if ev['season']==2098))
  self.assertTrue(any(ev['cache_hit']for ev in worker['cache_events']if ev['season']==2098 and ev['week']==1))
  for row in doc['rows']:
   self.assertEqual(row['method_id'],'R0');self.assertEqual(row['training_state'],'UPSTREAM_TRAINING_UNOBSERVED')
   self.assertNotIn('training_started_at',row);self.assertEqual(row['original_R0_identity_sha256'],ref.R0_IDENTITY)
   if row['category']!='anytime_td':self.assertEqual((row['product'],row['prediction_functional']),('point_legacy','legacy_unknown'))
   else:
    self.assertEqual(row['forecast_value'],.393);self.assertNotEqual(row['forecast_value'],.00393)
    self.assertEqual(row['product'],'binary_probability');self.assertEqual(row['prediction_functional'],'event_probability')
    self.assertTrue(row['saved_event_probability'])
  zero=next(r for r in doc['rows']if r['player_id']=='00-0000001'and r['category']=='rec')
  self.assertEqual(zero['forecast_value'],0)
  catalog=dict(schema_version=selector.VERSION,methods={'R0':self.control},categories={})
  for target in {r['category']for r in self.offers}:
   binary=target=='anytime_td';signed=target.endswith('_yd');product='binary_probability'if binary else'point_median'if signed else'point_mean'
   catalog['categories'][target]=dict(state='READY',support='bernoulli'if binary else'signed_integer'if signed else'count',
    product=product,primary_metric='brier'if binary else'point_mae'if signed else'point_mse',reference_id='R0',shortlist=['R0'],eligible_methods=['R0'],
    **({'event_contract':selector.ANYTIME_EVENT_CONTRACT}if binary else{}))
  panel=selector.Panel(dict(schema_version=selector.VERSION,offers=self.offers,forecasts=doc['rows'],outcomes=[],decisions=[],weeks=[]),catalog)
  self.assertTrue(all(panel.eligible('R0',o,'original_pregame')for o in self.offers))
  self.assertFalse(result['remote_durability_qualified']);self.assertFalse(result['actual_actions_api_authenticated'])
  completion=ref.read_owned(self.store,result['control_completion'])
  self.assertLess(utc(completion['body_persist_completed_at']),utc(self.slate['game_cutoffs'][GAME]))
  self.assertLessEqual(utc(completion['original_native_persist_completed_at']),utc(completion['body_persist_completed_at']))

 def test_durable_original_cache_continuity_and_no_bootstrap_reuse(self):
  prepared,result,doc=self.full();state=ref.read_owned(self.store,result['next_state'])
  old=state['files']['data/cache/stats_2098_01.json'];raw=Path(old['path']).read_bytes()
  next_prepared=self.prepare('second',result['next_state'])
  self.assertEqual(self.bootstrap_calls,1)
  p=ref.read_owned(self.store,next_prepared)
  self.assertEqual((Path(p['worker'])/'data/cache/stats_2098_01.json').read_bytes(),raw)
  self.assertEqual(Path(old['path']).read_bytes(),raw)
  next_result=ref.read_owned(self.store,self.capture(next_prepared));self.assertEqual(next_result['available_rows'],len(self.offers))
  self.assertEqual(ref.read_owned(self.store,next_result['next_state'])['previous_state'],result['next_state'])

 def test_missing_player_keeps_every_opportunity_unavailable_not_zero(self):
  item=deepcopy(self.bridge[0]);item.update(gsis_id='00-0000003',sleeper_id='9999',website_player_id='9999')
  item['identity_binding_sha256']=digest({k:v for k,v in item.items()if k!='identity_binding_sha256'});self.bridge.append(item)
  offer=deepcopy(self.offers[0]);offer['player_id']=item['gsis_id'];offer['offered_id']=selector.offered_id(offer);self.offers.append(offer)
  _,result,doc=self.full();self.assertEqual(len(doc['rows']),len(self.offers));self.assertEqual(result['unavailable_rows'],1)
  row=next(r for r in doc['rows']if r['player_id']==item['gsis_id'])
  self.assertIsNone(row['forecast_value']);self.assertFalse(row['operational_eligible'])
  self.assertEqual(row['unavailable_reason'],'ORIGINAL_R0_PLAYER_UNAVAILABLE')

 def test_duplicate_names_do_not_bridge_conflicting_source_ids(self):
  self.bridge[1]['sleeper_id']='1001';self.bridge[1]['website_player_id']='1001'
  self.bridge[1]['identity_binding_sha256']=digest({k:v for k,v in self.bridge[1].items()if k!='identity_binding_sha256'})
  with self.assertRaisesRegex(ref.ReferenceError,'DUPLICATE'):self.prepare()
  self.assertFalse(self.counter.exists())

 def test_bridge_team_or_game_conflict_retains_original_native_but_fails_control_attempt(self):
  self.bridge[0]['website_game_id']='400000002';self.bridge[1]['website_game_id']='400000002'
  for item in self.bridge:item['identity_binding_sha256']=digest({k:v for k,v in item.items()if k!='identity_binding_sha256'})
  p=self.prepare()
  with self.assertRaisesRegex(ref.ReferenceError,'IDENTITY_CONFLICT'):self.capture(p)
  self.assertTrue((self.base/'first/native/original-native.json.gz').exists())
  self.assertTrue((self.base/'first/CAPTURE_FAILED.json').exists())
  self.assertFalse((self.base/'first/CAPTURE_COMPLETE.json').exists())

 def test_changed_or_legacy_incomplete_permit_rejects_before_provider_calls(self):
  self.permit.pop('metadata_cas_readback_sha256')
  with self.assertRaisesRegex(ref.ReferenceError,'SHARED_CUTOFF'):self.prepare()
  self.assertFalse(self.counter.exists())

 def test_corrected_bytes_cannot_be_used_as_original_code(self):
  originals=ref.original_sources(self.repo);originals['pull/scoring.py']=originals['pull/scoring.py']+b'\n'
  p=self.prepare();stage=Path(ref.read_owned(self.store,p)['worker'])
  with self.store.capture_writes([stage]):self.store.write_bytes(stage/'pull/scoring.py',originals['pull/scoring.py'],replace=True)
  with self.assertRaisesRegex(ref.ReferenceError,'WORKER_FAILED'):self.capture(p)
  self.assertFalse(self.counter.exists());self.assertFalse((self.base/'first/CAPTURE_COMPLETE.json').exists())

 def test_repeated_capture_does_not_acquire_again(self):
  p,_,_=self.full();before=self.counter.read_bytes()
  with self.assertRaisesRegex(ref.ReferenceError,'ALREADY_CONSUMED'):self.capture(p)
  self.assertEqual(self.counter.read_bytes(),before)

 def test_changed_shared_cutoff_or_extra_outcome_field_rejects_before_calls(self):
  self.offers[0]['cutoff_utc']='2099-10-25T16:30:00+00:00'
  with self.assertRaises(ref.ReferenceError):self.prepare()
  self.offers[0]['cutoff_utc']=self.slate['game_cutoffs'][GAME];self.offers[0]['actual']=30
  with self.assertRaisesRegex(ref.ReferenceError,'CLOSED_REFERENCE_OFFER'):self.prepare()
  self.assertFalse(self.counter.exists())

 def test_unregistered_or_future_registered_control_cannot_acquire(self):
  self.control['registered_at']=(now_utc()+timedelta(minutes=1)).isoformat()
  with self.assertRaisesRegex(ref.ReferenceError,'CONTROL_REGISTRATION'):self.prepare()
  self.assertFalse(self.counter.exists())

 def test_crossing_cutoff_during_control_persistence_keeps_bytes_without_success(self):
  p=self.prepare();actual_write=self.store.write_bytes;actual_stamp=ref.stamp;written=[False]
  def write(path,body,**kwargs):
   result=actual_write(path,body,**kwargs)
   if Path(path).name=='R0_CONTROL_FORECAST_ROWS.json':written[0]=True
   return result
  def clock():return self.slate['game_cutoffs'][GAME]if written[0]else actual_stamp()
  with patch.object(self.store,'write_bytes',side_effect=write),patch.object(ref,'stamp',side_effect=clock):
   with self.assertRaisesRegex(ref.ReferenceError,'PERSISTENCE_MISSED_CUTOFF'):self.capture(p)
  self.assertTrue((self.base/'first/R0_CONTROL_FORECAST_ROWS.json').exists())
  self.assertTrue((self.base/'first/CAPTURE_FAILED.json').exists())
  self.assertFalse((self.base/'first/CAPTURE_COMPLETE.json').exists())

 def test_current_baseline_state_cannot_seed_original_R0(self):
  folder=self.store.register_root(self.base/'prior')
  bad=ref.write(self.store,folder/'BAD.json',dict(schema_version=ref.VERSION+'-state',source=ref.SOURCE,
   procedure=ref.PROCEDURE,model='sleeper-matchup-classic-fg-identity-v1',frozen_R0_identity_sha256=ref.R0_IDENTITY,
   source_files=ref.SOURCE_FILES,files={}))
  with self.assertRaisesRegex(ref.ReferenceError,'NOT_CURRENT_BASELINE'):self.prepare(previous=bad)
  self.assertFalse(self.counter.exists())

 def test_cross_job_state_uses_exact_complete_aliases_without_rewriting_original_metadata(self):
  p=self.prepare();stage=Path(ref.read_owned(self.store,p)['worker'])
  # A self-contained fictional completed-state descriptor; no provider calls.
  files=ref._files(stage)
  state=dict(schema_version=ref.VERSION+'-state',source=ref.SOURCE,procedure=ref.PROCEDURE,model=ref.ORIGINAL_MODEL,
   frozen_R0_identity_sha256=ref.R0_IDENTITY,source_files=ref.SOURCE_FILES,files=files,
   previous_state=None,actual_completed_at=now_utc().isoformat(),native_sha256=digest('fictional-native'),fits=0,public_release=False)
  original=ref.write(self.store,self.base/'first/STATE_FIXTURE.json',state);raw=Path(original['path']).read_bytes()
  policy=json.loads((ROOT/'config/operational-source-policy-v2.json').read_text())
  restored=OperationalStorage(self.base/'restored-cache',policy,state=self.base/'restored-state')
  dest=restored.register_root(self.base/'restored-files');aliases={}
  copied=restored.import_file(original['path'],dest/'STATE.json',expected_sha256=original['sha256'])
  original_ref={k:copied[k]for k in ('path','bytes','sha256')}
  for name,v in files.items():
   alias=restored.import_file(v['path'],dest/name,expected_sha256=v['sha256'])
   aliases[name]={k:alias[k]for k in ('path','bytes','sha256')}
  with patch.object(ref,'_bootstrap',side_effect=AssertionError('Do not reset restored original cache')):
   prepared=ref.prepare_reference(restored,self.base/'third',repository=self.repo,permit=self.permit,slate=self.slate,
    control=self.control,offers=self.offers,bridge=self.bridge,previous_state=original_ref,previous_state_aliases=aliases)
  doc=ref.read_owned(restored,prepared)
  self.assertEqual((Path(doc['worker'])/'data/cache/stats_2098_01.json').read_bytes(),Path(files['data/cache/stats_2098_01.json']['path']).read_bytes())
  self.assertEqual(Path(original_ref['path']).read_bytes(),raw)
  self.assertFalse(self.counter.exists())
  incomplete=dict(aliases);incomplete.pop(next(iter(incomplete)))
  with self.assertRaisesRegex(ref.ReferenceError,'COMPLETE_HASH_IDENTICAL'):
   ref.prepare_reference(restored,self.base/'fourth',repository=self.repo,permit=self.permit,slate=self.slate,
    control=self.control,offers=self.offers,bridge=self.bridge,previous_state=original_ref,previous_state_aliases=incomplete)
  self.assertFalse(self.counter.exists())

 def test_unapproved_cli_template_never_discovers_or_opens_source_repository(self):
  result=subprocess.run([sys.executable,'-B',str(ROOT/'tools/audit_reference_capture_v1.py')],capture_output=True,text=True,check=True)
  doc=json.loads(result.stdout);self.assertFalse(doc['approved']);self.assertEqual(doc['source_reads'],0)
  self.assertEqual(doc['fits'],0);self.assertFalse(doc['public_release'])

 def test_send_and_redirect_budget_cannot_bypass_source_scope(self):
  import requests
  folder=self.store.register_root(self.base/'send-metadata');calls=[]
  def fake_send(session,request,**kwargs):calls.append(request.url);return object()
  request=requests.Request('GET','https://api.sleeper.app/v1/state/nfl').prepare()
  with patch.object(requests.sessions.Session,'send',fake_send),patch.dict(ref.LIMITS,requests=1):
   with ref._Observations(self.store,folder,self.slate['game_cutoffs'][GAME])as observations:
    session=requests.Session();session.send(request)
    with self.assertRaisesRegex(ref.ReferenceError,'WIRE_REQUEST_BOUND'):session.send(request)
    self.assertEqual(len(calls),1);self.assertTrue(observations.fatal)
    other=requests.Request('GET','https://unapproved.invalid/feed').prepare()
    with self.assertRaisesRegex(ref.ReferenceError,'SOURCE_SCOPE'):session.send(other)


if __name__=='__main__':unittest.main()
