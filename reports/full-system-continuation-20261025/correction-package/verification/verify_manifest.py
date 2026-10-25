"""Read-only verification of the entire review package and its correction files."""
from pathlib import Path
import hashlib
import json

PACKAGE=Path(__file__).resolve().parents[1]
def main():
    manifest=json.loads((PACKAGE/'manifest.json').read_text())
    for name,expected in manifest['package_files'].items():
        path=PACKAGE/name
        assert path.resolve().is_relative_to(PACKAGE)and not path.is_symlink(),name
        raw=path.read_bytes()
        assert len(raw)==expected['bytes']and hashlib.sha256(raw).hexdigest()==expected['sha256'],name
    for name,expected in manifest['correction_files'].items():
        assert hashlib.sha256((PACKAGE/'files'/name).read_bytes()).hexdigest()==expected['postimage_sha256'],name
    actual={path.relative_to(PACKAGE).as_posix()for path in PACKAGE.rglob('*')if path.is_file()and path.name!='manifest.json'}
    assert actual==set(manifest['package_files']),actual^set(manifest['package_files'])
    print(json.dumps(dict(state='PASS',files=len(actual),source_base=manifest['source_base'],package_revision=manifest['package_revision'])))
if __name__=='__main__':main()
