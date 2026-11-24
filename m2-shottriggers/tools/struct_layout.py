#!/usr/bin/env python3
"""Compute the binary layout of an M2 save struct from its PSB definition
(e.g. RomFS 102/config/title_struct_systemdata.psb -> save file data_008_0000.bin).

Rules (verified against ESP Ra.De. Psi; file size and several known values match):
  * fields are laid out in key-sorted order (PSB object order), nested structs inline
  * natural alignment: u16 -> 2, u32 -> 4; structs themselves are not padded
  * type codes:  3 = u16   4 = u32   6 = char[n]   8 = struct   10 = u8[n]
                 11 = u16[n]   12 = u32[n]   16 = struct[n]
  * a negative count (e.g. "_90_boundary": [10, -5184]) moves the cursor BACK by that many bytes
    (used to keep the total size fixed); later fields overlap the padding of earlier ones

Usage: struct_layout.py STRUCT.psb [root_struct] [--all]
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from psb_dump import PSB

ARR = {10: (1, 'u8'), 11: (2, 'u16'), 12: (4, 'u32'), 6: (1, 'char')}


def layout(defs, sname, off, out, prefix=''):
    for k in sorted(defs[sname]):
        t = defs[sname][k]; c = t[0]
        if c == 8:
            off = layout(defs, t[1], off, out, prefix + k + '.')
        elif c == 16:
            for i in range(t[2]):
                off = layout(defs, t[1], off, out, f'{prefix}{k}[{i}].')
        elif c == 4:
            off += -off % 4; out[prefix + k] = (off, 'u32', 1); off += 4
        elif c == 3:
            off += -off % 2; out[prefix + k] = (off, 'u16', 1); off += 2
        elif c in ARR:
            es, name = ARR[c]; n = t[1]
            off += -off % es; out[prefix + k] = (off, name, n); off += es * n
        else:
            raise ValueError(f'unknown type {t} at {prefix}{k}')
    return off


if __name__ == '__main__':
    defs = PSB(open(sys.argv[1], 'rb').read()).root()
    rootname = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith('--') else 'struct_systemdata'
    out = {}
    total = layout(defs, rootname, 0, out)
    for k, (o, t, n) in sorted(out.items(), key=lambda x: x[1][0]):
        if '--all' not in sys.argv and '[' in k and '[0]' not in k:
            continue
        print(f'0x{o:06x}  {t:<4} x{n:<5} {k}')
    print(f'total 0x{total:x} ({total})')
