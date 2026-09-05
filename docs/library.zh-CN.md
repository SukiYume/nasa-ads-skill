# Web 与个人文献库指南

[返回 README](../README.zh-CN.md#个人文献库) · [English](library.md)

- [定位已安装的 skill](#定位已安装的-skill)
- [启动 Web](#启动-web)
- [导出引用](#导出引用)
- [选择数据目录](#选择数据目录)
- [迁移到新电脑](#迁移到新电脑)
- [升级旧版数据库](#升级旧版文献库)
- [检查文献库状态](#检查文献库状态)

## 定位已安装的 Skill

可以让 Agent 完成本指南中的操作。它会从已加载的 `SKILL.md` 定位脚本，并使用你选定的文献库。本地浏览、缓存引用、备份和状态检查都可以在没有 ADS token 的环境中运行。

手动运行命令时，先选定包含已安装 `SKILL.md` 的目录。下面使用 Codex 独立 skill 的默认位置。

Windows PowerShell：

```powershell
$nasaAdsSkill = Join-Path $HOME '.agents\skills\nasa-ads'
```

macOS、Linux 或 WSL：

```bash
nasa_ads_skill="$HOME/.agents/skills/nasa-ads"
```

Claude 独立 skill 使用 `~/.claude/skills/nasa-ads`，源码安装使用 `<仓库目录>/plugins/nasa-ads/skills/nasa-ads`，marketplace 插件使用 Agent 报告的实际目录。将变量设为对应目录，并在同一个终端中执行所属平台的后续命令。

## 启动 Web

按安装指南完成一次 [adslib 注册](installation.zh-CN.md#注册-adslib-命令)，之后在任意目录执行：

```bash
adslib
```

命令会自动打开浏览器，复用相同数据目录的已有 NASA ADS 服务，或启动一个新服务。新服务运行时保持终端打开，按 `Ctrl+C` 停止。端口冲突时自动选择可用端口。可用 `adslib --port 8766` 指定优先端口，或用 `adslib --library-dir "<目录>"` 浏览另一文献库。`--no-open` 适用于只启动服务并读取地址的环境。

未注册命令时，可以直接运行已安装的启动器：

Windows PowerShell：

```powershell
python "$nasaAdsSkill/scripts/adslib.py"
```

macOS、Linux 或 WSL：

```bash
python3 "$nasa_ads_skill/scripts/adslib.py"
```

浏览器和服务运行在同一台电脑上，默认地址是 [http://127.0.0.1:8765](http://127.0.0.1:8765)，实际地址以终端输出为准。重启电脑后再次运行 `adslib`。新安装可以直接显示空库，启动时无需创建数据库。Web 使用打包资源和 Python 标准库。需要手动管理服务时，原有 `literature_db.py serve --port 8765` 仍可使用。

Claude 插件可以使用 `/nasa-ads:ads-memory serve`，由 Agent 定位安装路径。[README](../README.zh-CN.md#打开-web-文献库)也提供了可在任意工作目录运行的完整 Codex 独立 skill 命令。

| 想做的事情 | 页面操作 |
| --- | --- |
| 查找科学主题 | 展开主题树；上级目录会包含下级目录中的论文 |
| 查找某个写作部分的文献 | 将主题与方法、讨论等写作用途组合筛选 |
| 搜索某个证据层级 | 选择题录、已写总结或已存全文 |
| 限定年份 | 展开年份，输入范围，点击“应用年份”；筛选项可以逐个移除 |
| 阅读详细结论 | 打开论文，在概览、科学维度、引用和全文版本之间切换 |
| 回到相同检索位置 | 复制文献链接，在同一电脑恢复筛选、页码、论文和详情栏目 |
| 使用键盘 | `/` 聚焦搜索；Escape 收起年份或阅读区；方向键切换已聚焦的详情标签 |
| 查看新入库论文 | Agent 更新同一文献库后，点击刷新 |

界面提供只读浏览。需要补充总结、分类、主题说明或笔记时，可以直接要求 Agent 整理。文献库信息按钮会显示当前数据目录。引用下载支持勾选论文和整组筛选结果，整组导出每次最多 2000 篇。

## 导出引用

> 导出选定主题中的论文 BibTeX，优先使用缓存的 ADS 官方条目，并保存为 references.bib。

Web 的引用栏目会显示条目来源。ADS 官方条目保留其原始引用键。没有官方缓存时，会根据已知的本地题录生成引用，并标记来源。在线获取官方条目需要 ADS 凭据。

下面的例子将 `references.bib` 写入当前工作目录。将主题替换为文献库中已有的目录。

Windows PowerShell：

```powershell
python "$nasaAdsSkill/scripts/literature_db.py" citations --collection "FRB/Propagation" --output references.bib
python "$nasaAdsSkill/scripts/literature_db.py" citations --all --output personal-library.bib
python "$nasaAdsSkill/scripts/literature_db.py" citations "2016PhRvL.116f1102A" --fetch
```

macOS、Linux 或 WSL：

```bash
python3 "$nasa_ads_skill/scripts/literature_db.py" citations --collection "FRB/Propagation" --output references.bib
python3 "$nasa_ads_skill/scripts/literature_db.py" citations --all --output personal-library.bib
python3 "$nasa_ads_skill/scripts/literature_db.py" citations "2016PhRvL.116f1102A" --fetch
```

最后一条命令为已在本地库中的论文获取并缓存官方引用。论文尚未入库时，可以让 Agent 先检索题录。需要 RIS、AASTeX、MNRAS 或其他受支持格式时，在请求中说明格式，Agent 会使用 ADS 引用导出。

## 选择数据目录

| 设置 | 位置或作用 |
| --- | --- |
| Windows 默认目录 | `%LOCALAPPDATA%\nasa-ads\literature` |
| macOS / Linux / WSL 默认目录 | `${XDG_DATA_HOME:-~/.local/share}/nasa-ads/literature` |
| `NASA_ADS_LITERATURE_DIR` | 指定检索、存储和 Web 使用的个人文献库 |
| `NASA_ADS_CACHE_DIR` | 指定临时全文下载缓存 |

个人文献库包含 `literature.sqlite3` 和受管理的 `objects/` 目录，共同保存题录、来源总结、精确文章文件、分类、结论和引用。清理下载缓存后，已存的完整版本仍可复用。迁移文献库时使用 CLI 的备份与恢复功能，以保持文章文件路径有效。

只为某次服务选择自定义文献库时，将 `--library-dir` 放在 `serve` 前面：

Windows PowerShell：

```powershell
python "$nasaAdsSkill/scripts/literature_db.py" --library-dir "$HOME/nasa-ads-literature" serve --port 8765
```

macOS、Linux 或 WSL：

```bash
python3 "$nasa_ads_skill/scripts/literature_db.py" --library-dir "$HOME/nasa-ads-literature" serve --port 8765
```

长期使用时，按下方迁移步骤设置 `NASA_ADS_LITERATURE_DIR`。Agent 与 Web 服务需要获得同一变量值。修改目录后，重新启动已经运行的服务。

## 迁移到新电脑

> 备份我的个人文献库，给出需要转移的完整备份目录；在新电脑恢复到新目录，并让 Agent 和 Web 使用这个目录。

1. **在旧电脑创建备份。** 命令会报告一个新的备份目录，其中包含数据库快照、文章对象和 `backup.json`。

Windows PowerShell：

```powershell
python "$nasaAdsSkill/scripts/literature_db.py" backup
```

macOS、Linux 或 WSL：

```bash
python3 "$nasa_ads_skill/scripts/literature_db.py" backup
```

2. **转移输出的完整目录。** 在新电脑安装 skill 和 Python。下面假定转移后的目录是 `$HOME/nasa-ads-library-backup`，恢复目标是 `$HOME/nasa-ads-literature`。恢复目标需要是尚未存在的新目录。

3. **在新电脑恢复并选定文献库。** 执行前，按[第一节](#定位已安装的-skill)设置当前电脑上的 skill 目录变量。

Windows PowerShell：

```powershell
python "$nasaAdsSkill/scripts/literature_db.py" restore "$HOME/nasa-ads-library-backup" --destination "$HOME/nasa-ads-literature"
$env:NASA_ADS_LITERATURE_DIR = "$HOME/nasa-ads-literature"
[Environment]::SetEnvironmentVariable('NASA_ADS_LITERATURE_DIR', $env:NASA_ADS_LITERATURE_DIR, 'User')
```

macOS、Linux 或 WSL：

```bash
python3 "$nasa_ads_skill/scripts/literature_db.py" restore "$HOME/nasa-ads-library-backup" --destination "$HOME/nasa-ads-literature"
export NASA_ADS_LITERATURE_DIR="$HOME/nasa-ads-literature"
```

macOS/Linux/WSL 用户可以将 `export` 这一行加入 `~/.zshrc` 或 `~/.bashrc` 等当前 shell 的启动文件，让后续会话继续使用该设置。设置持久环境变量后，新建 Agent 会话。恢复操作会校验备份，并调整已存文件在目标目录中的路径。

4. **验证并打开恢复后的文献库。** 执行[状态检查](#检查文献库状态)，再[启动 Web](#启动-web)。旧版 schema 需要先按下一节升级。核对文献库目录和数量是否与来源备份一致。

## 升级旧版文献库

当前数据库 schema 为 3，完整文章 digest 的 schema version 为 2。已有 schema 1 或 2 的文献库报告版本不匹配时，先更新完整 skill，再显式执行 `init`。它会在迁移前创建完整备份并报告位置。尚未创建文献库的新安装可以直接打开空库。

Windows PowerShell：

```powershell
python "$nasaAdsSkill/scripts/literature_db.py" init
python "$nasaAdsSkill/scripts/literature_db.py" audit
```

macOS、Linux 或 WSL：

```bash
python3 "$nasa_ads_skill/scripts/literature_db.py" init
python3 "$nasa_ads_skill/scripts/literature_db.py" audit
```

Schema 迁移准备数据存储格式。科学分类由 Agent 阅读每篇文章现有的总结与证据后确定。旧库尚未分类时，可以另行要求 Agent 完成内容整理。

## 检查文献库状态

Windows PowerShell：

```powershell
python "$nasaAdsSkill/scripts/literature_db.py" stats
python "$nasaAdsSkill/scripts/literature_db.py" check
python "$nasaAdsSkill/scripts/literature_db.py" audit
```

macOS、Linux 或 WSL：

```bash
python3 "$nasa_ads_skill/scripts/literature_db.py" stats
python3 "$nasa_ads_skill/scripts/literature_db.py" check
python3 "$nasa_ads_skill/scripts/literature_db.py" audit
```

`stats` 显示数量和目录。`check` 报告未完成的总结与主题分类；这些内容工作尚未完成时，退出码为 1。`audit` 检查数据库关联与文章文件完整性。文献库可以同时处于“完整性正常”和“部分阅读工作待完成”两种状态。

找不到预期文本时，按内容选择检索范围：题录用于标题和来源摘要，总结用于已写阅读记录与结论，全文用于存储的文章正文。中文词项使用子串匹配；短语模式匹配连续短语，词项模式要求全部检索词出现。查询最新发表状态或变化后的文章版本时，可能需要重新核对来源。

[Agent 文献库参考](../plugins/nasa-ads/skills/nasa-ads/references/literature-memory.md)记录完整命令与证据要求，[Web 审查记录](web-audit.md)保留浏览器测试和截图。
