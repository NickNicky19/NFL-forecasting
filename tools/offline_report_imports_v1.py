"""Avoid urllib3's unnecessary local IPv6 socket probe in offline reports."""
from contextlib import contextmanager
import socket


@contextmanager
def offline_dependency_imports():
    """Restore the stdlib capability flag; never alter a network audit guard.

    Original report dependencies import requests/urllib3 despite this caller
    having no network route. urllib3 probes IPv6 at import by making a socket.
    A false capability skips that probe. Frozen dependency bytes stay intact;
    all socket/process audit denials remain active throughout this context.
    """
    previous = socket.has_ipv6
    socket.has_ipv6 = False
    try:
        yield
    finally:
        socket.has_ipv6 = previous
