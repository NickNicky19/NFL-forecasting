"""Single finite, offline complete inventory for the original-session continuation."""
from pathlib import Path
import hashlib
import importlib.util
import json
import resource
import signal
import sys
import time


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    root = Path('/workspace/nfl-methods-integration')
    plan = json.loads((root / 'config/category-topfive-opportunity-over-under-capacity-v3.json').read_text())
    output = root / plan['output']
    assert not output.exists(), 'one registered inventory invocation'
    result = {'version': plan['version'], 'state': 'FAILED_RETAINED', 'new_fits_forecasts_models_HTTP_CAS': 0}
    cpu, wall = time.process_time(), time.monotonic()
    resource.setrlimit(resource.RLIMIT_CPU, (60, 61))
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('90second inventory limit')))
    signal.alarm(90)
    def deny(event, args):
        if event.startswith('socket.') or event in ('subprocess.Popen', 'os.fork', 'os.system', 'os.posix_spawn'):
            raise RuntimeError('offline childfree inventory')
    sys.addaudithook(deny)
    try:
        sp = json.loads((root / plan['storage_base_plan']).read_text())['storage']
        for name, ref in sp.items():
            if isinstance(ref, dict) and 'sha256' in ref and name != 'metadata_descriptor':
                content = Path(ref['path']).read_bytes()
                assert len(content) == ref['bytes'] and hashlib.sha256(content).hexdigest() == ref['sha256'], name
        old = load(sp['original_helper']['path'], 'continuation_market')
        wrap = load(sp['helper']['path'], 'continuation_prior_metadata')
        top = load(root / 'nfl_lab/category_topfive_storage_v1.py', 'continuation_topfive_metadata')
        base = old.load_frozen(sp['forward_implementation']['path'], sp['legacy_library_root'])
        prior = wrap.build_storage_class(old.build_storage_class(base), json.loads((root / plan['old_metadata_descriptor']).read_text()))
        cls = top.build_storage_class(prior, json.loads((root / plan['topfive_metadata_descriptor']).read_text()))
        store = cls(sp['legacy_cache'], json.loads(Path(sp['market_policy']['path']).read_text()), json.loads(Path(sp['legacy_policy']['path']).read_text()), json.loads(Path(sp['prior_policy']['path']).read_text()))
        with store.transaction():
            store._refresh()
            usage = store._require(plan['incoming_private_peak_bytes'])
            def compact(value):
                if not isinstance(value, (dict, list)):
                    return value
                encoded = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
                return {'entries': len(value), 'bytes': len(encoded), 'sha256': hashlib.sha256(encoded).hexdigest()}
            result.update(state='PASS_POSTEXECUTION_COMPLETE_INHERITED_ACCOUNTING_80MiB_PEAK', inventory={k: compact(v) for k, v in usage.items()}, original_caps_locks_and_failure_history_unchanged=True)
    except BaseException as exc:
        result.update(error_type=type(exc).__name__, error=str(exc))
        raise
    finally:
        signal.alarm(0)
        result['actual'] = {'CPU_seconds': time.process_time()-cpu, 'wall_seconds': time.monotonic()-wall, 'RSS_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}
        encoded = (json.dumps(result, sort_keys=True, indent=2, allow_nan=False)+'\n').encode()
        assert len(encoded) <= 16384
        with output.open('xb') as handle:
            handle.write(encoded)
        print(json.dumps({'state': result['state'], 'actual': result['actual']}))


if __name__ == '__main__':
    main()
