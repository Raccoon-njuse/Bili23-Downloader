<p align="center">
    <a href="https://bili23.scott-sloan.cn" target="_blank">
        <img src="https://bili23.scott-sloan.cn/logo.png" alt="Bili23 Downloader" style="width: 500px;"/>
    </a>
</p>

<h1 align="center">Bili23 CLI + Codex Skill</h1>

<p align="center">
    <img src="https://img.shields.io/github/v/release/ScottSloan/Bili23-Downloader?style=flat-square" alt="Release"/>
    <img src="https://img.shields.io/github/license/ScottSloan/Bili23-Downloader?style=flat-square" alt="License"/>
    <img src="https://img.shields.io/github/downloads/ScottSloan/Bili23-Downloader/total?style=flat-square" alt="Downloads"/>
    <img src="https://img.shields.io/github/stars/ScottSloan/Bili23-Downloader?style=flat-square" alt="Stars"/>
    <img src="https://img.shields.io/github/actions/workflow/status/ScottSloan/Bili23-Downloader/publish.yml?style=flat-square" alt="Build"/>
</p>

<div align="center">
    <h3>
        <a href="https://bili23.scott-sloan.cn/">上游官网</a>
        <span> • </span>
        <a href="https://bili23.scott-sloan.cn/doc/intro.html">上游文档</a>
        <span> • </span>
        <a href="#bilibili-cli-与-codex-skill">CLI 安装</a>
        <span> • </span>
        <a href="README.md">中文</a>
        <span> • </span>
        <a href="README_en.md">English</a>
    </h3>
</div>

<div align="center">
    <strong>基于 Bili23-Downloader 的 B 站视频下载 CLI 与 Codex Skill</strong><br>
    <span>个人授权内容的本地媒体准备与后续转写工作流入口</span>
</div><br>

<p align="center"><img src="https://bili23.scott-sloan.cn/main_interface_cn.png" alt="程序截图" style="width: 80%;"></p>

## ⚡ 程序特性

| 特性 | 详细说明 |
| :--- | :--- |
| 🖥️ **跨平台支持** | 完美兼容 **Windows**（含 Win 7）、**Linux** 和 **macOS** 三大桌面操作系统。 |
| 🎨 **现代 UI 设计** | 基于 Fluent Design 设计语言，支持浅色 / 深色主题无缝切换，原生适配高分屏。 | 
| 🚀 **多线程与加速**| 原生集成多线程并行下载、断点续传及网络异常自动重试机制，提供极致的下载速率。 |
| 🔗 **多类型解析** | 全面支持：`投稿视频`、`番剧`、`课程`、`UP主空间`、`收藏夹`、`每周必看`、`订阅合集`、`追番追剧`、`稍后再看`、`历史记录`等，支持批量处理。 |
| ⚙️ **音视频自定义**| **画质**：`8K`、`4K`、`HDR`、`杜比视界`等 <br>**音质**：`Hi-Res 无损`、`杜比全景声`等 <br>**编码**：`AVC`、`HEVC`、`AV1` |
| 💬 **弹幕与字幕** | **弹幕**：`xml`、`ass`、`json`<br>**字幕**：`srt`、`lrc`、`txt`、`ass`、`json` |
| 🖼️ **封面解析嵌入**| 无损保存原图质量（`jpg`、`png`、`avif`、`webp`），并原生支持将图片自动嵌入最终的视频文件中。 |
| 🧩 **NFO 元数据** | 自动刮削并生成符合 **Kodi**、**Jellyfin**、**Emby** 等媒体中心标准格式的本地媒体元数据。 |
| 📁 **分类与命名** | 内置强大规则引擎，支持高度自定义的本地文件命名模板与多级目录分类存储模式。 |
| 📦 **封装格式转化**| 智能音视频流混合提取，支持封装输出为 `mp4` 或 `mkv`，充分满足不同播放设备的兼容需求。 |
| 🌐 **国际化支持** | 内置多语言界面，开箱可用：简体中文、繁体中文、English。 |
| 🔒 **账号安全登录**| 支持快捷安全的**扫码登录**与**短信验证登录**。 |
| 📖 **完全开源免费**| 基于 **GPL-3.0** 协议发布，代码完全开源、无内购、无广告，拥抱社区共建。 |

## Bilibili CLI 与 Codex Skill

本 fork 将无界面 `bili23` CLI 与 `.agents/skills/bili23-cli` 作为可从源码安装的通用 Agent 接口。CLI 复用桌面端保存的登录态、链接解析、下载任务和 FFmpeg 合并链路；Skill 约束 Agent 以个人授权、精确选集、可审计的方式为后续音视频转写、字幕比对或视觉分析准备本地媒体。

它不是网络服务或 MCP 端点，不监听端口。CLI 成功与失败结果均为单行 JSON，下载进度输出到 stderr。CLI 不输出或额外持久化 Cookie/token，但 `auth status`、`doctor` 的 JSON 可能包含 UID、昵称等账户摘要，Agent 不应将这些内容写入日志或对外报告。

### 从源码安装与全局注册（macOS/Linux）

需要 Git、Python 3.9+ 和 [uv](https://docs.astral.sh/uv/)。先克隆本 fork 并创建它自己的运行环境：

```bash
git clone https://github.com/Raccoon-njuse/Bili23-Downloader.git
cd Bili23-Downloader
uv sync
./bili23 doctor
```

登录仍由桌面端 Bili23 Downloader 完成；CLI 不会接管扫码或收集凭据。接着将 CLI 与 Codex Skill 一起注册到当前用户目录：

```bash
./scripts/install-global.sh --all
```

该脚本仅创建可追踪的软链接，不复制源码：默认将命令链接到 `${BILI23_BIN_DIR:-$HOME/.local/bin}/bili23`，并将 Skill 链接到 `${CODEX_HOME:-$HOME/.codex}/skills/bili23-cli`。若 `~/.local/bin` 不在 `PATH`，请把它加入所用 shell 的启动配置，然后开启新 shell 或重启 Codex：

```bash
export PATH="$HOME/.local/bin:$PATH"
command -v bili23
bili23 --help
```

Codex 必须新建任务或重启后才会重新发现全局 Skill。其他 Agent 没有统一的全局 Skill 目录，应将 `.agents/skills/bili23-cli` 作为其用户级/项目级 Skill 来源，并确保其 shell 能找到 `bili23`。只在源码目录临时使用时，直接执行 `./bili23` 即可。

更新源码后执行 `git pull --ff-only`、`uv sync`；由于安装的是软链接，CLI 与 Skill 会立即指向更新后的内容。需要移除当前 checkout 注册的两个链接时，执行 `./scripts/install-global.sh --uninstall`；脚本不会覆盖或删除指向其他来源的同名路径。

### 常用命令

```bash
bili23 auth status
bili23 favorites list --include-collected
bili23 favorites items 123456 --page 1
bili23 inspect 'https://www.bilibili.com/bangumi/play/ss38385' --episode 27 --with-media
bili23 download 'https://www.bilibili.com/bangumi/play/ss38385' --episode 27 --quality 720p --output ~/Downloads/bili23
```

下载命令默认等待文件下载和 FFmpeg 合并完成；先使用 `--dry-run` 可验证目标剧集及清晰度而不创建任务或文件。多集链接不得默认下载整季，需显式传入 `--episode`、`--part`、`--ep-id`、`--cid`、`--match`；`--all` 仅用于用户明确授权的批量任务。可用 `doctor` 检查登录态、FFmpeg 和下载目录磁盘空间。

该 CLI/Skill 仅用于用户本人已获授权内容的个人、私有、非商业处理，不提供共享账号、媒体公开分发、批量抓取或绕过平台保护的能力。它只完成媒体获取与准备，不内置语音识别；下载成功后再将本地媒体交给独立的转写工作流。完整接入和操作边界见 [Agent CLI 文档](docs/agent-cli.md)，本 fork 的上游归属和许可说明见 [NOTICE](NOTICE)。

## 📥 上游桌面端下载

以下上游发行包用于桌面端登录和 GUI 使用，**不包含本 fork 新增的 `bili23` CLI、全局注册脚本或 Codex Skill**。CLI 请按上文从本 fork 源码安装。

- [**GitHub Releases**](https://github.com/ScottSloan/Bili23-Downloader/releases/latest) - 适合访问 GitHub 较稳定的用户，获取最新发布版本。
- [**官网下载（国内用户推荐）**](https://bili23.scott-sloan.cn/doc/releases.html) - 适合国内用户，通常访问更快、更稳定。

## 🪧 使用协议
本项目仅供个人学习与研究用途，下载内容**仅限于个人非商业使用，严禁用于任何形式的商业目的、公开传播或分发**。  
本软件仅基于用户账号的合法访问权限操作，**不会绕过任何付费墙或平台知识产权保护措施**。请勿将本软件用于批量抓取或任何违反目标平台服务条款的行为。  

**免责声明**：用户需完全自行承担使用本项目可能带来的所有风险（包括但不限于账号封禁、版权纠纷等）。项目开发者不对任何人因使用或无法使用本软件所引发的任何直接或间接法律纠纷、损害承担责任。  

继续使用即表示您已充分理解并同意遵守上述全部条款。

## 🔑 开源许可
本项目在 **GPLv3 License** 许可协议下进行发布。

wbi 签名、部分接口以及 buvid3 等参数生成参考 [SocialSisterYi/bilibili-API-collect](https://github.com/SocialSisterYi/bilibili-API-collect)  

## 🛠️ 参与贡献
欢迎提出新的点子~

<a href="https://github.com/ScottSloan/Bili23-Downloader/graphs/contributors" target="_blank">
    <img src="https://contrib.rocks/image?repo=ScottSloan/Bili23-Downloader" alt="Contributors" style="width: 300px;"/>
</a>

Made with [contrib.rocks](https://contrib.rocks).

## 🌟 社区交流
加入社区，获取项目最新动态、问题答疑和技术交流。

- [QQ 交流群](https://qm.qq.com/q/KX3uJIFIYK)
- [QQ 频道](https://pd.qq.com/s/8941to1p0)

> 如需提问，请提供**问题描述**、**完整日志**，以便我们更好地提供帮助。

## 💪 支持作者

本项目由开发者 [Scott Sloan](https://github.com/ScottSloan) 利用业余时间独立开发与维护，初衷是为大家提供纯粹、无广告且高效的 B 站本地下载工具。

> **⭐️ 点亮星标**  
> 如果这款工具为你节省了宝贵的时间，欢迎在项目右上角为其点亮一颗 **Star**！  
> 你的支持能让更多有需要的人看到这个项目，这也会成为作者持续更新的最大动力。

### ☕️ 请作者喝杯咖啡

除了日常的代码维护外，处理复杂的跨平台环境以及重构发布都耗费了大量的时间与精力。如果软件确实帮你解决了不少麻烦，欢迎通过下方的赞助码请作者喝杯咖啡。**这是对“为爱发电”最实在的认可！**

<p align="center">
    <img src="https://bili23.scott-sloan.cn/assets/sponsor_weixin.Bqpdl-if.png" alt="赞助二维码" style="width: 300px; margin: 10px 0; border-radius: 8px;" />
</p>
