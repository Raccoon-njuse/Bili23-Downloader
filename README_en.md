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
        <a href="https://bili23.scott-sloan.cn/">Upstream Website</a>
        <span> • </span>
        <a href="https://bili23.scott-sloan.cn/doc/intro.html">Upstream Documentation</a>
        <span> • </span>
        <a href="#bilibili-cli-and-codex-skill">CLI Setup</a>
        <span> • </span>
        <a href="README.md">中文</a>
        <span> • </span>
        <a href="README_en.md">English</a>
    </h3>
</div>

<div align="center">
    <strong>Bilibili video-download CLI and Codex Skill based on Bili23-Downloader</strong><br>
    <span>Local media preparation for personally authorized content and later transcription workflows</span>
</div><br>

<p align="center"><img src="https://bili23.scott-sloan.cn/main_interface_en.png" alt="Program Screenshot" style="width: 80%;"></p>

## ⚡ Features

| Feature | Detailed Description |
| :--- | :--- |
| 🖥️ **Cross-Platform** | Fully compatible with **Windows** (including Win 7), **Linux**, and **macOS** desktop operating systems. |
| 🎨 **Modern UI** | Based on Fluent Design, supports seamless light/dark theme switching and native High-DPI scaling. | 
| 🚀 **Multithreading & Acceleration**| Native integration of multi-threaded parallel downloading, breakpoint resuming, and automatic network error retries for extreme download speed. |
| 🔗 **Multi-Type Parsing** | Fully supports: `Standard Videos`, `Bangumi`, `Movies`, `Courses`, `User Space`, `Favorites`, `Weekly Must-Watch`, `Subscriptions`, `Watch Later`, `History`, etc., with batch mode support. |
| ⚙️ **Media Customization**| **Video**: 8K, 4K, HDR, Dolby Vision <br>**Audio**: Hi-Res Lossless, Dolby Atmos <br>**Codec**: AVC, HEVC, AV1 |
| 💬 **Danmaku & Subtitles** | **Danmaku**: `xml`, `ass`, `json` <br>**Subtitles**: `srt`, `lrc`, `txt`, `ass`, `json` |
| 🖼️ **Cover Extraction & Embedding**| Losslessly save covers (`jpg`, `png`, `avif`, `webp`), natively supports embedding posters directly into output video files. |
| 🧩 **NFO Metadata** | Automatically scrapes and generates local media metadata formats complying with standards of media centers like **Kodi**, **Jellyfin**, and **Emby**. |
| 📁 **Classification & Naming** | Built-in powerful rule engine, supporting highly customizable local file naming templates and multi-level directory classification modes. |
| 📦 **Format Muxing**| Smart audio & video stream mixing/extraction, supports output format to `mp4` or `mkv` to fulfill broad device compatibility requirements. |
| 🌐 **i18n Support** | Built-in multi-language interface out of the box: Simplified Chinese, Traditional Chinese, and English. |
| 🔒 **Secure Auth**| Supports quick and secure **QR Code Login** and **SMS Verification Login**. |
| 📖 **Open Source & Free**| Released under the **GPL-3.0** License, fully open-source, no in-app purchases, no ads, embracing community contribution. |

## Bilibili CLI and Codex Skill

This fork exposes a headless `bili23` CLI and `.agents/skills/bili23-cli` as source-installable Agent interfaces. The CLI reuses the desktop application's stored login state, link parsing, download task, and FFmpeg merging pipeline. The Skill gives Agents a bounded, auditable workflow for preparing local media for later transcription, subtitle comparison, or visual analysis.

This is not a network service or MCP endpoint and does not listen on a port. Successful and failed CLI commands emit one JSON object on stdout; download progress goes to stderr. The CLI does not emit or additionally persist Cookies/tokens, but `auth status` and `doctor` JSON can include an account summary such as UID or display name, which Agents must not place in logs or external reports.

### Source Setup and Global Registration (macOS/Linux)

Install Git, Python 3.9+, and [uv](https://docs.astral.sh/uv/), then clone this fork and create its dedicated runtime environment:

```bash
git clone https://github.com/Raccoon-njuse/Bili23-Downloader.git
cd Bili23-Downloader
uv sync
./bili23 doctor
```

Account login still happens in the Bili23 Downloader desktop application. The CLI does not collect credentials or complete QR login. Register both the CLI and Codex Skill in the current user account with:

```bash
./scripts/install-global.sh --all
```

The script only creates traceable symlinks; it does not copy source. By default it links the command at `${BILI23_BIN_DIR:-$HOME/.local/bin}/bili23` and the Skill at `${CODEX_HOME:-$HOME/.codex}/skills/bili23-cli`. If `~/.local/bin` is not on `PATH`, add it to your shell startup configuration, then open a new shell or restart Codex:

```bash
export PATH="$HOME/.local/bin:$PATH"
command -v bili23
bili23 --help
```

Start a new Codex task or restart Codex after installing the global Skill so it can be discovered. Other Agent products do not share a universal global-Skill directory; point their user/project Skill registry at `.agents/skills/bili23-cli` and make sure their shell can resolve `bili23`. For one-off use from a checkout, run `./bili23` directly.

After updating source, run `git pull --ff-only` and `uv sync`; the symlinks immediately use the updated CLI and Skill. To remove only links registered by this checkout, run `./scripts/install-global.sh --uninstall`. The script refuses to replace or delete same-named paths owned by another source.

### Common Commands

```bash
bili23 auth status
bili23 favorites list --include-collected
bili23 favorites items 123456 --page 1
bili23 inspect 'https://www.bilibili.com/bangumi/play/ss38385' --episode 27 --with-media
bili23 download 'https://www.bilibili.com/bangumi/play/ss38385' --episode 27 --quality 720p --output ~/Downloads/bili23
```

Downloads wait for both transfer and FFmpeg merging. Start with `--dry-run` to validate the selected episode and quality without creating a task or file. Multi-episode links must use an explicit `--episode`, `--part`, `--ep-id`, `--cid`, or `--match`; use `--all` only for an explicitly authorized batch job. Run `doctor` to check login, FFmpeg, and free space.

The CLI/Skill is only for personal, private, non-commercial processing of content the account holder is authorized to access. It does not provide account sharing, public media distribution, batch scraping, or protection bypassing. It prepares media only and does not perform ASR itself. See the full [Agent CLI guide](docs/agent-cli.en.md) and the fork attribution in [NOTICE](NOTICE).

## 📥 Upstream Desktop Download

The upstream release packages below are for desktop login and GUI use. They **do not include this fork's `bili23` CLI, global-registration script, or Codex Skill**. Install the CLI from this fork's source as described above.

- [**Go to GitHub Releases**](https://github.com/ScottSloan/Bili23-Downloader/releases/latest) - Recommended if GitHub is easily accessible for you, and you want the latest release.
- [**Official Website Download (Recommended for users in China)**](https://bili23.scott-sloan.cn/doc/releases.html) - Recommended for users in China, usually faster and more stable to access.

## 🪧 Terms of Use
This project is for personal learning and research purposes only. The downloaded content is **strictly for personal, non-commercial use, and any form of commercial use, public dissemination, or distribution is completely prohibited.**  
This software operates solely based on the user's legal account access permissions and **will not bypass any paywalls or platform intellectual property protection measures.** Please do not use this software for batch scraping or any action that violates the target platform's terms of service.  

**Disclaimer**: Users must independently bear all risks associated with using this project (including but not limited to account bans, copyright disputes, etc.). The project developer assumes no responsibility for any direct or indirect legal disputes or damages caused by the use or inability to use this software.  

By continuing to use this software, you indicate your full understanding and agreement to comply with all the above terms.

## 🔑 Open Source License
This project is released under the **GPLv3 License**.

Wbi signature, specific APIs, and buvid3 generation parameters are inspired by [SocialSisterYi/bilibili-API-collect](https://github.com/SocialSisterYi/bilibili-API-collect).

## 🛠️ Contributors
New ideas and pull requests are always welcome!

<a href="https://github.com/ScottSloan/Bili23-Downloader/graphs/contributors" target="_blank">
    <img src="https://contrib.rocks/image?repo=ScottSloan/Bili23-Downloader" alt="Contributors" style="width: 300px;"/>
</a>

Made with [contrib.rocks](https://contrib.rocks).

## 🌟 Community
Join our community to get the latest updates, Q&A, and technical discussions.

- [QQ Group](https://qm.qq.com/q/KX3uJIFIYK)
- [QQ Channel](https://pd.qq.com/s/8941to1p0)

> When asking questions, please provide the **problem description** and **complete logs** so we can assist you better.

## 💪 Support the Author

This project is independently developed and maintained by [Scott Sloan](https://github.com/ScottSloan) in his spare time. The original intention is to provide everyone with a pure, ad-free, and efficient local Bilibili downloading tool.

> **⭐️ Leave a Star**  
> If this tool has saved your precious time, please consider giving it a **Star** in the top right corner of the project!  
> Your support helps more people discover this project and is the greatest motivation for continuous updates.

### ☕️ Buy the Author a Coffee

Besides routine code maintenance, handling complex cross-platform environments and refactoring releases take a massive amount of time and energy. If the software has indeed helped you, you are welcome to buy the author a coffee via the sponsor QR code below. **This is the most practical recognition of open-source dedication!**

<p align="center">
    <img src="https://bili23.scott-sloan.cn/assets/sponsor_weixin.Bqpdl-if.png" alt="Sponsor QR Code" style="width: 300px; margin: 10px 0; border-radius: 8px;" />
</p>
