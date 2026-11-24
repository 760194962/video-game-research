#!/usr/bin/env python3
"""Minimal reader for emote/M2 PSB files (after mdf decryption). Dumps the tree as JSON.

Enough for config / struct-definition PSBs (no resource extraction).

Usage: psb_dump.py FILE.psb
"""
import json, struct, sys


class PSB:
    def __init__(self, d):
        assert d[:4] == b'PSB\0', 'not a PSB'
        self.d = d
        self.version, = struct.unpack_from('<H', d, 4)
        (_, o_names, o_str, self.o_strdata, _, _, _, self.o_root) = struct.unpack_from('<8I', d, 8)
        p = o_names
        self.charset, p = self._arr(p)
        self.tree, p = self._arr(p)
        self.name_idx, p = self._arr(p)
        self.names = [self._name(i) for i in range(len(self.name_idx))]
        self.str_off, _ = self._arr(o_str)

    def _u(self, p, n):
        return int.from_bytes(self.d[p:p + n], 'little')

    def _arr(self, p):
        t = self.d[p]; n = t - 0xC
        cnt = self._u(p + 1, n); p += 1 + n
        es = self.d[p] - 0xC; p += 1
        return [self._u(p + i * es, es) for i in range(cnt)], p + cnt * es

    def _name(self, i):
        ch = self.tree[self.name_idx[i]]; out = []
        while ch:
            code = self.tree[ch]
            out.append(ch - self.charset[code]); ch = code
        return bytes(reversed(out)).decode('utf-8', 'replace')

    def _str(self, i):
        p = self.o_strdata + self.str_off[i]
        return self.d[p:self.d.index(b'\0', p)].decode('utf-8', 'replace')

    def value(self, p):
        t = self.d[p]
        if t == 0x1: return None
        if t == 0x2: return False
        if t == 0x3: return True
        if t == 0x4: return 0
        if 0x5 <= t <= 0xC: return int.from_bytes(self.d[p + 1:p + 1 + t - 4], 'little', signed=True)
        if 0xD <= t <= 0x14: return self._arr(p)[0]
        if 0x15 <= t <= 0x18: return self._str(self._u(p + 1, t - 0x14))
        if 0x19 <= t <= 0x1C: return {'resource': self._u(p + 1, t - 0x18)}
        if t == 0x1D: return 0.0
        if t == 0x1E: return struct.unpack_from('<f', self.d, p + 1)[0]
        if t == 0x1F: return struct.unpack_from('<d', self.d, p + 1)[0]
        if t == 0x20:
            offs, q = self._arr(p + 1)
            return [self.value(q + o) for o in offs]
        if t == 0x21:
            names, q = self._arr(p + 1)
            offs, q = self._arr(q)
            return {self.names[n]: self.value(q + o) for n, o in zip(names, offs)}
        return {'unknown_type': hex(t)}

    def root(self):
        return self.value(self.o_root)


if __name__ == '__main__':
    print(json.dumps(PSB(open(sys.argv[1], 'rb').read()).root(), ensure_ascii=False, indent=1))
