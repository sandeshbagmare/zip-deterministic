# Changelog

## 0.1.0

First release.

- `zip_bytes` / `write_zip`: sorted members, 1980-01-01 timestamps, fixed mode,
  normalised separators, no extra fields.
- `tar_bytes` / `write_tar`: sorted members, mtime 0, fixed mode, gzip header with the
  timestamp and name cleared.
- Refuses absolute paths, `..` traversal and duplicate members.
