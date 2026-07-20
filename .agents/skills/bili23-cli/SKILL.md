---
name: bili23-cli
description: 在个人、私有、非商业且已获账号授权的前提下，使用本仓库的 Bili23 CLI 查看收藏夹、解析 Bilibili 链接、精确选择剧集和清晰度下载媒体，为后续本地音视频转写或分析工作流准备输入时使用。
---

# Bili23 CLI

全局安装后使用 `bili23`；若用户只提供源码 checkout，则在仓库根目录使用 `./bili23`。先用 `command -v bili23` 判断全局命令是否已注册。若两者都不可用，说明安装或 PATH 尚未完成；不要自行修改用户全局环境，改为说明需要按仓库 README 注册。

此 Skill 是 Agent 调用本地 CLI 的操作规范，不是网络暴露的 MCP 服务，也不提供或保存新的登录凭据。

## 使用边界

- 仅处理用户本人已合法登录并获授权访问的 Bilibili 内容；仅限个人、私有、非商业用途。
- 不共享账号、Cookie、token、签名 URL、下载文件或账户摘要；不得把 CLI 包装成面向他人的下载服务。
- 不绕过付费墙、DRM、平台访问控制或版权保护；遇到受保护或不可下载内容应停止并如实报告。
- 不默认批量下载。`--all`、多链接或收藏夹批处理必须得到用户明确、逐次的请求。
- `auth status` 和 `doctor` 的 JSON 可能含 UID、昵称等账户摘要。只在确有必要时调用，不在报告、日志或后续提示中复述这些字段。

## 标准流程

1. 在首次任务或环境变化后运行 `bili23 doctor`。确认登录态、FFmpeg 和磁盘空间；若未登录，停止并请用户在桌面端 Bili23 Downloader 中自行扫码登录。
2. 只有用户明确要求时，使用 `favorites list` 或 `favorites items`。不读取浏览历史、评论等不必要的个性化数据。
3. 对下载请求，先解析链接，再明确选择一个目标。番剧、多 P、收藏夹等多项内容必须使用 `--episode`、`--part`、`--ep-id`、`--cid` 或 `--match`。
4. 使用同一 selector 执行 `download --dry-run`，核对标题、目标剧集、清晰度和计划；成功后再开始真实下载。
5. 下载完成后检查进程退出码与 stdout 的单行 JSON。将实际输出文件作为后续本地 ASR、字幕比对或视频分析流程的输入；除非用户要求，不自动执行转写或上传媒体。

下载进度写入 stderr；stdout 只能按 JSON 解析。失败时保留退出码和 JSON 中的错误信息，不要从 stderr 推断成功。

## 常用命令

```bash
# 查看收藏夹（仅在用户请求时）
bili23 favorites list --include-collected
bili23 favorites items 123456 --page 1

# 先查看可选剧集和可用媒体规格
bili23 inspect 'https://www.bilibili.com/bangumi/play/ss38385' --episode 27 --with-media

# 先确认下载计划，不创建任务或文件
bili23 download 'https://www.bilibili.com/bangumi/play/ss38385' --episode 27 --quality 720p --dry-run

# 为本地转写工作流下载单独音频到用户指定的任务目录
bili23 download 'https://www.bilibili.com/bangumi/play/ss38385' --episode 27 --audio-only --output ./artifacts/bili/episode-27
```

用户指定视频清晰度时使用其精确值；未指定时先在 `inspect --with-media` 结果中确认可用选项。需要视觉分析时下载合并媒体；需要语音转写时优先 `--audio-only`，可按任务需要追加 `--subtitle` 获取平台已有字幕。不要假定文件扩展名或文件名，以下载结果 JSON 与目标目录中的实际文件为准。

## Agent 接入

Codex 的全局安装目录是 `${CODEX_HOME:-$HOME/.codex}/skills/bili23-cli`。本仓库的 `scripts/install-global.sh --skill` 会在该目录创建指向本文件的链接；安装后应新建任务或重启 Codex，使其重新发现 Skill。其他 Agent 没有统一的全局 Skill 目录，应把本目录作为其项目/用户级 Skill 来源，并确保其 shell 能找到 `bili23`。

该 CLI 是媒体获取与准备阶段，不内置语音识别。转写工作流应在下载成功后接收本地媒体路径，并由独立的 ASR/OCR 工具处理；不要把用户的登录态传递给下游步骤。

## Fork 与开源归属

本仓库是 [ScottSloan/Bili23-Downloader](https://github.com/ScottSloan/Bili23-Downloader) 的独立 fork。保留上游署名、版权声明和 GPLv3 许可；本 fork 新增的 CLI/Skill 文档不代表上游作者或 Bilibili 的认可。修改或分发代码时遵守仓库根目录的 `LICENSE` 与 `NOTICE`，并清楚标注本 fork 的改动。
