# M2 ShotTriggers（M2 引擎）通用笔记

M2 在 Switch / PS4 上的 ShotTriggers 系列共用一套引擎，以下内容在 ESP Ra.De. Ψ 上确认，其他作品大概率相同（每作的 title_seed 不同）。

- RomFS 中 `*.nut.m` / `*.psb.m` 为 `mdf` 格式：MD5(title_seed + 文件名小写) → MT19937 → 64 字节密钥循环 XOR → zlib。
- 解出的 `.nut` 为明文 Squirrel 源码。
- 存档结构由 `config/title_struct_*.psb` 定义；字段按 key 排序、自然对齐。
- 系统存档没有校验和。

| 作品 | Title ID | title_seed |
|---|---|---|
| エスプレイドΨ | 0100F9600E746000 | `25G/xpvTbsb+6` |

工具见 [`tools/`](tools/)，使用示例见 [`../esprade-psi/`](../esprade-psi/)。
