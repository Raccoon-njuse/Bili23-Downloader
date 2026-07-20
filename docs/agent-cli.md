# Media Agent CLI 与 Agent Skill

`media-agent` 是本仓库的本地 CLI，`.agents/skills/media-agent-cli` 是与它配套的 Agent 操作规范。二者把用户在本机自行登录后的收藏夹查询、链接解析、单集选择和下载能力提供给本地 Agent，用于后续转写、字幕比对或视觉分析。

它不是 MCP 服务，不监听网络端口。任何可访问用户 `PATH` 的 Agent 都能执行 CLI，因此 Skill 必须遵守最小权限、最小数据读取和逐次确认的边界。

## 源码与全局安装

```bash
git clone https://github.com/Raccoon-njuse/media-agent-cli.git
cd media-agent-cli
uv sync
./scripts/install-global.sh --all
export PATH="$HOME/.local/bin:$PATH"
media-agent --help
```

安装脚本只创建以下软链接，并拒绝覆盖其他路径：

| 对象 | 默认路径 | 可覆盖环境变量 |
| --- | --- | --- |
| CLI | `$HOME/.local/bin/media-agent` | `MEDIA_AGENT_BIN_DIR` |
| Codex Skill | `$HOME/.codex/skills/media-agent-cli` | `CODEX_HOME`、`CODEX_SKILLS_DIR` |

只注册一个组件时使用 `--cli` 或 `--skill`；移除当前 checkout 的链接时使用 `--uninstall`。安装 Skill 后应新建 Codex 任务或重启 Codex。其他 Agent 应将 `.agents/skills/media-agent-cli` 注册到自身的项目级或用户级 Skill 路径。

## 登录与诊断

用户自行启动 `uv run python src/main.py` 并完成本地扫码登录。CLI 不处理短信、二维码或明文凭据。首次调用前运行：

```bash
media-agent doctor
```

该命令返回登录状态、FFmpeg 状态和下载目录空间。`auth status` 与 `doctor` 可能包含 UID、昵称等账户摘要；Agent 不应将这些字段写入外部日志、工单或报告。

## 命令契约

所有成功与失败结果都在 stdout 输出一行 JSON；下载进度只写 stderr。Agent 应以进程退出码和 stdout JSON 判断结果，不得把 stderr 当结构化协议。

| 目标 | 命令 |
| --- | --- |
| 读取登录摘要 | `media-agent auth status` |
| 列出本人收藏夹 | `media-agent favorites list` |
| 查询一个收藏夹 | `media-agent favorites items <ID或链接> --page 1` |
| 解析链接 | `media-agent inspect '<链接>'` |
| 读取一个目标的媒体规格 | `media-agent inspect '<链接>' --episode 27 --with-media` |
| 验证计划 | `media-agent download '<链接>' --episode 27 --quality 720p --dry-run` |
| 下载合并媒体 | `media-agent download '<链接>' --episode 27 --quality 720p --output <任务目录>` |
| 下载转写用音频 | `media-agent download '<链接>' --episode 27 --audio-only --output <任务目录>` |

使用 `--episode`、`--part`、`--ep-id`、`--cid` 或 `--match` 明确选择目标。对多集、多 P 或收藏夹链接，不得因可解析而默认下载整季；`--all` 只在用户明确要求批量处理时使用。

## 推荐 Agent 工作流

1. 运行 `media-agent doctor`；无有效登录态时停下，等待用户自行登录。
2. 对用户指定链接运行 `inspect`，确认用户指定的剧集、分 P 或标题。
3. 有质量要求时运行 `inspect --with-media`，只从返回的可用规格中选择。
4. 用同一 selector 和规格运行 `download --dry-run`，核对计划。
5. 使用独立的 `--output <任务目录>` 执行真实下载。
6. 将成功结果中的本地文件路径交给后续处理，不把登录态、Cookie 或签名 URL 传递给下游。

## 使用与开源边界

只处理账号持有人本人有权访问的内容，且仅用于个人、本地、非商业任务。不得绕过 DRM、付费墙或平台访问控制，也不得将账号、凭据、请求签名或媒体公开分享。

这是一条媒体使用和 Agent 操作规则，不是对 GPLv3 代码权利的附加限制。来源、版权和再分发义务见根目录的 [NOTICE](../NOTICE)、[UPSTREAM.md](../UPSTREAM.md) 与 [LICENSE](../LICENSE)。
