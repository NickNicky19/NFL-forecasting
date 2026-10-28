"""Additional accounted metadata for the next finite wave; original CAS intact."""
from pathlib import Path
import os

VERSION = "next-checkpoint-metadata-v1"
RESERVE = 16 * 1024**2
OLD_JOINT = 1280 * 1024**2


def _walk_error(error):
    raise error


def metadata_bytes(policy, forbidden_roots=()):
    if (policy["version"] != VERSION
            or policy["new_metadata_limit_and_reserved_bytes"] != RESERVE
            or policy["old_global_limit_bytes"] != OLD_JOINT
            or policy["combined_global_limit_bytes"] != OLD_JOINT + RESERVE):
        raise ValueError("exact separate next-wave metadata allocation required")
    total, seen = 0, set()
    for scope in policy["new_scopes"]:
        root = Path(scope["root"])
        if root.resolve() != root or any(p.is_symlink() for p in (root, *root.parents)):
            raise ValueError("canonical metadata roots only")
        if any(root == r or root.is_relative_to(r) or r.is_relative_to(root)
               for r in map(Path, forbidden_roots)):
            raise ValueError("metadata must not overlap managed private data")
        for match in root.glob(scope["pattern"]):
            items = [match]
            if match.is_dir():
                for directory, dirs, files in os.walk(match, followlinks=False, onerror=_walk_error):
                    items.extend(Path(directory) / n for n in dirs + files)
            for p in items:
                if p.is_symlink():
                    raise ValueError("symlink in new metadata scope")
                if p.is_dir():
                    continue
                st = p.stat()
                key = st.st_dev, st.st_ino
                if st.st_nlink != 1:
                    raise ValueError("unaccounted metadata link")
                if key not in seen:
                    seen.add(key)
                    total += st.st_size
    if total > RESERVE:
        raise ValueError("new metadata allocation exhausted; evidence retained")
    return total


def build_storage_class(unchanged_market_class, policy):
    """Only extend accounting; inherit all original locks and immutable writers."""
    metadata_bytes(policy)

    class NextCheckpointStorage(unchanged_market_class):
        def _scan(self):
            usage = super()._scan()
            roots = self._roots + self.prior_forward._roots + self.legacy._roots
            actual = metadata_bytes(policy, roots)
            joint = usage["global_accounted_bytes"] + RESERVE
            if joint > policy["combined_global_limit_bytes"]:
                raise ValueError("new combined wave capacity exhausted")
            return {**usage, "next_metadata_actual_bytes": actual,
                    "next_metadata_reserved_bytes": RESERVE,
                    "next_combined_accounted_bytes": joint,
                    "next_combined_limit_bytes": policy["combined_global_limit_bytes"]}

        def _require(self, incoming):
            usage = super()._require(incoming)
            if (usage["next_combined_accounted_bytes"] + incoming
                    > policy["combined_global_limit_bytes"]):
                raise ValueError("incoming write exceeds complete next-wave peak")
            return usage

    return NextCheckpointStorage
