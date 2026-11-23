# zip-deterministic

[![PyPI](https://img.shields.io/pypi/v/zip-deterministic.svg)](https://pypi.org/project/zip-deterministic/)
[![Python](https://img.shields.io/pypi/pyversions/zip-deterministic.svg)](https://pypi.org/project/zip-deterministic/)
[![tests](https://github.com/sandeshbagmare/zip-deterministic/actions/workflows/ci.yml/badge.svg)](https://github.com/sandeshbagmare/zip-deterministic/actions/workflows/ci.yml)
[![license](https://img.shields.io/pypi/l/zip-deterministic.svg)](https://github.com/sandeshbagmare/zip-deterministic/blob/main/LICENSE)

Build the same archive twice, get the **same bytes**.

```python
from zip_deterministic import zip_bytes

assert zip_bytes({"a.txt": b"hello"}) == zip_bytes({"a.txt": b"hello"})
```

A zip or tar file stores the modification time, permission bits and member order of
everything it contains, so two builds of the same tree normally differ. That breaks
cache keys, signatures, reproducible builds and "did this artifact really change?"
comparisons. This package pins all of it:

| value | default | why |
| ----- | ------- | --- |
| modification time | `1980-01-01 00:00:00` for zip, `0` for tar | the earliest zip can store, and the reproducible-builds convention for tar |
| permissions | `0o644` | no umask, no author's home directory leaking into the artifact |
| member order | sorted by name | the order of a `dict` or a directory listing must not matter |
| gzip header | no timestamp, no file name | `gzip` writes the current time and the name of the file it compressed |

Zero dependencies, Python 3.9+.

## Install

```console
pip install zip-deterministic
```

## Use

```python
from zip_deterministic import zip_bytes, tar_bytes, write_zip, write_tar

data = zip_bytes(
    {"README.md": b"# hello\n", "src/app.py": b"print('hi')\n"},
    compression=__import__("zipfile").ZIP_DEFLATED,
    level=6,
)

tar = tar_bytes({"README.md": b"# hello\n"})  # .tar.gz, gzip header cleared
plain = tar_bytes({"README.md": b"# hello\n"}, gz=False)  # bare .tar

write_zip("release.zip", {"a.txt": b"a"})  # returns the size in bytes
write_tar("release.tar.gz", {"a.txt": b"a"})
```

Executables keep their bit when you ask for it:

```python
zip_bytes({"bin/run.sh": b"#!/bin/sh\n"}, mode=0o755)
```

Members are checked before anything is written. Absolute paths, `..` traversal,
duplicate names and non-bytes content raise instead of producing an archive that
extracts outside the target directory.

## What it does not do

- It does not walk a directory for you: pass the members, so the caller decides what
  goes in and in what encoding.
- Symbols, hard links and directories are not modelled; only regular file members.
- Deflate output still depends on the zlib version. Same interpreter and zlib, same
  bytes; across zlib versions the compressed stream may differ, which is why the
  reproducible-builds project recommends `ZIP_STORED` when that matters.

## Development

```console
python -m venv .venv
.venv/bin/pip install -e ".[test]"
.venv/bin/pytest
```

## License

MIT.
