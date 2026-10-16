"""Where sealed transcript segments are kept: `SegmentObjects`, an object store with ranged
reads, in memory (`MemorySegmentObjects`), in a directory (`DirectorySegmentObjects`) and
in an S3 bucket (`S3SegmentObjects`). `open_objects` picks one from a URL.

A key is a `/`-separated path (`<run name>/<uid>/<log>/<first line>.seg`); an object is
written once under its key and never changes, except that writing the same key again
writes the same bytes.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Protocol
from urllib.parse import parse_qs, urlparse
from urllib.request import url2pathname

from contraagent._internal.runs.files import write_document


class SegmentObjects(Protocol):
    """An object store with ranged reads."""

    def put(self, key: str, data: bytes) -> None:
        """Store `data` under `key`; once this returns, the object is durable and whole."""
        ...

    def get_range(self, key: str, start: int, end: int | None) -> bytes:
        """Bytes `start`..`end` (end excluded) of the object; with a negative `start` and
        `end` None, its last `-start` bytes. `FileNotFoundError` when there is no such object."""
        ...

    def delete(self, key: str) -> None:
        """Remove the object; nothing happens when there is none."""
        ...

    def keys(self, prefix: str = "") -> list[str]:
        """Every key that starts with `prefix`, sorted."""
        ...


def _slice(data: bytes, start: int, end: int | None) -> bytes:
    if start < 0:
        return data[start:]
    return data[start:end]


class MemorySegmentObjects:
    """`SegmentObjects` in memory. Safe across threads."""

    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}
        self._lock = threading.Lock()

    def put(self, key: str, data: bytes) -> None:
        with self._lock:
            self._objects[key] = bytes(data)

    def get_range(self, key: str, start: int, end: int | None) -> bytes:
        with self._lock:
            data = self._objects.get(key)
        if data is None:
            raise FileNotFoundError(key)
        return _slice(data, start, end)

    def delete(self, key: str) -> None:
        with self._lock:
            self._objects.pop(key, None)

    def keys(self, prefix: str = "") -> list[str]:
        with self._lock:
            return sorted(k for k in self._objects if k.startswith(prefix))


class DirectorySegmentObjects:
    """`SegmentObjects` as files under `root` (`<root>/<key>`). An object is written to a
    temporary file, flushed to disk and renamed into place, so it is whole once it appears."""

    def __init__(self, root: str | os.PathLike[str]) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        parts = key.split("/")
        if not key or key.startswith("/") or any(p in ("", ".", "..") for p in parts):
            raise ValueError(f"not an object key: {key!r}")
        return self.root.joinpath(*parts)

    def put(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        write_document(path, data, fsync=True)

    def get_range(self, key: str, start: int, end: int | None) -> bytes:
        with open(self._path(key), "rb") as f:
            if start < 0:
                size = f.seek(0, os.SEEK_END)
                f.seek(max(size + start, 0))
                return f.read()
            f.seek(start)
            return f.read(-1 if end is None else max(end - start, 0))

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def keys(self, prefix: str = "") -> list[str]:
        out = []
        for dirpath, _, files in os.walk(self.root):
            for name in files:
                if name.startswith("."):  # a write not finished (`write_document`'s temporary file)
                    continue
                key = Path(dirpath, name).relative_to(self.root).as_posix()
                if key.startswith(prefix):
                    out.append(key)
        return sorted(out)


class S3SegmentObjects:
    """`SegmentObjects` in an S3 bucket at `url`: `s3://<bucket>/<prefix>?endpoint=<url>&region=<region>`,
    as `S3Blobs` takes it. Each object is `<prefix>/<key>`; reads are ranged GETs."""

    def __init__(self, url: str) -> None:
        import boto3

        parsed = urlparse(url)
        if parsed.scheme != "s3" or not parsed.netloc:
            raise ValueError(f"not an s3://<bucket>/<prefix> URL: {url!r}")
        query = {k: v[-1] for k, v in parse_qs(parsed.query).items()}
        self.bucket = parsed.netloc
        self.prefix = parsed.path.strip("/")
        self._client = boto3.client("s3", endpoint_url=query.get("endpoint"), region_name=query.get("region"))

    def _key(self, key: str) -> str:
        return f"{self.prefix}/{key}" if self.prefix else key

    def put(self, key: str, data: bytes) -> None:
        self._client.put_object(Bucket=self.bucket, Key=self._key(key), Body=bytes(data))

    def get_range(self, key: str, start: int, end: int | None) -> bytes:
        from botocore.exceptions import ClientError

        if start < 0:
            wanted = f"bytes={start}"
        elif end is None:
            wanted = f"bytes={start}-"
        elif end <= start:
            return b""
        else:
            wanted = f"bytes={start}-{end - 1}"
        try:
            got = self._client.get_object(Bucket=self.bucket, Key=self._key(key), Range=wanted)
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
                raise FileNotFoundError(key) from e
            raise
        return got["Body"].read()

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self.bucket, Key=self._key(key))

    def keys(self, prefix: str = "") -> list[str]:
        base = f"{self.prefix}/" if self.prefix else ""
        out: list[str] = []
        for page in self._client.get_paginator("list_objects_v2").paginate(Bucket=self.bucket, Prefix=base + prefix):
            out.extend(o["Key"][len(base) :] for o in page.get("Contents", []))
        return sorted(out)


def open_objects(url: str | None) -> SegmentObjects:
    """The `SegmentObjects` a URL names: `s3://...` (`S3SegmentObjects`), `memory:` or None
    (`MemorySegmentObjects`), or a directory path, optionally as `file://<path>`."""
    if url is None or url == "memory:":
        return MemorySegmentObjects()
    if url.startswith("s3://"):
        return S3SegmentObjects(url)
    if url.startswith("file://"):
        return DirectorySegmentObjects(url2pathname(urlparse(url).path))  # file:///C:/x: C:\x on Windows
    return DirectorySegmentObjects(url)
