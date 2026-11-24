#!/usr/bin/env python3
"""sh4save - Silent Hill 4: The Room (Xbox, NTSC-U) save tool.

Decode / encode the save obfuscation, check and replace the Xbox save
signature (retail consoles and xemu  <->  xbased), show what a save
contains, and apply a few documented edits (unlock flags, Eileen's
possession).

Everything here comes from reverse engineering default.xbe of
"Silent Hill 4 - The Room (USA)" (title ID 4B4E001F); see README.md.
Only the Python standard library is used.
"""
import argparse
import hashlib
import hmac
import os
import random
import struct
import sys

# --------------------------------------------------------------------------
# File kinds
# --------------------------------------------------------------------------
SLOT_BODY = 0x5A30          # 23088 bytes: one save slot (sh4_save_NN.dat)
COMMON_BODY = 0x5E0         # 1504 bytes: system data (sh4_common.dat)
SIG_LEN = 20                # Xbox files carry an HMAC-SHA1 at the end
SLOT_KEY_OFF = 0x28         # where the obfuscation key is stored
COMMON_KEY_OFF = 0x10

XBOX_SLOT_MAGIC = 0x53D4    # Xbox slot header: "used size" of the struct
PS2_SLOT_MAGIC = 0x5A20     # PS2 slot header (different block layout)

# XboxSignatureKey values the game ends up signing with (XCalculateSignature,
# roamable).  "retail" is the per-title key a real console / Xbox 360 /
# xemu-with-retail-BIOS derives for the NTSC-U disc; xbased's HLE kernel
# exports 16 zero bytes instead.
SIGKEYS = {
    "retail": bytes.fromhex("2dc1fd8c6f2ee0524a766d37e586b742"),
    "xbased": bytes(16),
}

DIFFICULTY = {1: "Easy", 2: "Normal", 3: "Hard"}
MODE = {0: "normal", 1: "One Weapon", 2: "All Weapons"}
# ending index -> bit (1 << index) in the endings mask
ENDINGS = {1: "Escape", 2: "Mother", 3: "Eileen's Death", 4: "21 Sacraments"}
ALL_ENDINGS = 0x1E


# --------------------------------------------------------------------------
# Obfuscation (default.xbe 0xFE4D0)
# --------------------------------------------------------------------------
def xcrypt(data, key):
    """3-byte rolling XOR. key>>24 is the step, the low 24 bits the seed.
    Symmetric: the same call encodes and decodes."""
    k = [(key >> 16) & 0xFF, (key >> 8) & 0xFF, key & 0xFF]
    step = (key >> 24) & 0xFF
    out = bytearray(len(data))
    i = 0
    for n, c in enumerate(data):
        out[n] = c ^ k[i]
        k[i] = (k[i] + step) & 0xFF
        i = (i + 1) % 3
    return out


def new_key():
    """Like the game: step 8..247, random 24-bit seed."""
    return ((random.randrange(0xF0) + 8) << 24) | random.getrandbits(24)


def decode(body, key_off):
    key = struct.unpack_from("<I", body, key_off)[0]
    plain = xcrypt(body, key)
    struct.pack_into("<I", plain, key_off, key)   # the game keeps the key here
    return plain, key


def encode(plain, key_off, key):
    p = bytearray(plain)
    struct.pack_into("<I", p, key_off, key)
    out = xcrypt(p, key)
    struct.pack_into("<I", out, key_off, key)     # stored in clear
    return out


# --------------------------------------------------------------------------
# Signature
# --------------------------------------------------------------------------
def sign(body, sigkey):
    return hmac.new(sigkey, bytes(body), hashlib.sha1).digest()


def which_key(raw):
    body, sig = raw[:-SIG_LEN], raw[-SIG_LEN:]
    for name, k in SIGKEYS.items():
        if sign(body, k) == sig:
            return name
    return None


def parse_sigkey(s):
    if s in SIGKEYS:
        return SIGKEYS[s]
    k = bytes.fromhex(s)
    if len(k) != 16:
        raise SystemExit("signature key must be 16 bytes (32 hex digits)")
    return k


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------
class Save:
    """A loaded Xbox save file (slot or common)."""

    def __init__(self, path):
        self.path = path
        raw = open(path, "rb").read()
        if len(raw) == SLOT_BODY + SIG_LEN:
            self.kind, self.key_off = "slot", SLOT_KEY_OFF
        elif len(raw) == COMMON_BODY + SIG_LEN:
            self.kind, self.key_off = "common", COMMON_KEY_OFF
        else:
            raise SystemExit("%s: %d bytes is not an Xbox SH4 slot (%d) or "
                             "common file (%d)" % (path, len(raw),
                                                   SLOT_BODY + SIG_LEN,
                                                   COMMON_BODY + SIG_LEN))
        self.signed_with = which_key(raw)
        self.plain, self.key = decode(raw[:-SIG_LEN], self.key_off)

    def save(self, path=None, sigkey=None, fresh_key=False):
        if sigkey is None:
            if self.signed_with is None:
                raise SystemExit("%s: unknown signature key; pass --sigkey"
                                 % self.path)
            sigkey = SIGKEYS[self.signed_with]
        key = new_key() if fresh_key else self.key
        body = encode(self.plain, self.key_off, key)
        open(path or self.path, "wb").write(bytes(body) + sign(body, sigkey))


# --------------------------------------------------------------------------
# Slot layout (Xbox)
# --------------------------------------------------------------------------
# Header, written by 0xFE640 and read back by 0xFEA60:
#  +00 u32 used size (0x53D4)      +04 u32 play time (1/30 s)
#  +0C u32 difficulty 1..3          +10 u16 endings mask
#  +12 u16 costume selected         +14 u32 / +18 u32 position ids
#  +1C u8  nurse costume unlocked   +1D u8  all endings seen
#  +1E u16 best rank (0..100)       +20 u32 continues
#  +24 u32 enemies defeated         +28 u32 obfuscation key
#  +2C u32[12] block offsets
EILEEN_BLOCK_INDEX = 6               # 7th block: Eileen (0x4BCC on Xbox)


def blocks(p):
    return list(struct.unpack_from("<12I", p, 0x2C))


def eileen_off(p):
    return blocks(p)[EILEEN_BLOCK_INDEX]


def eileen_fields(p):
    b = eileen_off(p)
    f = lambda o, fmt: struct.unpack_from(fmt, p, b + o)[0]
    return {
        "current": f(0x20, "<f"),      # actor+0x08, possession now (0..1)
        "damage": f(0x24, "<f"),       # actor+0x14, cumulative damage
        "A": f(0x30, "<H"), "B": f(0x2E, "<H"), "C": f(0x32, "<H"),
        "G": f(0x34, "<H"), "H": f(0x36, "<H"),
        "E": f(0x38, "<I"), "D": f(0x3C, "<I"),
    }


def possession_baseline(e):
    """default.xbe 0x45B40: the level Eileen's possession drifts back to."""
    cl = lambda v, a, b: max(a, min(b, v))
    if e["A"] < 10:
        return 0.0
    r1 = cl(e["D"] / e["E"] - 0.5, 0, 1) if e["E"] else 0.0
    t1 = (e["B"] + (e["A"] - e["C"])) / e["A"] - 0.2 * r1
    x = cl(0.05 * cl(e["G"], 0, 10) - 0.05 + t1
           + cl(e["damage"] * 0.0003, 0, 0.2)
           + cl(e["H"] * 0.02, 0, 0.5) - 0.2, 0, 0.8)
    return cl(x * 1.25, 0, 0.95)


def clear_eileen(p):
    b = eileen_off(p)
    a = struct.unpack_from("<H", p, b + 0x30)[0]
    struct.pack_into("<H", p, b + 0x2E, 0)        # B
    struct.pack_into("<H", p, b + 0x32, a)        # C = A
    struct.pack_into("<HH", p, b + 0x34, 0, 0)    # G, H
    struct.pack_into("<f", p, b + 0x24, 0.0)      # cumulative damage
    struct.pack_into("<f", p, b + 0x20, 0.0)      # current possession


def unlock_slot(p, rank=100):
    endings = struct.unpack_from("<H", p, 0x10)[0] | ALL_ENDINGS
    struct.pack_into("<H", p, 0x10, endings)
    p[0x1C] = 1                                   # nurse costume
    p[0x1D] = 1                                   # all endings (Cynthia)
    struct.pack_into("<H", p, 0x1E, rank)         # best rank


# --------------------------------------------------------------------------
# Common file: header + 30 directory entries of 0x30 bytes at +0x20
# (built by 0xFE860, read by the load menu)
# --------------------------------------------------------------------------
#  +00 u16 7 = used   +02 u16 1   +04 u32 play time   +10 u32 chapter (0x12 = clear data)
#  +14 u32 difficulty +18 u16 endings mask  +1A u8 this run's ending bit
#  +1B u8  this run's rank (200 = perfect)  +1C u32 save count
#  +20 u32 nurse costume unlocked  +24 u8 mode  +25 u8 All Weapons unlocked
#  +26 u16 best rank (>=100 opens One Weapon mode)
def entry_off(n):
    return 0x20 + n * 0x30


def unlock_entry(c, n, rank=100):
    e = entry_off(n)
    if c[e] != 7:
        raise SystemExit("directory entry %d is empty" % n)
    endings = struct.unpack_from("<H", c, e + 0x18)[0] | ALL_ENDINGS
    struct.pack_into("<H", c, e + 0x18, endings)
    struct.pack_into("<I", c, e + 0x20, 1)
    c[e + 0x25] = 1
    struct.pack_into("<H", c, e + 0x26, rank)


def fmt_time(t):
    s = t // 30
    return "%d:%02d:%02d" % (s // 3600, s // 60 % 60, s % 60)


def fmt_endings(m):
    names = [n for i, n in ENDINGS.items() if m & (1 << i)]
    return "%#x (%s)" % (m, ", ".join(names) or "none")


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------
def cmd_info(a):
    s = Save(a.file)
    p = s.plain
    print("%s: %s, signed with %s, obfuscation key %08x"
          % (a.file, s.kind, s.signed_with or "UNKNOWN key", s.key))
    if s.kind == "slot":
        u = lambda o, f: struct.unpack_from(f, p, o)[0]
        if u(0, "<I") != XBOX_SLOT_MAGIC:
            print("  unexpected header %#x" % u(0, "<I"))
        print("  play time      %s" % fmt_time(u(4, "<I")))
        print("  difficulty     %s" % DIFFICULTY.get(u(0xC, "<I"), u(0xC, "<I")))
        print("  endings        %s" % fmt_endings(u(0x10, "<H")))
        print("  costume        %s" % ("nurse" if u(0x12, "<H") else "normal"))
        print("  nurse unlocked %d   all endings %d   best rank %d"
              % (p[0x1C], p[0x1D], u(0x1E, "<H")))
        print("  continues      %d   enemies defeated %d"
              % (u(0x20, "<I"), u(0x24, "<I")))
        e = eileen_fields(p)
        print("  Eileen         current %.3f  baseline %.3f  damage %.2f"
              % (e["current"], possession_baseline(e), e["damage"]))
        print("                 A=%(A)d B=%(B)d C=%(C)d D=%(D)d E=%(E)d "
              "G=%(G)d H=%(H)d" % e)
    else:
        print("  last saved slot %d" % struct.unpack_from("<I", p, 4)[0])
        for n in range(30):
            e = entry_off(n)
            if p[e] != 7:
                continue
            g = lambda o, f: struct.unpack_from(f, p, e + o)[0]
            line = ("  %02d  %s  %-6s  chapter %#04x  endings %#x  saves %d"
                    % (n + 1, fmt_time(g(4, "<I")),
                       DIFFICULTY.get(g(0x14, "<I"), "?"), g(0x10, "<I"),
                       g(0x18, "<H"), g(0x1C, "<I")))
            line += "  nurse %d  mode %s  AW %d  best %d" % (
                g(0x20, "<I"), MODE.get(p[e + 0x24], p[e + 0x24]),
                p[e + 0x25], g(0x26, "<H"))
            if g(0x10, "<I") == 0x12:
                line += "  [clear: ending %#x rank %d]" % (p[e + 0x1A],
                                                          p[e + 0x1B])
            print(line)


def cmd_decode(a):
    s = Save(a.file)
    open(a.out, "wb").write(s.plain)
    print("%s -> %s (%s, %d bytes)" % (a.file, a.out, s.kind, len(s.plain)))


def cmd_encode(a):
    plain = open(a.file, "rb").read()
    if len(plain) == SLOT_BODY:
        ko = SLOT_KEY_OFF
    elif len(plain) == COMMON_BODY:
        ko = COMMON_KEY_OFF
    else:
        raise SystemExit("plain body must be %d or %d bytes"
                         % (SLOT_BODY, COMMON_BODY))
    key = struct.unpack_from("<I", plain, ko)[0] if a.keep_key else new_key()
    body = encode(plain, ko, key)
    open(a.out, "wb").write(bytes(body) + sign(body, parse_sigkey(a.sigkey)))
    print("%s -> %s (key %08x, signed for %s)" % (a.file, a.out, key, a.sigkey))


def cmd_resign(a):
    s = Save(a.file)
    s.save(a.out, parse_sigkey(a.to))
    print("%s: %s -> %s%s" % (a.file, s.signed_with or "unknown", a.to,
                              " (%s)" % a.out if a.out else ""))


def cmd_unlock(a):
    c = Save(a.common)
    if c.kind != "common":
        raise SystemExit("%s is not sh4_common.dat" % a.common)
    for n in a.slots:
        path = os.path.join(a.dir or os.path.dirname(a.common),
                            "sh4_save_%02d.dat" % (n - 1))
        s = Save(path)
        unlock_slot(s.plain, a.rank)
        unlock_entry(c.plain, n - 1, a.rank)
        s.save()
        print("slot %02d (%s): all endings, nurse, All Weapons, best rank %d"
              % (n, os.path.basename(path), a.rank))
    c.save()


def cmd_eileen(a):
    for path in a.files:
        s = Save(path)
        before = possession_baseline(eileen_fields(s.plain))
        clear_eileen(s.plain)
        s.save()
        print("%s: baseline %.3f -> %.3f" % (path, before,
                                             possession_baseline(
                                                 eileen_fields(s.plain))))


def cmd_rank(a):
    c = Save(a.common)
    e = entry_off(a.slot - 1)
    if c.plain[e] != 7 or struct.unpack_from("<I", c.plain, e + 0x10)[0] != 0x12:
        raise SystemExit("slot %d is not clear data" % a.slot)
    c.plain[e + 0x1B] = a.value
    c.save()
    print("slot %02d: this run's rank -> %d" % (a.slot, a.value))


def cmd_fixmeta(a):
    raw = open(a.file, "rb").read()
    if raw[:2] == b"\xff\xfe":
        print("%s is already UTF-16LE" % a.file)
        return
    text = raw.decode("ascii").replace("\r\n", "\n").replace("\n", "\r\n")
    open(a.file, "wb").write(b"\xff\xfe" + text.encode("utf-16-le"))
    print("%s rewritten as UTF-16LE with BOM" % a.file)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sigkey_help = "retail, xbased, or 32 hex digits"

    p = sub.add_parser("info", help="show what a slot or common file holds")
    p.add_argument("file")
    p.set_defaults(func=cmd_info)

    p = sub.add_parser("decode", help="write the de-obfuscated body")
    p.add_argument("file")
    p.add_argument("-o", "--out", required=True)
    p.set_defaults(func=cmd_decode)

    p = sub.add_parser("encode", help="obfuscate and sign a plain body")
    p.add_argument("file")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--sigkey", default="xbased", help=sigkey_help)
    p.add_argument("--keep-key", action="store_true",
                   help="reuse the key stored in the body instead of a new one")
    p.set_defaults(func=cmd_encode)

    p = sub.add_parser("resign", help="replace the signature")
    p.add_argument("file")
    p.add_argument("--to", required=True, help=sigkey_help)
    p.add_argument("-o", "--out", help="output file (default: in place)")
    p.set_defaults(func=cmd_resign)

    p = sub.add_parser("unlock", help="all endings, nurse costume, One Weapon "
                                      "and All Weapons modes for menu slots")
    p.add_argument("common", help="sh4_common.dat")
    p.add_argument("slots", type=int, nargs="+", help="menu slot numbers 1-30")
    p.add_argument("--dir", help="folder of the sh4_save_NN.dat files")
    p.add_argument("--rank", type=int, default=100)
    p.set_defaults(func=cmd_unlock)

    p = sub.add_parser("eileen", help="clear Eileen's possession")
    p.add_argument("files", nargs="+")
    p.set_defaults(func=cmd_eileen)

    p = sub.add_parser("rank", help="set a clear save's 'this run' rank "
                                    "(menu colour only; 200 = perfect)")
    p.add_argument("common")
    p.add_argument("slot", type=int, help="menu slot number 1-30")
    p.add_argument("value", type=int)
    p.set_defaults(func=cmd_rank)

    p = sub.add_parser("fixmeta", help="convert SaveMeta.xbx back to UTF-16LE")
    p.add_argument("file")
    p.set_defaults(func=cmd_fixmeta)

    a = ap.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
