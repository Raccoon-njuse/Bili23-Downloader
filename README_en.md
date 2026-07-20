# Media Agent CLI

`media-agent` is a local command-line tool and Agent Skill for preparing media that the account holder is authorized to access. It can inspect links, select a single episode or part, list favorites when requested, and download local media for later transcription or analysis.

It is not a network service. It does not open a listening port or expose Cookies, QR-login credentials, or signed URLs to an Agent.

## Install from Source

Install Git, Python 3.9+, and [uv](https://docs.astral.sh/uv/), then run:

```bash
git clone https://github.com/Raccoon-njuse/media-agent-cli.git
cd media-agent-cli
uv sync
./media-agent --help
```

To complete a local QR login yourself, open the bundled local login companion:

```bash
uv run python src/main.py
```

For an isolated development state directory, set MEDIA_AGENT_APPDATA_DIR before launching the login companion or CLI.

Register the command and Codex Skill as symlinks:

```bash
./scripts/install-global.sh --all
export PATH="$HOME/.local/bin:$PATH"
media-agent --help
```

The installer never overwrites an existing path. Its default links are `$HOME/.local/bin/media-agent` and `$HOME/.codex/skills/media-agent-cli`; use `MEDIA_AGENT_BIN_DIR`, `CODEX_HOME`, or `CODEX_SKILLS_DIR` to override them.

## Agent Contract

Commands emit one JSON object on stdout and use stderr only for progress. Confirm the target explicitly, run `download --dry-run` before a real download, and use the process exit code plus stdout JSON as the result contract.

```bash
media-agent inspect 'https://www.bilibili.com/bangumi/play/ss38385' --episode 27 --with-media
media-agent download 'https://www.bilibili.com/bangumi/play/ss38385' --episode 27 --quality 720p --dry-run
```

See [docs/agent-cli.en.md](docs/agent-cli.en.md) for the command and Skill workflow.

## Provenance and License

Media Agent CLI is a modified derivative of [ScottSloan/Bili23-Downloader](https://github.com/ScottSloan/Bili23-Downloader). It preserves applicable copyright notices, the full Git history, and the GNU GPL v3.0 license. It is not affiliated with or endorsed by the upstream project or Bilibili. See [UPSTREAM.md](UPSTREAM.md) and [NOTICE](NOTICE).
