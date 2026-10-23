"""One source-matched prediction freeze followed by one scoring phase."""
import json,socket,sys
from pathlib import Path
from nfl_lab.source_matched_benchmark import run_benchmark, report_benchmark
ROOT=Path(__file__).resolve().parent
freeze=json.loads((ROOT/'SOURCE_MATCHED_BENCHMARK_FREEZE.json').read_text())
def forbidden_network(*args,**kwargs):
    raise RuntimeError('No network permitted in frozen cached benchmark')
socket.socket=forbidden_network
socket.create_connection=forbidden_network
result=run_benchmark(freeze['plan_path'],config_sha256=freeze['plan_sha256'])
print(json.dumps({'phase':'GLOBAL_FORECASTS_FROZEN','fatal':result['fatal'],'usage':result['usage'],'slots':len(result['slots'])}),flush=True)
report=report_benchmark(freeze['plan_path'],config_sha256=freeze['plan_sha256'])
print(json.dumps({'phase':'REPORT_COMPLETE','targets':list(report['targets']),'evidence':'EXPOSED_SOURCE_MATCHED_DEVELOPMENT; no independent confirmation or website-relative claim'}),flush=True)
