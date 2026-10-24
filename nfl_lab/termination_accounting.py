"""Owned-child termination classification; never excuses missing live RSS.

No process discovery or resource measurement occurs here. The production entry
calls poll on the existing Popen child; post-reap measurements remain required.
"""
import math
import subprocess

VERSION = "owned-child-termination-accounting-v1"
EXIT_RECONCILABLE = frozenset(("LIVE_RSS_COUNTER_MISSING", "LIVE_RSS_ZERO_AFTER_RELEASE",
                              "REQUIRED_PROCESS_ACCOUNTING_MISSING"))


class AccountingFailure(ValueError):
    pass


def _require(condition, reason):
    if not condition:
        raise AccountingFailure(reason)


def classify_terminated_observation(binding, *, child_pid, returncode, reason_code, snapshot):
    """Pure transition contract; returncode must come from the owned Popen poll.

    An observed R/S state is not relabeled as Z, nor asserted to prove a cause.
    The later exact waitpid confirmation establishes termination independently.
    """
    _require(isinstance(binding, dict) and type(binding.get("pid")) is int and binding["pid"] > 1
             and type(binding.get("start_ticks")) is int and binding["start_ticks"] > 0,
             "KNOWN_CHILD_IDENTITY_REQUIRED")
    _require(type(child_pid) is int and child_pid == binding["pid"], "OWNED_CHILD_PID_CONFLICT")
    _require(reason_code in EXIT_RECONCILABLE, "ACCOUNTING_FAILURE_NOT_EXIT_RECONCILABLE")
    _require(type(returncode) is int, "OWNED_CHILD_TERMINATION_NOT_CONFIRMED")
    _require(isinstance(snapshot, dict) and type(snapshot.get("pid")) is int and snapshot["pid"] == binding["pid"]
             and type(snapshot.get("start_ticks")) is int and snapshot["start_ticks"] == binding["start_ticks"], "OBSERVATION_IDENTITY_CONFLICT")
    for field in ("before_start_ticks", "after_start_ticks"):
        _require(field not in snapshot or type(snapshot[field]) is int and snapshot[field] == binding["start_ticks"],
                 "OBSERVED_START_TICKS_CONFLICT")
    for field in ("stat_RSS_before_bytes", "stat_RSS_after_bytes", "status_RSS_bytes", "status_HWM_bytes"):
        _require(field not in snapshot or type(snapshot[field]) is int and snapshot[field] >= 0, "INVALID_OBSERVED_RSS_COUNTER")
    status = snapshot.get("status_fields", {})
    _require(isinstance(status, dict), "INVALID_OBSERVED_STATUS_FIELDS")
    if "Pid" in status:
        _require(status["Pid"] == [str(binding["pid"])], "OBSERVED_STATUS_PID_CONFLICT")
    for field in ("VmRSS", "VmHWM"):
        if field in status:
            value = status[field]
            _require(isinstance(value, list) and len(value) == 2 and value[1] == "kB"
                     and isinstance(value[0], str) and value[0].isdecimal(), "INVALID_OBSERVED_STATUS_COUNTER")
    observed_cpu = snapshot.get("CPU_seconds")
    _require(observed_cpu is None or type(observed_cpu) in (int, float)
             and math.isfinite(observed_cpu) and observed_cpu >= 0, "INVALID_OBSERVED_CPU_COUNTER")
    return {"schema_version": VERSION, "state": "OWNED_CHILD_EXIT_CONFIRMED_REAP_CHARGE_REQUIRED",
            "pid": binding["pid"], "start_ticks": binding["start_ticks"], "returncode": returncode,
            "original_reason_code": reason_code, "original_snapshot": dict(snapshot),
            "termination_evidence": "OWNED_POPEN_POLL_WAITPID",
            "current_live_RSS_bytes": None, "observed_child_CPU_lower_bound": observed_cpu,
            "missing_live_counter_excused": False, "post_reap_accounting_required": True}


def confirm_owned_child_exit(child, binding, *, reason_code, snapshot):
    """Production entry: no arbitrary PID polling, discovery, wait-all or retry."""
    _require(isinstance(child, subprocess.Popen), "ORIGINAL_POPEN_OBJECT_REQUIRED")
    _require(child.pid == binding.get("pid"), "OWNED_CHILD_PID_CONFLICT")
    return classify_terminated_observation(binding, child_pid=child.pid, returncode=child.poll(),
                                           reason_code=reason_code, snapshot=snapshot)


def validate_reaped_accounting(transfer, *, child_CPU_seconds, child_highwater_bytes):
    """Require actual full reaped usage; values are charged unchanged by caller."""
    _require(transfer.get("schema_version") == VERSION
             and transfer.get("state") == "OWNED_CHILD_EXIT_CONFIRMED_REAP_CHARGE_REQUIRED"
             and transfer.get("termination_evidence") == "OWNED_POPEN_POLL_WAITPID"
             and transfer.get("post_reap_accounting_required") is True,
             "ORIGINAL_TERMINATION_TRANSFER_REQUIRED")
    _require(type(child_CPU_seconds) in (int, float) and math.isfinite(child_CPU_seconds)
             and child_CPU_seconds >= 0, "INVALID_REAPED_CPU_COUNTER")
    observed = transfer.get("observed_child_CPU_lower_bound")
    _require(observed is None or child_CPU_seconds >= observed, "REAPED_CPU_BELOW_OBSERVED_COUNTER")
    _require(type(child_highwater_bytes) is int and child_highwater_bytes > 0, "POSITIVE_REAPED_HIGHWATER_REQUIRED")
    return {"schema_version": VERSION, "state": "TERMINATION_ACCOUNTING_CHARGED",
            "pid": transfer["pid"], "start_ticks": transfer["start_ticks"],
            "child_CPU_seconds": child_CPU_seconds, "child_highwater_bytes": child_highwater_bytes,
            "current_live_RSS_bytes": None, "live_counter_zero_fallback": False}
