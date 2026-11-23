"""Tests for zip_deterministic."""

import gzip
import io
import tarfile
import time
import zipfile

import pytest

from zip_deterministic import (
    DEFAULT_DATE_TIME,
    DEFAULT_MODE,
    now_as_zip_time,
    tar_bytes,
    write_tar,
    write_zip,
    zip_bytes,
)


class TestZip:
    def test_two_builds_are_byte_identical(self):
        members = {"b.txt": b"second", "a.txt": b"first"}
        assert zip_bytes(members) == zip_bytes(dict(reversed(list(members.items()))))

    def test_round_trips_through_zipfile(self):
        data = zip_bytes({"a.txt": b"hello", "dir/b.bin": b"\x00\xff"})
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            assert archive.namelist() == ["a.txt", "dir/b.bin"]
            assert archive.read("a.txt") == b"hello"

    def test_entry_order_is_sorted(self):
        data = zip_bytes({"z.txt": b"z", "a.txt": b"a", "m/x.txt": b"m"})
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            assert archive.namelist() == ["a.txt", "m/x.txt", "z.txt"]

    def test_timestamp_is_pinned(self):
        with zipfile.ZipFile(io.BytesIO(zip_bytes({"a.txt": b"a"}))) as archive:
            assert archive.getinfo("a.txt").date_time == DEFAULT_DATE_TIME

    def test_permissions_are_pinned(self):
        with zipfile.ZipFile(io.BytesIO(zip_bytes({"a.txt": b"a"}))) as archive:
            mode = archive.getinfo("a.txt").external_attr >> 16
        assert mode == DEFAULT_MODE

    def test_permissions_can_be_chosen(self):
        data = zip_bytes({"run.sh": b"#!/bin/sh\n"}, mode=0o755)
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            assert archive.getinfo("run.sh").external_attr >> 16 == 0o755

    def test_windows_separators_are_normalised(self):
        with zipfile.ZipFile(io.BytesIO(zip_bytes({"dir\\a.txt": b"a"}))) as archive:
            assert archive.namelist() == ["dir/a.txt"]

    def test_accepts_an_iterable_of_pairs(self):
        with zipfile.ZipFile(io.BytesIO(zip_bytes([("a.txt", b"a")]))) as archive:
            assert archive.namelist() == ["a.txt"]

    def test_rejects_absolute_paths(self):
        with pytest.raises(ValueError, match="escapes the root"):
            zip_bytes({"/etc/passwd": b"x"})

    def test_rejects_traversal(self):
        with pytest.raises(ValueError, match="escapes the root"):
            zip_bytes({"../outside.txt": b"x"})

    def test_rejects_duplicate_members(self):
        with pytest.raises(ValueError, match="duplicate"):
            zip_bytes([("a.txt", b"1"), ("a.txt", b"2")])

    def test_rejects_non_bytes_content(self):
        with pytest.raises(TypeError, match="must be bytes"):
            zip_bytes({"a.txt": "text"})  # type: ignore[dict-item]

    def test_rejects_non_string_names(self):
        with pytest.raises(TypeError, match="must be str"):
            zip_bytes({1: b"x"})  # type: ignore[dict-item]

    def test_write_zip_returns_the_size(self, tmp_path):
        target = tmp_path / "out.zip"
        size = write_zip(target, {"a.txt": b"hello"})
        assert size == target.stat().st_size
        with zipfile.ZipFile(target) as archive:
            assert archive.read("a.txt") == b"hello"


class TestTar:
    def test_two_builds_are_byte_identical(self):
        members = {"b.txt": b"second", "a.txt": b"first"}
        assert tar_bytes(members) == tar_bytes(dict(reversed(list(members.items()))))

    def test_round_trips_through_tarfile(self):
        data = tar_bytes({"a.txt": b"hello"}, gz=False)
        with tarfile.open(fileobj=io.BytesIO(data)) as archive:
            assert archive.getnames() == ["a.txt"]
            assert archive.extractfile("a.txt").read() == b"hello"

    def test_gzip_header_carries_no_timestamp_or_name(self):
        data = tar_bytes({"a.txt": b"hello"})
        header = data[:10]
        assert header[:2] == b"\x1f\x8b"
        assert int.from_bytes(header[4:8], "little") == 0
        assert header[3] & 0x08 == 0  # FNAME unset
        with gzip.open(io.BytesIO(data)) as handle:
            assert handle.read()

    def test_metadata_is_pinned(self):
        data = tar_bytes({"a.txt": b"hello"}, gz=False, mtime=1_600_000_000, mode=0o600)
        with tarfile.open(fileobj=io.BytesIO(data)) as archive:
            info = archive.getmember("a.txt")
        assert (info.mtime, info.mode, info.uid, info.gid) == (1_600_000_000, 0o600, 0, 0)

    def test_defaults_use_epoch_zero(self):
        data = tar_bytes({"a.txt": b"hello"}, gz=False)
        with tarfile.open(fileobj=io.BytesIO(data)) as archive:
            assert archive.getmember("a.txt").mtime == 0

    def test_write_tar_returns_the_size(self, tmp_path):
        target = tmp_path / "out.tar.gz"
        size = write_tar(target, {"a.txt": b"hello"})
        assert size == target.stat().st_size

    def test_rejects_traversal(self):
        with pytest.raises(ValueError, match="escapes the root"):
            tar_bytes({"../outside.txt": b"x"})


def test_gzip_reproducible_across_time(monkeypatch):
    """Two calls separated by a clock change must still match."""
    first = tar_bytes({"a.txt": b"hello"})
    monkeypatch.setattr(time, "time", lambda: 1_900_000_000)
    assert tar_bytes({"a.txt": b"hello"}) == first


class TestRigour:
    """The opt-out clock helper and the tar entry points."""

    def test_now_as_zip_time_is_a_six_tuple(self):
        value = now_as_zip_time()
        assert len(value) == 6
        assert all(isinstance(part, int) for part in value)
        assert value[0] >= 1980

    def test_the_mode_is_carried_on_every_entry(self):
        data = zip_bytes([("run.sh", b"#!/bin/sh\n")], mode=0o755)
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            info = archive.getinfo("run.sh")
        assert (info.external_attr >> 16) & 0o777 == 0o755

    def test_a_tar_archive_is_written_to_disk(self, tmp_path):
        path = tmp_path / "a.tar"
        size = write_tar(path, [("a.txt", b"hi")])
        assert size == path.stat().st_size
        with tarfile.open(path) as archive:
            assert archive.getnames() == ["a.txt"]

    def test_a_directory_entry_in_a_zip(self):
        data = zip_bytes([("dir/", b"")])
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            assert archive.namelist() == ["dir/"]
