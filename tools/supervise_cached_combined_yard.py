"""Fresh stdlib parent; study-local c57 derivative forwards all seven caps."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools import combined_yard_native_core_env_f2 as core
from tools.run_cached_combined_yard import gate

def main():
    p=argparse.ArgumentParser();p.add_argument('manifest');p.add_argument('sha256');p.add_argument('go');p.add_argument('receipt');a=p.parse_args()
    core.require_isolated_monitor();m=gate(a.manifest,a.sha256,a.go)
    if m['worker']['cwd']!=str(Path(__file__).resolve().parents[1]):raise ValueError('owned code root differs')
    worker=core.binding(m['worker']['script']);interpreter=core.binding(m['worker']['interpreter'],interpreter=True)
    return core.supervise([str(interpreter),'-B',str(worker),a.manifest,a.sha256,a.go],cwd=Path(m['worker']['cwd']),output=Path(m['output']),receipt=Path(a.receipt),limits=core.Limits(cpu=900,wall=1200,rss=2147483648,retained=67108864,soft_reserve=30,grace=2,poll=.05,address_space=8589934592),metadata=dict(manifest_sha256=a.sha256,base_fits=0,maximum_dependence_fits=2,HTTP=0,native_helper_version='combined-yard-native-env-f2-v1',native_helper_baseline_sha256='1ef8e8a4109ebc2c098e6f814d72e7aeb17da66cba31d0dfea809d6ac7d751a6'))

if __name__=='__main__':main()
