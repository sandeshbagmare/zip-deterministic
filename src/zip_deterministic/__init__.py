"""Write archives whose bytes do not change between runs.

A zip or tar file records the modification time, permissions and order of every
member, so building the same tree twice usually gives two different files, which
breaks cache keys, signatures and reproducible builds. This module writes archives
with those values pinned.

    >>> from zip_deterministic import zip_bytes
    >>> data = zip_bytes({"a.txt": b"hello"})
    >>> zip_bytes({"a.txt": b"hello"}) == data
    True

The defaults follow the reproducible-builds convention: modification time
1980-01-01 00:00:00 (the earliest a zip can express), permissions ``0o644``, entries
in sorted order, no extra fields, and gzip headers with the timestamp and file name
cleared.
"""

from __future__ import annotations

import gzip
import io
import os
import tarfile
import time
import zipfile
from collections.abc import Iterable, Mapping
from pathlib import Path

__all__ = [
    "DEFAULT_DATE_TIME",
    "DEFAULT_MODE",
    "tar_bytes",
    "write_tar",
    "write_zip",
    "zip_bytes",
]

__version__ = "0.1.3"

#: 1980-01-01 00:00:00, the earliest timestamp a zip file can store.
DEFAULT_DATE_TIME = (1980, 1, 1, 0, 0, 0)
DEFAULT_MODE = 0o644

Entry = tuple[str, bytes]


def _normalise(name: str) -> str:
    """Archive member names always use forward slashes, on every platform."""
    return name.replace("\\", "/")


def _entries(source: Mapping[str, bytes] | Iterable[Entry]) -> list[Entry]:
    """Return the members as a sorted list, rejecting unsafe or duplicate names."""
    items = list(source.items()) if isinstance(source, Mapping) else list(source)
    seen: set[str] = set()
    for name, data in items:
        if not isinstance(name, str):
            raise TypeError(f"archive member name must be str, got {type(name).__name__}")
        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise TypeError(f"archive member {name!r} must be bytes")
        normalised = _normalise(name)
        if normalised.startswith("/") or ".." in normalised.split("/"):
            raise ValueError(f"archive member escapes the root: {name!r}")
        if normalised in seen:
            raise ValueError(f"duplicate archive member: {name!r}")
        seen.add(normalised)
    return sorted(((_normalise(name), bytes(data)) for name, data in items))


def zip_bytes(
    members: Mapping[str, bytes] | Iterable[Entry],
    *,
    date_time: tuple[int, int, int, int, int, int] = DEFAULT_DATE_TIME,
    mode: int = DEFAULT_MODE,
    compression: int = zipfile.ZIP_DEFLATED,
    level: int | None = 6,
) -> bytes:
    """Return a zip archive of ``members`` as bytes."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=compression, allowZip64=True) as archive:
        for name, data in _entries(members):
            info = zipfile.ZipInfo(filename=name, date_time=date_time)
            info.external_attr = (mode & 0xFFFF) << 16
            info.create_system = 3  # Unix, so the permission bits are read as Unix bits
            info.compress_type = compression
            if level is not None:
                archive.writestr(info, data, compresslevel=level)
            else:  # pragma: no cover - only for stored archives
                archive.writestr(info, data)
    return buffer.getvalue()


def write_zip(
    path: str | os.PathLike[str],
    members: Mapping[str, bytes] | Iterable[Entry],
    **kwargs,
) -> int:
    """Write a zip archive to ``path`` and return its size in bytes."""
    data = zip_bytes(members, **kwargs)
    Path(path).write_bytes(data)
    return len(data)


def _tar_info(name: str, size: int, mtime: int, mode: int) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name)
    info.size = size
    info.mtime = mtime
    info.mode = mode
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    info.type = tarfile.REGTYPE
    return info


def tar_bytes(
    members: Mapping[str, bytes] | Iterable[Entry],
    *,
    mtime: int = 0,
    mode: int = DEFAULT_MODE,
    gz: bool = True,
    compresslevel: int = 9,
) -> bytes:
    """Return a tar (or ``.tar.gz``) archive of ``members`` as bytes."""
    buffer = io.BytesIO()
    format_ = tarfile.PAX_FORMAT
    with tarfile.open(fileobj=buffer, mode="w", format=format_) as archive:
        for name, data in _entries(members):
            archive.addfile(_tar_info(name, len(data), mtime, mode), io.BytesIO(data))
    raw = buffer.getvalue()
    if not gz:
        return raw
    compressed = io.BytesIO()
    # mtime=0 and an empty filename keep the gzip header identical between runs.
    with gzip.GzipFile(
        filename="",
        mode="wb",
        fileobj=compressed,
        mtime=0,
        compresslevel=compresslevel,
    ) as handle:
        handle.write(raw)
    return compressed.getvalue()


def write_tar(
    path: str | os.PathLike[str],
    members: Mapping[str, bytes] | Iterable[Entry],
    **kwargs,
) -> int:
    """Write a tar archive to ``path`` and return its size in bytes."""
    data = tar_bytes(members, **kwargs)
    Path(path).write_bytes(data)
    return len(data)


def now_as_zip_time() -> tuple[int, int, int, int, int, int]:
    """The current time in the tuple form a zip file wants, for opt-out use."""
    return time.localtime()[:6]
