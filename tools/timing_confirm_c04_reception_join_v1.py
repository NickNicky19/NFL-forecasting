"""Exact C04 saved points on A's retained reception board; no fit or law inference.

The prior C03 comparison is immutable. F0/F1 are typed aliases of C03 R1/R2;
F2/F3 are the distinct one-day reconstructed-timing procedures. Public-source
preparation is separate from root-authorized private-board scoring.
"""
from __future__ import annotations
import argparse, collections, copy, datetime, gzip, hashlib, importlib, importlib.util, json, lzma, math, os
from pathlib import Path
import resource, signal, sys, time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
VERSION='A::PROFILE-TIMING-CLOSURE-AND-CONFIRM-01::C04-REC-POINT-v1'
C_REF='d3d1ef4dc60826334234cfa1a1b8e373b2ee024e'
C_PATH='reports/profile-closure-next-02/timing/POINT_HANDOFF.json.xz'
C_SHA='4fd67d7915f9da3df9bec152155e809eb34d60f89d3ea751e26da9eb0a5c8abc'
C_BYTES=234104
MANIFEST_SHA='bd541f4425f1ac0c627583fbcf5fad8fd7a4fcd598526fe803ea89d84d97367c'
PRIOR_ID='NEXT02_C03_REC_COMPLETE_SCORES_V1.json.gz'
PRIOR_SHA='f50f710c41de70e6ff4998f701e259ef532a5cf3c99d3ac7f3be9bfb6e1035e8'
PREFIX='C-RECEIVING-ALIGNED-TIMING-v1::'
PRODUCTS=['MEAN','MEDIAN']
ARMS=['F0','F1','F2','F3']
IDS=[PREFIX+a+'::'+p for a in ARMS for p in PRODUCTS]
NEW=IDS[4:]
ALIASES={PREFIX+a+'::'+p:'C-RECEIVING-PROFILE-INCREMENT-v2::'+b+'::'+p for a,b in [('F0','R1'),('F1','R2')]for p in PRODUCTS}
PHASE='NOT_STARTED'
CODE_METADATA={
 'src/receiving_timing_c04.py':'314b4f645a51e2d9c239ea4e18dc6d53db5ec1f3d85de7c2751d45c6d86a0ac7',
 'src/receiving_increment_c03.py':'5c42b388bad93cbb46f4f1d93e37c78c0cb8b3af416aa00b23632bcd7b3a8198',
 'src/data_v2.py':'e217c62617ea394a514fbde274e0074274f04a24890522db2af70f3b35ec2b9a',
 'src/context_features_c01.py':'e9c2b76df51ecd18e9f270a93838b5c36bd765fdb2f47306304b3db4dd914725',
 'src/receiving_defense_c03.py':'1822f048fcdabaefc7f4edcb7e69f4846a119d1212b9a5f575f9190303c7d1c9',
 'src/laws_v2.py':'70251578ac1f431c7da63cd14760386eef5c38ce1915a40a4520340189ffce7c',
 'src/safe_models_v4.py':'c6ae2868ab6530803cd5a9c56dae2922aeaf1f0b4c5cae54341d25dda8dea0e0'}

def enc(x):return(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def check(ok,message):
 if not ok:raise ValueError(message)
def finite(x):return type(x)in[float,int]and math.isfinite(x)
def local(name,path):
 spec=importlib.util.spec_from_file_location(name,ROOT/path);module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module
def checked(path,digest,size=None):
 b=Path(path).read_bytes();check(sha(b)==digest and(size is None or len(b)==size),'immutable bytes differ: '+Path(path).name);return b
def aware(value):
 t=datetime.datetime.fromisoformat(value.replace('Z','+00:00'));check(t.tzinfo is not None,'timezone-aware source/decision clock required');return t.astimezone(datetime.timezone.utc)

def public_sources(args,c03):
 """Read only public point and metadata bytes; never A offers/outcomes."""
 c03body,c03src,r0,oldslots,oldproof=c03.public_sources(args.c03_points,args.c_r0,args.c03_metadata)
 folder=args.c04_dir
 body=checked(folder/'POINT_HANDOFF.json.xz',C_SHA,C_BYTES)
 manifest_raw=checked(folder/'POINT_HANDOFF_MANIFEST.json',MANIFEST_SHA)
 manifest=json.loads(manifest_raw);src=json.loads(lzma.decompress(body))
 check(src['id']==manifest['id']=='C04-POINT-ONLY-OWNER-LOCAL-HANDOFF-v1','C04 handoff identity differs')
 check(manifest['category']=='rec' and manifest['statistic']=='FULL_GAME_OVERTIME_OFFICIAL_RECEPTIONS','C04 target differs')
 check(manifest['new_fits']==manifest['new_inference']==manifest['future_queries_issued']==0,'cached export must not claim issuance/inference')
 check(manifest['export']==dict(path=C_PATH,SHA256=C_SHA,query_rows=4811,arm_query_records=19244,typed_point_values=38488,public_bytes=C_BYTES),'C04 export scope differs')
 check(set(manifest['procedures'])==set(IDS) and len(manifest['origins'])==64,'exact finite C04 procedure/origin roster differs')
 docs={}
 for filename,digest in [('INPUT_BINDINGS.json','38e2a1d44452e5253792be6d50b791615dfaf39f3ec55563186d33ff0e92681e'),('FEATURE_ORDER.json','07aca583ee388a8fbdc2a9284a899df184e12e0a6f064ce74ddc6b4b9cca8e9f'),('REGISTRATION.json','bb2e118bf6d4fdab9d1ef78cf398811b184d42b25da52ea566166fc93046eefe'),('PILOT_REGISTRATION.json','eae556a49575268f76d1fbc78b8bd1c069d8e64997c2bde90b56277de378c153')]:
  b=checked(folder/filename,digest);docs[filename]=dict(bytes=len(b),sha256=sha(b))
 features=json.loads((folder/'FEATURE_ORDER.json').read_bytes())
 check(features['F0']==features['F2'] and features['F1']==features['F3'] and len(features['F0'])==41 and len(features['F1'])==58,'same-input timing arms/feature order differs')
 for path,digest in CODE_METADATA.items():
  b=checked(folder/path.replace('/','__'),digest);docs[path]=dict(bytes=len(b),sha256=sha(b))
 oldlookup={(r['season'],r['week'],r['game_id'],r['player_id'],r['procedure'].rsplit('::',1)[1]):r for r in c03src['rows']}
 seen=set();reused_values=0;rows=src['rows'];check(len(rows)==4811,'C04 query row count differs')
 for r in rows:
  check(set(r)=={'game_id','player_id','position','team','opponent_team','season','week','query_cutoff_UTC','category','forecasts'},'unexpected C04 point-row fields')
  check(r['category']=='rec' and r['position']in['RB','WR','TE'] and r['season']in[2025,2026] and r['week']in range(1,9),'C04 population differs')
  key=(r['season'],r['week'],r['game_id'],r['player_id']);check(key not in seen,'duplicate canonical C04 query');seen.add(key)
  cutoff=aware(r['query_cutoff_UTC']);check(set(r['forecasts'])==set(ARMS),'C04 query lacks a registered arm')
  for arm in ARMS:
   f=r['forecasts'][arm];check(set(f)=={'mean','median','mean_procedure_id','median_procedure_id','origin_ref'},'unexpected forecast or outcome/probability in point-only export')
   check(f['mean_procedure_id']==PREFIX+arm+'::MEAN' and f['median_procedure_id']==PREFIX+arm+'::MEDIAN','typed procedure differs')
   check(all(finite(f[p])and f[p]>=0 for p in ['mean','median'])and f['median']==math.floor(f['median']),'unrounded count point invalid')
   origin=f"{r['season']}-W{r['week']:02}-{arm}";check(f['origin_ref']==origin and origin in manifest['origins'],'model origin binding differs')
   model=manifest['origins'][origin]
   check(model['arm']==arm and aware(model['model_fit_cutoff_UTC'])<=cutoff,'model fit is after query cutoff')
   check(type(model['training_rows'])is int and model['training_rows']>0 and len(model['membership_SHA256'])==64 and len(model['SHA256'])==64,'missing fit/membership/model hash')
   expected_policy='RECONSTRUCTED_KICKOFF_PLUS7D_STRICT_CURRENT_VINTAGE'if arm in['F0','F1']else'RECONSTRUCTED_KICKOFF_PLUS1D_STRICT_CURRENT_VINTAGE_NOT_OBSERVED_PUBLICATION'
   check(model['availability_policy']==expected_policy and manifest['procedures'][PREFIX+arm+'::MEAN']['availability_policy']==expected_policy,'timing policy differs')
   if arm in ['F0','F1']:
    original={'F0':'R1','F1':'R2'}[arm];old=oldlookup[key+(original,)]
    check(model['original_C03_arm']==original and model['reused_original_fit']is True,'C04 reused source arm differs')
    check((r['position'],r['team'],r['opponent_team'])==(old['role'],old['team'],old['opponent']),'reused canonical role/team differs')
    check((f['mean'],f['median'])==(old['mean'],old['median']),'C04 baseline points are not exact original C03 values')
    check(model['SHA256']==c03src['models'][old['model_key']]['SHA256'],'C04 baseline model bytes differ')
    reused_values+=2
   else:
    check(model['original_C03_arm']is None and model['reused_original_fit']is False and model['source_code_SHA256']==CODE_METADATA['src/receiving_timing_c04.py'] and model['source_registration_SHA256']==docs['PILOT_REGISTRATION.json'if origin=='2026-W01-F2'else'REGISTRATION.json']['sha256'],'new timing recipe/model provenance differs')
 check(reused_values==19244,'C04 baseline value parity incomplete')
 oldkeys={(r['game_id'],r['player_id'])for r in c03src['rows']if r['season']==2026 and r['week']<=7}
 current={(r['game_id'],r['player_id'])for r in rows if r['season']==2026 and r['week']<=7}
 check(len(current)==2152 and current==oldkeys,'C04/C03 historical query universe changed')
 proof=dict(repository='NickNicky19/NFL-forecasting-NGS-C',commit=C_REF,path=C_PATH,bytes=len(body),sha256=sha(body),manifest=dict(path='reports/profile-closure-next-02/timing/POINT_HANDOFF_MANIFEST.json',bytes=len(manifest_raw),sha256=sha(manifest_raw)),metadata=docs,procedures=manifest['procedures'],origins=manifest['origins'],query_rows=4811,typed_values=38488,public_baseline_values_checked_exactly=reused_values,source_model_rows_checked=19244,old_C03_source_sha256=sha(c03body),old_C03_proof_sha256=sha(enc(oldproof)),rights='C explicitly published derived typed-point owner-local handoff; no grant for private A rows or peer models.',no_probabilities_or_issued_selections=True,timing='Current-revised reconstructed1day versus7day; per-gamekickoffquery/weeklyearliestfit; no authenticatedsourceobservationorquote availability.',fallback='Typedexportdoesnotcarryfallback/profilecoverage/imputationflags; F0/F1 flags reusedfromexactC03source, F2/F3rowflags UNKNOWN_NOT_EXPORTED. FrozenCdriverdeclares hard_fallback=False; that is separately labelled sourcecode evidence, not an exported row flag.',limitations='Model hashes/code/featureorders inspected; no C model bytes restored, deserialized or fit independently. Historical actual source availability remains unauthenticated.')
 return src,c03src,r0,proof

def candidate_sets(c03):
 controls=list(c03.CANDIDATES)
 pairs=[[a,b]for a in NEW for b in controls]
 pairs += [[PREFIX+a+'::'+p,PREFIX+b+'::'+p]for a,b in [('F1','F0'),('F2','F0'),('F3','F2'),('F3','F1'),('F3','F0')]for p in PRODUCTS]
 check(len(controls)==22 and len(pairs)==98 and len(set(map(tuple,pairs)))==98,'finite comparison roster differs')
 return controls,controls+IDS,pairs

def make_row(base,board_row,point,*,fallback=None,profile_covered=None,any_imputed=None,reason=None,flag_state='SOURCE_EXPORTED'):
 r=dict(season=2026,week=board_row['week'],game_id=board_row['game'],player_id=board_row['player'],category='rec',line=float(board_row['original_line_exact_text']),actual=board_row['actual'],appearance=board_row['appearance'],opportunity_key=board_row['opportunity'],source_panel=board_row['source_panel'],selected_side=base.side(point,board_row['original_line_exact_text']),point=point,fallback=fallback,profile_covered=profile_covered,any_imputed=any_imputed,unavailability_reason=reason,comparator='STRICT_OVER_UNDER',fallback_flag_state=flag_state)
 r['status']=base.grade(r);return r

def build_old_vectors(base,oldjoin,c03,board,forecasts,oldjoined,c03src):
 vectors=oldjoin.old_vectors(base,board,forecasts)
 for cid,field in zip(c03.R0_IDS,['mean','median']):
  vectors[cid]=[make_row(base,b,float(f[field])if(f:=oldjoined[b['opportunity']]['forecast'])is not None else None,fallback=f['fallback']if f else None,reason=oldjoined[b['opportunity']]['unavailable_reason'])for b in board]
 lookup={(r['procedure'].rsplit('::',1)[1],r['game_id'],r['player_id']):r for r in c03src['rows']if r['season']==2026 and r['week']<=7}
 for cid in c03.NEW:
  arm,product=cid.split('::')[-2:];vv=[]
  for b in board:
   reason=oldjoined[b['opportunity']]['unavailable_reason'];f=lookup.get((arm,b['game'],b['player']))if reason is None else None
   if reason is None:check(f is not None and f['role']==b['position']and f['week']==b['week'],'old C03 qualified identity/role differs')
   vv.append(make_row(base,b,float(f[product.lower()])if f else None,fallback=f['hard_fallback']if f else None,profile_covered=f['profile_covered']if f else None,any_imputed=f['any_imputed']if f else None,reason=reason))
  vectors[cid]=vv
 return vectors

def run(args):
 global PHASE
 started,cpu=time.monotonic(),time.process_time()
 check(not args.output.exists()and not args.public_receipt.exists(),'immutable result/receipt already exists')
 raw=checked(args.protocol,args.protocol_sha256);plan=json.loads(raw)
 check(plan['version']==VERSION and plan['state']=='ROOT_REGISTERED_SCORING_GO'and plan['registered_by']=='/root','exact root scoring GO required')
 caps=plan['resources'];check(caps['CPU_seconds']==400 and caps['wall_seconds']==900 and caps['RSS_bytes']==3*1024**3 and caps['private_fullscore_max_bytes']==524288 and caps['additional_private_max_bytes']<=1048576,'finite execution/retention envelope differs')
 for path,digest in plan['code_sha256'].items():check(sha((ROOT/path).read_bytes())==digest,'bound code differs: '+path)
 own=str(Path(__file__).resolve().relative_to(ROOT));check(plan['code_sha256'][own]==sha(Path(__file__).read_bytes()),'worker source not exact-bound')
 for name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[name]='1'
 resource.setrlimit(resource.RLIMIT_CPU,(380,400));resource.setrlimit(resource.RLIMIT_AS,(caps['RSS_bytes'],)*2)
 def stop(sig,_):
  if sig==signal.SIGXCPU:signal.signal(signal.SIGXCPU,signal.SIG_IGN)
  raise TimeoutError('finite C04 saved-point scoring budget')
 signal.signal(signal.SIGXCPU,stop);signal.signal(signal.SIGALRM,stop);signal.alarm(880)
 def offline(event,_):
  if event in {'socket.connect','socket.connect_ex','socket.getaddrinfo'}:raise RuntimeError('offline saved-output comparison')
 sys.addaudithook(offline)
 c03=local('timing_confirm_original_C03','tools/next02_c03_reception_join_v1.py');controls,candidates,pair_ids=candidate_sets(c03)
 check(plan['candidate_ids']==candidates and plan['paired_candidate_ids']==pair_ids,'registered contender/pair roster differs')
 PHASE='PUBLIC_SAVED_OUTPUT_CONTRACT'
 src,c03src,r0,proof=public_sources(args,c03);check(plan['public_source_proof']==proof,'registered C04 public provenance differs')
 guard=local('timing_confirm_C04_storage','nfl_lab/profile_freshness_a_storage_v1.py')
 store=guard.FreshnessStore(ROOT,ROOT/plan['allocation']['path'],plan['allocation']['sha256'],root_go=guard.GO)
 pref=plan['prior_result_ref'];check(pref==dict(id=PRIOR_ID,bytes=112129,sha256=PRIOR_SHA,namespace='DEF_REMAINDER'),'prior C03 immutable score ref differs')
 priorraw=store.read_many([pref])[pref['id']];prior=json.loads(gzip.decompress(priorraw))
 check(prior['candidate_ids']==controls and len(prior['summaries'])==1056,'prior completed C03 result binding differs')
 base=local('timing_confirm_original_source','tools/player_context_completion_reception_v1.py');oldjoin=local('timing_confirm_original_leaf_join','tools/profile_increment_a_c_leaf_join_v1.py');np,pd=base.runtime()
 PHASE='EXACT_ORIGINAL_A733_SOURCE_RESTORE'
 _,_,refs,board,forecasts,fixed,excluded,offers=oldjoin.source_inputs(pd)
 check(plan['source_sha256']=={k:v['sha256']for k,v in refs.items()},'original private source versions differ')
 check(sha(base.encode(sorted(b['opportunity']for b in board)))==plan['outer733_mask_sha256']and sha(base.encode(sorted(fixed)))==plan['fixed667_mask_sha256'],'original full/common masks differ')
 oldjoined,_,_=oldjoin.join_inventory(r0,board,offers,pd);check(sum(x['forecast']is not None for x in oldjoined.values())==678,'old qualified join scope differs')
 vectors=build_old_vectors(base,oldjoin,c03,board,forecasts,oldjoined,c03src)
 for alias,original in ALIASES.items():vectors[alias]=[dict(r,C04_alias_of=original)for r in vectors[original]]
 newlookup={(r['game_id'],r['player_id']):r for r in src['rows']if r['season']==2026 and r['week']<=7}
 for cid in NEW:
  arm,product=cid.split('::')[-2:];vv=[]
  for b in board:
   reason=oldjoined[b['opportunity']]['unavailable_reason'];f=newlookup.get((b['game'],b['player']))if reason is None else None
   if reason is None:check(f is not None and f['position']==b['position']and f['week']==b['week'],'C04 qualified identity/role differs')
   vv.append(make_row(base,b,float(f['forecasts'][arm][product.lower()])if f else None,reason=reason,flag_state='UNKNOWN_NOT_EXPORTED'if f else'UNAVAILABLE_FORECAST'))
  vectors[cid]=vv
 peer=checked(ROOT/'reports/abc-championship/player-context-acceptance-01/PEER_PROTOCOL_V2.json',base.PEER_PROTOCOL_SHA)
 for ref in json.loads(peer)['peer_overlap']['C_bound_code']:checked(args.c_code_cache/Path(ref['path']).name,ref.get('sha256',ref.get('SHA256')))
 sys.path.insert(0,str(args.c_code_cache));common=importlib.import_module('abc_championship_v2')
 for cid in IDS:
  for r in vectors[cid]:check(common.status(r)==r['status'],'original Decimal and pinned common grade disagree')
 PHASE='FROZEN_POINT_DIRECTION_AND_MATCHED_NUMERICAL_SCORES'
 summaries=copy.deepcopy(prior['summaries']);contrasts=[]
 for alias,original in ALIASES.items():
  source=[r for r in prior['summaries']if r['candidate_id']==original];check(len(source)==48,'old baseline summary scope differs')
  summaries += [dict(copy.deepcopy(r),candidate_id=alias,exact_output_alias_of=original,view_reuse='EXACT_OLD_SCORE_ALIAS_NOT_NEW_NFL_OBSERVATION')for r in source]
 for view,mask in [('FULL_A733',{b['opportunity']for b in board}),('FIXED_C667',fixed)]:
  vv={cid:[r for r in rows if r['opportunity_key']in mask]for cid,rows in vectors.items()}
  for cid in NEW:
   for panel in ['ALL']+sorted({r['source_panel']for r in vv[cid]}):
    for week in ['ALL']+list(range(1,8)):
     rows=[r for r in vv[cid]if(panel=='ALL'or r['source_panel']==panel)and(week=='ALL'or r['week']==week)]
     summaries.append(dict(candidate_id=cid,view=view,source_panel=panel,week_view=week,**common.summary(rows),numerical=c03.numerical(rows),actual_scored_weeks=sorted({r['week']for r in rows if r['status']in ['WIN','LOSS','PUSH']}),outer_appearance_states=dict(collections.Counter(r['appearance']for r in rows)),unavailable_reasons=dict(collections.Counter(r['unavailability_reason']for r in rows if r['unavailability_reason'])),fallback_outputs=None,profile_covered_outputs=None,any_imputed_outputs=None,unknown_fallback_flags=sum(r['point']is not None for r in rows),fallback_flag_state='UNKNOWN_NOT_EXPORTED;not_assumed_no_fallback',probability='N/A_POINT_ONLY_EXPORT;NO_INFERRED_LAW_OR_CONFIDENCE'))
  for left,right in pair_ids:
   for panel in ['ALL']+sorted({r['source_panel']for r in vv[left]}):
    ll=[r for r in vv[left]if panel=='ALL'or r['source_panel']==panel];rr=[r for r in vv[right]if panel=='ALL'or r['source_panel']==panel]
    contrasts.append(dict(view=view,source_panel=panel,left=left,right=right,**c03.paired(ll,rr,base,np),fallback_attribution='NOT_ESTABLISHED_NEW_C04_ROW_FLAGS_NOT_EXPORTED'))
 check(len(summaries)==1440 and len(contrasts)==588,'registered finite cell counts differ')
 check(enc(summaries[:1056])==enc(prior['summaries']),'old C03 summaries changed')
 coverage={cid:dict(eligible=len(vectors[cid]),available=sum(r['point']is not None for r in vectors[cid]),unavailable=sum(r['point']is None for r in vectors[cid]),decided=sum(r['status']in ['WIN','LOSS']for r in vectors[cid]),states=dict(collections.Counter(r['status']for r in vectors[cid])))for cid in IDS}
 view=dict(version=VERSION,protocol_sha256=args.protocol_sha256,source_sha256=plan['source_sha256'],public_source_proof=proof,prior_C03_score_sha256=PRIOR_SHA,candidate_ids=candidates,paired_candidate_ids=pair_ids,aliases=ALIASES,outer733_mask_sha256=plan['outer733_mask_sha256'],fixed667_mask_sha256=plan['fixed667_mask_sha256'],restore='Exact original A source bytes plus public point/metadata snapshots at C immutable refs regenerate all scored rows; no peer model loading.',new_fits=0,new_inference=0,new_original_selections=0)
 viewbody=lzma.compress(enc(view),preset=6);check(len(viewbody)<=caps['private_view_max_bytes'],'score view exceeds reservation')
 result=dict(version=VERSION,state='EXACT_C04_TIMING_POINTS_OWNER_LOCAL_SCORED',protocol_sha256=args.protocol_sha256,public_source_proof=proof,source_sha256=plan['source_sha256'],candidate_ids=candidates,paired_candidate_ids=pair_ids,aliases=ALIASES,original_outer=733,fixed667=667,outer733_mask_sha256=plan['outer733_mask_sha256'],fixed667_mask_sha256=plan['fixed667_mask_sha256'],coverage=coverage,summaries=summaries,paired=contrasts,prior_C03_score_sha256=PRIOR_SHA,old_summary_cells_reused_exactly=1056,old_baseline_alias_summary_cells=192,new_timing_summary_cells=192,new_paired_cells=588,actual_line_weeks=[1,2,3,4,5],diagnostic_offer_status_unqualified_weeks=[6,7],W8_in_this_board='NO_RETAINED_ROWS;not_extended_by_numerical_W8_forecasts',point_rule='unrounded_point>exact_line_OVER;<UNDER;equal_ABSTAIN',probability='NOT_PROVIDED_NOT_INFERRED;native_C_two_week_law_scores_separate',source_timing='EXPOSED_CURRENT_VINTAGE_TIMING_RECONSTRUCTION;QUOTE_TIME_UNVERIFIED;NOT_ORIGINAL_ISSUANCE',fallback_scope=proof['fallback'],new_fits=0,new_model_loading=0,new_inference=0,new_original_issued_selections=0,production_writes=0,C_admission='NOT_OBSERVED',consumer_acknowledgment='NOT_OBSERVED',uncertainty='Existing registered500 game/week paired bootstrap; only7exposedweekclusters/multipleviews; actualofferW1-5 distinctfromW6-7diagnostic',resources_asof='BEFORE_NATIVE_RESULT_PERSISTENCE',resources=dict(CPU_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-started,RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024))
 payload=gzip.compress(enc(result),mtime=0);check(len(payload)<=caps['private_fullscore_max_bytes']and len(payload)+len(viewbody)<=caps['additional_private_max_bytes'],'finite protected result reservation exceeded')
 PHASE='GUARDED_NATIVE_RETENTION'
 vref=store.put('TIMING_CONFIRM_C04_REC_VIEW_V1.json.xz',viewbody);sref=store.put('TIMING_CONFIRM_C04_REC_SCORES_V1.json.gz',payload)
 restored=store.read_many([vref,sref]);check(restored[vref['id']]==viewbody and restored[sref['id']]==payload,'complete score/view byte readback differs')
 with args.output.open('xb')as f:f.write(payload);f.flush();os.fsync(f.fileno())
 storage=store.checkpoint()
 receipt=dict(version=VERSION,state='PASS_C04_EXACT_POINTS_SCORE_AND_NATIVE_READBACK',score_sha256=sha(payload),score_compressed_bytes=len(payload),private_score=sref,private_view=vref,public_source_sha256=C_SHA,prior_result_sha256=PRIOR_SHA,old_summary_cells_reused_exactly=1056,alias_summary_cells_reused=192,new_timing_summary_cells=192,new_paired_cells=588,storage=storage,resources=dict(CPU_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-started,RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024),new_fits=0,new_model_loading=0,new_inference=0,new_original_selections=0,production_writes=0)
 with args.public_receipt.open('xb')as f:f.write(enc(receipt));f.flush();os.fsync(f.fileno())
 signal.alarm(0);print(json.dumps(dict(state=receipt['state'],private_score=sref,summary_cells=1440,paired_cells=588,new_fits=0,new_inference=0)))

def main():
 p=argparse.ArgumentParser()
 for name in ['protocol','c04-dir','c03-points','c-r0','c03-metadata','c-code-cache','output','public-receipt']:p.add_argument('--'+name,type=Path,required=True)
 p.add_argument('--protocol-sha256',required=True);a=p.parse_args()
 try:run(a)
 except BaseException as error:
  signal.alarm(0);failure=dict(version=VERSION,state='FAILED_C04_SAVED_POINT_JOIN_NO_AUTOMATIC_RETRY',phase=PHASE,error_type=type(error).__name__,error_sha256=sha(str(error).encode()),CPU_seconds=time.process_time(),RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,new_fits=0,new_inference=0)
  with a.output.with_name('C04_JOIN_FAILURE_'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json').open('xb')as f:f.write(enc(failure))
  print(json.dumps(failure));raise
if __name__=='__main__':main()
