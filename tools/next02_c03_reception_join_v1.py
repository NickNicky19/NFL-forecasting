"""A owner-local C03 saved-point comparison; no model loading or inference.

The accepted scorer and original A733/FIXED_C667 populations are reused. Public
forecast preparation reads no A labels; scoring requires the exact root GO.
"""
from __future__ import annotations
import argparse,collections,datetime,gzip,hashlib,importlib,importlib.util,io,json,lzma,math,os
from pathlib import Path
import resource,signal,sys,time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
VERSION="A::PROFILE-INCREMENT-CLOSURE-AND-NEXT-02::C03-REC-SAVED-POINT-v1"
C_REF="471066ee8fd0745def26b8c5c1ae6bbcaf8f6d3e"
C_PATH="reports/profile-increment-v2/C03_TYPED_POINTS_2025_2026_W1_W8.json.xz"
C_SHA="0a374a147bdad11bf3226265894b00b39928903f62740e0a4d2344f91eeb8497"
C_BYTES=246128
R0_SHA="05a6b8bbad28ce7978c59f1ae026d6fb61fed964db724f41be253e4606119ccc"
OLD_RESULT="reports/abc-championship/profile-increment-to-release-01/C_LEAF_SAVED_CONTROL_RESULTS_V1.json"
OLD_RESULT_SHA="55b87ecbd68cb58a8497d80cfa82e4245a56635319feb0f34bad65cfcefea433"
R0_PREFIX="C::C-ALL12-LAW-THRESHOLD-v2.1::rec::H-MULTI::P2_LEAF::E0_OP::"
R0_IDS=[R0_PREFIX+v for v in ["MEAN_POINT_DIRECTION","MEDIAN_POINT_DIRECTION"]]
NEW=["C-RECEIVING-PROFILE-INCREMENT-v2::"+a+"::"+p for a in ["R1","R2","R3"]for p in ["MEAN","MEDIAN"]]
OLD_IDS=["A::"+m+"::"+p for m,p in [
 ("COUNT_A_LEGACY_POINT","legacy_empirical_point"),("COUNT_A_MEAN","mean_objective_point"),
 ("HGB_MAE_DIRECT","mae_objective_point"),("CATBOOST_MEDIUM","mean_objective_point"),
 ("LEAF_CDF","mean"),("LEAF_CDF","median"),("ORDERED_CDF","mean"),("ORDERED_CDF","median")]]+[
 "C::PLAYER-CONTEXT-MATCHUP-01::v1.1::"+m+"::"+p for m in ["P1","P2"]for p in ["mean","median"]]+["ALWAYS_OVER","ALWAYS_UNDER"]+R0_IDS
CANDIDATES=OLD_IDS+NEW
PAIRS=[[a,b]for a in NEW for b in OLD_IDS]+[["C-RECEIVING-PROFILE-INCREMENT-v2::"+a+"::"+p,
 "C-RECEIVING-PROFILE-INCREMENT-v2::"+b+"::"+p]for a,b in [("R2","R1"),("R3","R2")]for p in ["MEAN","MEDIAN"]]
assert len(CANDIDATES)==22 and len(PAIRS)==100
PHASE="NOT_STARTED"

def enc(x):return(json.dumps(x,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def check(x,message):
 if not x:raise ValueError(message)
def finite(x):return type(x)in [float,int]and math.isfinite(x)
def checked_file(path,expected,size=None):
 b=Path(path).read_bytes();check(sha(b)==expected and(size is None or len(b)==size),"immutable source bytes differ");return b
def aware(v,pd):
 t=pd.Timestamp(v);check(not pd.isna(t)and t.tzinfo is not None,"timezone-aware metadata required");return t.tz_convert("UTC")
def local(name,path):
 s=importlib.util.spec_from_file_location(name,ROOT/path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def public_sources(points,r0,metadata):
 """Forecast/schema identities only. No A private file or outcome is read."""
 body=checked_file(points,C_SHA,C_BYTES);src=json.loads(lzma.decompress(body))
 rb=checked_file(r0,R0_SHA,45935);base=json.loads(gzip.decompress(rb))
 meta_raw=Path(metadata).read_bytes();meta=json.loads(meta_raw)
 runraw=meta["reports/profile-increment-v2/experiment/RUN-2026.json"].encode();run=json.loads(runraw)
 inputraw=meta["reports/profile-increment-v2/experiment/INPUT_BINDINGS.json"].encode();inputs=json.loads(inputraw)
 initial=meta["reports/profile-increment-v2/experiment/INITIAL_2026_REGISTRATION.json"].encode()
 code=meta["src/receiving_increment_c03.py"].encode()
 check(src["id"]=="C03-TYPED-POINT-HANDOFF-v2"and len(src["rows"])==14433 and len(src["models"])==48,"C03 format/scope changed")
 check(src["outcomes_or_selections_in_export"]is False and src["new_fits"]==src["new_inference"]==0,"C03 cached-point contract changed")
 check(src["products"]==["UNROUNDED_EXPECTED_MEAN","LOWER_MEDIAN"],"C03 products changed")
 check(sha(code)==run["code_SHA256"]=="5c42b388bad93cbb46f4f1d93e37c78c0cb8b3af416aa00b23632bcd7b3a8198","C03 code provenance differs")
 check(sha(initial)==run["registration_SHA256"]=="fe5eecd325fc4074acfd5d9e4540cdc994495addf058814d7267467f3ee8d274","C03 executing registration differs")
 check(inputs["old_leaf"]["SHA256"]==base["source_archive_SHA256"]=="5262b7bb374c066adf14bfd10e6992a2568eff84943ea11b96218084be4d1f51","R0 baseline source differs")
 rows=src["rows"];check(not any(k in r for r in rows for k in ["actual","outcome","line","selected_side","grade","status"]),"unexpected evaluation information in forecast-only export")
 seen=set()
 for r in rows:
  check(r["category"]=="rec"and r["role"]in ["RB","WR","TE"]and r["season"]in [2025,2026]and r["week"]in range(1,9),"C03 target/population mismatch")
  check(r["procedure"]in [x.rsplit("::",1)[0]for x in NEW]and r["model_key"]==f"{r['season']}-W{r['week']:02}-"+r["procedure"].rsplit("::",1)[1],"C03 exact procedure/origin mismatch")
  check(r["model_key"]in src["models"]and len(src["models"][r["model_key"]]["SHA256"])==64,"missing model binding")
  check(all(finite(r[k])and r[k]>=0 for k in ["mean","median"])and r["median"]==math.floor(r["median"]),"count point type invalid")
  check(all(type(r[k])is bool for k in ["hard_fallback","profile_covered","any_imputed"]),"fallback/support flag unknown")
  k=r["model_key"],r["game_id"],r["player_id"];check(k not in seen,"duplicated C03 forecast identity");seen.add(k)
 old={(r["game_id"],r["player_id"]):r for r in base["rows"]}
 rr=[r for r in rows if r["season"]==2026 and r["week"]in range(1,8)]
 for arm in ["R1","R2","R3"]:
  part=[r for r in rr if r["procedure"].endswith("::"+arm)]
  check(len(part)==2152 and {(r["game_id"],r["player_id"])for r in part}==set(old),"new C03/R0 query universe differs")
 for r in rr:
  o=old[r["game_id"],r["player_id"]]
  check((r["role"],r["team"],r["opponent"],r["week"])==(o["position"],o["team"],o["opponent"],o["week"]),"new C03/R0 canonical role/team mismatch")
 slots={int(z["origin"].rsplit("W",1)[1]):z for z in run["origins"]}
 oldslots={int(z["slot"].rsplit("W",1)[1]):z for z in base["slots"]}
 for w in range(1,8):
  check(slots[w]["training_rows"]==oldslots[w]["training_rows"]and slots[w]["fit_cutoff_UTC"]==oldslots[w]["origin_UTC"]and slots[w]["latest_training_available_UTC"]==datetime.datetime.fromtimestamp(oldslots[w]["latest_training_available"],datetime.timezone.utc).isoformat(),"baseline/augmented origin count/cutoff/latest-availability differs")
 proof=dict(C_source=dict(repository="NickNicky19/NFL-forecasting-NGS-C",commit=C_REF,path=C_PATH,bytes=len(body),sha256=sha(body)),
  R0_sha256=sha(rb),metadata_commit="a9cb8ef61a294b73f558b3c5daad483094af80b2",metadata_files={path:dict(bytes=len(text.encode()),sha256=sha(text.encode()))for path,text in meta.items()},public_metadata_sha256=sha(meta_raw),C_run_sha256=sha(runraw),C_inputs_sha256=sha(inputraw),C_code_sha256=sha(code),C_executing_registration_sha256=sha(initial),
  original_queries_2026_W1_W7=2152,augmented_rows_2026_W1_W7=len(rr),original_and_augmented_identity_role_team_match=True,baseline_and_augmented_weekly_origin_count_match=True,
  C_models=src["models"],origins_2026=run["origins"],evidence=src["history"],rights=src["rights"],no_outcomes_or_offers=True)
 return body,src,base,slots,proof

def numerical(rows):
 e=[r["point"]-r["actual"]for r in rows if finite(r["point"])and r["appearance"]=="PLAYED"and r["actual"]is not None]
 mse=math.fsum(z*z for z in e)/len(e)if e else None
 ae=sorted(map(abs,e));tail=ae[max(0,math.ceil(.9*len(ae))-1)]if ae else None
 return dict(scored=len(e),MAE=math.fsum(ae)/len(e)if e else None,MSE=mse,RMSE=math.sqrt(mse)if mse is not None else None,bias=math.fsum(e)/len(e)if e else None,absolute_error_p90_nearest_rank=tail,max_absolute_error=max(ae)if ae else None)

def paired(left,right,base,np):
 z=base.paired(left,right,np,500,20261110);rightmap={r["opportunity_key"]:r for r in right}
 weeks=collections.defaultdict(lambda:[0.,0.])
 for a in left:
  b=rightmap.get(a["opportunity_key"])
  if b is not None and a["status"]in ["WIN","LOSS"]and b["status"]in ["WIN","LOSS"]:
   weeks[a["week"]][0]+=int(a["status"]=="WIN")-int(b["status"]=="WIN");weeks[a["week"]][1]+=1
 z["paired_accuracy_week_interval95"]=base.bootstrap(weeks,np,500,20261110)
 common=[(a,rightmap[a["opportunity_key"]])for a in left if a["opportunity_key"]in rightmap and finite(a["point"])and finite(rightmap[a["opportunity_key"]]["point"])and a["appearance"]=="PLAYED"and a["actual"]is not None]
 groups=collections.defaultdict(lambda:[0.,0.]);changes=[]
 for a,b in common:
  check(a["actual"]==b["actual"]and a["appearance"]==b["appearance"],"numerical comparison outcome mismatch")
  delta=abs(a["point"]-a["actual"])-abs(b["point"]-b["actual"]);changes.append(delta);groups[a["game_id"]][0]+=delta;groups[a["game_id"]][1]+=1
 z["numerical_paired"]=dict(common_cases=len(common),MAE_change=math.fsum(changes)/len(changes)if changes else None,game_interval95=base.bootstrap(groups,np,500,20261110),common_mask_sha256=sha(enc(sorted(a["opportunity_key"]for a,b in common))))
 return z

def run(args):
 global PHASE
 check(not args.output.exists()and not args.public_receipt.exists(),"immutable output/receipt already exists")
 started,cpu=time.monotonic(),time.process_time();raw=args.protocol.read_bytes();check(sha(raw)==args.protocol_sha256,"root protocol hash differs");plan=json.loads(raw)
 check(plan["version"]==VERSION and plan["state"]=="ROOT_REGISTERED_SCORING_GO"and plan["registered_by"]=="/root","root exact scoring GO required")
 check(plan["candidate_ids"]==CANDIDATES and plan["paired_candidate_ids"]==PAIRS,"finite candidates/pairs changed")
 check(plan["bootstrap_replicates"]==500 and plan["bootstrap_seed"]==20261110,"registered precision policy differs")
 for p,h in plan["code_sha256"].items():check(sha((ROOT/p).read_bytes())==h,"bound code changed")
 own=str(Path(__file__).resolve().relative_to(ROOT));check(plan["code_sha256"].get(own)==sha(Path(__file__).read_bytes()),"worker hash not bound")
 caps=plan["resources"];check(caps["CPU_seconds"]<=400 and caps["wall_seconds"]<=900 and caps["RSS_bytes"]<=3*1024**3,"finite budget exceeded")
 resource.setrlimit(resource.RLIMIT_CPU,(caps["CPU_seconds"],caps["CPU_seconds"]+1));resource.setrlimit(resource.RLIMIT_AS,(caps["RSS_bytes"],)*2);signal.alarm(caps["wall_seconds"])
 for k in ["OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","NUMEXPR_NUM_THREADS"]:os.environ[k]="1"
 def offline(event,_):
  if event in {"socket.connect","socket.connect_ex","socket.getaddrinfo"}:raise RuntimeError("saved-point scoring is offline")
 sys.addaudithook(offline)
 base=local("next02_reception_original","tools/player_context_completion_reception_v1.py")
 oldjoin=local("next02_reception_leaf","tools/profile_increment_a_c_leaf_join_v1.py")
 np,pd=base.runtime();PHASE="PUBLIC_FORECAST_CONTRACT"
 source_bytes,src,r0,slots,proof=public_sources(args.c_points,args.c_r0,args.c_metadata)
 check(plan["public_source_proof"]==proof,"registered public source provenance differs")
 for z in slots.values():check(aware(z["latest_training_available_UTC"],pd)<aware(z["fit_cutoff_UTC"],pd),"C training availability not earlier than model origin")
 PHASE="EXISTING_A733_RESTORE"
 _,_,refs,board,forecasts,fixed,excluded,offers=oldjoin.source_inputs(pd)
 check(plan["source_sha256"]=={k:v["sha256"]for k,v in refs.items()},"retained private source versions changed")
 check(sha(base.encode(sorted(b["opportunity"]for b in board)))==plan["outer733_mask_sha256"]and sha(base.encode(sorted(fixed)))==plan["fixed667_mask_sha256"],"original board/mask changed")
 priorraw=checked_file(ROOT/OLD_RESULT,OLD_RESULT_SHA);prior=json.loads(priorraw)
 check(prior["candidate_ids"]==OLD_IDS and len(prior["summaries"])==768,"prior completed result binding differs")
 oldjoined,oldreasons,oldweekly=oldjoin.join_inventory(r0,board,offers,pd)
 check(sum(v["forecast"]is not None for v in oldjoined.values())==678,"old R0 join coverage changed")
 lookup={(r["procedure"].rsplit("::",1)[1],r["game_id"],r["player_id"]):r for r in src["rows"]if r["season"]==2026 and r["week"]in range(1,8)}
 vectors=oldjoin.old_vectors(base,board,forecasts)
 for cid,key in zip(R0_IDS,["mean","median"]):
  vv=[]
  for b in board:
   item=oldjoined[b["opportunity"]];f=item["forecast"];point=float(f[key])if f is not None else None
   rr=dict(season=2026,week=b["week"],game_id=b["game"],player_id=b["player"],category="rec",line=float(b["original_line_exact_text"]),actual=b["actual"],appearance=b["appearance"],opportunity_key=b["opportunity"],source_panel=b["source_panel"],selected_side=base.side(point,b["original_line_exact_text"]),point=point,fallback=f["fallback"]if f else None,unavailability_reason=item["unavailable_reason"],comparator="STRICT_OVER_UNDER");rr["status"]=base.grade(rr);vv.append(rr)
  vectors[cid]=vv
 peerraw=checked_file(ROOT/'reports/abc-championship/player-context-acceptance-01/PEER_PROTOCOL_V2.json',base.PEER_PROTOCOL_SHA)
 for ref in json.loads(peerraw)["peer_overlap"]["C_bound_code"]:check(sha((args.c_code_cache/Path(ref["path"]).name).read_bytes())==ref.get("sha256",ref.get("SHA256")),"pinned common scorer differs")
 sys.path.insert(0,str(args.c_code_cache));common=importlib.import_module("abc_championship_v2")
 coverage={}
 for cid in NEW:
  arm,product=cid.split("::")[-2:];vv=[];states=collections.Counter()
  for b in board:
   olditem=oldjoined[b["opportunity"]];f=lookup.get((arm,b["game"],b["player"]));reason=olditem["unavailable_reason"]
   if reason is None:
    check(f is not None,"C03 missed R0-supported identity")
    check(f["role"]==b["position"]and f["week"]==b["week"],"C03 joined role/week differs")
   else:f=None
   point=float(f[product.lower()])if f else None
   rr=dict(season=2026,week=b["week"],game_id=b["game"],player_id=b["player"],category="rec",line=float(b["original_line_exact_text"]),actual=b["actual"],appearance=b["appearance"],opportunity_key=b["opportunity"],source_panel=b["source_panel"],selected_side=base.side(point,b["original_line_exact_text"]),point=point,fallback=f["hard_fallback"]if f else None,profile_covered=f["profile_covered"]if f else None,any_imputed=f["any_imputed"]if f else None,unavailability_reason=reason,comparator="STRICT_OVER_UNDER")
   rr["status"]=base.grade(rr);check(common.status(rr)==rr["status"],"Decimal and canonical grade differ");vv.append(rr);states[reason or "SUPPORTED_CACHED_POINT"]+=1
  vectors[cid]=vv;coverage[cid]=dict(states)
 PHASE="NEW_SAVED_POINT_SCORES"
 summaries=list(prior["summaries"]);contrasts=[]
 for view,mask in [("FULL_A733",{b["opportunity"]for b in board}),("FIXED_C667",fixed)]:
  vv={c:[r for r in rows if r["opportunity_key"]in mask]for c,rows in vectors.items()}
  for cid in NEW:
   for panel in ["ALL"]+sorted({r["source_panel"]for r in vv[cid]}):
    for week in ["ALL"]+list(range(1,8)):
     rr=[r for r in vv[cid]if(panel=="ALL"or r["source_panel"]==panel)and(week=="ALL"or r["week"]==week)]
     summaries.append(dict(candidate_id=cid,view=view,source_panel=panel,week_view=week,**common.summary(rr),numerical=numerical(rr),actual_scored_weeks=sorted({r["week"]for r in rr if r["status"]in ["WIN","LOSS","PUSH"]}),outer_appearance_states=dict(collections.Counter(r["appearance"]for r in rr)),unavailable_reasons=dict(collections.Counter(r["unavailability_reason"]for r in rr if r["unavailability_reason"])),fallback_outputs=sum(r["fallback"]not in [None,False,""]for r in rr),profile_covered_outputs=sum(r["profile_covered"]is True for r in rr),any_imputed_outputs=sum(r["any_imputed"]is True for r in rr),probability="N/A_POINT_ONLY_EXPORT;NO_INFERRED_LAW_OR_CONFIDENCE"))
  for left,right in PAIRS:
   for panel in ["ALL"]+sorted({r["source_panel"]for r in vv[left]}):
    ll=[r for r in vv[left]if panel=="ALL"or r["source_panel"]==panel];rr=[r for r in vv[right]if panel=="ALL"or r["source_panel"]==panel]
    contrasts.append(dict(view=view,source_panel=panel,left=left,right=right,**paired(ll,rr,base,np)))
 check(len(summaries)==1056 and len(contrasts)==600,"registered cell counts differ")
 check(enc(summaries[:768])==enc(prior["summaries"]),"prior completed summary bytes changed")
 PHASE="GUARDED_PRIVATE_RETENTION"
 guard=local("next02_saved_join_storage","nfl_lab/profile_increment_a_def_remainder_storage_v1.py")
 store=guard.RemainderStore(ROOT,ROOT/plan["allocation"]["path"],plan["allocation"]["sha256"],root_go=guard.GO)
 source_ref=store.put("NEXT02_C03_ORIGINAL_TYPED_POINTS.json.xz",source_bytes)
 
 view=dict(version=VERSION,protocol_sha256=args.protocol_sha256,source_refs=refs,C_source=source_ref,public_source_proof=proof,R0_source_sha256=R0_SHA,prior_result_sha256=OLD_RESULT_SHA,candidate_ids=CANDIDATES,paired_candidate_ids=PAIRS,fixed667_mask_sha256=plan["fixed667_mask_sha256"],outer733_mask_sha256=plan["outer733_mask_sha256"],restore="Exact original forecasts/offers/labels/C733 relational bytes plus protected original C03 bytes, immutable metadata/R0 public bytes and this code regenerate all rows; no model loading",no_original_issuance=True,no_probability_qualification=True)
 vp=lzma.compress(enc(view),preset=6);check(len(vp)<=plan["resources"]["private_view_max_bytes"],"private view exceeds finite reservation")
 view_ref=store.put("NEXT02_C03_REC_SCORE_VIEW_V1.json.xz",vp)
 result=dict(version=VERSION,state="SAVED_NEW_C03_RECEPTION_POINTS_SCORED",protocol_sha256=args.protocol_sha256,source_sha256={k:v["sha256"]for k,v in refs.items()},public_source_proof=proof,candidate_ids=CANDIDATES,paired_candidate_ids=PAIRS,original_outer=733,fixed667=667,outer733_mask_sha256=plan["outer733_mask_sha256"],fixed667_mask_sha256=plan["fixed667_mask_sha256"],source_coverage=coverage,summaries=summaries,paired=contrasts,old_summary_cells_reused_exactly=768,new_summary_cells=288,new_paired_cells=600,prior_result_sha256=OLD_RESULT_SHA,private_source=source_ref,private_scorecard_view=view_ref,evidence="EXPOSED_CURRENT_VINTAGE_SEVEN_DAY_FOOTBALL_RECONSTRUCTION;ACTUAL_LINE_QUOTE_TIMING_UNVERIFIED;NOT_ORIGINAL_ISSUED_PICKS",probability_scope="N/A_POINT_ONLY;NO_LAW_OR_PROBABILITY_FROM_POINT",original_C_two_week_probability_panel_separate=True,grade_versions="Exact prior A qualified labels/source retained; no revisions orzero filling",uncertainty="Nominal500draw game intervals for paired changes; inherited common summaries retain registered2000week policy;7exposed weekclusters/multipleviews;no prospectiveclaim",C_admission="NOT_OBSERVED",consumer_acknowledgment="NOT_OBSERVED",new_fits=0,new_model_loading=0,new_inference=0,production_writes=0,storage_asof="FINAL_NATIVE_CHECKPOINT_IS_IN_SEPARATE_READBACK_RECEIPT",resources_asof="BEFORE_COMPLETE_SCORE_PERSISTENCE",resources=dict(CPU_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-started,RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024))
 payload=gzip.compress(enc(result),mtime=0);check(len(payload)+len(source_bytes)+len(vp)<=caps["additional_private_max_bytes"],"complete source/view/score exceeds registered total")
 score_ref=store.put("NEXT02_C03_REC_COMPLETE_SCORES_V1.json.gz",payload)
 readback=store.read_many([source_ref,view_ref,score_ref])
 check(readback[source_ref["id"]]==source_bytes and readback[view_ref["id"]]==vp and readback[score_ref["id"]]==payload,"complete source/view/score native batch readback differs")
 with args.output.open("xb")as f:f.write(payload if args.output.suffix==".gz"else enc(result));f.flush();os.fsync(f.fileno())
 receipt=dict(version=VERSION,state="PASS_NEW_C03_SCORE_SOURCE_AND_VIEW_NATIVE_READBACK",score_sha256=sha(payload),score_compressed_bytes=len(payload),private_score=score_ref,private_source=source_ref,private_view=view_ref,storage=store.checkpoint(),resources=dict(CPU_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-started,RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024),summary_cells=len(summaries),new_summary_cells=288,old_summary_cells_reused_exactly=768,new_paired_cells=len(contrasts),new_fits=0,new_inference=0,production_writes=0)
 with args.public_receipt.open("xb")as f:f.write(enc(receipt));f.flush();os.fsync(f.fileno())
 signal.alarm(0);print(json.dumps(dict(state=receipt["state"],summary_cells=len(summaries),new_summary_cells=288,paired_cells=len(contrasts),private_score=score_ref,private_source=source_ref,new_fits=0,new_inference=0)))

def main():
 p=argparse.ArgumentParser();p.add_argument("--protocol",type=Path,required=True);p.add_argument("--protocol-sha256",required=True);p.add_argument("--c-points",type=Path,required=True);p.add_argument("--c-r0",type=Path,required=True);p.add_argument("--c-metadata",type=Path,required=True);p.add_argument("--output",type=Path,required=True);p.add_argument("--public-receipt",type=Path,required=True);p.add_argument("--c-code-cache",type=Path,default=Path("/tmp/acceptance-c-review/src"));a=p.parse_args()
 try:run(a)
 except BaseException as e:
  signal.alarm(0);failure=dict(version=VERSION,state="FAILED_SAVED_JOIN_NO_AUTOMATIC_RETRY",phase=PHASE,error_type=type(e).__name__,error_sha256=sha(str(e).encode()),new_fits=0,new_inference=0)
  path=a.output.with_name("NEXT02_C03_JOIN_FAILURE_"+datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")+".json")
  with path.open("xb")as f:f.write(enc(failure))
  print(json.dumps(failure));raise

if __name__=="__main__":main()
