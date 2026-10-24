# Private operational storage v2

The frozen `config/operational-source-policy-v2.json` defines a new accounting
boundary. `OperationalStorage` counts file `st_size` once for each unique
`(device, inode)`, across its control directory, source snapshots, features,
live cache, every byte under a supplied state directory, and explicitly
registered run or baseline intake directories. It also reports logical bytes
for every referenced file path. These figures describe file bytes rather than
filesystem block allocation. Frozen v1 evidence outside these roots stays
excluded and unchanged.

One cache-owned flock covers registry changes, each exact serialized incoming
body, each streaming chunk, immutable publication, and the old plus incoming
peak during atomic replacement. A persisted root registry makes later instances
count previously supplied state and run roots even when they omit those
arguments. Ownership markers reject overlapping roots owned by another store.
The registry binds the permanent lock inode; corrupt controls, foreign links,
symlinks and paths containing parent traversal fail closed.

```python
storage = OperationalStorage(cache, policy, state=state)
storage.register_root(private_runs)
storage.register_root(optional_baseline_cache)
receipt = storage.import_file(old_original, new_snapshot_source,
    expected_sha256=original_receipt["sha256"])
storage.validate_reference(new_snapshot_source, original_receipt["sha256"])
usage = storage.snapshot()
```

External originals are copied after reservation, verified and preserved with
their original inode and permissions. The owned SHA256 blob is readonly and
published references are hardlinks to that verified inode. Identical bodies
share physical bytes; distinct authentic receipt clocks remain distinct bytes.
Every blob, orphan, partial and control file counts. This version has no expiry,
deletion or garbage collection. Reaching the finite cap abstains the affected
write. Failure metadata needs its own capacity; failure to save it is an error.

New `write_bytes`, `write_text` and `atomic_json` references are immutable by
default. Repeating identical owned bytes is idempotent. Replacing different
bytes requires `replace=True` inside an explicit mutable helper scope. Earlier
blobs stay retained. A newly captured streaming file can be verified and
promoted into the owned store without another copy. Arbitrary preexisting
registered files cannot be promoted in place.

```python
with storage.capture_writes():
    with storage.capture_writes(roots=[private_stage]):
        frozen_data_loader(private_stage)
        storage.write_dataframe(qualified, private_stage / "processed/history.parquet",
            index=False, replace=True)
```

The scoped adapter covers `Path.write_bytes`, `Path.write_text`, streaming
`Path.open("wb")`, and pandas parquet/CSV destinations. Dataframes serialize in
memory through the original pandas serializer, then reserve their exact bytes.
Each unbuffered stream chunk reserves its actual length before writing. Direct
stream writes cannot truncate retained files or expose a writable descriptor.
The frozen state writer may flock its known empty `.writer.lock`, whose file
descriptor is readonly. Other writable open modes fail closed. Nested scopes
retain outer capture while narrowing which existing files may be replaced.

Only registered managed destinations are captured. Unrelated paths delegate to
the original methods; managed paths outside the active scope are rejected.
Builtins, `io.open`, `tempfile` streams and raw OS writes are outside this narrow
adapter. Operational routing must replace the frozen model atomic serializer
and `state.save` through scoped adapters using quota primitives. The state
adapter must keep its separate 200 MiB evidence cap inside `storage.transaction()`.
The frozen helper source files remain unchanged.

Fictional fixtures exercise quota boundaries, atomic replacement and interrupted
writes, process concurrency, restart, metadata/lock/blob corruption, ownership
overlap, external links, symlinks and both directions of parent traversal,
partial streams, serializer bytes, nested scopes and original preservation.
They perform no HTTP, NFL data reading, model fitting, predictions or scoring.
Passing these software fixtures supplies no forecasting evidence or operational
release qualification.
