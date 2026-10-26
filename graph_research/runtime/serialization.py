"""Stable JSON identities; preserve existing byte formats and strict numbers.

These are the project's established json.dumps formats, not RFC 8785.
The spaced format remains necessary for existing extension and result records.
"""
import hashlib
import json


def canonical_json(value):
    """Sorted, compact UTF-8-compatible JSON text; reject NaN and infinity."""
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)


def json_fingerprint(value):
    """SHA256 of the established compact JSON representation."""
    return hashlib.sha256(canonical_json(value).encode('utf-8')).hexdigest()


def legacy_json_fingerprint(value):
    """Keep default JSON spaces for historical extension and result identities."""
    text=json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False)
    return hashlib.sha256(text.encode('utf-8')).hexdigest()
