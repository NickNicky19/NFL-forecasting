"""Metadata fixtures for Main's optional Count A template interpretation.

No native authority, private template, model, NFL row or network is used.
"""
from pathlib import Path
import copy
import hashlib

import pytest

from nfl_lab import audit_weekly_template_v1 as template

ROOT = Path(__file__).resolve().parents[1]
HELPERS = {
    'nfl_lab/count_a_native_extension_v1.py': 'abd34b0827ac551230f03a863466b8b9f381df5a175d3f8c3a81e8073b6f47fe',
    'nfl_lab/count_a_mean_export_adapter_v1.py': 'a3b44ee5c7937e830d0c2693d3fa55b0fed52c9cba51ae5058c04b2e7075b527',
    'tools/modern_count_a_mean_v3.py': 'aa7c002506b57d7c1ca643f4236e5fb8b5132bebb00ad86720ee11221b6d9fb6',
}


def test_count_a_template_checks_exact_helper_bytes_before_import():
    root = {'count_a_mean_shadow': {'helper_pins': dict(HELPERS)}}
    assert all(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == value
               for name, value in HELPERS.items())
    assert template.count_a_helper_pins(root, ROOT) is True
    changed = copy.deepcopy(root)
    changed['count_a_mean_shadow']['helper_pins']['nfl_lab/count_a_native_extension_v1.py'] = '0' * 64
    with pytest.raises(template.TemplateError, match='COUNT_A_PREIMPORT_SOURCE_BYTES'):
        template.count_a_helper_pins(changed, ROOT)


def test_old_template_does_not_require_optional_count_a_files():
    assert template.count_a_helper_pins({}, Path('/no/count-a-files')) is False
    assert template.root_keys({'schema_version': template.ROOT_V5}) == template.ROOT_V5_KEYS


def test_count_a_static_field_requires_explicit_v5_interpretation():
    root = {'schema_version': template.ROOT_V5, 'count_a_mean_shadow': {}}
    assert template.root_keys(root) == template.ROOT_V5_KEYS | {'count_a_mean_shadow'}
    root['schema_version'] = template.ROOT_V4
    with pytest.raises(template.TemplateError, match='COUNT_A_SHADOW_REQUIRES_CURRENT_V5_ROOT'):
        template.root_keys(root)


def test_lossless_history_validator_import_is_metadata_only():
    # Main's source-history guard keeps the original retained validator. Its
    # existing module closure must be present without loading numerical stacks.
    import importlib
    import sys
    before = set(sys.modules)
    retained = importlib.import_module('nfl_lab.audit_count_retained_v1')
    assert callable(retained.validate_registration)
    assert not ({'numpy', 'pandas', 'sklearn', 'joblib'} & (set(sys.modules) - before))
