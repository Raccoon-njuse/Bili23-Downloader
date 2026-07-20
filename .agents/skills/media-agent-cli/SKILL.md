---
name: media-agent-cli
description: 在用户本人已完成本地登录、明确授权且只进行个人本地处理的前提下，使用 Media Agent CLI 查询收藏夹、解析媒体链接、精确选择剧集和清晰度，并下载媒体作为后续转写或分析工作流的输入时使用。
---

# Media Agent CLI

全局注册后使用 `media-agent`；若用户只提供源码 checkout，则在仓库根目录使用 `./media-agent`。先用 `command -v media-agent` 判断命令是否已注册。若不可用，不要自行修改用户全局环境，说明需要按仓库 README 安装。

此 Skill 约束 Agent 调用本地 CLI 的流程。它不是 MCP 服务，不监听网络端口，也不接管扫码或保存新的登录凭据。

## 使用边界

- 仅处理账号持有人本人已合法登录、有权访问且明确要求处理的内容；仅作个人、本地、非商业工作流。
- 不共享账号、Cookie、token、签名 URL、下载媒体或账户摘要；不得把 CLI 包装为他人可用的下载服务。
- 不绕过付费墙、DRM、平台访问控制或其他技术保护措施。遇到不可访问或受保护内容时停止并如实报告。
- 不默认批量下载。`--all`、多链接和收藏夹批处理必须由用户明确、逐次提出。
- `auth status` 与 `doctor` 的 JSON 可能含 UID、昵称等账户摘要。只在必要时调用，不在报告、日志或后续提示中复述这些字段。

## 标准流程

1. 首次任务或环境变化后运行 `media-agent doctor`，确认登录态、FFmpeg 和磁盘空间。若未登录，停止并请用户在本产品的本地登录窗口自行扫码。
2. 只有用户明确要求时，使用 `favorites list` 或 `favorites items`。不读取浏览历史、评论或其他无关个性化数据。
3. 下载前先 `inspect`。多集、多 P 或收藏夹内容必须使用 `--episode`、`--part`、`--ep-id`、`--cid` 或 `--match` 明确选择一个目标。
4. 使用相同 selector 执行 `download --dry-run`，核对标题、目标剧集、清晰度和下载计划；确认无误后才执行真实下载。
5. 检查退出码和 stdout 的单行 JSON。下载完成后仅将本地文件交给用户要求的 ASR、字幕比对或视觉分析步骤，不自动上传、转写或清理媒体。

下载进度写入 stderr；stdout 是唯一结构化结果通道。失败时保留退出码和 JSON 错误信息，不要从 stderr 推断成功。

## 常用命令

```bash
media-agent favorites list --include-collected
media-agent favorites items 123456 --page 1

media-agent inspect 'https://www.bilibili.com/bangumi/play/ss38385' --episode 27 --with-media
media-agent download 'https://www.bilibili.com/bangumi/play/ss38385' --episode 27 --quality 720p --dry-run
media-agent download 'https://www.bilibili.com/bangumi/play/ss38385' --episode 27 --audio-only --output ./artifacts/episode-27
```

用户指定清晰度时使用其精确值；未指定时先阅读 `inspect --with-media` 的可用选项。需要语音转写时优先 `--audio-only`；需要视觉分析时下载合并媒体。不要假定文件名或扩展名，应以下载结果 JSON 与实际输出为准。

## 安装与接入

Codex 的默认 Skill 路径是 `${CODEX_HOME:-$HOME/.codex}/skills/media-agent-cli`。`./scripts/install-global.sh --skill` 会创建指向本目录的链接；安装后新建 Codex 任务或重启 Codex。其他 Agent 没有统一的全局 Skill 路径，应把本目录注册到该 Agent 的用户级或项目级 Skill 目录，并确保其 shell 能解析 `media-agent`。

该 CLI 只处理媒体获取与准备，不内置语音识别。下游工作流只能接收本地媒体路径，不能接收登录态、Cookie 或请求签名。

## 开源归属

本仓库是 [ScottSloan/Bili23-Downloader](https://github.com/ScottSloan/Bili23-Downloader) 的 GPLv3 修改版派生作品。保留上游署名、版权声明和许可证；本产品的 CLI/Skill 改动不代表上游作者或 Bilibili 的认可。再分发时遵守根目录的 `LICENSE`、`NOTICE` 和 `UPSTREAM.md`。
