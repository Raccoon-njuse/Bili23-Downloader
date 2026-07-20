<p align="center">
    <a href="https://bili23.scott-sloan.cn" target="_blank">
        <img src="https://bili23.scott-sloan.cn/logo.png" alt="Bili23 Downloader" style="width: 500px;"/>
    </a>
</p>

<h1 align="center">Bili23-Downloader</h1>

<p align="center">
    <img src="https://img.shields.io/github/v/release/ScottSloan/Bili23-Downloader?style=flat-square" alt="Release"/>
    <img src="https://img.shields.io/github/license/ScottSloan/Bili23-Downloader?style=flat-square" alt="License"/>
    <img src="https://img.shields.io/github/downloads/ScottSloan/Bili23-Downloader/total?style=flat-square" alt="Downloads"/>
    <img src="https://img.shields.io/github/stars/ScottSloan/Bili23-Downloader?style=flat-square" alt="Stars"/>
    <img src="https://img.shields.io/github/actions/workflow/status/ScottSloan/Bili23-Downloader/publish.yml?style=flat-square" alt="Build"/>
</p>

<div align="center">
    <h3>
        <a href="https://bili23.scott-sloan.cn/">Official Website</a>
        <span> • </span>
        <a href="https://bili23.scott-sloan.cn/doc/intro.html">Documentation</a>
        <span> • </span>
        <a href="#-download">Download</a>
        <span> • </span>
        <a href="README.md">中文</a>
        <span> • </span>
        <a href="README_en.md">English</a>
    </h3>
</div>

<div align="center">
    <strong>Open Source, Free, Cross-Platform Bilibili Video Downloader</strong><br>
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

## Bilibili CLI and Agent Skill

This fork adds a headless `bili23` CLI and a project-local `.agents/skills/bili23-cli` Agent Skill. They reuse the desktop application's stored login state, link parsing, download task, and FFmpeg merging pipeline so an Agent can prepare local media for a later transcription, subtitle-comparison, or visual-analysis workflow.

This is not a network service or MCP endpoint and does not listen on a port. An Agent invokes `./bili23` through a shell at the source root. Successful and failed commands emit one JSON object on stdout; download progress goes to stderr. The CLI does not emit or persist Cookies/tokens, but `auth status` and `doctor` JSON can include an account summary such as UID or display name, which Agents must not place in logs or external reports.

```bash
./bili23 auth status
./bili23 favorites list --include-collected
./bili23 favorites items 123456 --page 1
./bili23 inspect 'https://www.bilibili.com/bangumi/play/ss38385' --episode 27 --with-media
./bili23 download 'https://www.bilibili.com/bangumi/play/ss38385' --episode 27 --quality 720p --output ~/Downloads/bili23
```

Downloads wait for both transfer and FFmpeg merging. Start with `--dry-run` to validate the selected episode and quality without creating a task or file. Multi-episode links must use an explicit `--episode`, `--part`, `--ep-id`, `--cid`, or `--match`; use `--all` only for an explicitly authorized batch job. Run `doctor` to check login, FFmpeg, and free space.

The CLI/Skill is only for personal, private, non-commercial processing of content the account holder is authorized to access. It does not provide account sharing, public media distribution, batch scraping, or protection bypassing. It prepares media only and does not perform ASR itself. See the full [Agent CLI guide](docs/agent-cli.en.md) and the fork attribution in [NOTICE](NOTICE).

## 📥 Download

Two download methods are available. Choose the one that fits your situation best:

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
