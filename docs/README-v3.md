# 六壬带读工作区

`pi` 分支提供宋本带读、原文锚点检索和 L1–L6 浏览器训练。Obsidian 打开 `六壬vault/`；
Pi 在仓库根目录启动。已导入《中黄经》阅读整理版，首个书魂是凝神子。

## 启动

Windows 启动器会从 Conda 环境登记中寻找六壬 `ai-env`；也可显式设置
`LIUREN_PYTHON` 指向专属 Python。当前机器已找到 `D:\术数\六壬\.conda\envs\ai-env\python.exe`，
Python 3.12.14，已补齐 PyYAML；底本原文件保持不变。

```powershell
.\启动六壬.ps1 -DryRun            # 检查实际命令，不调用模型
.\启动六壬.ps1                    # 凝神子书魂，DeepSeek 后端
.\启动六壬.ps1 -Book 复盘官       # 独立跨书校勘会话
.\启动训练.ps1                    # 浏览器训练服务，默认仅本机8765端口
.\验收.ps1                        # 工程、Pi加载、网页与模型凭据集中检查
.\验收.ps1 -Model                 # 配置DeepSeek凭据后跑24条模型用例
```

统一入口：[书魂与辅助卡](http://127.0.0.1:8765/catalogue.html)，
训练页面：[六关训练](http://127.0.0.1:8765/curriculum.html)。启动训练服务后打开。
基础免修须一次 12 题全对；L1–L6 每轮 12 题、至少 11/12，再通过白话复述。
开放断辞先核盘面与引文，再由用户做有评语的人工文义验收。旧九关及成绩仍保留，
不自动折算新成绩；测试全在临时状态中跑，不写个人训练成绩。

Pi 0.99.1 实际支持 `--append-system-prompt`，没有 `--agents-file`。
启动器显式载入系统规则、一个书魂和检索/输出验证扩展；使用新会话避免书魂记忆串戏。
主讲按需调用课堂讨论工具，自动请他书魂补证/质疑、复盘官核阅，再返回同一会话。
你只在主动更换主读底本时使用-Book；课堂跨书讨论无需手动切书。详见`docs/自动课堂.md`。
DeepSeek key 在 Pi 自身登录/凭据系统管理，不能写入仓库。

## 已落地

- 《中黄经》79 个卷篇、49 张表格；保留经文、释文、眉批、校记和原字形。
- 原文块锚点、源文件 hash、逐条 body hash；按 OOXML 块定位，不冒充原书页码。
- 六条红线、凝神子五段书魂、导读官/排盘守卫/复盘官，跨书越界挂号。
- L1 课体、L2 涉害贵人天将、L3 特殊宗门、L4 年命、L5 断辞组织、L6 断案复盘。
- 服务端首答计分、刷新续答、原题 1/3/7/21 天复现、复述闸门、五例留出结课测。
- 以真实原文锚点生成七件套导读；v3 开场简报与复盘使用新成绩，不混入旧关。
- 十二书魂全档与八张辅助卡，各两处可核验原句；断案三魂按显式标记安全检索。
- 集中验收页面、报告和24条模型用例；旧段索引不再将短注后的原辞归给注家。
- 自动课堂协调：独立书魂发言、复盘官核阅、会话内来源授权与讨论次数上限。

## 原文检索与验证

```powershell
& $env:LIUREN_PYTHON tools\vault_sources.py --author 凝神子 --query 己身
& $env:LIUREN_PYTHON tools\import_zhonghuang.py --verify
& $env:LIUREN_PYTHON tools\selfcheck.py --v3
& $env:LIUREN_PYTHON tools\tutor.py --curriculum v3 --status
& $env:LIUREN_PYTHON tools\retro.py --brief --curriculum v3
```

`LIUREN_PYTHON` 未显式设置时，上面的维护命令用专属环境 Python 的绝对路径代替。
导读使用 `tools/guide_v3.py --anchor 检索返回的锚点`；只出骨架，填写后 `--check`。
收尾执行 `signal_log.py close`、`retro.py --close --curriculum v3`；流程提案仍须用户批准。

`sources/` 的 Word/PDF 原书按既有规则不提交 Git。已构建的 vault、源文清单与 hash
正常跟随 Git；另一台机器可以读书和训练，重建中黄经须另备相同 Word。

## 验证与边界

```powershell
& $env:LIUREN_PYTHON tools\validate_delivery.py
```

规则/工具/前后端已作本地验证。子平诱导测试验证的是确定性输出检查器；
Pi 就绪检测发现尚未配置 DeepSeek 凭据，真实课堂或长会话验收受阻，不能声称模型始终遵守红线。
中黄经底本是整理版，未核原刻；断案未标清的续文仍待句级复核，L6 提交后显示完整校注上下文。
用户已追加授权全部完成：剩余十一份书魂和八张禄命辅助卡现已补齐，内容完成不认证原刻。
集中验收与当前限制见 `docs/统一验收清单.md`；实际结果见 `docs/acceptance-results.json`。

旧指令与旧使用说明存于 `docs/history/`。设计与实现详见
`docs/superpowers/specs/2026-09-30-liuren-tutor-design.md`、`docs/implementation-2026-09-30.md`。
