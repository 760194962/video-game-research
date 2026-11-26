#!/usr/bin/env python3
"""ESP Ra.De. Psi (Switch, 0100F9600E746000, v1.0.5 / v327680) — unlock patcher for data_008_0000.bin.

Usage:
    esprade_unlock.py alice SRC DST   # Alice Master (all modes) + Irori's Room 4 characters
    esprade_unlock.py all   SRC DST   # alice + everything below (100%)

Best applied to a fresh/initial save. Only data_008_0000.bin is touched; there is no checksum.
All offsets are derived from RomFS 102/config/title_struct_systemdata.psb and the game's Squirrel
scripts (title_const.nut etc.). See ../README.md.
"""
import struct, sys

SIZE = 0x34400
HIST = 0xE000                 # _24_battle_history._00_data      u32[256]   (enum HISTORY)
SCORE = 0xE408                # _24_battle_history._10_score_record u32[8192]
ROOM = SCORE + 3328 * 4       # HISTORY_SCORE_OFFSET_ROOM = 3328  -> 0x11808

H_BOSS_DEFEAT_SB_S = 93       # secret boss (Alice) defeated; S/P/C = 93/94/95
H_CREDIT = 149                # credit-limit step, 8 = unlimited credits (no FREE PLAY option in this title)

# Irori's Room (index into ROOM, u32 each)
R_CHARA, R_EXP, R_ALICE_OPENED = 0, 1, 14
R_JUDGE_MONEY, R_NEXT_TICKET_MONEY = 9, 15
FUKUBIKI_UNIT_PRICE = 1000
R_LAYOUT, R_LAYOUT_SIZE = 40, 80
L_EMOTE, L_PET_TYPE_1, L_PET_EXP_1 = 0, 57, 61
R_ITEM = 360
ITEM_CATS = [(0, 3), (30, 5), (60, 5), (90, 6), (120, 5), (150, 3), (180, 71), (370, 4)]  # (offset, count)
R_PET = 760
PET_COUNTS = [5, 6, 5, 5]                         # dog, cat, bird, hamster
R_MISSION = 800                                   # + chara*800 + (mission-1)*8
MISSIONS = [*range(1, 11), *range(11, 42), *range(71, 76), *range(81, 89), *range(91, 97)]  # 60
R_ACC = 4000                                      # + type*20 + chara*5 + part
ACC_COUNTS = [[5, 7, 9, 2, 4], [3, 6, 7, 2, 4], [4, 18, 5, 1, 3], [6, 12, 4, 2, 6]]  # [chara][part]
EXP_MAX = 4860000                                 # Lv99 for characters and pets


def main(mode, src, dst):
    d = bytearray(open(src, 'rb').read())
    assert len(d) == SIZE, 'unexpected data_008 size'
    r = lambda o: struct.unpack_from('<i', d, o)[0]
    w = lambda o, v: struct.pack_into('<i', d, o, v)
    def atleast(o, v):
        if r(o) < v: w(o, v)
    room = lambda i: ROOM + i * 4

    # --- Alice ---
    atleast(HIST + H_BOSS_DEFEAT_SB_S * 4, 1)            # Alice selectable in Arcade Plus / Super Easy / Custom
    w(room(R_ALICE_OPENED), r(room(R_ALICE_OPENED)) | 15)  # Irori's Room: all 4 rooms opened

    # If the room was never entered, the game forces a "pick a room to unlock" screen that soft-locks
    # when every room is already opened. Skip it and replicate what that first visit initialises.
    if r(room(R_CHARA)) == 0:
        w(room(R_CHARA), 3)                              # current room = Irori (1-based)
        for it in (0, 30, 120):
            atleast(room(R_ITEM + it), 1)                # starter furniture
        for k in range(4):
            atleast(room(R_PET + 10 * k), 1)             # starter pet of each kind
        for ch in range(4):
            L = R_LAYOUT + ch * R_LAYOUT_SIZE
            for k in range(4):
                atleast(room(L + L_PET_TYPE_1 + k), 1)
            w(room(L + L_EMOTE), 1 * 7 + 3)              # character stands at (3,1)

    if mode == 'all':
        atleast(HIST + H_CREDIT * 4, 8)
        for off, n in ITEM_CATS:
            for i in range(n):
                atleast(room(R_ITEM + off + i), 1)
        for k, n in enumerate(PET_COUNTS):
            for p in range(n):
                atleast(room(R_PET + 10 * k + p), 1)
        for ch in range(4):
            for part in range(5):
                for t in range(ACC_COUNTS[ch][part]):
                    atleast(room(R_ACC + 20 * t + 5 * ch + part), 1)
        for ch in range(4):
            atleast(room(R_EXP + ch), EXP_MAX)
            for k in range(4):
                atleast(room(R_LAYOUT + ch * R_LAYOUT_SIZE + L_PET_EXP_1 + k), EXP_MAX)
            for m in MISSIONS:
                base = R_MISSION + ch * 800 + (m - 1) * 8
                atleast(room(base + 0), 1)               # played
                atleast(room(base + 2), 1)               # cleared
                w(room(base + 5), 16)                    # star: 16 = perfect
        # JUDGE MONEY only ever increases, by the same amount as the clearing character's EXP,
        # so a consistent save has money >= sum of character EXP. One ticket per 1000 earned:
        # next-ticket threshold = 100 + tickets_given * 1000.
        money = max(r(room(R_JUDGE_MONEY)), sum(r(room(R_EXP + ch)) for ch in range(4)))
        w(room(R_JUDGE_MONEY), money)
        w(room(R_NEXT_TICKET_MONEY), 100 + ((money - 100) // FUKUBIKI_UNIT_PRICE + 1) * FUKUBIKI_UNIT_PRICE)

    open(dst, 'wb').write(d)


if __name__ == '__main__':
    if len(sys.argv) != 4 or sys.argv[1] not in ('alice', 'all'):
        sys.exit(__doc__)
    main(*sys.argv[1:])
