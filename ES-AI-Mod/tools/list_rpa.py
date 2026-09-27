#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""List file names inside a Ren'Py RPA archive (RPA-3.0 / RPA-2.0), no extraction.

Usage: python list_rpa.py <archive.rpa> [filter_regex]
"""
import re
import struct
import sys
import zlib


def read_index(path):
    with open(path, "rb") as f:
        header = f.read(40)
        if header.startswith(b"RPA-3.0"):
            offset = int(header[8:8 + 16], 16)
            key = int(header[24:24 + 8], 16)
            f.seek(offset)
            index_bin = f.read()
            index_bin = zlib.decompress(index_bin)
            index = pickle_loads(index_bin, key)
            return index
        elif header.startswith(b"RPA-2.0"):
            offset = int(header[7:7 + 16], 16)
            f.seek(offset)
            index_bin = zlib.decompress(f.read())
            index = pickle_loads(index_bin, 0)
            return index
        elif header.startswith(b"UnRPA"):
            # not handled
            raise SystemExit("Unsupported archive format")
        else:
            raise SystemExit("Not an RPA archive (RPA-1.0 unsupported)")


def pickle_loads(data, key):
    # Minimal RPA index unpickler: the index is a pickle of
    # {name: [(offset_xor, length, prefix_bytes_or_null), ...]}
    # We replicate with a tiny safe loader instead of pickle.loads.
    # The pickle protocol is 2; easiest is to use pickle with a fake Unpickler
    # that xors offsets. Simpler approach: use pickle.loads after xoring is
    # impossible (xor applies to ints inside). So use real pickle with a
    # controlled Unpickler (no GLOBAL/REDUCE execution needed for RPA-3.0).
    import io
    import pickle

    class SafeUnpickler(pickle.Unpickler):
        def find_class(self, module, name):
            raise pickle.UnpicklingError("global forbidden: %s.%s" % (module, name))

    obj = SafeUnpickler(io.BytesIO(data)).load()
    out = {}
    if key:
        for name, entries in obj.items():
            fixed = []
            for off, ln, prefix in entries:
                fixed.append((off ^ key, ln, prefix))
            out[name] = fixed
    else:
        out = obj
    return out


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    index = read_index(sys.argv[1])
    names = sorted(index.keys())
    filt = None
    if len(sys.argv) > 2:
        filt = re.compile(sys.argv[2])
    for n in names:
        if filt is None or filt.search(n):
            print(n)
    print("TOTAL: %d files" % len(names), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
