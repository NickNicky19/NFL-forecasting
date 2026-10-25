"""One first scoring pass for immutable forecasts after a pre-score timeout."""
import json,sys
from pathlib import Path
def deny_network_events(event,args):
    if event.startswith('socket.'):
        raise RuntimeError('Recovery is cache-only; no socket events permitted')
sys.addaudithook(deny_network_events)
from nfl_lab.source_matched_report_recovery import run_recovery
ROOT=Path(__file__).resolve().parent
freeze=json.loads((ROOT/'RECOVERY_EXECUTION_FREEZE.json').read_text())
run_recovery(freeze['plan_path'],config_sha256=freeze['plan_sha256'])
print('FROZEN_REPORT_RECOVERY_RETURNED',flush=True)
