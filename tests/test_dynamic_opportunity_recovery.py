"""Four NEW fictional recovery contracts; no NFL/source/model/CAS calls."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from nfl_lab import dynamic_opportunity_recovery as recovery


def binding(path):
    return dict(path=path, bytes=123, sha256="a" * 64)


def envelope():
    old = "/tmp/fictional-dynamic-failed"
    identity = dict(source_policy=binding("/tmp/fictional-policy"), calendar=binding("/tmp/fictional-raw-calendar"),
                    queries={str(y): binding(f"/tmp/fictional-query-{y}") for y in (2022, 2023, 2024)},
                    accepted_features=binding("/tmp/fictional-accepted"))
    return dict(schema_version=recovery.VERSION, state="REGISTERED_NO_INVOCATION", original_registration_id=recovery.ORIGINAL,
        original_output=old, output="/tmp/fictional-dynamic-new",
        previous_consumption=dict(wall_seconds=43.3, CPU_seconds=45.7, prior_vector_reservations=2,
                                  forecast_packages=0, forecast_row_incidences=0, retained_bytes=12691530),
        remaining_limits=dict(wall_seconds=540, CPU_seconds=540, prior_vector_formations=14,
                              planned_prior_vectors=13, campaign_retention_bytes=50331648),
        source_phase_consumption=dict(wall_seconds=3.7, CPU_seconds=3.8),
        reuse=dict(calendar=binding(old + "/calendar.json"),
                   contexts={str(y): binding(old + f"/private/context/{y}.parquet") for y in range(2020, 2025)},
                   source_identity=identity), previous_receipts=[binding(f"/tmp/fictional-receipt-{i}") for i in range(4)])


class RecoveryContracts(unittest.TestCase):
    def test_01_cumulative_envelope_preserves_failed_budget_and_source_identity(self):
        value = envelope(); plan = value["reuse"]["source_identity"]
        self.assertIs(recovery.validate(value, source_plan=plan, output=value["output"]), value)
        for key, changed in (("forecast_packages", 1), ("forecast_row_incidences", 1),
                             ("prior_vector_reservations", 0), ("retained_bytes", 0)):
            bad = deepcopy(value); bad["previous_consumption"][key] = changed
            with self.assertRaises(ValueError): recovery.validate(bad)
        for field in ("CPU_seconds", "wall_seconds"):
            bad = deepcopy(value); bad["previous_consumption"][field] = 61
            with self.assertRaises(ValueError): recovery.validate(bad)
        bad = deepcopy(value); bad["reuse"]["contexts"]["2020"]["path"] = "/tmp/other-context"
        with self.assertRaises(ValueError): recovery.validate(bad)
        bad_plan = deepcopy(plan); bad_plan["calendar"]["sha256"] = "b" * 64
        with self.assertRaises(ValueError): recovery.validate(value, source_plan=bad_plan)

    def test_02_compact_environment_references_every_original_pin(self):
        with tempfile.TemporaryDirectory(prefix="fictional-dynamic-env-") as temporary:
            path = Path(temporary) / "parent.json"
            env = dict(executable="/fictional/python", python="fictional-version", packages={"fictional": "1"},
                       file_bindings=[binding("/fictional/one"), binding("/fictional/two")])
            path.write_text(json.dumps(dict(environment=env)))
            parent = dict(path=str(path), bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            encoded = json.dumps(env, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
            freeze = dict(parent_execution=parent, bindings=[dict(parent, inode=[1, 2], mode="fictional")],
                execution_metadata=dict(recovery_envelope=envelope()),
                environment_reference=dict(parent, json_pointer="/environment", environment_sha256=hashlib.sha256(encoded).hexdigest()))
            observed = []
            def pin(item):
                observed.append(item)
                self.assertEqual(hashlib.sha256(Path(item["path"]).read_bytes()).hexdigest(), item["sha256"])
            expanded = recovery.expand_environment(freeze, pin=pin)
            self.assertEqual(expanded["environment"], env); self.assertEqual(len(observed), 1)
            self.assertNotIn("environment", freeze)  # No rewritten large inventory.
            bad = deepcopy(freeze); bad["environment_reference"]["environment_sha256"] = "0" * 64
            with self.assertRaises(ValueError): recovery.expand_environment(bad, pin=pin)
            with self.assertRaises(ValueError): recovery.expand_environment(dict(freeze, environment=env), pin=pin)

    def test_03_failed_plus_new_retention_is_one48MiB_and_aliases_add_zero(self):
        previous = 12691530
        planned_new = 6291456 + 14856192 + 5504000 + 5565056 + 4194304 + 73728
        self.assertEqual(recovery.campaign_charge(previous, planned_new), 49176266)
        self.assertEqual(recovery.campaign_charge(previous, planned_new, 0), 49176266)
        with self.assertRaises(ValueError): recovery.campaign_charge(previous, planned_new, 1155383)
        for invalid in (-1, True, 1.5):
            with self.assertRaises(ValueError): recovery.campaign_charge(previous, invalid)
        self.assertEqual(recovery.campaign_charge(previous, recovery.CAMPAIGN_BYTES - previous), recovery.CAMPAIGN_BYTES)

    def test_04_remaining_runtime_and_prior_caps_cannot_reset_original_search(self):
        value = envelope(); spec = dict(recovery_envelope=value, output=value["output"], source_plan=value["reuse"]["source_identity"])
        limits = recovery.caps(spec)
        self.assertEqual((limits["wall_seconds"], limits["CPU_seconds"], limits["prior_reserved"]), (540, 540, 2))
        self.assertEqual(value["previous_consumption"]["prior_vector_reservations"] + value["remaining_limits"]["planned_prior_vectors"], 15)
        for field, changed in (("CPU_seconds", 541), ("wall_seconds", 541), ("prior_vector_formations", 16),
                               ("planned_prior_vectors", 14), ("campaign_retention_bytes", 67108864)):
            bad = deepcopy(spec); bad["recovery_envelope"]["remaining_limits"][field] = changed
            with self.assertRaises(ValueError): recovery.caps(bad)
        bad = deepcopy(spec); bad["output"] = value["original_output"]
        with self.assertRaises(ValueError): recovery.caps(bad)
        freeze = dict(execution_metadata=spec, external_timeout_seconds=540,
            external_timeout=dict(path="/usr/bin/timeout"), environment=dict(executable="/fictional/python"),
            tools=dict(supervisor=dict(path="/fictional/supervisor.py")))
        supplied = SimpleNamespace(freeze="/fictional/freeze.json", freeze_sha256="e" * 64)
        argv = recovery.expected_external_argv(freeze, supplied)
        self.assertEqual(argv[:4], ["/usr/bin/timeout", "--signal=KILL", "--kill-after=1s", "540s"])
        self.assertEqual(argv[-4:], ["--freeze", supplied.freeze, "--freeze-sha256", supplied.freeze_sha256])
        with self.assertRaises(ValueError): recovery.expected_external_argv(dict(freeze, external_timeout_seconds=600), supplied)


if __name__ == "__main__":
    unittest.main()
