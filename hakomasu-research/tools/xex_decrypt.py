#!/usr/bin/env python3
"""Decrypt + decompress default.xex (XEX2, retail-encrypted, "basic" compression) to a raw image.

Usage:
  python3 xex_decrypt.py default.xex default.pe --key <32 hex chars, Xbox 360 retail XEX key>
  python3 xex_decrypt.py default.xex --scan <binary that embeds the key, e.g. an emulator exe>

The retail key is not included in this repository. --scan tries every 4-byte-aligned 16-byte
window of the given file as the key and prints the ones that decrypt to a real PE header
(see check_pe). Checking only for "MZ" gives false positives: a 17 MB file produces dozens.
The output is the memory image loaded at 0x82000000 (file offset = VA - 0x82000000).
Requires: pip install cryptography
"""
import argparse
import struct

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


def check_pe(p):
    # 'MZ' alone matches by chance about once per 65536 wrong keys; also require the PE signature.
    if p[:2] != b'MZ' or len(p) < 0x40:
        return False
    e = struct.unpack('<I', p[0x3C:0x40])[0]
    return e + 4 <= len(p) and p[e:e + 4] == bytes([0x50, 0x45, 0, 0])


def scan(d, path):
    magic, flags, peoff, _res, secoff, optcnt = struct.unpack('>4sIIIII', d[:24])
    assert magic == b'XEX2'
    enc_session = d[secoff + 0x150:secoff + 0x160]
    head = d[peoff:peoff + 0x100]
    b = open(path, 'rb').read()
    for off in range(0, len(b) - 16, 4):
        key = b[off:off + 16]
        session = Cipher(algorithms.AES(key), modes.ECB()).decryptor().update(enc_session)
        p = Cipher(algorithms.AES(session), modes.CBC(bytes(16))).decryptor().update(head)
        if check_pe(p):
            print('key candidate at', hex(off), key.hex())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('xex')
    ap.add_argument('out', nargs='?')
    ap.add_argument('--key')
    ap.add_argument('--scan')
    a = ap.parse_args()
    d = open(a.xex, 'rb').read()
    if a.scan:
        scan(d, a.scan)
        return
    assert a.out and a.key, 'need out and --key (or use --scan)'
    magic, flags, peoff, _res, secoff, optcnt = struct.unpack('>4sIIIII', d[:24])
    assert magic == b'XEX2'
    opts = dict(struct.unpack('>II', d[24 + 8 * i:32 + 8 * i]) for i in range(optcnt))
    fi = opts[0x3FF]                                   # file format info
    isz, enc, comp = struct.unpack('>IHH', d[fi:fi + 8])
    assert comp == 1, 'only basic compression is handled'
    session = Cipher(algorithms.AES(bytes.fromhex(a.key)), modes.ECB()).decryptor().update(d[secoff + 0x150:secoff + 0x160])
    data = d[peoff:]
    data = data[:len(data) // 16 * 16]
    dec = Cipher(algorithms.AES(session), modes.CBC(bytes(16))).decryptor().update(data) if enc else data
    out, pos = bytearray(), 0
    for i in range((isz - 8) // 8):
        ds, zs = struct.unpack('>II', d[fi + 8 + 8 * i:fi + 16 + 8 * i])
        out += dec[pos:pos + ds]
        pos += ds
        out += bytes(zs)
    assert check_pe(bytes(out[:0x400])), 'wrong key?'
    open(a.out, 'wb').write(out)
    print('image size', hex(len(out)))


if __name__ == '__main__':
    main()
