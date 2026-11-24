# THE IDOLM@STER（Xbox 360）研究

对象：THE IDOLM@STER，Xbox 360 版，Title ID `4E4D07DB`。
目的：研究存档格式和游戏逻辑。已做的有修改胜率、补全配饰、为真机（RGH）解锁成就准备存档，以及审核出现规则的反编译。验证环境为 Xenia Canary 和 Horizon。

## 已确认

- **存档包与校验**：存档包是 STFS `CON `，里面的 `gamedata` 前 2 字节是 CRC-16/CCITT-FALSE（计算范围 0x10 到末尾）。可以原位写回存档包，再用 Horizon 做 Rehash + Resign。
- **试镜胜率**：制作人 PEVA 的 [0] 是试镜次数，[1] 是合格次数，把 [1] 改成等于 [0] 即为 100%。真机和模拟器都已验证。
- **战绩栏**：每个 Unit 只保留最近 5 场试镜，新的在前，旧的会被挤掉，不留痕迹。
- **制作人名**：UTF-16BE，最多 8 个字，存档里有两处（0x80、0xB460）。改名工具已写好，但改名后的存档还没进游戏测试过。
- **配饰/衣装**：ID 与部位、DLC 的对应已经和官方 12 期目录、攻略站核对过。存档容量 246 条，正好是全部有效 ID：配饰 189 件，衣装 57 件。补满后剩下的"？"是从未发行的预留格。
- **成就**：奖杯在存档里的位置和顺序已确认；成就在事件点发放，清空奖杯记录后会重新发放。10 个成就都在模拟器上拿到过。
- **Unit 槽**：可以整块复制到空槽，改偶像 ID 和名字后能正常列出、推进和存档；前提是把"Unit 数"（0x39D0D0）一起改。
- **default.xex**：已解密解压，存档标签字符串和部分读写函数已定位。
- **审核列表**：审核表在 `auditionlist.bxr` 里，栏位是随机刷新的。IDOL VISION 属于 c 类栏位里 20% 的替换，其中 ver4（奖励 7 万粉丝）在一次刷新里约 1%，详见 [docs/audition.md](docs/audition.md)。概率来自反编译，没有在游戏里实测。
- **一 Unit 一成就存档**：[saves/unit-set](saves/unit-set/)，9 个槽各差一步拿一个成就，真アイドルマスター 单独一个文件。实机（RGH）上用它解锁了全部 10 个成就（スーパーアイドル、ベストED 两个槽没单独测，那个档案原来就有）。
- **Just Appeal**：按键时刻离拍点在 ±12% 拍长以内即为 JA，窗口是 `battle.bna` 里的固定值，Tension 不参与；JA 让单次 Appeal 的基础值 +10（上限 100），详见 [docs/just-appeal.md](docs/just-appeal.md)。来自反编译，没有在游戏里实测。

详细内容：

- [docs/gamedata-format.md](docs/gamedata-format.md)：偏移表、PEVA、偶像 ID、Unit 槽
- [docs/accessories.md](docs/accessories.md)：配饰/衣装 ID 表、DLC 核对、剩余"？"
- [docs/achievements.md](docs/achievements.md)：奖杯顺序和触发方式
- [docs/xex-notes.md](docs/xex-notes.md)：xex 解包与函数位置
- [docs/audition.md](docs/audition.md)：审核列表的数据格式、栏位刷新规则和概率（IDOL VISION ver4 约 1%）
- [docs/week-cycle.md](docs/week-cycle.md)：周循环、推进周数的代码路径，以及"一周内课程+营业"的补丁可行性（未实测）
- [docs/just-appeal.md](docs/just-appeal.md)：JA 判定窗口、得分效果、各曲 BPM

## 未确认 / 未完成

- 成就发放点已经反编译出来（见 [docs/achievements.md](docs/achievements.md)），并用一 Unit 一成就存档复现了 8 个；スーパーアイドル、ベストED 没有单独复现，季节祭典营业"成功"的条件没有确认。
- Unit 槽里周数、等级等推进字段没有逐个解出来。
- PEVA 部分下标的含义只是推测。
- TU 补丁没有分析。

## 工具

需要 Python 3；`xex_decrypt.py` 另外需要 `cryptography`。

```
python3 tools/gamedata.py info gamedata                    # 查看摘要
python3 tools/gamedata.py winrate100 gamedata out          # 胜率 100%（制作人和各 Unit）
python3 tools/gamedata.py rename gamedata out アイマス      # 改制作人名
python3 tools/gamedata.py fixcrc gamedata                  # 只重算 CRC
python3 tools/unitset.py 基础存档 main输出 combined输出 shin输出  # 生成一 Unit 一成就存档
python3 tools/stfs_gamedata.py extract 存档包 gamedata      # 从真机存档包取出
python3 tools/stfs_gamedata.py inject 存档包 gamedata 输出包 # 原位写回，之后在 Horizon 里 Rehash + Resign
python3 tools/xex_decrypt.py default.xex default.pe --key <零售 XEX 密钥>
python3 tools/xex_decrypt.py default.xex --scan <内嵌密钥的文件>   # 在模拟器 exe 里找密钥，只打印通过 PE 签名校验的候选
```

改存档前请先备份。本仓库不包含游戏本体文件和密钥。
