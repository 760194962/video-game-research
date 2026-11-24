#!/usr/bin/env python3
"""Extract / inject `gamedata` from / into the Xbox 360 save package (STFS "CON ") in place.

Usage:
  python3 stfs_gamedata.py extract PACKAGE gamedata_out
  python3 stfs_gamedata.py inject  PACKAGE gamedata_in PACKAGE_out

`inject` only overwrites the data blocks, so the package keeps its size (4,837,376 bytes).
Hash tables and the signature are NOT updated: open the result in Horizon and use
"Save, Rehash and Resign" (do not use Horizon's "replace file", it re-allocates the
package and doubles its size).

Only the layout seen in this game's save is supported: contiguous file, 0xAA blocks per
level-0 hash table, two copies of each hash block. Verified by round-tripping the
original package.
"""
import struct
import sys


def data_block_offset(base, n):
    if n < 170:
        r = n + 2
    else:
        r = 176 + 172 * (n // 170 - 1) + (n % 170)
    return base + r * 0x1000


def open_pkg(path):
    d = bytearray(open(path, 'rb').read())
    if d[:4] != b'CON ':
        sys.exit('not a CON package')
    hs = struct.unpack('>I', d[0x340:0x344])[0]
    base = (hs + 0xFFF) & ~0xFFF
    vd = 0x379
    ftb = int.from_bytes(d[vd + 5:vd + 8], 'little')
    ft = data_block_offset(base, ftb)
    for j in range(64):
        e = d[ft + j * 64: ft + j * 64 + 64]
        name = e[:40].split(b'\0')[0]
        if name == b'gamedata':
            flags = e[0x28]
            nblk = int.from_bytes(e[0x29:0x2C], 'little')
            start = int.from_bytes(e[0x2F:0x32], 'little')
            size = struct.unpack('>I', e[0x34:0x38])[0]
            if not flags & 0x40:
                sys.exit('gamedata is not contiguous; unsupported')
            return d, base, start, nblk, size
    sys.exit('gamedata not found in file table')


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    cmd, pkg = sys.argv[1], sys.argv[2]
    d, base, start, nblk, size = open_pkg(pkg)
    if cmd == 'extract':
        out = b''.join(bytes(d[data_block_offset(base, start + k):data_block_offset(base, start + k) + 0x1000])
                       for k in range(nblk))[:size]
        open(sys.argv[3], 'wb').write(out)
        print('extracted', size, 'bytes')
    elif cmd == 'inject':
        g = open(sys.argv[3], 'rb').read()
        if len(g) != size:
            sys.exit('size mismatch: package has %d, file is %d' % (size, len(g)))
        for k in range(nblk):
            o = data_block_offset(base, start + k)
            chunk = g[k * 0x1000:(k + 1) * 0x1000]
            d[o:o + len(chunk)] = chunk
        open(sys.argv[4], 'wb').write(d)
        print('injected; now Rehash + Resign in Horizon')
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main()
