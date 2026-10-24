"""Exact frozen public-publication policy metadata; standard library only.

The general source validator remains in operational_sources. This reader admits
only its already reviewed, exact e7 configuration bytes, before JSON decoding.
"""
import hashlib
import json
import os
from pathlib import Path
import stat

FROZEN_POLICY_SHA256="e7f54213218031c978c766af7a1a3b22a57c2a424b51f62056742162154fe441"
MAX_BYTES=64<<10


def load_frozen_source_policy(path: Path) -> dict:
    if not isinstance(path,Path) or ".." in path.parts:
        raise ValueError("frozen source policy requires an explicit safe Path")
    path=path.absolute();directory=os.open("/",os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        for component in path.parts[1:-1]:
            next_directory=os.open(component,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=directory)
            os.close(directory);directory=next_directory
        descriptor=os.open(path.name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=directory)
    finally:
        os.close(directory)
    with os.fdopen(descriptor,"rb") as stream:
        info=os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size>MAX_BYTES:
            raise ValueError("frozen source policy regular-file byte bound exceeded")
        body=stream.read(MAX_BYTES+1)
    if len(body)!=info.st_size or hashlib.sha256(body).hexdigest()!=FROZEN_POLICY_SHA256:
        raise ValueError("exact frozen source policy SHA256 required before JSON")
    document=json.loads(body)
    clean={k:v for k,v in document.items() if not k.startswith("_")}
    canonical=(json.dumps(clean,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode()
    return {**clean,"_policy_sha256":FROZEN_POLICY_SHA256,
            "_canonical_policy_sha256":hashlib.sha256(canonical).hexdigest()}
