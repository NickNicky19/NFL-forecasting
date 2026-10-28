import sys,os,time,resource,signal,threading,hashlib,json,io,zipfile,csv
from pathlib import Path
START=time.monotonic();CPU=time.process_time();sys.dont_write_bytecode=True
resource.setrlimit(resource.RLIMIT_CPU,(20,21))
def stop(*args):raise RuntimeError("PAPER_READONLY_QA_CAP")
signal.signal(signal.SIGALRM,stop);signal.signal(signal.SIGUSR1,stop);signal.signal(signal.SIGXCPU,stop);signal.alarm(28)
done=threading.Event()
def watch():
 while not done.wait(.025):
  if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024>402653184:os.kill(os.getpid(),signal.SIGUSR1);return
threading.Thread(target=watch,daemon=True).start()
try:
 import numpy as np
 import pandas as pd
 import pyarrow.parquet as pq
 ROOT=Path("/workspace/nfl-market-archive-source-no2025-v1/reports/historical-market-no2025-v1")
 READ={};checks=0;intervals=0;csvrows=0
 def need(ok,label):
  global checks
  if not bool(ok):raise AssertionError(label)
  checks+=1
 def read(path,ref=None):
  p=Path(path);b=p.read_bytes();h=hashlib.sha256(b).hexdigest()
  if ref:need(len(b)==ref["bytes"] and h==ref["sha256"],"file binding")
  READ[str(p)]=(len(b),h);return b
 bindings=json.loads(read(ROOT/"paper-completion-technical-v2-member-bindings.json"))
 terminal=json.loads(read(ROOT/"paper-completion-technical-v2-consumed-terminal.json"))
 need(terminal["state"]=="COMPLETE_FROZEN_PAPER_ACCOUNTING_AND_READABLE_SCORECARD" and terminal["final_resource_gate"]["violations"]==[],"terminal gate")
 need(terminal["V1_failed_attempt_preserved"] and terminal["managed_write_attempts"]==1,"failure consumption")
 z=zipfile.ZipFile(io.BytesIO(read(bindings["container"]["path"],bindings["container"])))
 need(set(z.namelist())=={"SUMMARY.json","PREDICTIONS_ACTUALS.csv","GUIDE.html"},"artifact member set")
 for r in bindings["members"]:
  with z.open(r["member"]) as f:h=hashlib.file_digest(f,"sha256").hexdigest()
  need(z.getinfo(r["member"]).file_size==r["bytes"] and h==r["sha256"],"inner member")
 main=json.loads(read(Path("/workspace/nfl-market-comparison-no2025-v1/reports/historical-market-comparison-no2025-technical-v3/COMPLETE_NATIVE.json")))
 r=main["bindings"]["SCORES_COMPLETE.zip"]
 archive=zipfile.ZipFile(io.BytesIO(read(r["path"],r)))
 def member(name):
  ref=main["scores"][name];b=archive.read(name)
  need(len(b)==ref["bytes"] and hashlib.sha256(b).hexdigest()==ref["sha256"],"frozen score member");return b
 def frame(name,cols):return pq.ParquetFile(io.BytesIO(member(name))).read(columns=cols,use_threads=False).to_pandas(strings_to_categorical=True)
 UNIT=["season","week","game_id","player_id","target"];OFFER=UNIT+["book_id","line","source_collection_naive"]
 POL=["projectiongap","footballEV","independentmarketEV","hybridEV","probabilityfirst"]
 PROB=[a+"_probability" for a in ["F","FC","FS","M","H"]]
 NUM=["F_point","FC_point","M_point","H_point"]+PROB+["actual"]
 matched=frame("MATCHED_SCORES.parquet",OFFER+["kickoff_utc","outcome_state"]+NUM)
 graded=frame("PAPER_ASSUMED_SETTLEMENT.parquet",OFFER+["policy","side","settlement","net_units"])
 def ix(f,cols=OFFER):return pd.MultiIndex.from_frame(f[cols])
 need(len(matched)==62576 and ix(matched).is_unique,"complete immutable matched membership")
 need(set(matched.season)=={2024,2026} and not graded.season.eq(2025).any(),"no2025")
 need(not graded.duplicated(["policy"]+UNIT).any(),"unique immutable paper selections")
 # Exact artifact/member hashes authenticate serialized display order.
 # Compare logical CSV records by immutable unique offer keys without imposing
 # a new categorical-sorting convention on the retained representation.
 # CSV is streamed; no names or raw rows are printed or materialized as a whole.
 with z.open("PREDICTIONS_ACTUALS.csv") as f:header=next(csv.reader(io.TextIOWrapper(f,encoding="utf-8")))
 need(len(header)==len(set(header)),"CSV unique header")
 ERR=[a+s for a in ["F","FC","M","H"] for s in ["_error","_absolute_error"]]
 FLAGS=[p+s for p in POL for s in ["_selected","_selected_side","_settlement","_net_units"]]
 cols=OFFER+["actual","outcome_state"]+[a+"_point" for a in ["F","FC","M","H"]]+PROB+ERR+FLAGS
 need(set(cols)<=set(header) and "display_name" in header and "F_model_sha256" in header,"CSV contract header")
 seen=np.zeros(len(matched),bool);mi=ix(matched);lookups={p:graded.loc[graded.policy.eq(p)].reset_index(drop=True) for p in POL}
 with z.open("PREDICTIONS_ACTUALS.csv") as f:
  for chunk in pd.read_csv(f,usecols=cols,chunksize=8192,float_precision="round_trip",dtype={"game_id":str,"player_id":str,"target":str,"source_collection_naive":str}):
   pos=mi.get_indexer(ix(chunk));need((pos>=0).all() and not seen[pos].any(),"CSV frozen membership");seen[pos]=True
   need(ix(chunk).is_unique,"unique CSV chunk offer identities")
   base=matched.iloc[pos].reset_index(drop=True)
   for c in NUM:need(np.array_equal(chunk[c].to_numpy(float),base[c].to_numpy(float),equal_nan=True),"CSV frozen numeric:"+c)
   need(chunk.outcome_state.astype(str).reset_index(drop=True).equals(base.outcome_state.astype(str).reset_index(drop=True)),"CSV outcome-state values")
   for arm in ["F","FC","M","H"]:
    e=base[arm+"_point"].to_numpy(float)-base.actual.to_numpy(float);e[~base.outcome_state.eq("supported_played").to_numpy()]=np.nan
    for c,v in [(arm+"_error",e),(arm+"_absolute_error",np.abs(e))]:need(np.array_equal(chunk[c].to_numpy(float),v,equal_nan=True),"CSV errors")
   for p,g in lookups.items():
    at=ix(g).get_indexer(ix(chunk));selected=at>=0
    need(np.array_equal(chunk[p+"_selected"].to_numpy(bool),selected),"CSV frozen selected flags")
    for suffix,field in [("_selected_side","side"),("_settlement","settlement")]:
     need(chunk.loc[selected,p+suffix].astype(str).reset_index(drop=True).equals(g.iloc[at[selected]][field].astype(str).reset_index(drop=True)),"CSV frozen pick text")
     need(chunk.loc[~selected,p+suffix].isna().all(),"CSV unselected blank")
    expected=np.full(len(chunk),np.nan);expected[selected]=g.iloc[at[selected]].net_units.to_numpy(float)
    need(np.array_equal(chunk[p+"_net_units"].to_numpy(float),expected,equal_nan=True),"CSV exact pick net")
   csvrows+=len(chunk)
 need(seen.all() and csvrows==62576,"CSV complete matched rows")
 for path,(n,h) in READ.items():
  b=Path(path).read_bytes();need(len(b)==n and hashlib.sha256(b).hexdigest()==h,"current postread unchanged")
 need(time.process_time()-CPU<20 and time.monotonic()-START<30 and resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024<=402653184,"final CSV-only resources")
 done.set();signal.alarm(0)
 print(json.dumps({"state":"CSV_VALUE_MEMBERSHIP_QA_TECHNICAL_V4_PASS","checks":checks,"CSV_rows":csvrows,"CSV_columns":len(header),"frozen_numeric_cells":csvrows*len(NUM),"derived_error_cells":csvrows*len(ERR),"frozen_policy_flag_side_settlement_net_cells":csvrows*len(FLAGS),"entire_opportunity_membership_numeric_values_errors_and_frozen_selection_verified":True,"serialized_order_authenticated_by_original_CSV_member_hash":True,"summary_bootstrap_reruns":0,"fits_models_new_predictions_selection_HTTP_filewrites":0,"CPU_seconds":time.process_time()-CPU,"wall_seconds":time.monotonic()-START,"RSS_peak_bytes":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,"current_input_files_rehashed":len(READ),"V1_V2_V3_remain_FAILED":True,"composite_scope":"V2 reached all aggregate/bootstrap checks before its index-sensitive CSV assertion; this V4 separately completes CSV value/membership checks. Earlier checker failures and unrecorded final resource totals remain unchanged."},sort_keys=True))
except BaseException as error:
 done.set();signal.alarm(0)
 print(json.dumps({"state":"CSV_VALUE_MEMBERSHIP_QA_TECHNICAL_V4_FAILED","error_type":type(error).__name__,"error":str(error),"CPU_seconds":time.process_time()-CPU,"wall_seconds":time.monotonic()-START,"RSS_peak_bytes":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024},sort_keys=True))
 raise
