# Bili23 CLI 与 Codex Skill

`bili23` 是本 fork 提供的 Bilibili 视频下载 CLI，`.agents/skills/bili23-cli` 是配套的 Agent Skill。两者把已登录桌面端的收藏夹查询、链接解析、按集数/清晰度下载能力暴露为一个本地、可复用的 Agent 接口，为后续音视频转写、字幕比对或视觉分析准备媒体文件。

它不是 MCP 服务，不监听网络端口。全局注册后，任何能访问用户 `PATH` 的 Agent 都可以执行 `bili23`；Codex 通过用户级 Skill 目录发现操作规范。

## 从源码安装（macOS/Linux）

该仓库目前采用源码 checkout 加专用 uv 环境的分发方式，不宣称已发布为 PyPI 包。准备 Git、Python 3.9+ 和 [uv](https://docs.astral.sh/uv/)，然后执行：

```bash
git clone https://github.com/Raccoon-njuse/Bili23-Downloader.git
cd Bili23-Downloader
uv sync
./bili23 --help
```

根目录的 `bili23` 启动器固定使用该 checkout 的 `.venv` 和 `src`，避免误用系统 Python。它会解析自身的软链接，因此全局命令仍能回到正确的源码目录。

## 注册为全局 CLI 和 Skill

在完成 `uv sync` 后，运行：

```bash
./scripts/install-global.sh --all
```

该脚本只创建软链接，绝不复制项目或覆盖已有同名路径：

| 对象 | 默认注册位置 | 可覆盖环境变量 |
| --- | --- | --- |
| CLI | `$HOME/.local/bin/bili23` | `BILI23_BIN_DIR` |
| Codex Skill | `$HOME/.codex/skills/bili23-cli` | `CODEX_HOME` 或 `CODEX_SKILLS_DIR` |

如果 CLI 目录不在 `PATH`，把它加入你的 shell 启动配置并新开 shell：

```bash
export PATH="$HOME/.local/bin:$PATH"
command -v bili23
bili23 --help
```

安装 Skill 后，新建 Codex 任务或重启 Codex，使其重新扫描 `${CODEX_HOME:-$HOME/.codex}/skills`。这是 Codex 的约定；其他 Agent 产品没有统一的 Skill 注册位置，应将 `.agents/skills/bili23-cli` 指向各自的用户级或项目级 Skill 目录，并确保该 Agent 的 shell 能找到 `bili23`。

可分别注册一个组件：

```bash
./scripts/install-global.sh --cli
./scripts/install-global.sh --skill
```

只在当前源码目录使用时，无需全局注册，执行 `./bili23` 即可。

## 更新与移除

软链接指向源码目录，因此更新后不需要复制 CLI 或 Skill：

```bash
git pull --ff-only
uv sync
./scripts/install-global.sh --all
```

移除当前 checkout 创建的注册项：

```bash
./scripts/install-global.sh --uninstall
```

`--uninstall` 只会删除确实指向当前源码目录的链接；同名普通文件或指向其他目录的链接会被保留并报告错误。

## 登录与本地配置

登录由用户在 Bili23 Downloader 图形界面中自行完成。CLI 直接复用已有的本地登录态，不会处理扫码、短信或明文凭据。首次使用和环境变化后运行：

```bash
bili23 doctor
```

`doctor` 返回登录状态、FFmpeg 可用性和下载目录空间。`auth status` 与 `doctor` JSON 可能有 UID、昵称等账户摘要；CLI 不输出或额外持久化 Cookie/token，但 Agent 仍不应把账户摘要写入日志、工单或对外报告。

## 命令契约

每个命令的成功结果为一行 JSON；下载进度写到 stderr。失败时 stdout 仍为 JSON，且进程以非零状态退出。Agent 应以退出码和 stdout JSON 判断结果，不应解析 stderr 作为结构化数据。

| 目标 | 命令 |
| --- | --- |
| 查看登录摘要 | `bili23 auth status` |
| 列出本人收藏夹 | `bili23 favorites list` |
| 包含收藏的他人收藏夹 | `bili23 favorites list --include-collected` |
| 查看一个收藏夹的视频 | `bili23 favorites items <收藏夹ID或链接> --page 1` |
| 解析链接与剧集 | `bili23 inspect '<链接>'` |
| 查看一个目标的可用清晰度、编码与音质 | `bili23 inspect '<链接>' --episode 27 --with-media` |
| 仅验证下载计划 | `bili23 download '<链接>' --episode 27 --quality 720p --dry-run` |
| 下载合并视频 | `bili23 download '<链接>' --episode 27 --quality 720p --output <任务目录>` |
| 下载转写用音频 | `bili23 download '<链接>' --episode 27 --audio-only --output <任务目录>` |

查看完整参数：

```bash
bili23 --help
bili23 inspect --help
bili23 download --help
```

可用 selector 为 `--episode`、`--part`、`--ep-id`、`--cid` 和 `--match`。对于番剧、多 P、收藏夹等多个条目的链接，Agent 必须明确给出其中一个 selector；不得因链接能解析而推断用户想下载整季。`--all` 只能在用户明确要求批量下载时使用。

## Agent 工作流

1. 运行 `bili23 doctor`，确认全局命令、登录、FFmpeg 和可用磁盘空间；无有效登录态时停止，等待用户在 GUI 中登录。
2. 对用户给出的链接执行 `inspect`。若包含多集或多 P，使用用户明确指定的集数、分 P、标题或 ID；否则要求澄清。
3. 需要指定清晰度时，对同一 selector 运行 `inspect --with-media`。只能在返回的可用规格中选择；用户没有指定时不要擅自提升画质。
4. 以相同 selector 和质量执行 `download --dry-run`，核对结果 JSON 中的标题、剧集和下载计划。
5. 真实下载使用 `--output <任务目录>`。一个下载任务一个目录，便于后续转写管线按目录接收媒体。
6. 检查下载命令退出码及 JSON 结果。成功后将实际本地媒体路径交给 ASR/OCR 或视频分析步骤；未得到用户请求时，不自动上传、转写或清理媒体。

示例：为第 27 集准备音频转写输入。`--audio-only` 只负责下载音频，不执行语音识别；需要平台已有字幕时可以增加 `--subtitle`。

```bash
bili23 inspect 'https://www.bilibili.com/bangumi/play/ss38385' --episode 27 --with-media
bili23 download 'https://www.bilibili.com/bangumi/play/ss38385' --episode 27 --audio-only --dry-run
bili23 download 'https://www.bilibili.com/bangumi/play/ss38385' --episode 27 --audio-only --output ./artifacts/bili/episode-27
```

不要假定输出文件名或扩展名；应以下载结果 JSON 和目标目录内实际产物为准。转写程序只接收本地媒体文件，不应获得 Bilibili Cookie、账户信息或请求签名。

## 使用范围、隐私与 Fork

- 仅限个人、私有、非商业使用，且只处理用户本人已合法登录并有权访问的内容。
- 不共享账号、Cookie、token、签名 URL 或下载文件；不得将 CLI 包装成面向他人的下载服务。
- 不绕过付费墙、DRM、平台访问控制或版权保护；不得公开传播、分发或转售媒体。
- Skill 只在用户请求时读取收藏夹，不使用浏览历史、评论等无关个性化数据。下载的内容、URL 与收藏夹名称也可能具有个人信息属性。

本仓库是 [ScottSloan/Bili23-Downloader](https://github.com/ScottSloan/Bili23-Downloader) 的独立 fork。上游项目提供桌面应用以及登录、解析、下载和媒体处理基础；本 fork 新增 CLI、全局注册脚本和 Agent Skill 文档。代码的 GPLv3 授权与媒体内容的使用权是两回事。修改或再分发代码时，请遵守根目录的 [LICENSE](../LICENSE) 和 [NOTICE](../NOTICE)，保留上游署名，并清楚标记 fork 改动；不要暗示上游作者或 Bilibili 为本 fork 的 Agent 集成背书。
