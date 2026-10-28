"""One bounded no-write capacity admission for the new finite wave."""
import hashlib
import importlib.util
import json
from pathlib import Path
import resource
import signal
import time

ROOT = Path('/workspace/nfl-methods-integration')


def load(name, path, expected):
    path = Path(path)
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError('allocation implementation changed')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    resource.setrlimit(resource.RLIMIT_CPU, (60, 61))
    signal.signal(signal.SIGALRM, lambda *args: (_ for _ in ()).throw(TimeoutError('90s allocation check')))
    signal.alarm(90)
    start, cpu = time.monotonic(), time.process_time()
    market = load('unchanged_market_allocation', ROOT/'nfl_lab/historical_market_storage_v1.py',
                  '5650f1934b7471c9f414b8bc77a8e096e700851558deebd8ef119a49f2575c09')
    wrapper = load('next_metadata_allocation', ROOT/'nfl_lab/next_checkpoint_storage.py',
                   '0e56fce31ebc9357ab94d4a31925a29ab3df7bf05ed0d10e81e3879c7109f240')
    p = ROOT/'config/next-checkpoint-metadata-v5.json'
    body = p.read_bytes()
    if hashlib.sha256(body).hexdigest() != '6d672f36fee6acf5745135ff9dfcfbbd6fe1d16edf49e24e95eec0c0d761791f':
        raise ValueError('new metadata allocation changed')
    next_policy = json.loads(body)
    policy = json.loads((ROOT/'config/historical-market-forward-v1.json').read_bytes())
    prior = json.loads(Path('/workspace/nfl-forward-storage-20261026/config/operational-forward-storage-v3.json').read_bytes())
    legacy = json.loads((ROOT/'config/operational-source-policy-v2.json').read_bytes())
    controls = [Path('/workspace/website-methods-research/resumed/operational-storage-v2-20261023/cache/operational-storage-v2/registry.json'),
                Path('/workspace/website-methods-research/resumed/operational-forward-storage-v3-20261026/operational-forward-storage-v3/registry.json'),
                Path('/workspace/website-methods-research/resumed/historical-market-forward-v1-20261028/operational-forward-storage-v3/registry.json'),
                Path('/workspace/website-methods-research/resumed/historical-market-forward-v1-20261028/state/historical-market-outer-policy.json')]
    before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in controls]
    base = market.load_frozen('/workspace/nfl-forward-storage-20261026/nfl_lab/operational_forward_storage.py', '/workspace/nfl-session-scorecard-20261025')
    cls = wrapper.build_storage_class(market.build_storage_class(base), next_policy)
    store = cls('/workspace/website-methods-research/resumed/operational-storage-v2-20261023/cache', policy, legacy, prior)
    snapshot = store.snapshot()
    if before != [hashlib.sha256(p.read_bytes()).hexdigest() for p in controls]:
        raise ValueError('old control changed during no-write admission')
    used, wall = time.process_time()-cpu, time.monotonic()-start
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
    if used > 60 or wall > 90 or rss > 384*1024**2:
        raise RuntimeError('no-write allocation resource limit exceeded')
    signal.alarm(0)
    print(json.dumps({'state':'NEXT_ALLOCATION_FINAL_NO_WRITE_SNAPSHOT_PASS',
          'old_controls_unchanged': True, 'managed_writes':0, 'fits':0,
          'models':0, 'NFL_table_decodes':0, 'HTTP':0,
          'snapshot':snapshot, 'CPU_seconds':used, 'wall_seconds':wall,
          'RSS_peak_bytes':rss, 'offhost_restoration':'UNPROVEN'}, sort_keys=True))


if __name__ == '__main__':
    main()
