"""Linux owned-child lifetime guard; importing performs no I/O."""
from __future__ import annotations


def arm_parent_death():
    import ctypes
    import os
    import signal
    expected=int(os.environ.get("AUDIT_WEEKLY_PARENT_PID",str(os.getppid())))
    if expected<=1 or os.getppid()!=expected:
        raise RuntimeError("OWNED_PARENT_ALREADY_EXITED")
    libc=ctypes.CDLL(None,use_errno=True)
    if libc.prctl(1,signal.SIGKILL,0,0,0)!=0:
        raise RuntimeError("OWNED_PARENT_DEATH_GUARD_REQUIRED")
    if os.getppid()!=expected:
        raise RuntimeError("OWNED_PARENT_EXITED_DURING_GUARD")
