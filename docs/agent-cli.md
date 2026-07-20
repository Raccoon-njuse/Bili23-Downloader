# Bili23 CLI 与 Agent Skill

`bili23` 是本 fork 新增的 Bilibili 视频下载命令行入口；`.agents/skills/bili23-cli` 是与它配套的项目级 Agent Skill。两者将已登录的桌面端能力以本地命令方式提供给 Agent，用于收藏夹查询、链接解析、按集数与清晰度下载，以及为后续音视频转写、字幕比对或视觉分析准备本地媒体。

它不是 MCP 服务，不会监听端口。Agent 在本机仓库根目录通过 shell 调用 `./bili23` 即可；支持项目级 Skill 的 Agent 应加载 `.agents/skills/bili23-cli/SKILL.md`。

## 使用范围

- 只允许个人、私有、非商业使用。
- 只处理用户本人已合法登录并有权访问的内容，不共享账号或登录态。
- 不得公开传播、分发、转售下载媒体，也不得把 CLI 包装成给他人使用的下载服务。
- 不绕过付费墙、DRM、平台访问控制或版权保护，并应遵守 Bilibili 服务条款与适用法律。
- 代码的 GPLv3 授权与媒体内容的使用权是两回事；本说明不授予任何媒体内容权利。

## 前置条件

在仓库根目录安装项目依赖，并先在桌面端完成用户本人扫码登录：

```bash
uv sync
./bili23 doctor
```

`doctor` 会返回登录状态、FFmpeg 可用性和下载目录空间。未登录时，CLI 不会代替用户处理扫码或凭据；请在 Bili23 Downloader 图形界面中自行完成登录。

注意：`auth status` 与 `doctor` 的 JSON 中可能有 UID、昵称等账户摘要。CLI 不会输出或持久化 Cookie/token，但 Agent 仍不应把账户摘要写入日志、工单或对外报告。

## 命令接口

每个命令的成功结果为一行 JSON；下载进度写到 stderr。失败时 stdout 仍为 JSON，且进程以非零状态退出。Agent 应以退出码和 stdout JSON 判断结果，不应解析 stderr 作为结构化数据。

| 目标 | 命令 |
| --- | --- |
| 查看登录摘要 | `./bili23 auth status` |
| 列出本人收藏夹 | `./bili23 favorites list` |
| 包含收藏的他人收藏夹 | `./bili23 favorites list --include-collected` |
| 查看一个收藏夹的视频 | `./bili23 favorites items <收藏夹ID或链接> --page 1` |
| 解析链接与剧集 | `./bili23 inspect '<链接>'` |
| 查看一个目标的可用清晰度、编码与音质 | `./bili23 inspect '<链接>' --episode 27 --with-media` |
| 仅验证下载计划 | `./bili23 download '<链接>' --episode 27 --quality 720p --dry-run` |
| 下载合并视频 | `./bili23 download '<链接>' --episode 27 --quality 720p --output <任务目录>` |
| 下载转写用音频 | `./bili23 download '<链接>' --episode 27 --audio-only --output <任务目录>` |

查看完整参数：

```bash
./bili23 --help
./bili23 inspect --help
./bili23 download --help
```

可用 selector 为 `--episode`、`--part`、`--ep-id`、`--cid` 和 `--match`。对于番剧、多 P、收藏夹等可能包含多个条目的链接，Agent 必须明确给出其中一个 selector；不得因链接能解析而推断用户想下载整季。`--all` 只能在用户明确要求批量下载时使用。

## Agent 工作流

1. 运行 `./bili23 doctor`，确认登录、FFmpeg 和可用磁盘空间；无有效登录态时停止，等待用户在 GUI 中登录。
2. 对用户给出的链接执行 `inspect`。若包含多集或多 P，向用户确认或使用其已经明确指定的集数、分 P、标题或 ID。
3. 需要指定清晰度时，对同一 selector 运行 `inspect --with-media`。只能在返回的可用规格中选择；用户没有指定时不要擅自提升画质。
4. 以相同 selector 和质量执行 `download --dry-run`，核对结果 JSON 中的标题、剧集和下载计划。
5. 真实下载使用 `--output <任务目录>`。一个下载任务一个目录，便于后续转写管线按目录接收媒体。
6. 检查下载命令退出码及 JSON 结果。成功后将下载结果中的实际文件路径交给本地 ASR/OCR 或视频分析步骤；未得到用户请求时，不自动上传、转写或清理媒体。

示例：为第 27 集创建音频转写输入。`--audio-only` 只负责下载音频，不执行语音识别；需要现有字幕时可以增加 `--subtitle`。

```bash
./bili23 inspect 'https://www.bilibili.com/bangumi/play/ss38385' --episode 27 --with-media
./bili23 download 'https://www.bilibili.com/bangumi/play/ss38385' --episode 27 --audio-only --dry-run
./bili23 download 'https://www.bilibili.com/bangumi/play/ss38385' --episode 27 --audio-only --output ./artifacts/bili/episode-27
```

不要假定输出文件名或扩展名；应以下载结果 JSON 和目标目录内实际产物为准。转写程序只接收本地媒体文件，不应获得 Bilibili Cookie、账户信息或请求签名。

## 隐私与权限

Skill 只在用户请求时读取收藏夹，不读取或暴露浏览历史、评论等无关的个性化数据。下载前不应保留 Cookie、token、签名 URL 或账户摘要到持久化日志。下载的内容、URL、收藏夹名称也可能具有个人信息属性，默认只在当前任务中处理。

## 上游与 Fork 说明

本仓库是 [ScottSloan/Bili23-Downloader](https://github.com/ScottSloan/Bili23-Downloader) 的独立 fork。上游项目提供桌面应用以及登录、解析、下载和媒体处理基础；本 fork 在此基础上新增 `bili23` CLI 和 Agent Skill 文档。

保留上游署名、版权声明与 GPLv3 许可。修改或再分发代码时，请遵守根目录的 [LICENSE](../LICENSE) 和 [NOTICE](../NOTICE)，清楚标记 fork 的改动；不要暗示上游作者或 Bilibili 为本 fork 的 Agent 集成背书。
