# エスプレイドΨ / ESP Ra.De. Ψ（Switch）存档与解锁研究

| 项目 | 值 |
|---|---|
| 平台 | Nintendo Switch（M2 ShotTriggers） |
| Title ID | `0100F9600E746000`（更新 `0100F9600E746800`） |
| 研究所用版本 | Base v0 + Update v327680 |
| 引擎 | M2 自研引擎，游戏逻辑为 Squirrel 脚本（RomFS `102/script`、`system/script`），配置/结构为 PSB |

> 结论全部来自游戏自带脚本和结构定义，并用真实存档上的已知值核对过。
> 「实机确认」= 已在 Switch 上恢复存档后实际看到效果；其余为按脚本推导、尚未单独在实机上逐项确认。

---

## 1. 存档文件构成

存档里一共 11 个文件，大小与 RomFS 中 PSB 结构定义算出的大小逐字节一致：

| 文件 | 大小 | 结构定义 | 内容 |
|---|---|---|---|
| `data_008_0000.bin` | 214,016 (0x34400) | `title_struct_systemdata.psb` | **系统数据**：设置、解锁、游玩记录、排行榜、いろりの部屋 |
| `data_013_0000.bin` ～ `data_017_0004.bin` | 2,979,840 ×5 | `title_struct_statedata_pack.psb` | **即时存档（save state）**，每个文件 30 个槽位 |
| `data_018_0000.bin` ～ `data_022_0004.bin` | 8,257,536 ×5 | `title_struct_replaydata.psb` | **回放（replay）**，每个文件一组记录 |

- data_008 **没有校验和**，直接改即可。
- 全新存档里 013～022 全部是 0 填充，文件本身存在。
- **删除 save state**：把 `data_013`～`data_017` 换成同样大小、全 0 的文件（或直接从初始存档拷这 5 个文件）。不要真的删掉文件，初始存档里这些文件也是存在的。回放同理（`data_018`～`data_022`）。

## 2. 脚本 / 配置解密（`*.nut.m`、`*.psb.m`）

RomFS 中脚本和配置是 M2 的 `mdf` 格式：

```
0x00 "mdf\0"
0x04 u32 解压后大小
0x08 XOR 混淆过的 zlib 流
```

- 种子：`MD5(title_seed + 文件名小写)`，例：`"25G/xpvTbsb+6" + "title_const.nut.m"`
- 用 MD5 的 4 个 u32（LE）做 MT19937 `init_by_array`，取前 **64 字节**输出作为密钥，循环 XOR `data[8:]`，再 zlib 解压。
- 本作 title_seed：**`25G/xpvTbsb+6`**（位于 main NSO 解压后的只读数据段，是一个 13 字符的独立字符串）。
- 解出来的 `.nut` 是 **明文 Squirrel 源码**（Shift_JIS 注释），不是字节码。

工具：[`../m2-shottriggers/tools/mdf_decrypt.py`](../m2-shottriggers/tools/mdf_decrypt.py)

## 3. data_008 结构

由 `title_struct_systemdata.psb` 推出，规则：

- 字段按 **key 排序** 依次排列，嵌套结构内联展开
- 自然对齐（u16→2、u32→4），结构体本身不额外补齐
- PSB 类型码：`3`=u16，`4`=u32，`6`=char[n]，`8`=结构体，`10`=u8[n]，`11`=u16[n]，`12`=u32[n]，`16`=结构体数组

核对点（都与真实存档相符）：总大小 0x34400；`_24_battle_history._01_boot_time`(0xE400) / `_02_play_time`(0xE404) 为合理秒数；排行榜第一条的日期字符串 `1900/01/01 00:00` 正好落在 0x1645B；`_10_setting_network` 的音量 100 落在 0xF44。

工具：[`../m2-shottriggers/tools/struct_layout.py`](../m2-shottriggers/tools/struct_layout.py)

### 关键偏移

| 偏移 | 字段 | 说明 |
|---|---|---|
| 0x0000 | `_00_header._00_version` | 0x00010015 |
| 0x046C | `_02_setting_screen._11_wallpaper_secret_opened` | 隐藏壁纸开关（M2 通用字段；本作无实际效果，见第 4 节） |
| 0x047C | `_02_setting_screen._3d_secret_opened` | 3D 模式开关（M2 通用字段，全新存档默认为 1；Switch 上菜单不显示） |
| 0x15C0 | `_21_setting_game_setting._00_secret_character` | 有字段但**脚本里没有任何地方使用** |
| 0xE000 | `_24_battle_history._00_data` u32[256] | `enum HISTORY`（见下） |
| 0xE408 | `_24_battle_history._10_score_record` u32[8192] | "HISTORY SCORE"，下分多个区 |
| 0x11808 | score_record[3328]～ | いろりの部屋数据区（`HISTORY_SCORE_OFFSET_ROOM = 3328`，共 4800 项） |

### HISTORY（`0xE000 + idx*4`）

| idx | 名称 | 用途 |
|---|---|---|
| 93 / 94 / 95 | `BOSS_DEFEAT_SB_S / _P / _C` | 打倒隐藏 Boss アリス的次数。三者之和 > 0 时，`EXRAM_ALICEP_IS_UNLOCKED = 1`，自机アリス可选 |
| 143 | `REACHED_SCENE_A` | Arcade 最远到达场景（只用于排行榜附带信息） |
| 149 | `CREDIT` | 投币上限档位：0..7 = 可投 2..9 枚，**8 = 投币无限**。每次 Arcade 打完一局 +1。脚本里还留着"开放 FREE PLAY"的提示和判断，但本作没有启用（见下） |

### いろりの部屋（`0x11808 + idx*4`）

| idx | 内容 |
|---|---|
| 0 | 当前房间（1=ゆうすけ 2=J-B 3=いろり 4=アリス；**0=从未进入**） |
| 1～4 | 各角色经验值（4,860,000 = Lv99） |
| 5～9 | 抽奖券、金/银/铜饲料券、JUDGE MONEY |
| 14 | 角色开放位：bit0..3 = ゆうすけ/J-B/いろり/アリス（兼容：值 8 视为 15） |
| 40 + 角色×80 + … | 各角色房间布局：+0 站位（y×7+x），+57..60 宠物配置，+61..64 宠物经验 |
| 360 + … | 家具持有数（>0 即拥有）。8 类起点 0/30/60/90/120/150/180/370，件数 3/5/5/6/5/3/71/4（共 102） |
| 760 + 种类×10 + n | 宠物持有数：狗 5、猫 6、鸟 5、仓鼠 5（共 21） |
| 800 + 角色×800 + (任务−1)×8 | 任务记录：+0 出击 +2 成功 +3 失败 +4 熟练 +5 星级（16 = 完美）。任务编号 1–10、11–41、71–75、81–88、91–96（共 60） |
| 4000 + 类型×20 + 角色×5 + 部位 | 饰品持有数。各角色各部位件数：ゆうすけ 5/7/9/2/4，J-B 3/6/7/2/4，いろり 4/18/5/1/3，アリス 6/12/4/2/6（共 110） |

## 4. 解锁要素一览

| 要素 | 原本条件 | 存档里的位置 | 状态 |
|---|---|---|---|
| 自机アリス（Arcade Plus / Super Easy / Custom） | 在 Ψ 模式打倒アリス | HISTORY[93..95] 之和 > 0 | 按脚本推导 |
| いろりの部屋 4 人（含アリス） | 第 2、3 个房间：JUDGE MONEY 累计 3000 / 6000；アリス：已开满 3 个房间 + 任意角色通关ストーリー第 28 关（アリスマスター战第一段） | room[14] = 15 | **实机确认** |
| 家具 / 宠物 / 饰品 | 抽奖 | 见上表 | **实机确认**（家具） |
| 角色、宠物 Lv99 | 养成 | room[1..4]、各角色 +61..64 | 按脚本推导 |
| 任务全部完美通关 | 逐个通关 | 任务记录 +0/+2/+5 | 按脚本推导 |
| 投币无限 | Arcade 打完 8 局 | HISTORY[149] = 8 | 按脚本推导 |
| FREE PLAY 选项 | — | **本作不存在**：「FREE PLAY設定」在各设置菜单的配置里有定义，但没有放进任何一个菜单的显示列表（`layout`），游戏里不会出现 | 配置确认；实机也未见 |
| 隐藏壁纸 / 3D 模式 | — | **本作实际不存在**：画面设定菜单的显示列表（`system/config/setting_screen.psb` 的 `layout`）只有旋转/预设/自动尺寸/尺寸/平滑/扫描线；3D 三项在不支持 3D 的平台上被脚本移除；`title_prof.psb` 中壁纸总数 `max_num` 为 1，开关打开也不会多出壁纸。存档里 0x46C / 0x47C 仍有对应字段，改了也无效果，`esprade_unlock.py` 不修改这两处 | 配置确认；实机也未见 |
| ACチャレンジ全场景 | — | 无需修改：`challengeGuiGetIsUnlocked()` 在此版本中固定返回 1 | 脚本确认 |
| おさらい（絆育成）角色 | — | 无需修改：相关解锁显示已被注释掉，未启用 | 脚本确认 |
| 勋章 / 奖杯 | — | Switch 版不存在：`trophy_TrophyUnlock()` 只在 PS4 上发放，medal 区在 Switch 上恒为 0 | 脚本确认 |
| 更难版アリス（ボスアリス2） | 默认：2 ミス以下才出现 | **不需要解锁**：OTHER SETTINGS 里的「ボスアリス2 出現条件」可选 2ミス以下で出現 / 出現しない / 必ず出現する（`title_setting_game_setting.psb` 的 `Alice2mode`） | 配置确认 |

## 5. 坑：いろりの部屋首次进入会卡死

如果只把 room[14] 设为 15，而 room[0]（当前房间）仍为 0，第一次进入时游戏会强制弹出
「解禁する部屋を選んでください」，只允许选**未开放**的房间。四个都已开放时无法选择，就卡死在这一屏（**实机遇到过**）。

解决：同时把 room[0] 设为某个房间，并补上首次进入时游戏本来会做的初始化
（`title_mode_room.nut` 中 `roomGuiGetChara() == 0` 分支）：

- 家具 360、390、480 各 1（初始家具）
- 四种宠物的第 0 号各 1（初始宠物）
- 各角色宠物配置 +57..60 = 1
- 各角色站位 +0 = 10（即 (3,1)）

`esprade_unlock.py` 已包含这一步。修正后实机可正常进入。

## 6. 工具

| 工具 | 用途 |
|---|---|
| [`tools/esprade_unlock.py`](tools/esprade_unlock.py) | `alice`：只开アリス；`all`：100% 全开。输入/输出为 `data_008_0000.bin` |
| [`../m2-shottriggers/tools/mdf_decrypt.py`](../m2-shottriggers/tools/mdf_decrypt.py) | 解 `*.m` |
| [`../m2-shottriggers/tools/psb_dump.py`](../m2-shottriggers/tools/psb_dump.py) | PSB → JSON |
| [`../m2-shottriggers/tools/struct_layout.py`](../m2-shottriggers/tools/struct_layout.py) | 由结构 PSB 计算存档偏移 |

用法（JKSV 备份）：

```sh
python3 esprade_unlock.py all  "Initial save/data_008_0000.bin" out/data_008_0000.bin
# 再把初始存档里的其余文件（含 .nx_save_meta.bin）一起拷进 out/，用 JKSV Restore
```

## 7. 获取 RomFS 的流程（备忘）

1. DBI 的 MTP 模式下，已安装游戏会以 Base / Update 两个 `.nsp` 形式出现，拷出
2. 用自机的 `prod.keys` + `hactool`：`-t pfs0` 解 NSP；Update 的 titlekey 在 `.tik` 偏移 0x180
3. `hactool --basenca=<base 程序 nca> --titlekey=<key> --romfsdir=... <update 程序 nca>` 得到合并后的 RomFS
4. `main`（NSO）各段 LZ4 解压后，在只读数据段里找 title_seed
