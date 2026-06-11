# NASA ADS Skill

[English README](./README.md)

一个面向 Claude Code、Codex 等工具的 NASA ADS skill/plugin 打包仓库。

本仓库以文档和技能封装为主，不提供独立的 API client 或后台服务；它提供了一组 prompt/skill 资产，用来指导宿主代理通过本地 shell 和你的 token 调用 [NASA Astrophysics Data System (ADS)](https://ui.adsabs.harvard.edu/) REST API。

从定位上说，这个仓库是对公开项目 [adsabs-dev-api](https://github.com/adsabs/adsabs-dev-api) 的技能化封装：把 ADS API 的能力重新包装成适用于 Claude Code、Codex、Gemini 等代理工具的 skills、slash commands 和 plugin manifests。

## 功能覆盖

| 功能 | 说明 |
|------|------|
| 文献检索 | 支持按作者、标题、摘要、bibcode、DOI、arXiv ID、天体对象、ORCID 或全文检索 |
| 元数据 | 返回标题、作者、摘要、年份、期刊、DOI、被引数和标识符 |
| 引文导出 | 导出 BibTeX、AASTeX、MNRAS、RIS、EndNote、IEEE 等格式 |
| 文库管理 | 列出、查看、创建、更新、分享、组合和删除 ADS libraries |
| 指标统计 | 获取 h-index、g-index、i10-index、引文统计、阅读统计和其他指标 |
| 引文辅助 | 推荐相关文献或可能遗漏的引用 |
| Resolver | 返回 ADS、出版社、arXiv 和数据归档链接 |

## 范围

本包刻意聚焦在实际文献调研和引用导出工作流，不尝试封装 ADS API 的所有端点。如果需要期刊元数据、天体对象查询、可视化或参考文献解析等较少用的能力，请直接查阅官方 ADS API 文档。

## 依赖要求

你需要具备以下条件：

1. 一个 ADS API token，可从 [ADS token settings](https://ui.adsabs.harvard.edu/#user/settings/token) 获取
2. 可以访问 `https://api.adsabs.harvard.edu` 的外网 HTTPS 连接
3. 宿主环境允许代理运行 shell 命令，例如 `curl`

支持的环境变量：

- `ADS_API_TOKEN`
- `ADS_DEV_KEY`

示例：

```bash
export ADS_API_TOKEN="your-token-here"
```

```powershell
[System.Environment]::SetEnvironmentVariable("ADS_API_TOKEN", "your-token-here", "User")
```

## 安装后：创建并设置 ADS API token

安装 skill 或 plugin 后，首次调用 ADS 前需要先创建个人 ADS API token。检索、导出引用、管理 library、统计 metrics、citation helper 和 resolver 都需要这个 token。

1. 打开 [ADS token settings](https://ui.adsabs.harvard.edu/#user/settings/token)。
2. 注册 ADS 账号，或登录已有账号。
3. 如果直达链接没有打开 token 页面，就进入账户设置并选择 **API Token**。
4. 点击 **Generate a new key**。
5. 复制生成的 token，并妥善保管。不要把 token 提交到本仓库，也不要贴到共享日志里。
6. 把 token 保存为名为 `ADS_API_TOKEN` 的环境变量：

```bash
export ADS_API_TOKEN="paste-your-token-here"
```

```powershell
[System.Environment]::SetEnvironmentVariable("ADS_API_TOKEN", "paste-your-token-here", "User")
```

7. 重启终端或宿主助手会话，让它能读取新的环境变量。

## 一句话交给代理安装

如果你的宿主代理可以修改文件并执行 shell 命令，很多时候可以直接复制一句话给代理，而不用自己手工按步骤操作。

### Codex

把下面这句话直接发给 Codex：

```text
Install the NASA ADS skill from https://github.com/SukiYume/nasa-ads-skill into this repository by copying `plugins/nasa-ads` into `./plugins/nasa-ads`, then merge the `nasa-ads` entry from `.agents/plugins/marketplace.json` into `./.agents/plugins/marketplace.json` without overwriting existing plugins.
```

如果只想安装 skill：

```text
Install only the NASA ADS skill from https://github.com/SukiYume/nasa-ads-skill by copying `plugins/nasa-ads/skills/nasa-ads/SKILL.md` to `$CODEX_HOME/skills/nasa-ads/SKILL.md` (default `~/.codex/skills/nasa-ads/SKILL.md`).
```

### Claude Code

把下面这句话直接发给 Claude Code：

```text
Add `SukiYume/nasa-ads-skill` as a Claude plugin marketplace and install `nasa-ads@nasa-ads-community`, then confirm the NASA ADS slash commands are available.
```

### Gemini CLI

把下面这句话直接发给 Gemini：

```text
Install the NASA ADS skill from https://github.com/SukiYume/nasa-ads-skill by placing `plugins/nasa-ads/skills/nasa-ads/SKILL.md` in this project and adding `@./plugins/nasa-ads/skills/nasa-ads/SKILL.md` to `GEMINI.md`.
```

### 通用 AI Assistant

对于任何支持 Markdown skill 或 prompt 文件的代理，可以直接发：

```text
Download `https://raw.githubusercontent.com/SukiYume/nasa-ads-skill/master/plugins/nasa-ads/skills/nasa-ads/SKILL.md` and load it as a reusable Markdown skill for NASA ADS search, metadata, BibTeX, libraries, metrics, and resolver workflows.
```

## 人工安装

下面是面向研究者和开发者的手工安装说明。

### Claude Code (CLI / Desktop / VS Code / JetBrains)

先把这个仓库加到插件市场，再安装插件：

```bash
# Step 1: Add the marketplace
claude plugin marketplace add SukiYume/nasa-ads-skill

# Step 2: Install the plugin
claude plugin install nasa-ads@nasa-ads-community
```

也可以在 Claude Code 会话里执行：

```text
/plugin marketplace add SukiYume/nasa-ads-skill
/plugin install nasa-ads@nasa-ads-community
```

安装后会得到五个 slash commands：

```text
/nasa-ads:ads-search author:Einstein gravitational waves
/nasa-ads:ads-bibtex 2016PhRvL.116f1102A
/nasa-ads:ads-library list
/nasa-ads:ads-metrics 2016PhRvL.116f1102A
/nasa-ads:ads-cite similar 2016PhRvL.116f1102A
```

`/nasa-ads:ads-library` 额外支持元数据更新、按查询增删、权限分享、集合运算和删除 library。

这个 skill 也会在自然语言请求中自动触发，例如 papers、citations、ADS、BibTeX、arXiv、libraries、metrics 等相关问题。

首次运行命令前，请先完成[安装后：创建并设置 ADS API token](#安装后创建并设置-ads-api-token)。如果缺少 `ADS_API_TOKEN` 或 `ADS_DEV_KEY`，命令会返回 `401 Unauthorized` 或要求你提供 token。

### Codex

**方案 A：在当前仓库中安装插件**

1. 把 `plugins/nasa-ads` 目录复制到你的项目
2. 把 `nasa-ads` 插件条目合并到 `.agents/plugins/marketplace.json`

```bash
git clone https://github.com/SukiYume/nasa-ads-skill.git /tmp/nasa-ads-skill
cp -r /tmp/nasa-ads-skill/plugins/nasa-ads ./plugins/nasa-ads
python - <<'PY'
import json
from pathlib import Path

path = Path(".agents/plugins/marketplace.json")
path.parent.mkdir(parents=True, exist_ok=True)
entry = {
    "name": "nasa-ads",
    "source": {"source": "local", "path": "./plugins/nasa-ads"},
    "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
    "category": "Research",
}

if path.exists():
    data = json.loads(path.read_text())
else:
    data = {"name": "local", "interface": {"displayName": "Local Plugins"}, "plugins": []}

data.setdefault("name", "local")
data.setdefault("interface", {}).setdefault("displayName", "Local Plugins")
data["plugins"] = [p for p in data.get("plugins", []) if p.get("name") != "nasa-ads"] + [entry]
path.write_text(json.dumps(data, indent=2) + "\n")
PY
```

**方案 B：个人安装，供所有仓库复用**

```bash
cp -r plugins/nasa-ads ~/plugins/nasa-ads
mkdir -p ~/.agents/plugins
# 把 nasa-ads 条目合并到 ~/.agents/plugins/marketplace.json；不要覆盖已有插件。
```

**方案 C：只安装 skill，不安装 plugin metadata**

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills/nasa-ads"
cp plugins/nasa-ads/skills/nasa-ads/SKILL.md "${CODEX_HOME:-$HOME/.codex}/skills/nasa-ads/SKILL.md"
```

### Gemini CLI

在项目的 `GEMINI.md` 中加入这一行：

```text
@./plugins/nasa-ads/skills/nasa-ads/SKILL.md
```

或者把 skill 文件复制到 Gemini 的 skill 目录中。

### 其他 AI Assistant

核心文件是 `plugins/nasa-ads/skills/nasa-ads/SKILL.md`。这是一个自包含的 ADS API Markdown skill，可以复制到任何支持 skill/prompt 文件的代理目录中。

---

## 给 AI Agent 的安装说明

这一节面向会替用户自动执行安装动作的代理。

无论使用下面哪种安装方式，安装完成后都要明确提醒用户创建 ADS API token：

1. 打开 https://ui.adsabs.harvard.edu/#user/settings/token。
2. 注册或登录 ADS。
3. 如果直达链接没有进入 token 页面，就进入账户设置，再选择 **API Token**。
4. 点击 **Generate a new key** 并复制 token。
5. 把 token 保存到用户 shell 环境中的 `ADS_API_TOKEN` 或 `ADS_DEV_KEY`。
6. 重启终端或助手会话后再调用 ADS API。

### Claude Code Agent

执行下面两个命令：

```bash
claude plugin marketplace add SukiYume/nasa-ads-skill
claude plugin install nasa-ads@nasa-ads-community
```

安装后无需额外的插件配置，skill 和 commands 会立即可用；但 ADS API 调用仍然要求用户创建 ADS API token，并把它暴露为 `ADS_API_TOKEN` 或 `ADS_DEV_KEY`。

如果是本地开发或测试：

```bash
git clone https://github.com/SukiYume/nasa-ads-skill.git /tmp/nasa-ads-skill
cd /tmp/nasa-ads-skill
claude plugin marketplace add .
claude plugin install nasa-ads@nasa-ads-community
```

### Codex Agent

克隆仓库并接入 marketplace：

```bash
git clone https://github.com/SukiYume/nasa-ads-skill.git /tmp/nasa-ads-skill
cp -r /tmp/nasa-ads-skill/plugins/nasa-ads ./plugins/nasa-ads
python - <<'PY'
import json
from pathlib import Path

path = Path(".agents/plugins/marketplace.json")
path.parent.mkdir(parents=True, exist_ok=True)
entry = {
    "name": "nasa-ads",
    "source": {"source": "local", "path": "./plugins/nasa-ads"},
    "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
    "category": "Research",
}

if path.exists():
    data = json.loads(path.read_text())
else:
    data = {"name": "local", "interface": {"displayName": "Local Plugins"}, "plugins": []}

data.setdefault("name", "local")
data.setdefault("interface", {}).setdefault("displayName", "Local Plugins")
data["plugins"] = [p for p in data.get("plugins", []) if p.get("name") != "nasa-ads"] + [entry]
path.write_text(json.dumps(data, indent=2) + "\n")
PY
```

如果只需要 skill：

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills/nasa-ads"
curl -sL https://raw.githubusercontent.com/SukiYume/nasa-ads-skill/master/plugins/nasa-ads/skills/nasa-ads/SKILL.md \
  -o "${CODEX_HOME:-$HOME/.codex}/skills/nasa-ads/SKILL.md"
```

如果希望 Codex 的 skill-only 安装也有更好的 UI 元数据，也把 `plugins/nasa-ads/skills/nasa-ads/agents/openai.yaml` 复制到同样相对位置的 `agents/openai.yaml`。

### Gemini Agent

把 skill 引用追加到 `GEMINI.md`：

```bash
echo '@./plugins/nasa-ads/skills/nasa-ads/SKILL.md' >> GEMINI.md
```

或者直接拉取 skill 文件：

```bash
mkdir -p plugins/nasa-ads/skills/nasa-ads
curl -sL https://raw.githubusercontent.com/SukiYume/nasa-ads-skill/master/plugins/nasa-ads/skills/nasa-ads/SKILL.md \
  -o plugins/nasa-ads/skills/nasa-ads/SKILL.md
echo '@./plugins/nasa-ads/skills/nasa-ads/SKILL.md' >> GEMINI.md
```

### 通用 Agent

对于任何支持 Markdown skill 的代理，只需要获取这一个文件：

```bash
curl -sL https://raw.githubusercontent.com/SukiYume/nasa-ads-skill/master/plugins/nasa-ads/skills/nasa-ads/SKILL.md \
  -o nasa-ads-skill.md
```

然后把 `nasa-ads-skill.md` 加载到系统提示词或 skill 目录即可。基础功能不依赖其他文件。

## 使用示例

自然语言请求：

- “搜索关于系外行星大气的最新 ADS 文献”
- “给我这篇论文的 BibTeX：2016PhRvL.116f1102A”
- “列出我的 ADS libraries”
- “这些 bibcodes 的 citation metrics 是什么？”
- “找和 2016PhRvL.116f1102A 相似的论文”

Claude command 示例：

```text
/nasa-ads:ads-search dark matter year:2020-2024
/nasa-ads:ads-bibtex 2016PhRvL.116f1102A 2017ApJ...848L..12A --format aastex
/nasa-ads:ads-library create "My Reading List"
/nasa-ads:ads-cite links 2016PhRvL.116f1102A
```

## 仓库结构

```text
nasa-ads-skill/
├── .claude-plugin/
│   └── marketplace.json
├── .agents/
│   └── plugins/
│       └── marketplace.json
├── plugins/
│   └── nasa-ads/
│       ├── .claude-plugin/
│       │   └── plugin.json
│       ├── .codex-plugin/
│       │   └── plugin.json
│       ├── commands/
│       │   ├── ads-search.md
│       │   ├── ads-bibtex.md
│       │   ├── ads-library.md
│       │   ├── ads-metrics.md
│       │   └── ads-cite.md
│       └── skills/
│           └── nasa-ads/
│               ├── agents/
│               │   └── openai.yaml
│               └── SKILL.md
├── AGENTS.md
├── CLAUDE.md
├── GEMINI.md
├── README.zh-CN.md
└── README.md
```

详细的 ADS API 参考位于 `plugins/nasa-ads/skills/nasa-ads/SKILL.md`；Claude command 文件是面向具体任务的包装层，应与该 skill 保持一致。

## 已覆盖的 API 端点

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/search/query` | GET | Search for papers |
| `/search/bigquery` | POST | Batch bibcode lookup |
| `/export/<format>` | GET/POST | Export citations |
| `/biblib/libraries` | GET/POST | List or create libraries |
| `/biblib/libraries/<id>` | GET | View library contents |
| `/biblib/documents/<id>` | POST/PUT/DELETE | POST adds/removes documents, PUT updates library metadata, DELETE removes the library |
| `/biblib/query/<id>` | GET/POST | Add or remove papers by query |
| `/biblib/libraries/operations/<id>` | POST | Library set operations |
| `/biblib/permissions/<id>` | GET/POST | Library permissions |
| `/metrics` | POST | Citation metrics and indicators |
| `/citation_helper` | POST | Suggested citations |
| `/resolver/<bibcode>` | GET | Full-text and data links |

## 说明

- 这些打包后的 commands 默认假设宿主代理可以运行 shell 命令。
- 示例里的 token 读取顺序会优先使用 `ADS_API_TOKEN`，其次回退到 `ADS_DEV_KEY`。
- 本仓库不会存储任何 token。
- 如果你新增或修改 ADS workflow，请先更新 `SKILL.md`，再同步更新暴露同一能力的 Claude command 文件。

## License

MIT
