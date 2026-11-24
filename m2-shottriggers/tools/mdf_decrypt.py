#!/usr/bin/env python3
"""Decrypt M2 engine "mdf" files (*.nut.m, *.psb.m) found in M2 ShotTriggers RomFS.

File layout:
    0x00  "mdf\\0"
    0x04  u32 decompressed size
    0x08  XOR-obfuscated zlib stream

Key stream:
    seed  = MD5( title_seed + basename(path).lower() )        # e.g. "25G/xpvTbsb+6" + "title_const.nut.m"
    MT19937 init_by_array( 4 x u32 LE words of seed )
    key   = first 64 bytes of genrand_int32() output (each u32 LE)
    body  = data[8:] XOR key (repeating every 64 bytes) -> zlib.decompress

The title seed is a 13-char string stored in the game's main NSO (search the
decompressed .rodata for 10–16 char tokens with mixed case/digits/+/).

Usage:
    mdf_decrypt.py [--seed SEED] FILE.m [FILE.m ...]
Writes FILE (".m" stripped) next to each input.
"""
import argparse, hashlib, os, struct, zlib


class MT19937:
    def __init__(self, key):
        mt = [0] * 624
        mt[0] = 19650218
        for i in range(1, 624):
            mt[i] = (1812433253 * (mt[i - 1] ^ (mt[i - 1] >> 30)) + i) & 0xFFFFFFFF
        i, j, n = 1, 0, len(key)
        for _ in range(max(624, n), 0, -1):
            mt[i] = ((mt[i] ^ ((mt[i - 1] ^ (mt[i - 1] >> 30)) * 1664525)) + key[j] + j) & 0xFFFFFFFF
            i += 1; j += 1
            if i >= 624: mt[0] = mt[623]; i = 1
            if j >= n: j = 0
        for _ in range(623, 0, -1):
            mt[i] = ((mt[i] ^ ((mt[i - 1] ^ (mt[i - 1] >> 30)) * 1566083941)) - i) & 0xFFFFFFFF
            i += 1
            if i >= 624: mt[0] = mt[623]; i = 1
        mt[0] = 0x80000000
        self.mt, self.idx = mt, 624

    def genrand_int32(self):
        mt = self.mt
        if self.idx >= 624:
            for k in range(624):
                y = (mt[k] & 0x80000000) | (mt[(k + 1) % 624] & 0x7FFFFFFF)
                mt[k] = mt[(k + 397) % 624] ^ (y >> 1) ^ (0x9908B0DF if y & 1 else 0)
            self.idx = 0
        y = mt[self.idx]; self.idx += 1
        y ^= y >> 11
        y ^= (y << 7) & 0x9D2C5680
        y ^= (y << 15) & 0xEFC60000
        y ^= y >> 18
        return y


def decrypt(path, seed, key_len=64):
    data = open(path, 'rb').read()
    if data[:4] != b'mdf\0':
        raise ValueError('not an mdf file')
    h = hashlib.md5((seed + os.path.basename(path).lower()).encode()).digest()
    mt = MT19937(list(struct.unpack('<4I', h)))
    ks = b''.join(struct.pack('<I', mt.genrand_int32()) for _ in range((key_len + 3) // 4))[:key_len]
    body = bytes(b ^ ks[i % key_len] for i, b in enumerate(data[8:]))
    return zlib.decompress(body)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--seed', default='25G/xpvTbsb+6', help='per-title seed (default: ESP Ra.De. Psi)')
    ap.add_argument('files', nargs='+')
    a = ap.parse_args()
    for p in a.files:
        try:
            out = p[:-2] if p.endswith('.m') else p + '.dec'
            open(out, 'wb').write(decrypt(p, a.seed))
            print('ok  ', out)
        except Exception as e:
            print('FAIL', p, e)
