#!/usr/bin/env python3
"""Build the one-achievement-per-unit saves from the old all-in-one save.

The base save was removed from the tree; get it with
  git show 5321443:saves/achievement-set/gamedata > base_gamedata

Usage:
  python3 unitset.py BASE_GAMEDATA MAIN_OUT COMBINED_OUT SHIN_OUT

MAIN_OUT: 9 units, each set up so that one achievement unlocks through normal play.
COMBINED_OUT: same, but the 10アイドル unit also has the last song, so one ending
          gives 10アイドル and 16ソング together.
SHIN_OUT: 1 unit for 真アイドルマスター (needs producer level 8 and all 10 idol counters,
          which would interfere with the main save; see docs/achievements.md).

Offsets are documented in docs/gamedata-format.md.
"""
import re
import struct
import sys

from gamedata import (PEVA, SLOT_BASE, SLOT_SIZE, SLOTS, TROPHY_BASE, TROPHY_COUNT,
                      UNIT_COUNT, fix_crc, i32s)

PROD_LEVEL = 0x11C90          # producer +0x48, 0..9 (9 = 真アイドルマスター)
IDOL_COUNTS = 0x11F90         # producer +0x60, 10 x i32, index = idol ID - 1 (亜美/真美 8, 美希 9)
UNIT_NAME = 0x390
UNIT_FLAGS = 0xAC4            # unit +0x370: audition-passed bits (0x4000 SUPER IDOL, 0x8 GP shown)
SONG_LIST = 0x520             # u32 count, then SONG TAG x 6 (0x20 each, data word 0 = song ID)
SUPER_IDOL, GP_DONE = 0x4000, 0x8
AMI = 9                       # 10アイドル target: the only idol never retired in this save
LAST_SONG = 5                 # 16ソング target: the only song missing from PEVA[21]
EMPTY_SLOT = 3                # an unused slot in the base save, copied to clear slots

# slot: (achievement, source slot in base save, unit name)
MAIN = [
    ('A100', 1, 'Ａ１００'),
    ('C100', 1, 'Ｃ１００'),
    ('L100', 1, 'Ｌ１００'),
    ('M100', 1, 'Ｍ１００'),
    ('4シーズン', 0, '４シーズン'),
    ('スーパーアイドル', 2, 'スーパーアイドル'),
    ('ベストエンディング', 2, 'ベストＥＤ'),
    ('16ソング', 0, '１６ソング'),
    ('10アイドル', 0, '１０アイドル'),
]


def slot(g, k):
    return SLOT_BASE + k * SLOT_SIZE


def put_i32(g, o, v):
    g[o:o + 4] = struct.pack('>i', v)


def get_i32(g, o):
    return struct.unpack('>i', g[o:o + 4])[0]


def copy_slot(g, base, dst, src):
    g[slot(g, dst):slot(g, dst) + SLOT_SIZE] = base[slot(base, src):slot(base, src) + SLOT_SIZE]


def set_name(g, k, name):
    b = name.encode('utf-16-be')
    assert len(b) <= 16, name
    o = slot(g, k) + UNIT_NAME
    g[o:o + 16] = b.ljust(16, b'\0')


def clear_flag(g, k, bit):
    o = slot(g, k) + UNIT_FLAGS
    put_i32(g, o, get_i32(g, o) & ~bit)


def set_flag(g, k, bit):
    o = slot(g, k) + UNIT_FLAGS
    put_i32(g, o, get_i32(g, o) | bit)


def idol_tags(g, k):
    s = slot(g, k)
    t = bytes(g[s:s + SLOT_SIZE])
    tags = [s + m.start() for m in re.finditer(rb'IDOL TAG', t)]   # each is followed by its ACDT TAGs
    assert len(tags) == get_i32(g, s + 0x20)
    return tags


def songs(g, k):
    o = slot(g, k) + SONG_LIST
    return [o + 0x10 + i * 0x20 for i in range(get_i32(g, o))]


def song_ids(g, k):
    return [get_i32(g, r + 0x10) for r in songs(g, k)]


def set_trophies(g, ids):
    g[TROPHY_BASE:TROPHY_BASE + 10 * 0x20] = bytes(10 * 0x20)
    for n, t in enumerate(ids):
        r = TROPHY_BASE + n * 0x20
        g[r:r + 16] = b'PTRP TAG' + struct.pack('>II', 1, 0)
        put_i32(g, r + 0x10, t)
    put_i32(g, TROPHY_COUNT, len(ids))


def build_main(base, combined=False):
    g = bytearray(base)
    for k in range(SLOTS):
        copy_slot(g, base, k, EMPTY_SLOT)
    for k, (_, src, name) in enumerate(MAIN):
        copy_slot(g, base, k, src)
        set_name(g, k, name)
        clear_flag(g, k, SUPER_IDOL)                     # else スーパーアイドル on the first night
        set_flag(g, k, GP_DONE)                          # hides the GP audition (4シーズン's last bit)
    clear_flag(g, 4, GP_DONE)                             # ...except here, in weeks 47-50
    # 10アイドル: one 雪歩 -> 亜美, and 亜美's counter is the only zero one
    r = idol_tags(g, 8)[2]
    assert get_i32(g, r + 0x10) == 3
    put_i32(g, r + 0x10, AMI)
    # 16ソング: the oldest song of this unit becomes the one song never retired with
    song_slots = (7, 8) if combined else (7,)
    for k in song_slots:
        r = songs(g, k)[-1]
        put_i32(g, r + 0x10, LAST_SONG)

    p = i32s(g, PEVA, 24)
    p[0] = p[1] = 99                                      # A100: passes >= 100
    p[11], p[12] = 99 - p[12], p[12]                      # C100: [11] + [12] >= 100
    p[15], p[16] = p[15], 99 - p[15]                      # L100: [15] + [16] >= 100
    p[19] = 0xFF & ~0x40                                  # 4シーズン: GP audition (0x25) bit missing
    p[20] = 99                                            # M100: memories >= 100
    p[21] = 0xFFFF & ~(1 << LAST_SONG)                    # 16ソング
    g[PEVA:PEVA + 96] = struct.pack('>24i', *p)
    put_i32(g, PROD_LEVEL, 7)                             # 7 -> at most 8 per ending, never 9
    counts = i32s(g, IDOL_COUNTS, 10)
    counts = [max(c, 1) for c in counts]
    counts[AMI - 1] = 0
    g[IDOL_COUNTS:IDOL_COUNTS + 40] = struct.pack('>10i', *counts)
    set_trophies(g, [])
    put_i32(g, UNIT_COUNT, len(MAIN))

    # the target song and idol must not be in any other unit
    for k in range(len(MAIN)):
        assert (LAST_SONG in song_ids(g, k)) == (k in song_slots), k
        assert (AMI in [get_i32(g, r + 0x10) for r in idol_tags(g, k)]) == (k == 8), k
    fix_crc(g)
    return g


def build_shin(base):
    g = bytearray(base)
    for k in range(SLOTS):
        copy_slot(g, base, k, EMPTY_SLOT)
    copy_slot(g, base, 0, 2)                              # S rank, 2 weeks before the ending
    set_name(g, 0, '真アイマス')
    put_i32(g, PROD_LEVEL, 8)                             # 8 + total >= 75 at the ending -> 9
    counts = [max(c, 1) for c in i32s(g, IDOL_COUNTS, 10)]
    g[IDOL_COUNTS:IDOL_COUNTS + 40] = struct.pack('>10i', *counts)
    set_trophies(g, list(range(1, 10)))                   # everything except 10 is already owned
    put_i32(g, UNIT_COUNT, 1)
    fix_crc(g)
    return g


def main():
    if len(sys.argv) != 5:
        sys.exit(__doc__)
    base = open(sys.argv[1], 'rb').read()
    for path, g in ((sys.argv[2], build_main(base)), (sys.argv[3], build_main(base, combined=True)),
                    (sys.argv[4], build_shin(base))):
        open(path, 'wb').write(g)
        print('written', path)


if __name__ == '__main__':
    main()
