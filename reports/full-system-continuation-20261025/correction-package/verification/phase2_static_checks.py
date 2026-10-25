"""Run the actual retained static tests against a source-only reconstructed copy."""
import json
from pathlib import Path
import socket
import sys
import unittest
import requests

sys.dont_write_bytecode=True
ROOT=Path('/tmp/nfl-phase2-source-reconstruction-e415912')
def blocked(*a,**k):raise AssertionError('NETWORK_DISABLED_PHASE2_STATIC_CHECK')
requests.sessions.Session.request=blocked
socket.socket.connect=socket.socket.connect_ex=socket.create_connection=blocked
sys.path[:0]=[str(ROOT/x)for x in ['pull','tools','tests']]
suite=unittest.TestSuite()
for name in ['test_weekly_phase2_integration.py','test_weekly_publication_authority_v2.py']:
    suite.addTests(unittest.defaultTestLoader.discover(str(ROOT/'tests'),pattern=name))
result=unittest.TextTestRunner(verbosity=2).run(suite)
print(json.dumps(dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),
    skipped=len(result.skipped),network='DENIED',scope='Retained static/binding tests; no full Phase2 or operating qualification')))
sys.exit(not result.wasSuccessful())
