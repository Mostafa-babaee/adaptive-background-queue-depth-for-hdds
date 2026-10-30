#!/usr/bin/env python3
"""
make_testfiles.py - create or verify a disposable test file with a known data pattern.
CSC 720 Project 03 (Adaptive HDD Queue Depth), Milestone 1.

Every 4 KiB block (4096 bytes) of the file looks like this (little-endian uint64 words):
    word 0      MAGIC = 0x5453455451444448  ("HDDQTEST" as ASCII)
    word 1      file_id     (e.g. 1 = foreground file, 2 = background file)
    word 2      block_no    (offset / 4096)
    words 3-511 filler = (block_no * 0x9E3779B97F4A7C15 + file_id) mod 2^64

So any read at a 4 KiB-aligned offset can be checked in C by comparing word 0..2
(and optionally the filler), without keeping a copy of the file.

Usage:
    python3 make_testfiles.py <path> <size_MiB> <file_id>        # create
    python3 make_testfiles.py --verify <path> <file_id>          # verify whole file
Only use this inside the instructor-approved test directory. It refuses to overwrite.
"""
import os
import struct
import sys
import time

BLOCK = 4096
MAGIC = 0x5453455451444448
GOLDEN = 0x9E3779B97F4A7C15
MASK = (1 << 64) - 1
CHUNK_BLOCKS = 256  # write 1 MiB at a time


def block_bytes(file_id: int, block_no: int) -> bytes:
    filler = (block_no * GOLDEN + file_id) & MASK
    return struct.pack("<QQQ", MAGIC, file_id, block_no) + struct.pack("<Q", filler) * 509


def create(path: str, size_mib: int, file_id: int) -> None:
    if not 1 <= size_mib <= 8192 or not 0 <= file_id <= MASK:
        raise ValueError('size must be 1..8192 MiB and file_id an unsigned 64-bit integer')
    if os.path.exists(path):
        sys.exit(f"refusing to overwrite existing file: {path}")
    nblocks = size_mib * 1024 * 1024 // BLOCK
    t0 = time.time()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_BINARY', 0), 0o644)
    try:
        for start in range(0, nblocks, CHUNK_BLOCKS):
            end = min(start + CHUNK_BLOCKS, nblocks)
            buf = b"".join(block_bytes(file_id, b) for b in range(start, end))
            view = memoryview(buf)
            while view:
                written = os.write(fd, view)
                if written <= 0:
                    raise OSError('fixture write made no progress')
                view = view[written:]
            if start % (CHUNK_BLOCKS * 1024) == 0 and start:
                print(f"  {start * BLOCK >> 20} MiB written", flush=True)
        os.fsync(fd)
    finally:
        os.close(fd)
    print(f"created {path}: {size_mib} MiB, {nblocks} blocks, file_id={file_id}, "
          f"{time.time() - t0:.1f} s")


def verify(path: str, file_id: int) -> None:
    size = os.path.getsize(path)
    if size % BLOCK:
        sys.exit(f"FAIL: size {size} is not a multiple of {BLOCK}")
    nblocks = size // BLOCK
    bad = 0
    with open(path, "rb") as f:
        for b in range(nblocks):
            data = f.read(BLOCK)
            if data != block_bytes(file_id, b):
                bad += 1
                if bad <= 5:
                    m, fid, bn = struct.unpack_from("<QQQ", data)
                    print(f"  bad block {b}: magic={m:#x} file_id={fid} block_no={bn}")
    if bad:
        sys.exit(f"FAIL: {bad} of {nblocks} blocks wrong in {path}")
    print(f"OK: {path} ({nblocks} blocks, file_id={file_id}) matches the pattern")


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) == 3 and a[0] == "--verify":
        verify(a[1], int(a[2]))
    elif len(a) == 3:
        create(a[0], int(a[1]), int(a[2]))
    else:
        sys.exit(__doc__)
