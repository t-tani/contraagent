"""A `BlobStore` in an S3 bucket: `S3Blobs`, for a hub of many processes.

Each blob is the object `<prefix>/<sha[:2]>/<sha>`. The credentials are the standard AWS
ones (environment, shared config and credentials files, instance roles). A blob's content
never changes, so small blobs that were read are kept in memory (`CACHE_BYTES` in all) and
served from there by `get`.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from collections.abc import Iterator
from urllib.parse import parse_qs, urlparse

import boto3
from botocore.exceptions import ClientError

from contraagent._internal.hub.store import BlobItem, _check

#: How many bytes of read blobs an `S3Blobs` keeps in memory, and the largest blob it keeps.
CACHE_BYTES = 64 * 1024 * 1024
CACHE_BLOB_BYTES = 1024 * 1024


def _is_hex_sha(sha256: str) -> bool:
    return len(sha256) == 64 and all(c in "0123456789abcdef" for c in sha256)


def _absent(error: ClientError) -> bool:
    return error.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound")


class S3Blobs:
    """A `BlobStore` at `url`: `s3://<bucket>/<prefix>?endpoint=<url>&region=<region>`.

    The prefix may be empty; `endpoint` (an S3-compatible service such as RustFS) and
    `region` are optional.
    """

    def __init__(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme != "s3" or not parsed.netloc:
            raise ValueError(f"not an s3://<bucket>/<prefix> URL: {url!r}")
        query = {k: v[-1] for k, v in parse_qs(parsed.query).items()}
        self.bucket = parsed.netloc
        self.prefix = parsed.path.strip("/")
        self._client = boto3.client("s3", endpoint_url=query.get("endpoint"), region_name=query.get("region"))
        self._cache: OrderedDict[str, bytes] = OrderedDict()
        self._cached = 0
        self._lock = threading.Lock()

    def _remember(self, sha256: str, data: bytes) -> None:
        if len(data) > CACHE_BLOB_BYTES:
            return
        with self._lock:
            if sha256 in self._cache:
                return
            self._cache[sha256] = data
            self._cached += len(data)
            while self._cached > CACHE_BYTES:
                _, dropped = self._cache.popitem(last=False)
                self._cached -= len(dropped)

    def _recall(self, sha256: str) -> bytes | None:
        with self._lock:
            data = self._cache.get(sha256)
            if data is not None:
                self._cache.move_to_end(sha256)
            return data

    def _key(self, sha256: str) -> str:
        if not _is_hex_sha(sha256):
            raise ValueError(f"not a SHA-256 in hex: {sha256!r}")
        key = f"{sha256[:2]}/{sha256}"
        return f"{self.prefix}/{key}" if self.prefix else key

    def has(self, sha256: str) -> bool:
        """Asks the bucket, never the cache: another hub process may have deleted the blob."""
        key = self._key(sha256)
        try:
            self._client.head_object(Bucket=self.bucket, Key=key)
        except ClientError as e:
            if _absent(e):
                return False
            raise
        return True

    def put(self, sha256: str, data: bytes) -> None:
        _check(sha256, data)
        if self.has(sha256):
            return
        self._client.put_object(Bucket=self.bucket, Key=self._key(sha256), Body=bytes(data))

    def get(self, sha256: str) -> bytes | None:
        key = self._key(sha256)
        data = self._recall(sha256)
        if data is not None:
            return data
        try:
            got = self._client.get_object(Bucket=self.bucket, Key=key)
        except ClientError as e:
            if _absent(e):
                return None
            raise
        data = got["Body"].read()
        self._remember(sha256, data)
        return data

    def items(self) -> Iterator[BlobItem]:
        """Every blob object under the prefix, dated by its `LastModified`."""
        base = f"{self.prefix}/" if self.prefix else ""
        for page in self._client.get_paginator("list_objects_v2").paginate(Bucket=self.bucket, Prefix=base):
            for obj in page.get("Contents", []):
                rel = obj["Key"][len(base) :]
                sub, _, sha = rel.partition("/")
                if _is_hex_sha(sha) and sub == sha[:2]:
                    yield BlobItem(sha, int(obj["Size"]), obj["LastModified"])

    def delete(self, sha256: str) -> None:
        key = self._key(sha256)
        with self._lock:
            data = self._cache.pop(sha256, None)
            if data is not None:
                self._cached -= len(data)
        self._client.delete_object(Bucket=self.bucket, Key=key)
