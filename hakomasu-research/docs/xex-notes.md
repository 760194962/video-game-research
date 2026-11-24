# default.xex 笔记

- XEX2，零售加密（AES-128：用零售 XEX 密钥解出 secinfo+0x150 处的文件密钥，再对 0x3000 起的 PE 数据做 CBC、IV 为 0），basic 压缩（(数据长度, 补零长度) 列表）。工具：`tools/xex_decrypt.py`，需要自行提供密钥。
- 镜像基址 0x82000000，.text RVA 0xE0000（大小 0x3A9B44），.rdata 0x400，.data 0x490000。
- 存档标签字符串（VA）：`ACDT TAG` 0x8203023C，`IDOL TAG` 0x82031D94，`MAILDATA` 0x82031E28，`PRODUCER` 0x82032C0C，`PEVA TAG` 0x820338D0，`PROD TAG` 0x82033A80，`PTRP TAG` 0x82033B9C，`REP SUB ` 0x82033BCC，`SYSTEM  ` 0x82033F3C，`UNIT    ` 0x82035978，`UNIT TAG` 0x82035ED8，`WORLD   ` 0x82036328，`gamedata` 0x820046FC，`savedata` 0x820046F0。
- 各记录类的构造函数都调用 0x8222DC50(标签, 版本号) 注册，例如 PROD TAG 在 0x82239A18，UNIT 在 0x8224A298，UNIT TAG 在 0x8224E7D8。
- UNIT 的反序列化函数在 0x8224A580：依次读入 UNIT TAG、REPO、PEVA、一个 6 元素数组、SONG，再读一个 0x38 字节结构、0xC 字节和 0x10 字节。
- 默认名字（"ナムコエンジェル"、制作人名）不在 xex 里，应在游戏数据文件中。
- 配饰能力值在 xex 里找不到静态表。
- TU（`TU_1A461UH_000000S000000.0000000000087`）还没有分析。Xenia 实际加载的 `default.xexp`（0.0.0.1 → 0.0.2.1，Module Hash `2DE0C2DE0637583C`）会让代码地址整体平移，写 Xenia 补丁时要用打过 TU 的镜像里的地址。可以用 `xextool -p default.xexp -o patched.xex default.xex` 和 `xextool -b patched.pe patched.xex` 得到镜像，两版函数的对应方法见 [week-cycle.md](week-cycle.md)。
- 零售密钥的来源：Xenia 的可执行文件里直接内嵌了这个 16 字节常量。用 `tools/xex_decrypt.py default.xex --scan <xenia exe>` 扫描即可（脚本会要求解出的头部带 `PE\0\0` 签名）。只检查 `MZ` 会有大量误判，扫一个 17 MB 的 exe 能撞出几十个，容易拿到一份"开头像 PE、后面全是乱码"的假镜像。解出后可以数一下镜像里的 `mfspr r12,LR`（`0x7D8802A6`）和 `blr`（`0x4E800020`）：正确的镜像里 `blr` 有上万条。
- 反编译笔记见 [audition.md](audition.md)：审核表的加载和栏位刷新逻辑在 `0x82308000`–`0x8230D500` 和 `0x82311850`。导入 Ghidra 的设置和几个坑（处理器变体、保存寄存器的 thunk 被当成不返回）也写在那里。
- 试镜对战与 JA 判定见 [just-appeal.md](just-appeal.md)：节拍函数 `0x820FF778`，普通 Appeal 处理 `0x822DE400`，得分函数 `0x823094E0`，曲目 BPM 表 `0x824948D8`。
