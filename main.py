#!/usr/bin/env python3
"""Entry program for make.fun news-image-20261122.

Copies the bundled front-page image (entry.png, in this repository) to
/output/entry.png, byte for byte, after validating the PNG thoroughly:

  * 8-byte PNG signature
  * IHDR chunk first, 13 bytes, 1024x1024, bit depth 8, colour type 2
  * every chunk's CRC32 matches its stored value
  * exactly one IEND chunk, last, with no trailing bytes
  * total size at most 1 MiB (1048576 bytes)

After the copy, the written file is re-read and its SHA-256 is compared
with the source file's, so a partial or altered copy fails loudly.

Python 3.13, standard library only. No network, no clock, no randomness:
two runs write identical bytes.

Run:  python3 main.py
"""
import hashlib
import os
import struct
import sys
import zlib

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "entry.png")
DST = "/output/entry.png"
MAX_BYTES = 1048576
WANT_W, WANT_H = 1024, 1024

PNG_SIG = b"\x89PNG\r\n\x1a\n"


def fail(msg):
    print(f"main.py: error: {msg}", file=sys.stderr)
    sys.exit(1)


def check_png(data):
    """Validate a PNG in memory; return (width, height)."""
    if len(data) < 8 or data[:8] != PNG_SIG:
        fail("bad PNG signature")
    if len(data) > MAX_BYTES:
        fail(f"file is {len(data)} bytes, over the 1 MiB limit")
    pos = 8
    seen_iend = False
    seen_ihdr = False
    width = height = None
    while pos < len(data):
        if pos + 8 > len(data):
            fail("truncated chunk header")
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        ctype = data[pos + 4:pos + 8]
        if pos + 12 + length > len(data):
            fail(f"truncated chunk {ctype!r}")
        chunk = data[pos + 4:pos + 8 + length]
        (stored_crc,) = struct.unpack(">I", data[pos + 8 + length:pos + 12 + length])
        if zlib.crc32(chunk) & 0xFFFFFFFF != stored_crc:
            fail(f"CRC mismatch in chunk {ctype!r}")
        if ctype == b"IHDR":
            if seen_ihdr:
                fail("duplicate IHDR chunk")
            seen_ihdr = True
            if length != 13:
                fail("IHDR is not 13 bytes")
            width, height, depth, ctype_no = struct.unpack(">IIBB", data[pos + 8:pos + 18])
            if (width, height) != (WANT_W, WANT_H):
                fail(f"IHDR is {width}x{height}, want {WANT_W}x{WANT_H}")
            if depth != 8 or ctype_no != 2:
                fail(f"unexpected bit depth {depth} / colour type {ctype_no}")
        elif ctype == b"IEND":
            if seen_iend:
                fail("duplicate IEND chunk")
            seen_iend = True
            if length != 0:
                fail("IEND carries data")
            if pos + 12 + length != len(data):
                fail("trailing bytes after IEND")
        pos += 12 + length
    if not seen_ihdr:
        fail("no IHDR chunk")
    if not seen_iend:
        fail("no IEND chunk")
    return width, height


def main():
    try:
        with open(SRC, "rb") as fh:
            data = fh.read()
    except OSError as exc:
        fail(f"cannot read {SRC}: {exc}")
    width, height = check_png(data)
    digest = hashlib.sha256(data).hexdigest()
    os.makedirs(os.path.dirname(DST), exist_ok=True)
    with open(DST, "wb") as fh:
        fh.write(data)
    with open(DST, "rb") as fh:
        written = fh.read()
    if hashlib.sha256(written).hexdigest() != digest:
        fail("SHA-256 mismatch after copy")
    print(f"main.py: wrote {DST} ({len(data)} bytes, {width}x{height}, "
          f"sha256 {digest})")


if __name__ == "__main__":
    main()
