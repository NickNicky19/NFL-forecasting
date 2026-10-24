"""Six fictional transition contracts; no process creation or real measurements."""
from copy import deepcopy
import unittest

from nfl_lab.termination_accounting import (
    AccountingFailure, EXIT_RECONCILABLE, classify_terminated_observation,
    confirm_owned_child_exit, validate_reaped_accounting,
)


class TerminationAccountingTests(unittest.TestCase):
    def setUp(self):
        self.binding = {"pid": 123456, "start_ticks": 987654}
        self.snapshot = {**self.binding, "stage": "FICTIONAL_AFTER_RELEASE", "before_state": "R", "after_state": "R",
                         "before_start_ticks": 987654, "after_start_ticks": 987654,
                         "stat_RSS_before_bytes": 0, "stat_RSS_after_bytes": 0,
                         "status_fields": {"Pid": ["123456"]}, "CPU_seconds": .16}

    def transfer(self, **changes):
        values = dict(child_pid=123456, returncode=0, reason_code="LIVE_RSS_COUNTER_MISSING", snapshot=self.snapshot)
        values.update(changes)
        return classify_terminated_observation(self.binding, **values)

    def test_01_missing_or_zero_live_RSS_without_exit_confirmation_fails(self):
        for reason in EXIT_RECONCILABLE:
            with self.subTest(reason=reason), self.assertRaises(AccountingFailure):
                self.transfer(returncode=None, reason_code=reason)

    def test_02_exact_confirmed_exit_transfers_to_mandatory_reap_charge(self):
        for code in (0, 1, -9):
            with self.subTest(code=code):
                transfer = self.transfer(returncode=code)
                self.assertEqual(transfer["returncode"], code)
                self.assertEqual(transfer["original_snapshot"], self.snapshot)
                self.assertIsNone(transfer["current_live_RSS_bytes"])
                self.assertFalse(transfer["missing_live_counter_excused"])
                self.assertTrue(transfer["post_reap_accounting_required"])
        minimal = {**self.binding, "stage": "FICTIONAL_PROC_FILE_ABSENT"}
        self.assertEqual(self.transfer(reason_code="REQUIRED_PROCESS_ACCOUNTING_MISSING", snapshot=minimal)["pid"], 123456)

    def test_03_PID_and_start_ticks_conflicts_remain_failure_after_exit(self):
        with self.assertRaises(AccountingFailure): self.transfer(child_pid=123457)
        for field in ("pid", "start_ticks", "before_start_ticks", "after_start_ticks"):
            with self.subTest(field=field):
                snapshot = {**self.snapshot, field: 999999}
                with self.assertRaises(AccountingFailure): self.transfer(snapshot=snapshot)
        snapshot = deepcopy(self.snapshot); snapshot["status_fields"]["Pid"] = ["123457"]
        with self.assertRaises(AccountingFailure): self.transfer(snapshot=snapshot)

    def test_04_other_failures_and_nonowned_or_unconfirmed_poll_are_rejected(self):
        for reason in ("PID_START_TICKS_CONFLICT", "NEGATIVE_RSS_COUNTER", "COMBINED_CPU_STOP"):
            with self.subTest(reason=reason), self.assertRaises(AccountingFailure): self.transfer(reason_code=reason)
        for code in (None, True, 0.0, "0"):
            with self.subTest(code=code), self.assertRaises(AccountingFailure): self.transfer(returncode=code)
        with self.assertRaises(AccountingFailure):
            confirm_owned_child_exit(object(), self.binding, reason_code="LIVE_RSS_COUNTER_MISSING", snapshot=self.snapshot)
        for field, value in (("stat_RSS_before_bytes", -1), ("stat_RSS_after_bytes", "0"),
                             ("status_fields", {"VmRSS": ["-1", "kB"]}), ("before_start_ticks", 987654.0)):
            with self.subTest(field=field, value=value), self.assertRaises(AccountingFailure):
                self.transfer(snapshot={**self.snapshot, field: value})

    def test_05_full_reaped_CPU_and_highwater_are_returned_unchanged(self):
        charge = validate_reaped_accounting(self.transfer(), child_CPU_seconds=.172547, child_highwater_bytes=19005440)
        self.assertEqual(charge["child_CPU_seconds"], .172547)
        self.assertEqual(charge["child_highwater_bytes"], 19005440)
        self.assertIsNone(charge["current_live_RSS_bytes"])
        self.assertFalse(charge["live_counter_zero_fallback"])

    def test_06_missing_or_insufficient_reap_usage_cannot_complete_transfer(self):
        for cpu, highwater in ((None, 1000), (.15, 1000), (float("inf"), 1000), (.17, 0), (.17, None), (.17, True)):
            with self.subTest(cpu=cpu, highwater=highwater), self.assertRaises(AccountingFailure):
                validate_reaped_accounting(self.transfer(), child_CPU_seconds=cpu, child_highwater_bytes=highwater)
        transfer = self.transfer(); transfer["post_reap_accounting_required"] = False
        with self.assertRaises(AccountingFailure):
            validate_reaped_accounting(transfer, child_CPU_seconds=.17, child_highwater_bytes=1000)
