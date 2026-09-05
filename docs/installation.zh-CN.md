# 安装与更新指南

[返回 README](../README.zh-CN.md#安装) · [English](installation.md)

选择正在使用的宿主，完成对应安装，配置在线 ADS 请求所需的 token，再验证结果。每个宿主的命令集中在同一个小节。已经安装的用户可以直接查看[更新步骤](#更新已有安装)。

- [安装前准备](#安装前准备)
- [Claude Code 插件](#claude-code-plugin)
- [Codex 插件](#codex-plugin)
- [Codex 独立 skill](#codex-独立-skill)
- [Gemini CLI](#gemini-cli)
- [其他宿主](#通用-markdown-skill-宿主)
- [注册 adslib](#注册-adslib-命令)
- [ADS token](#配置-ads-token)
- [安装与 API 验证](#验证-api)
- [更新步骤](#更新已有安装)

## 安装前准备

在全新电脑上先准备以下内容：

1. **Git**：从 [git-scm.com/downloads](https://git-scm.com/downloads) 安装。
2. **至少一个宿主**：
   - [Claude Code 安装文档](https://code.claude.com/docs/en/setup)
   - [Codex CLI 安装文档](https://developers.openai.com/codex/cli/)
   - [Gemini CLI 安装文档](https://geminicli.com/docs/get-started/installation/)
3. **ADS 账号和 API token**：用于在线 ADS 请求，按[配置 ADS token](#配置-ads-token)完成；本地浏览和缓存引用导出可以离线使用。
4. **Python 3.10 或更新版本**：完整的全文与文献记忆流程需要 Python，可从 [python.org/downloads](https://www.python.org/downloads/) 安装。四个自带 CLI 的核心路径都不需要第三方 Python 包。Python 不可用时，macOS/Linux/WSL 可用 `curl`，Windows 可用 PowerShell，执行有限的 ADS 元数据/API 直接 HTTP 回退；该回退不提供全文准备和持久文献记忆。
5. **可选 PDF 工具**：`pdftotext` 和 `pdfinfo` 可改善 PDF 文本处理，`pdftoppm` 可渲染扫描页。缺少这些工具时，具备相应能力的宿主仍可直接视觉阅读下载的 PDF 或页面图片。
6. **可访问外网 HTTPS**：需要连接 `api.adsabs.harvard.edu`、`arxiv.org` 和流程选中的合法出版社或仓储来源。

检查程序是否已经安装：

```bash
git --version
python3 --version   # macOS、Linux 或 WSL
python --version    # Windows；也可以使用 "py -3 --version"
claude --version   # 使用 Claude Code 时检查
codex --version    # 使用 Codex 时检查
gemini --version   # 使用 Gemini CLI 时检查
```

如果所选宿主命令不存在，请先按照上面的官方安装文档完成安装或升级。

## 安装

在下面选择一个宿主。Claude Code 和 Codex 可以直接把公开 GitHub 仓库加入 marketplace；独立 Skill 和 Gemini 安装会保留本地源码 clone，便于以后更新。

### Claude Code Plugin

Claude Code 安装完成后，以下命令可用于 macOS、Linux、Windows PowerShell 和 Windows Command Prompt。

1. 把 GitHub 仓库加入 Claude Code marketplace：

```bash
claude plugin marketplace add SukiYume/nasa-ads-skill
```

2. 从该 marketplace 安装 `nasa-ads`：

```bash
claude plugin install nasa-ads@nasa-ads-community
```

3. 检查安装结果：

```bash
claude plugin list
```

列表中应出现 `nasa-ads@nasa-ads-community`。

4. 启动 Claude Code：

```bash
claude
```

如果在现有会话期间完成安装，请运行 `/reload-plugins`。Plugin 提供以下命令：

```text
/nasa-ads:ads-search <query>
/nasa-ads:ads-bibtex <bibcodes>
/nasa-ads:ads-library [subcommand]
/nasa-ads:ads-metrics <bibcodes>
/nasa-ads:ads-cite [subcommand]
/nasa-ads:ads-fulltext <bibcodes, DOIs, or arXiv IDs>
/nasa-ads:ads-memory <search, collections, serve, citations, pending, or paper topics>
```

接着完成[注册 adslib](#注册-adslib-命令)和[配置 ADS token](#配置-ads-token)，然后执行[验证 API](#验证-api)中的公开论文测试。

### Codex Plugin

Codex plugin 可用于 Codex CLI 和桌面应用中的 Codex。IDE 扩展请使用下一节的独立 skill。

1. 把 GitHub 仓库加入 Codex marketplace：

```bash
codex plugin marketplace add SukiYume/nasa-ads-skill
```

2. 安装 plugin：

```bash
codex plugin add nasa-ads@nasa-ads-community
```

3. 确认 Codex 已识别：

```bash
codex plugin list
```

4. 新建一个 Codex 会话，让安装后的 skill 进入新会话的 skill 列表：

```bash
codex
```

可以用 `$nasa-ads` 显式调用、通过 `/skills` 查看，也可以直接描述天文文献任务。

接着完成[注册 adslib](#注册-adslib-命令)和[配置 ADS token](#配置-ads-token)，然后执行[验证 API](#验证-api)中的公开论文测试。

### Codex 独立 Skill

Codex 目前从 `~/.agents/skills` 发现用户级独立 skills。Codex CLI 和 IDE 扩展都可使用此路径。

#### macOS、Linux 或 WSL

把源码 clone 保存在固定的用户级路径，再把 skill 内容复制到 Codex 的发现目录：

```bash
mkdir -p "$HOME/.local/share"
git clone --depth 1 \
  https://github.com/SukiYume/nasa-ads-skill.git \
  "$HOME/.local/share/nasa-ads-skill"
mkdir -p "$HOME/.agents/skills/nasa-ads"
cp -R \
  "$HOME/.local/share/nasa-ads-skill/plugins/nasa-ads/skills/nasa-ads/." \
  "$HOME/.agents/skills/nasa-ads/"
```

检查必需文件：

```bash
test -f "$HOME/.agents/skills/nasa-ads/SKILL.md" \
  && test -f "$HOME/.agents/skills/nasa-ads/agents/openai.yaml" \
  && test -f "$HOME/.agents/skills/nasa-ads/scripts/ads_api.py" \
  && test -f "$HOME/.agents/skills/nasa-ads/scripts/fulltext.py" \
  && test -f "$HOME/.agents/skills/nasa-ads/scripts/literature_db.py" \
  && test -f "$HOME/.agents/skills/nasa-ads/scripts/library_catalog.py" \
  && test -f "$HOME/.agents/skills/nasa-ads/scripts/library_web.py" \
  && test -f "$HOME/.agents/skills/nasa-ads/scripts/adslib.py" \
  && test -f "$HOME/.agents/skills/nasa-ads/assets/library/index.html" \
  && test -f "$HOME/.agents/skills/nasa-ads/assets/library/style.css" \
  && test -f "$HOME/.agents/skills/nasa-ads/assets/library/app.js" \
  && test -f "$HOME/.agents/skills/nasa-ads/references/research-writing.md" \
  && test -f "$HOME/.agents/skills/nasa-ads/references/ads-cli.md" \
  && test -f "$HOME/.agents/skills/nasa-ads/references/fulltext.md" \
  && test -f "$HOME/.agents/skills/nasa-ads/references/literature-memory.md" \
  && test -f "$HOME/.agents/skills/nasa-ads/references/digest-schema.md" \
  && test -f "$HOME/.agents/skills/nasa-ads/references/http-fallback.md" \
  && test -f "$HOME/.agents/skills/nasa-ads/references/libraries.md" \
  && echo "NASA ADS skill installed"
```

#### Windows PowerShell

把源码 clone 保存在固定的用户级路径，再把 skill 内容复制到 Codex 的发现目录：

```powershell
$nasaAdsSource = Join-Path $HOME 'nasa-ads-skill-source'
$nasaAdsSkill = Join-Path $HOME '.agents\skills\nasa-ads'
git clone --depth 1 `
  https://github.com/SukiYume/nasa-ads-skill.git `
  $nasaAdsSource
New-Item -ItemType Directory -Force $nasaAdsSkill | Out-Null
Copy-Item -Recurse -Force `
  (Join-Path $nasaAdsSource 'plugins\nasa-ads\skills\nasa-ads\*') `
  $nasaAdsSkill
```

检查必需文件：

```powershell
$nasaAdsSkillReady = `
  (Test-Path "$HOME\.agents\skills\nasa-ads\SKILL.md") -and `
  (Test-Path "$HOME\.agents\skills\nasa-ads\agents\openai.yaml") -and `
  (Test-Path "$HOME\.agents\skills\nasa-ads\scripts\ads_api.py") -and `
  (Test-Path "$HOME\.agents\skills\nasa-ads\scripts\fulltext.py") -and `
  (Test-Path "$HOME\.agents\skills\nasa-ads\scripts\literature_db.py") -and `
  (Test-Path "$HOME\.agents\skills\nasa-ads\scripts\library_catalog.py") -and `
  (Test-Path "$HOME\.agents\skills\nasa-ads\scripts\library_web.py") -and `
  (Test-Path "$HOME\.agents\skills\nasa-ads\scripts\adslib.py") -and `
  (Test-Path "$HOME\.agents\skills\nasa-ads\assets\library\index.html") -and `
  (Test-Path "$HOME\.agents\skills\nasa-ads\assets\library\style.css") -and `
  (Test-Path "$HOME\.agents\skills\nasa-ads\assets\library\app.js") -and `
  (Test-Path "$HOME\.agents\skills\nasa-ads\references\research-writing.md") -and `
  (Test-Path "$HOME\.agents\skills\nasa-ads\references\ads-cli.md") -and `
  (Test-Path "$HOME\.agents\skills\nasa-ads\references\fulltext.md") -and `
  (Test-Path "$HOME\.agents\skills\nasa-ads\references\literature-memory.md") -and `
  (Test-Path "$HOME\.agents\skills\nasa-ads\references\digest-schema.md") -and `
  (Test-Path "$HOME\.agents\skills\nasa-ads\references\http-fallback.md") -and `
  (Test-Path "$HOME\.agents\skills\nasa-ads\references\libraries.md")
$nasaAdsSkillReady
```

成功时会返回 `True`。

新建 Codex 会话，通过 `/skills` 查看列表，或在提示词中输入 `$nasa-ads`。

如果只想让当前仓库使用它，请把同一个 `nasa-ads` skill 目录复制到 `<repository>/.agents/skills/nasa-ads`。

### Gemini CLI

Gemini CLI 通过 `GEMINI.md` 加载指令文件。下面的用户级安装会让 NASA ADS 在所有 Gemini CLI 项目中可用。

#### macOS、Linux 或 WSL

```bash
mkdir -p "$HOME/.gemini"
git clone --depth 1 \
  https://github.com/SukiYume/nasa-ads-skill.git \
  "$HOME/.gemini/nasa-ads-skill"
printf '\n@./nasa-ads-skill/plugins/nasa-ads/skills/nasa-ads/SKILL.md\n' \
  >> "$HOME/.gemini/GEMINI.md"
```

#### Windows PowerShell

```powershell
New-Item -ItemType Directory -Force "$HOME\.gemini" | Out-Null
git clone --depth 1 `
  https://github.com/SukiYume/nasa-ads-skill.git `
  "$HOME\.gemini\nasa-ads-skill"
Add-Content -Path "$HOME\.gemini\GEMINI.md" -Value `
  "`n@./nasa-ads-skill/plugins/nasa-ads/skills/nasa-ads/SKILL.md"
```

启动 Gemini CLI：

```bash
gemini
```

然后运行：

```text
/memory reload
/memory show
```

确认已加载内容中包含 `NASA ADS` 标题。本仓库自己的 [`GEMINI.md`](../GEMINI.md) 展示了同样的项目级相对导入格式。

### 通用 Markdown Skill 宿主

1. 克隆仓库：

```bash
git clone https://github.com/SukiYume/nasa-ads-skill.git
```

2. 把完整的 `plugins/nasa-ads/skills/nasa-ads/` 目录复制到宿主文档指定的 skill 或 prompt 目录。
3. 配置宿主加载其中的 `SKILL.md`。
4. 确认宿主可以用 Python 3 运行自带 CLI，或能通过 `curl`/PowerShell 使用直接 HTTP 回退。
5. 按下一节设置 ADS token。
6. 运行[验证 API](#验证-api)中的公开论文测试。

不同宿主使用的发现目录和调用语法可能不同。未采用上述 Claude Code、Codex 或 Gemini 约定时，请查阅该宿主的当前官方文档。

## 注册 adslib 命令

每台电脑安装 skill 时一并完成这项注册。手动安装或修复路径时，直接运行已安装的 Python 脚本。之后在任意目录输入 `adslib` 即可打开 Web。宿主的插件安装命令负责安装文件；下面这一步注册终端命令。README 中的一句话安装提示词已包含此步骤。

可以直接让 Agent 完成：

> 从当前已安装的 nasa-ads skill 定位 scripts/adslib.py，执行 install 注册 adslib 命令，保留已有 PATH 设置，并在新终端验证 adslib --version 和文献库页面。

**Windows PowerShell，Codex 独立 skill：**

```powershell
python "$HOME\.agents\skills\nasa-ads\scripts\adslib.py" install
```

**macOS、Linux 或 WSL，Codex 独立 skill：**

```bash
python3 "$HOME/.agents/skills/nasa-ads/scripts/adslib.py" install
```

Claude 独立 skill 使用 `~/.claude/skills/nasa-ads/scripts/adslib.py`；marketplace 插件使用已加载 `SKILL.md` 所在目录下的 `scripts/adslib.py`；Gemini 使用其源码副本中的同名脚本。路径由 Agent 从实际安装定位。

安装器在 Windows 创建 `~/.local/bin/adslib.cmd` 和供 Git Bash 使用的 `~/.local/bin/adslib` 并补充用户 PATH；macOS/Linux/WSL 创建 `~/.local/bin/adslib`，按需为当前 bash、zsh 或 sh 配置追加带标记的 PATH 段。已有设置会保留，同名第三方命令会保留并提示冲突。自主管理 PATH 时使用 `install --bin-dir <目录> --no-path`，再把该目录加入自己的 PATH。

新开终端后验证：

```bash
adslib --version
adslib
```

版本应为 `1.15.1`。浏览器自动打开，服务在后台运行。使用 `adslib status`、`adslib stop` 和 `adslib restart` 管理服务；`adslib serve` 在前台运行，按 `Ctrl+C` 停止。完整命令见[文献库指南](library.zh-CN.md)。找不到命令时重启终端应用或 IDE，使其读取新的 PATH；也可直接执行已安装的 `adslib.py`。移动 skill、升级到新的插件缓存目录或更换 Python 后，再运行一次 `install` 更新命令指向。

## 配置 ADS Token

每次调用 ADS Developer API 都需要个人 token。

1. 打开 [ADS token settings](https://ui.adsabs.harvard.edu/#user/settings/token)。
2. 注册 ADS 账号或登录已有账号。
3. 如果直达链接落在其他页面，请进入账号设置并选择 **API Token**。
4. 选择 **Generate a new key**。
5. 复制 token 并妥善保管。

建议使用 `ADS_API_TOKEN` 作为主要环境变量；`ADS_DEV_KEY` 可作为兼容回退。

### macOS、Linux 或 WSL

在当前终端设置 token：

```bash
export ADS_API_TOKEN='paste-your-token-here'
```

这个值会在终端关闭时失效。如果需要持久保存，可把同一行 `export` 加入当前 shell 的启动文件，常见文件包括 `~/.zshrc`、`~/.bashrc` 或 `~/.bash_profile`，然后打开新终端。

检查变量是否存在，同时避免打印 token：

```bash
if [ -n "${ADS_API_TOKEN:-${ADS_DEV_KEY:-}}" ]; then
  echo "ADS token is set"
else
  echo "ADS token is missing"
fi
```

### Windows PowerShell

在当前 PowerShell 会话中设置：

```powershell
$env:ADS_API_TOKEN = 'paste-your-token-here'
```

设置持久的用户环境变量：

```powershell
[Environment]::SetEnvironmentVariable(
  'ADS_API_TOKEN',
  'paste-your-token-here',
  'User'
)
```

执行持久设置后，请打开新终端并重启宿主。检查变量是否存在，同时避免打印 token：

```powershell
if ($env:ADS_API_TOKEN -or $env:ADS_DEV_KEY) {
  'ADS token is set'
} else {
  'ADS token is missing'
}
```

请勿把 token 放入仓库、截图、共享日志、shell 转录或支持请求。发现泄露时，请在 ADS 设置中撤销并重新生成。

## 验证 API

下面使用一篇公开论文验证网络、身份认证和 ADS 响应格式。

### 已安装的宿主

设置持久 token 后重启宿主。在 Claude Code 中运行：

```text
/nasa-ads:ads-search bibcode:2016PhRvL.116f1102A
```

在 Codex、Gemini CLI 或其他宿主中发送：

```text
在 NASA ADS 中检索 bibcode 2016PhRvL.116f1102A，返回标题、年份和 bibcode。
```

结果应识别出 *Observation of Gravitational Waves from a Binary Black Hole Merger*，并包含 `2016PhRvL.116f1102A`。如果提示缺少 token，说明宿主没有继承环境变量；如果返回 HTTP 错误，请按[排错](../README.zh-CN.md#排错)处理。

### 自带 Python CLI

检查已安装 skill 目录中的脚本。下面使用 Codex 独立 skill 的位置。Gemini 使用 `~/.gemini/nasa-ads-skill/plugins/nasa-ads/skills/nasa-ads`；marketplace 插件可以让 Agent 报告其已加载 `SKILL.md` 所在的目录。其他位置参见[定位已安装的 Skill](library.zh-CN.md#定位已安装的-skill)。将变量设为实际路径，并在同一个终端中执行后续检查。

macOS、Linux 或 WSL：

```bash
nasa_ads_skill="$HOME/.agents/skills/nasa-ads"
python3 "$nasa_ads_skill/scripts/ads_api.py" --version
python3 "$nasa_ads_skill/scripts/fulltext.py" --version
python3 "$nasa_ads_skill/scripts/literature_db.py" --version
python3 "$nasa_ads_skill/scripts/adslib.py" --version
python3 "$nasa_ads_skill/scripts/ads_api.py" --no-store search \
  --query 'bibcode:2016PhRvL.116f1102A' \
  --fields bibcode,title,year \
  --rows 1
```

Windows PowerShell：

```powershell
$nasaAdsSkill = Join-Path $HOME '.agents\skills\nasa-ads'
python "$nasaAdsSkill/scripts/ads_api.py" --version
python "$nasaAdsSkill/scripts/fulltext.py" --version
python "$nasaAdsSkill/scripts/literature_db.py" --version
python "$nasaAdsSkill/scripts/adslib.py" --version
python "$nasaAdsSkill/scripts/ads_api.py" --no-store search `
  --query 'bibcode:2016PhRvL.116f1102A' `
  --fields 'bibcode,title,year' `
  --rows 1
```

如果 Python 注册为 `py` launcher，请把 `python` 换成 `py -3`。四个版本命令均应报告 `1.15.1`。JSON 响应中应包含 bibcode `2016PhRvL.116f1102A`。`--no-store` 诊断会保留文献库当前内容。

### 全文 smoke test

这篇公开 arXiv 论文有官方 HTML 版本，因此 smoke test 不依赖 PDF 辅助工具。环境中没有 ADS token 时也可以运行。

macOS、Linux 或 WSL：

```bash
python3 "$nasa_ads_skill/scripts/fulltext.py" fetch \
  arXiv:1901.04502 \
  --source arxiv --no-store
```

Windows PowerShell：

```powershell
python "$nasaAdsSkill/scripts/fulltext.py" fetch `
  'arXiv:1901.04502' `
  --source arxiv --no-store
```

结果应报告 `status: fulltext`，选择 `https://arxiv.org/html/1901.04502`，并在用户缓存目录中给出确实存在的 `artifact_path`、`text_path` 和 `manifest_path`。官方 HTML 不可用时，脚本会自动尝试 `https://arxiv.org/pdf/<id>`。总结前可把返回的 `text_path` 传给 `fulltext.py outline <text_path>`，检查推断出的文章结构。

在公式、图、表、页码或视觉阅读检查中明确需要 PDF 时，使用 `--format pdf`；`--format html` 只请求结构化 HTML。默认的 `--format auto` 保持 HTML 优先和自动回退流程。

### 文献记忆 smoke test

数据库 CLI 不需要 ADS token 就能验证 schema 和摘要契约。`template` 只输出 JSON，不会创建文献库。

macOS、Linux 或 WSL：

```bash
python3 "$nasa_ads_skill/scripts/literature_db.py" --version
python3 "$nasa_ads_skill/scripts/adslib.py" --version
python3 "$nasa_ads_skill/scripts/literature_db.py" template
```

Windows PowerShell：

```powershell
python "$nasaAdsSkill/scripts/literature_db.py" --version
python "$nasaAdsSkill/scripts/adslib.py" --version
python "$nasaAdsSkill/scripts/literature_db.py" template
```

两个平台上的 CLI 版本命令均应报告 `1.15.1`。schema version 2 模板应包含 `overview`、`facets`、`findings`、`global_limitations` 和 `reading.coverage`。正常检索、全文获取和显式文献库写入会在 Windows 的 `%LOCALAPPDATA%\nasa-ads\literature` 或 macOS/Linux 的 `${XDG_DATA_HOME:-~/.local/share}/nasa-ads/literature` 创建或更新文献库。文献库不存在时，只读命令返回空结果且不会创建文件。可以通过 `NASA_ADS_LITERATURE_DIR` 选择其他位置。

### 直接 HTTP 回退

仅在 Python 3 无法运行自带 CLI，或所需端点尚未由 CLI 封装时使用。按 [`references/http-fallback.md`](../plugins/nasa-ads/skills/nasa-ads/references/http-fallback.md) 中的凭据预检、重定向规则、响应检查和对应平台示例操作。

## 更新已有安装

沿用安装时选择的方式和源码目录进行更新。已有数据库报告 schema 不匹配时，按[数据库升级步骤](library.zh-CN.md#升级旧版文献库)处理。

Claude Code 或 Codex plugin 需要刷新 marketplace 和已经安装的 plugin：

```bash
claude plugin marketplace update nasa-ads-community
claude plugin update nasa-ads@nasa-ads-community
```

```bash
codex plugin marketplace upgrade nasa-ads-community
codex plugin add nasa-ads@nasa-ads-community
```

Codex 独立 skill 或 Gemini CLI import 需要更新安装时选择的源码路径。下面的命令沿用本指南中的示例路径。

macOS、Linux 或 WSL 上的 Codex 独立 skill：

```bash
git -C "$HOME/.local/share/nasa-ads-skill" pull --ff-only
cp -R \
  "$HOME/.local/share/nasa-ads-skill/plugins/nasa-ads/skills/nasa-ads/." \
  "$HOME/.agents/skills/nasa-ads/"
```

Windows PowerShell 上的 Codex 独立 skill：

```powershell
$nasaAdsSource = Join-Path $HOME 'nasa-ads-skill-source'
$nasaAdsSkill = Join-Path $HOME '.agents\skills\nasa-ads'
git -C $nasaAdsSource pull --ff-only
Copy-Item -Recurse -Force `
  (Join-Path $nasaAdsSource 'plugins\nasa-ads\skills\nasa-ads\*') `
  $nasaAdsSkill
```

macOS、Linux 或 WSL 上的 Gemini CLI：

```bash
git -C "$HOME/.gemini/nasa-ads-skill" pull --ff-only
```

Windows PowerShell 上的 Gemini CLI：

```powershell
git -C "$HOME\.gemini\nasa-ads-skill" pull --ff-only
```

更新后从当前安装目录重新执行 `adslib.py install`，并验证 `adslib --version`。

Gemini CLI 更新后运行 `/memory reload`。Codex 或 Claude Code 更新后新建宿主会话。

验证通过后，可以[开始文献调研](../README.zh-CN.md#开始使用)或[打开 Web 文献库](../README.zh-CN.md#打开-web-文献库)。
