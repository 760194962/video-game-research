#!/usr/bin/env python3
"""THE IDOLM@STER (Xbox 360, 4E4D07DB) gamedata helper.

Usage:
  python3 gamedata.py info   gamedata            # summary
  python3 gamedata.py fixcrc gamedata [out]      # recompute header CRC
  python3 gamedata.py winrate100 gamedata out    # passes = auditions (producer + all unit slots)
  python3 gamedata.py rename gamedata out NAME   # producer name (max 8 chars, UTF-16BE)

Offsets are documented in docs/gamedata-format.md.
"""
import binascii
import re
import struct
import sys

SIZE = 4718624
PROD_NAME = (0x80, 0xB460)          # producer name, two copies
PEVA = 0xA0                         # producer counters, 24 x int32
ACC_COUNT, ACC_BASE, ACC_STRIDE, ACC_CAP = 0xCE50, 0xCE60, 0x50, 246
TROPHY_COUNT, TROPHY_BASE = 0x11B40, 0x11B50
SLOT_BASE, SLOT_SIZE, SLOTS = 0x11FC0, 0xB10, 10
UNIT_COUNT = 0x39D0D0               # number of units listed on the unit-select screen
IDOLS = {1: '春香', 2: '千早', 3: '雪歩', 4: 'やよい', 5: '律子', 6: 'あずさ',
         7: '伊織', 8: '真', 9: '亜美', 10: '真美', 11: '美希'}
TROPHIES = ['10アイドル', '16ソング', '4シーズン', 'スーパーアイドル', 'ベストエンディング',
            'A100', 'C100', 'L100', 'M100', '真アイドルマスター']


def crc(g):
    return binascii.crc_hqx(bytes(g[0x10:]), 0xFFFF)   # CRC-16/CCITT-FALSE


def fix_crc(g):
    g[0:2] = struct.pack('>H', crc(g))


def u32(g, o):
    return struct.unpack('>I', g[o:o + 4])[0]


def i32s(g, o, n):
    return list(struct.unpack('>%di' % n, g[o:o + 4 * n]))


def wstr(g, o, n=16):
    return bytes(g[o:o + n]).decode('utf-16-be', 'replace').rstrip('\0')


def info(g):
    print('size', len(g), 'ok' if len(g) == SIZE else 'UNEXPECTED')
    print('crc', 'ok' if u32(g, 0) >> 16 == crc(g) else 'BAD')
    print('producer', wstr(g, PROD_NAME[0]))
    p = i32s(g, PEVA, 24)
    print('auditions %d / passed %d' % (p[0], p[1]))
    print('producer PEVA', p)
    n = u32(g, ACC_COUNT)
    ids = [u32(g, ACC_BASE + k * ACC_STRIDE + 0x10) for k in range(n)]
    print('accessory+costume records', n, '(accessories %d, costumes %d)'
          % (sum(1 for i in ids if i < 182 or i > 238), sum(1 for i in ids if 182 <= i <= 238)))
    t = u32(g, TROPHY_COUNT)
    # records are in acquisition order; the trophy ID (1-10) is the data word at +0x10
    got = [TROPHIES[u32(g, TROPHY_BASE + k * 0x20 + 0x10) - 1] for k in range(min(t, 10))
           if g[TROPHY_BASE + k * 0x20:TROPHY_BASE + k * 0x20 + 8] == b'PTRP TAG']
    print('trophies', t, got)
    print('4 seasons mask (PEVA[19]) 0x%02X / 0xFF' % (p[19] & 0xFF))
    print('units listed', u32(g, UNIT_COUNT))
    for k in range(SLOTS):
        s = bytes(g[SLOT_BASE + k * SLOT_SIZE:SLOT_BASE + (k + 1) * SLOT_SIZE])
        if struct.unpack('>i', s[0x350:0x354])[0] == -1 or not s[0x40:0x44].strip(b'\0'):
            continue
        idols = [struct.unpack('>I', s[m.start() + 16:m.start() + 20])[0] for m in re.finditer(rb'IDOL TAG', s)]
        print('  slot %d: %s  idols %s  fans %d' % (k, wstr(s, 0x390), [IDOLS.get(i, i) for i in idols],
                                                    struct.unpack('>i', s[0x358:0x35C])[0]))


def winrate100(g):
    offs = [PEVA] + [SLOT_BASE + k * SLOT_SIZE + 0x4C0 for k in range(SLOTS)]
    for o in offs:
        g[o + 4:o + 8] = g[o:o + 4]


def rename(g, name):
    b = name.encode('utf-16-be')
    if len(b) > 16:
        sys.exit('name too long (max 8 chars)')
    for o in PROD_NAME:
        g[o:o + 16] = b.ljust(16, b'\0')


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    cmd, path = sys.argv[1], sys.argv[2]
    g = bytearray(open(path, 'rb').read())
    if cmd == 'info':
        info(g)
        return
    out = sys.argv[3] if len(sys.argv) > 3 else path
    if cmd == 'winrate100':
        winrate100(g)
    elif cmd == 'rename':
        rename(g, sys.argv[4])
    elif cmd != 'fixcrc':
        sys.exit(__doc__)
    fix_crc(g)
    open(out, 'wb').write(g)
    print('written', out)


if __name__ == '__main__':
    main()
