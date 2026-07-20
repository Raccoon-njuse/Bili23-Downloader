# Bili23 CLI and Codex Skill

`bili23` is the Bilibili video-download CLI provided by this fork, and `.agents/skills/bili23-cli` is its companion Agent Skill. Together they expose the already logged-in desktop application's local capabilities for favorite listing, link inspection, episode/quality selection, and downloads, preparing local media for later transcription, subtitle comparison, or visual analysis.

This is not an MCP service and does not listen on a network port. After global registration, any Agent shell that inherits the user's `PATH` can execute `bili23`; Codex discovers the workflow rules from its user-level Skill directory.

## Source Setup (macOS/Linux)

This repository currently distributes through a source checkout and dedicated uv environment. It does not claim to be a published PyPI package. Install Git, Python 3.9+, and [uv](https://docs.astral.sh/uv/), then run:

```bash
git clone https://github.com/Raccoon-njuse/Bili23-Downloader.git
cd Bili23-Downloader
uv sync
./bili23 --help
```

The root `bili23` launcher always uses this checkout's `.venv` and `src` tree, avoiding accidental system-Python use. It resolves its own symlink before locating the checkout, so a global command still reaches the correct source directory.

## Register the Global CLI and Skill

After `uv sync`, run:

```bash
./scripts/install-global.sh --all
```

The script creates symlinks only. It never copies project files or overwrites an existing same-named path:

| Item | Default registration path | Override |
| --- | --- | --- |
| CLI | `$HOME/.local/bin/bili23` | `BILI23_BIN_DIR` |
| Codex Skill | `$HOME/.codex/skills/bili23-cli` | `CODEX_HOME` or `CODEX_SKILLS_DIR` |

If the CLI directory is not on `PATH`, add it to your shell startup configuration and open a new shell:

```bash
export PATH="$HOME/.local/bin:$PATH"
command -v bili23
bili23 --help
```

Start a new Codex task or restart Codex after installing the Skill so it rescans `${CODEX_HOME:-$HOME/.codex}/skills`. This directory is a Codex convention. Other Agent products do not share a universal global-Skill location; point their user/project Skill registry at `.agents/skills/bili23-cli` and ensure their shell can resolve `bili23`.

Register a single component when needed:

```bash
./scripts/install-global.sh --cli
./scripts/install-global.sh --skill
```

For one-off use directly from a source checkout, run `./bili23` without global registration.

## Update and Uninstall

The links point at the source checkout, so no separate copying is required after an update:

```bash
git pull --ff-only
uv sync
./scripts/install-global.sh --all
```

Remove only links created by this checkout:

```bash
./scripts/install-global.sh --uninstall
```

`--uninstall` removes a link only when it points to the current checkout. It preserves and reports ordinary paths or symlinks owned by another source.

## Login and Local Configuration

The user completes login in the Bili23 Downloader desktop application. The CLI reuses the existing local login state and does not handle QR login, SMS, or plaintext credentials. Run this after first setup or an environment change:

```bash
bili23 doctor
```

`doctor` reports login state, FFmpeg availability, and free space. `auth status` and `doctor` JSON may contain an account summary such as UID or display name. The CLI does not emit or additionally persist Cookies/tokens, but Agents must still avoid writing account summaries to logs, tickets, or external reports.

## Command Contract

Successful commands emit one JSON object on stdout. Download progress goes to stderr. Failures also emit JSON on stdout and return a nonzero exit code. Agents must use the exit code and stdout JSON as the contract; stderr is not structured output.

| Goal | Command |
| --- | --- |
| Login summary | `bili23 auth status` |
| List owned favorites | `bili23 favorites list` |
| Include collected favorites | `bili23 favorites list --include-collected` |
| List a favorite's videos | `bili23 favorites items <favorite-id-or-url> --page 1` |
| Inspect a link and its episodes | `bili23 inspect '<url>'` |
| Read media options for one target | `bili23 inspect '<url>' --episode 27 --with-media` |
| Validate a download plan | `bili23 download '<url>' --episode 27 --quality 720p --dry-run` |
| Download merged video | `bili23 download '<url>' --episode 27 --quality 720p --output <job-dir>` |
| Download audio for transcription | `bili23 download '<url>' --episode 27 --audio-only --output <job-dir>` |

Use `bili23 --help`, `bili23 inspect --help`, and `bili23 download --help` for the complete argument list.

For seasons, multi-part uploads, and favorites, Agents must select one target explicitly with `--episode`, `--part`, `--ep-id`, `--cid`, or `--match`. Never infer that a whole season should be downloaded. Use `--all` only after an explicit user request for a batch download.

## Agent Workflow

1. Run `bili23 doctor` to verify the global command, login, FFmpeg, and disk capacity. Stop when no valid login state exists and ask the user to sign in through the GUI.
2. Run `inspect` for the supplied link. For multiple episodes or parts, use the user's explicit selector or ask for one.
3. For a requested quality, run `inspect --with-media` with the same selector and choose only an available option. Do not silently upgrade quality.
4. Run `download --dry-run` with the same selector and options, then check the returned title, episode, and plan.
5. Run the actual download with `--output <job-dir>`. Keep each job in its own directory so downstream workflows receive a clear local-media boundary.
6. Check the exit code and JSON result. Pass only the resulting local media files to a later ASR/OCR or video-analysis step. Do not upload, transcribe, or delete media unless the user requests it.

Example, preparing audio input for episode 27. `--audio-only` downloads audio but does not perform speech recognition. Add `--subtitle` only when platform-provided subtitles are needed.

```bash
bili23 inspect 'https://www.bilibili.com/bangumi/play/ss38385' --episode 27 --with-media
bili23 download 'https://www.bilibili.com/bangumi/play/ss38385' --episode 27 --audio-only --dry-run
bili23 download 'https://www.bilibili.com/bangumi/play/ss38385' --episode 27 --audio-only --output ./artifacts/bili/episode-27
```

Do not assume an output filename or extension. Use the download-result JSON and actual files in the destination directory. Downstream transcription tools must receive local media only, never Bilibili Cookies, account details, or signed request URLs.

## Scope, Privacy, and Fork Attribution

- Personal, private, non-commercial use only, and only for content that the account holder is legally authorized to access.
- Do not share accounts, Cookies, tokens, signed URLs, or downloaded files. Do not turn this CLI into a service for other people.
- Do not bypass paywalls, DRM, platform access controls, or copyright protections. Do not publicly distribute, resell, or expose media.
- The Skill reads favorites only when requested and does not use unrelated personalization data such as browsing history or comments. Treat downloaded media, source URLs, and favorite names as potentially personal data.

This repository is an independent fork of [ScottSloan/Bili23-Downloader](https://github.com/ScottSloan/Bili23-Downloader). The upstream project provides the desktop application and the underlying login, parsing, download, and media-processing work. This fork adds the CLI, source-global registration script, and Agent Skill documentation. GPLv3 applies to the source code, not to media rights. When modifying or redistributing source, follow [LICENSE](../LICENSE) and [NOTICE](../NOTICE), retain upstream attribution, and clearly label fork-specific changes. Do not imply endorsement by Scott Sloan, the upstream project, or Bilibili.
