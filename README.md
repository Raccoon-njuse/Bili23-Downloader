# Media Agent CLI

`media-agent` 是一个本地命令行工具和 Agent Skill。它使用用户在本机自行完成的登录状态，提供收藏夹查询、链接解析、按集数或分 P 选择、规格检查和本地媒体下载能力，为后续的音视频转写、字幕比对或视觉分析准备输入。

它不是网络服务，不监听端口，也不会把 Cookie、扫码凭据或签名链接暴露给 Agent。

## 适用范围

- 只处理账号持有人依法有权访问的内容，并由账号持有人自行在本机登录。
- Agent 必须先确认具体集数、分 P 或标题；`--all` 和批量下载需要用户明确提出。
- 不绕过 DRM、付费墙、平台访问控制或技术保护措施。
- 下载产物和账户摘要可能包含个人数据，应保留在本地任务目录，不写入外部日志或工单。

这些是媒体使用与 Agent 操作边界，不改变本仓库代码的 GPLv3 权利。

## 从源码安装

需要 Git、Python 3.9+ 和 [uv](https://docs.astral.sh/uv/)。

```bash
git clone https://github.com/Raccoon-njuse/media-agent-cli.git
cd media-agent-cli
uv sync
./media-agent --help
```

根目录的启动器始终使用该 checkout 的 `.venv` 和 `src`，避免误用系统 Python。首次使用时可启动本地登录窗口，再由用户自行扫码：

```bash
uv run python src/main.py
```

在受限开发或测试环境中，可将配置、日志和任务数据库重定向到独立目录：

```bash
export MEDIA_AGENT_APPDATA_DIR="$PWD/.runtime"
```

## 注册全局 CLI 与 Codex Skill

```bash
./scripts/install-global.sh --all
export PATH="$HOME/.local/bin:$PATH"
media-agent --help
```

安装脚本只创建软链接，不复制源码，也不会覆盖已有同名路径：

| 对象 | 默认位置 | 可覆盖项 |
| --- | --- | --- |
| CLI | `$HOME/.local/bin/media-agent` | `MEDIA_AGENT_BIN_DIR` |
| Codex Skill | `$HOME/.codex/skills/media-agent-cli` | `CODEX_HOME`、`CODEX_SKILLS_DIR` |

安装 Skill 后新建 Codex 任务或重启 Codex，使其重新发现 Skill。其他 Agent 没有统一的全局目录：将 `.agents/skills/media-agent-cli` 注册到其用户级或项目级 Skill 目录，并保证其 shell 可以找到 `media-agent`。

移除当前 checkout 创建的链接：

```bash
./scripts/install-global.sh --uninstall
```

## 常用命令

```bash
# 仅在需要时读取收藏夹
media-agent favorites list
media-agent favorites items 123456 --page 1

# 精确检查一个目标与其可用规格
media-agent inspect 'https://www.bilibili.com/bangumi/play/ss38385' --episode 27 --with-media

# 先验证下载计划，再下载到本地任务目录
media-agent download 'https://www.bilibili.com/bangumi/play/ss38385' --episode 27 --quality 720p --dry-run
media-agent download 'https://www.bilibili.com/bangumi/play/ss38385' --episode 27 --audio-only --output ./artifacts/episode-27
```

成功和失败均在 stdout 输出单行 JSON；下载进度写入 stderr。Agent 应依据进程退出码和 stdout JSON 判断结果。完整命令约定见 [docs/agent-cli.md](docs/agent-cli.md)。

## 开源与来源

Media Agent CLI 是 [ScottSloan/Bili23-Downloader](https://github.com/ScottSloan/Bili23-Downloader) 的修改版派生作品，保留完整 Git 历史、适用版权声明和 GNU GPL v3.0 许可证。它不是上游项目或 Bilibili 的关联、维护或背书产品。

具体来源、修改范围和商标说明见 [UPSTREAM.md](UPSTREAM.md) 与 [NOTICE](NOTICE)。
