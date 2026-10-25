"""Explicit private fixed-R0 child. Parent owns API/owner/checkpoint authority."""
from pathlib import Path
import argparse
import json
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nfl_lab import audit_reference_capture_v1 as reference
from nfl_lab.operational_storage import OperationalStorage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--prepared', type=Path)
    parser.add_argument('--prepared-sha256')
    parser.add_argument('--cache', type=Path)
    parser.add_argument('--storage-policy', type=Path)
    parser.add_argument('--worker', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--worker-sha256', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker or args.execute:
        from tools.audit_process_guard_v1 import arm_parent_death
        arm_parent_death()
    if args.worker:
        reference.worker(args.worker, args.worker_sha256)
    elif not args.execute:
        print(json.dumps(dict(schema_version=reference.VERSION, approved=False,
            control=reference.control_spec(), limits=reference.LIMITS,
            parent_authentication_required=True, source_reads=0, fits=0, public_release=False), sort_keys=True))
    else:
        if not all((args.prepared, args.prepared_sha256, args.cache, args.storage_policy)):
            parser.error('Explicit prepared binding and existing owned store required')
        store = OperationalStorage(args.cache, args.storage_policy)
        ref = dict(path=str(args.prepared.absolute()), bytes=args.prepared.stat().st_size, sha256=args.prepared_sha256)
        print(json.dumps(reference.capture_reference(store, ref), sort_keys=True))


if __name__ == '__main__':
    main()
