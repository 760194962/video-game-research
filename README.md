# video-game-research

游戏存档 / 数据格式研究笔记与工具。

| 目录 | 内容 |
|---|---|
| [`esprade-psi/`](esprade-psi/) | エスプレイドΨ（Switch）存档结构、解锁要素、解锁工具 |
| [`m2-shottriggers/`](m2-shottriggers/) | M2 引擎通用：`mdf` 解密、PSB 读取、存档结构计算 |
| [`silenthill4-xbox/`](silenthill4-xbox/) | 寂静岭4（Xbox）存档系统逆向笔记 + `sh4save.py` |
| [`ngb-patch-research/`](ngb-patch-research/) | Ninja Gaiden Black（Xbox）`default.xbe` 补丁整理（镜头、R3、HDDKey） |
| [`ngb-save-manager/`](ngb-save-manager/) | Ninja Gaiden Black（Xbox）存档管理器 |
| [`fatalframe1-save-converter/`](fatalframe1-save-converter/) | 零 ~zero~（Xbox）日版 ⇄ 美版存档互转 |
| [`doa2u-save-transfer/`](doa2u-save-transfer/) | Dead or Alive Ultimate（Xbox）档案在主机间迁移 |
| [`ps2-memcard-manager/`](ps2-memcard-manager/) | PCSX2 文件夹卡 / 记忆卡镜像管理器 |
| [`ps3-userid-counter-reset/`](ps3-userid-counter-reset/) | PS3 `lastCreatedUserId` 计数器研究与重置工具 |

后 7 个目录由原独立仓库合并而来，保留了提交历史；原独立仓库暂时保留，之后以本仓库为准。

## 内容说明

- 本仓库不包含任何游戏本体文件（含 XBE / ISO）、解包出的游戏数据或密钥；需要自行从自己的主机导出。
- 例外：`doa2u-save-transfer/saves/` 是作者自己制作的存档，已用全零 MAC / HDKey 签名，不绑定任何主机；`doa2u-save-transfer/bin/` 与 `fatalframe1-save-converter/` 的历史里有编译好的 Windows 工具 `.exe`。
