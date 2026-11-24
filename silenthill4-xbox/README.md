# Silent Hill 4: The Room – Xbox save research

Notes from reverse engineering the save system of **Silent Hill 4: The Room (Xbox, NTSC-U, title ID `4B4E001F`)**, plus `sh4save.py`, a small standard-library Python tool built on the findings.

All addresses are virtual addresses in the NTSC-U `default.xbe` (base `0x10000`). No game files, console keys or save files are included in this repository.

- [Files](#files)
- [Signature: which saves need re-signing](#signature-which-saves-need-re-signing)
- [Obfuscation](#obfuscation)
- [Slot file layout](#slot-file-layout)
- [Common file layout](#common-file-layout)
- [Unlocks](#unlocks)
- [Ranking](#ranking)
- [Eileen's possession](#eileens-possession)
- [PS2 saves](#ps2-saves)
- [The tool](#the-tool)

## Files

A save lives in `UDATA\4b4e001f\<save id>\`:

| File | Size | Contents |
|---|---|---|
| `sh4_common.dat` | 1524 = 1504 + 20 | system data, including the directory shown in the load menu |
| `sh4_save_NN.dat` | 23108 = 23088 + 20 | one slot; `NN` is 00–29, the menu shows NN+1 |
| `SaveMeta.xbx` | 54 | `Name=GAME DATA` / `NoCopy=…`, **UTF-16LE with BOM** |
| `saveimage.xbx` | 4096 | save icon (XPR) |

The last 20 bytes of each `.dat` are an HMAC-SHA1 signature over everything before it.

If `SaveMeta.xbx` is ASCII instead of UTF-16, the save is skipped entirely: the game opens `SaveMeta.xbx` and never reads the `.dat` files, so the menu shows *no game data* without any error.

## Signature: which saves need re-signing

Load path:

1. `0x16b250` (slot) / `0x16b180` (common) is the game-side state machine.
2. `0x160d0` → `0x15cf0` builds the file name (`0x15910`) and opens the file (`0x156d0`).
3. It checks that the file size is `body + 0x14`, then reads the body (`0x15770`) and the 20-byte signature (`0x15830`).
4. It recomputes the signature (`0x15c20`) and compares it with `repe cmpsd`, 5 dwords (`0x15880`).

`0x15c20` calls `XCalculateSignatureBegin(0)` / `Update` / `End` (`0x173be0` / `0x173bf4` / `0x173c42`). Flag `0` means a **roamable** signature: `HMAC-SHA1(XboxSignatureKey, body)`, with no hard-disk key and no MAC. `XboxSignatureKey` is kernel export 325. The console derives it from the title's signature key in the XBE certificate.

| Where the save was made | `XboxSignatureKey` the game uses |
|---|---|
| Original Xbox, Xbox 360 backward compatibility, xemu with a retail BIOS | `2dc1fd8c6f2ee0524a766d37e586b742` (NTSC-U) |
| xbased | 16 zero bytes |

So:

- Saves move between retail consoles, the Xbox 360 and xemu **as-is**. No console binding. This follows from the code; it was checked between xemu and xbased only.
- **xbased is the exception.** It runs without a BIOS, and its HLE kernel exports a zero `XboxSignatureKey`, so a save has to be re-signed going into or out of xbased.
  - xbased's own "Import from xemu" does this automatically, but only for games already in its library. Its log says `its game isn't in the library` and copies the file unsigned otherwise.
  - The same holds for other titles in xbased: Fatal Frame 1/2 saves there (non-roamable) verify with a zero signature key plus a hard-disk key, which in the tested setup was the same as that of the xemu install it imported from.
- Other regions have their own title signature key, so converting a save between regions also needs a re-sign, and the body may not be compatible.

## Obfuscation

After the signature check the body is de-obfuscated by `0xfe4d0` (`0xfe620` for a slot, `0xfe5f0` for common). Encoding runs the same function: `0xfe5a0` for a slot, `0xfe540` for common.

```
key  = u32 stored in the file (slot: +0x28, common: +0x10), kept in clear
k    = [(key >> 16) & 0xff, (key >> 8) & 0xff, key & 0xff]
step = key >> 24
for each byte n:  out[n] = in[n] ^ k[i];  k[i] += step;  i = (i + 1) % 3
```

The game picks a new key on every save: `rand() & 0xffffff` for the low 24 bits and a step of `rand() % 240 + 8`. Two consecutive saves therefore look completely different on disk, and small steps give a visibly low-entropy file.

## Slot file layout

Header, written by `0xfe640` and restored by `0xfea60` on load:

| Offset | Type | Meaning |
|---|---|---|
| `+00` | u32 | `0x53d4`, the used size of the struct |
| `+04` | u32 | play time in 1/30 s |
| `+0C` | u32 | difficulty, 1 Easy / 2 Normal / 3 Hard |
| `+10` | u16 | endings seen (bit mask, see below) |
| `+12` | u16 | Eileen costume selected (1 = nurse) |
| `+1C` | u8 | nurse costume unlocked |
| `+1D` | u8 | all four endings seen (Cynthia's costume) |
| `+1E` | u16 | best rank, 0–100 |
| `+20` | u32 | continues |
| `+24` | u32 | enemies defeated |
| `+28` | u32 | obfuscation key |
| `+2C` | u32[12] | block offsets: `7c 1bc 6dc 2264 36b4 4434 4bcc 4c24 4c34 521c 53b8 53ce` |

Block `0x1bc` is a copy of the global state at `0xf9b960`. Block `0x4bcc` (0x58 bytes) is Eileen, see [below](#eileens-possession).

Endings come from `0xd2380`: the first set flag in a table at `0x2a9c58`, defaulting to 4.

| Bit | Ending |
|---|---|
| `0x02` | Escape |
| `0x04` | Mother |
| `0x08` | Eileen's Death |
| `0x10` | 21 Sacraments |

## Common file layout

A 0x20-byte header, then 30 directory entries of 0x30 bytes at `+0x20`. The entries are built by `0xfe860` and read by the load menu.

| Offset | Type | Meaning |
|---|---|---|
| `+00` | u16 | 7 when the slot is used |
| `+04` | u32 | play time (1/30 s) |
| `+10` | u32 | chapter, `0x12` = clear data ("A Brand-new Fear") |
| `+14` | u32 | difficulty |
| `+18` | u16 | endings seen |
| `+1A` | u8 | ending bit obtained in this run (clear data) |
| `+1B` | u8 | rank of this run (clear data; 200 = perfect) |
| `+1C` | u32 | save count ("セーブ回数") |
| `+20` | u32 | nurse costume unlocked |
| `+24` | u8 | mode: 0 normal, 1 One Weapon, 2 All Weapons |
| `+25` | u8 | All Weapons mode unlocked |
| `+26` | u16 | best rank |

The menu reads the directory, not the slot files. An edit to a slot must therefore be mirrored in its entry, or the menu won't show it.

## Unlocks

| Unlock | Condition in code |
|---|---|
| Chainsaw | `0xe3c50`: endings mask ≠ 0, outside One Weapon mode |
| Submachine gun | `0xe5840`: best rank ≥ 90, outside One Weapon mode |
| Nurse uniform item in room 303 | `0xe9d80`: Escape or Mother seen and costume not yet unlocked |
| Nurse costume | `0xd23d0`: clear with Escape or Mother while holding item `0x7b` → header `+1C` |
| Cynthia's costume | `0xd2400`: bits 1–4 all set → header `+1D` |
| One Weapon mode | `0x16d6b2`: directory `+26` ≥ 100 |
| All Weapons mode | `0x16d6b2`: directory `+26` ≥ 100 and directory `+25` ≠ 0. On clear, `0x16b6d0` sets it after One Weapon mode on Hard |

On clear, `0x16b6d0` ORs the ending into the mask, keeps the maximum rank, and records this run's ending and rank. On load, `0xfea60` writes header `+10/+1C/+1D/+1E` back into the globals. Choosing a clear-data slot (`0x16dab0`) loads the save count, mode and All Weapons flag from the directory.

A fully unlocked save has:

- header `+10 |= 0x1e`, `+1C = 1`, `+1D = 1`, `+1E = 100`;
- directory `+18 |= 0x1e`, `+20 = 1`, `+25 = 1`, `+26 = 100`.

These match the values in genuine all-endings saves of the Japanese PS2 version.

## Ranking

`0x126b20` adds the following and caps the total at 100:

| Category | Source | Points | Max |
|---|---|---|---|
| Difficulty | header `+0C` | Easy 5, Normal 10, Hard 20 | 20 |
| Play time | play time | `24 − 2 × hours`, clamped to 0–20 | 20 (≤ 2 h) |
| Saves | save count | `12 − saves` | 12 |
| Continues | header `+20` | `10 − continues` | 10 |
| Enemies defeated | header `+24` | `kills / 6` | 20 (≥ 120) |
| Memos | event flags `0x65`–`0x98` set (`0xd3890`) | `memos × 20 / 52` | 20 (52/52) |

The maximum is 102, which is why two saves still allow 10 stars.

`0x127280` replaces this run's rank with **200** when every category is exactly at its maximum: Hard, ≤ 2 hours, no saves, no continues, ≥ 120 kills, 52/52 memos. 200 only goes into directory `+1B`. Unlocks use the best rank, which never exceeds 100, so 200 is a badge and nothing more.

The load menu (`0x16c020`) colours a clear save's ending by this run's rank. Endings seen in earlier runs are drawn dimmed, and endings never seen are not drawn.

| This run's rank | Colour index | Colour |
|---|---|---|
| 200 | 1 | blue-violet |
| ≥ 100 | 4 | yellow |
| ≥ 90 | 2 | red |
| ≤ 10 | 8 | not observed |
| otherwise | 0 | not observed |

The entry text in the list uses colour 4 for normal mode, 3 (green) for All Weapons and 6 (magenta) for One Weapon.

## Eileen's possession

Block `0x4bcc` is a stash of fields of Eileen's actor, kept at `0xbe5128`. It is saved by `0x53910`/`0x537c0` and restored by `0x53820`.

| Block offset | Actor field | Meaning |
|---|---|---|
| `+20` | `+08` | current possession, 0–1 |
| `+24` | `+14` | cumulative damage taken |
| `+2E`, `+30`, `+32`, `+34`, `+36` | | counters B, A, C, G, H |
| `+38`, `+3C` | `+8C`, `+90` | counters E, D |

- When Eileen is hit (`0x46fa0`), damage is added to `+14`, and her health is clamped so that she cannot die while following Henry.
- Every frame (`0x46da0`), the current value `+08` drifts toward a **baseline** `+10`. This is why a Holy Candle only helps for a few minutes.
- The baseline is not saved. `0x46050` recomputes it on load with `0x45b40`:

```
if A < 10: baseline = 0
r1 = clamp(D / E - 0.5, 0, 1)
t1 = (B + A - C) / A - 0.2 * r1
x  = clamp(0.05 * clamp(G, 0, 10) - 0.05 + t1
           + clamp(0.0003 * damage, 0, 0.2) + clamp(0.02 * H, 0, 0.5) - 0.2, 0, 0.8)
baseline = clamp(1.25 * x, 0, 0.95)
```

Cumulative damage contributes at most 0.2 before scaling. The counter ratio `(B + A − C) / A` dominates, so clearing only the damage value has almost no visible effect.

Setting `B = 0`, `C = A`, `G = H = 0`, `damage = 0` and current `= 0` gives a baseline of 0. The counters keep running afterwards, so possession can still build up again. What game events increment A–H was not traced.

## PS2 saves

The PS2 versions (SLUS-20873, SLPM-65574) use the same obfuscation and the same 1504-byte common file, but no Xbox signature.

- `savedata` holds 30 slots of 23088 bytes, and the common file's directory says which ones are valid. Stale data stays in unused slots.
- The slot struct differs: magic `0x5a20`, block offsets `7c 1bc 6e0 2270 36c0 46c0 5170 51d0 51e0 57d0 5a00 5a16`.
- A PS2 slot can't be copied onto Xbox without converting block by block.

## The tool

`sh4save.py` needs Python 3 and nothing else. It works on Xbox files.

```
python sh4save.py info sh4_save_10.dat            # header, unlocks, Eileen, signing key
python sh4save.py info sh4_common.dat             # the load-menu directory
python sh4save.py resign sh4_save_10.dat --to xbased      # or --to retail / 32 hex digits
python sh4save.py decode sh4_save_10.dat -o plain.bin     # de-obfuscated body
python sh4save.py encode plain.bin -o sh4_save_10.dat --sigkey xbased
python sh4save.py unlock sh4_common.dat 11 30     # menu slots 11 and 30: everything unlocked
python sh4save.py eileen sh4_save_10.dat          # possession baseline -> 0
python sh4save.py rank sh4_common.dat 30 200      # clear save's colour (cosmetic)
python sh4save.py fixmeta SaveMeta.xbx            # ASCII -> UTF-16LE
```

Edits keep the file's current signature key. Back up the save folder first.

Tested with NTSC-U saves made on xemu with a retail BIOS and on xbased 1.0.104. Decoding and re-encoding gives back the original files byte for byte, and edited saves load in xbased.
