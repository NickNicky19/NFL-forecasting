"""Actual complete unittest discovery, with all Python network connections denied."""
import json
from pathlib import Path
import socket
import sys
import unittest

import requests

attempts = []
def blocked(*args, **kwargs):
    attempts.append("NETWORK_ATTEMPT_DENIED")
    raise AssertionError("NETWORK_DISABLED_CORRECTION_QUALIFICATION")

requests.sessions.Session.request = blocked
socket.socket.connect = blocked
socket.socket.connect_ex = blocked
socket.create_connection = blocked
sys.path[:0] = [str(Path.cwd() / name) for name in ("pull", "tools", "tests")]
suite = unittest.defaultTestLoader.discover("tests")
result = unittest.TextTestRunner(verbosity=2).run(suite)
print(json.dumps(dict(tests=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                      skipped=len(result.skipped), network="DENIED", denied_network_attempts=len(attempts),
                      fgm_cache_trace=getattr(sys.modules.get('test_fgm_cache_contract'), 'TRACE', None),
                      grading_version=__import__("grade").GRADING_VERSION)))
sys.exit(not result.wasSuccessful())
