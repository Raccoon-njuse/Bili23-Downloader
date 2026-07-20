# Bili23 CLI and Agent Skill

`bili23` is the Bilibili video-download CLI added by this fork. `.agents/skills/bili23-cli` is its project-local Agent Skill. Together they expose the already logged-in desktop application's local capabilities to an Agent: listing favorites, inspecting links, selecting an episode and quality, downloading media, and preparing local files for later transcription, subtitle comparison, or visual-analysis workflows.

This is not an MCP service and does not listen on a network port. An Agent invokes `./bili23` through a shell at the repository root. Agent frameworks with project-skill support should load `.agents/skills/bili23-cli/SKILL.md`.

## Scope of Use

- Personal, private, non-commercial use only.
- Process only content that the account holder is legally authorized to access. Do not share accounts or login state.
- Do not publicly distribute, resell, or expose downloaded media, and do not turn this CLI into a service for other people.
- Do not bypass paywalls, DRM, platform access controls, or copyright protections. Follow Bilibili's terms and applicable law.
- GPLv3 applies to the software source; it does not grant rights to downloaded media. This document grants no media rights.

## Prerequisites

From the repository root, install project dependencies and complete the account holder's QR-code login in the desktop application:

```bash
uv sync
./bili23 doctor
```

`doctor` reports login state, FFmpeg availability, and free space in the download location. If login is missing, the CLI does not collect credentials or complete QR login; the user must sign in through the Bili23 Downloader GUI.

`auth status` and `doctor` JSON may contain an account summary such as UID or display name. The CLI does not emit or persist Cookies/tokens, but an Agent must still avoid writing account summaries to logs, tickets, or external reports.

## Command Contract

Successful commands emit one JSON object on stdout. Download progress goes to stderr. Failures also emit JSON on stdout and return a nonzero exit code. Agents must use the exit code and stdout JSON as the contract; stderr is not structured output.

| Goal | Command |
| --- | --- |
| Login summary | `./bili23 auth status` |
| List owned favorites | `./bili23 favorites list` |
| Include collected favorites | `./bili23 favorites list --include-collected` |
| List a favorite's videos | `./bili23 favorites items <favorite-id-or-url> --page 1` |
| Inspect a link and its episodes | `./bili23 inspect '<url>'` |
| Read media options for one target | `./bili23 inspect '<url>' --episode 27 --with-media` |
| Validate a download plan | `./bili23 download '<url>' --episode 27 --quality 720p --dry-run` |
| Download merged video | `./bili23 download '<url>' --episode 27 --quality 720p --output <job-dir>` |
| Download audio for transcription | `./bili23 download '<url>' --episode 27 --audio-only --output <job-dir>` |

Use `./bili23 --help`, `./bili23 inspect --help`, and `./bili23 download --help` for the complete argument list.

For seasons, multi-part uploads, and favorites, Agents must select one target explicitly with `--episode`, `--part`, `--ep-id`, `--cid`, or `--match`. Never infer that a whole season should be downloaded. Use `--all` only after an explicit user request for a batch download.

## Agent Workflow

1. Run `./bili23 doctor` to verify login, FFmpeg, and disk capacity. Stop when no valid login state exists and ask the user to sign in through the GUI.
2. Run `inspect` for the supplied link. For multiple episodes or parts, use the user's explicit selector or ask for one.
3. For a requested quality, run `inspect --with-media` with the same selector and choose only an available option. Do not silently upgrade quality.
4. Run `download --dry-run` with the same selector and options, then check the returned title, episode, and plan.
5. Run the actual download with `--output <job-dir>`. Keep each job in its own directory so downstream workflows receive a clear local-media boundary.
6. Check the exit code and JSON result. Pass only the resulting local media files to a later ASR/OCR or video-analysis step. Do not upload, transcribe, or delete media unless the user requests it.

Example, preparing audio input for episode 27. `--audio-only` downloads audio but does not perform speech recognition. Add `--subtitle` only when platform-provided subtitles are needed.

```bash
./bili23 inspect 'https://www.bilibili.com/bangumi/play/ss38385' --episode 27 --with-media
./bili23 download 'https://www.bilibili.com/bangumi/play/ss38385' --episode 27 --audio-only --dry-run
./bili23 download 'https://www.bilibili.com/bangumi/play/ss38385' --episode 27 --audio-only --output ./artifacts/bili/episode-27
```

Do not assume an output filename or extension. Use the download-result JSON and actual files in the destination directory. Downstream transcription tools must receive local media only, never Bilibili Cookies, account details, or signed request URLs.

## Privacy and Fork Attribution

The Skill reads favorites only when requested and does not use unrelated personalization data such as browsing history or comments. Do not persist Cookies, tokens, signed URLs, or account summaries. Treat downloaded media, source URLs, and favorite names as potentially personal data.

This repository is an independent fork of [ScottSloan/Bili23-Downloader](https://github.com/ScottSloan/Bili23-Downloader). The upstream project provides the desktop application and the underlying login, parsing, download, and media-processing work. This fork adds the `bili23` CLI and Agent Skill documentation.

Retain upstream attribution, copyright notices, and GPLv3 terms. When modifying or redistributing source, follow [LICENSE](../LICENSE) and [NOTICE](../NOTICE), clearly label fork-specific changes, and do not imply endorsement by Scott Sloan, the upstream project, or Bilibili.
