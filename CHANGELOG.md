# Changelog

- 0.1.2 — ship a `py.typed` marker; the docstring examples now run in the test suite.

## 0.1.1

- Member names are normalised to forward slashes on every platform. Before this,
  a name containing a backslash kept it when the package ran on POSIX, producing an
  archive that extracted as a file literally named ``dir.txt``.

## 0.1.0

First release.

- `zip_bytes` / `write_zip`: sorted members, 1980-01-01 timestamps, fixed mode,
  normalised separators, no extra fields.
- `tar_bytes` / `write_tar`: sorted members, mtime 0, fixed mode, gzip header with the
  timestamp and name cleared.
- Refuses absolute paths, `..` traversal and duplicate members.
