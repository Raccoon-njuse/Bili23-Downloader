# Media Agent CLI and Agent Skill

`media-agent` is a local CLI, and `.agents/skills/media-agent-cli` is its Agent workflow contract. They expose locally authorized favorite lookup, link inspection, explicit episode selection, and downloads for later local transcription or analysis.

## Setup

```bash
git clone https://github.com/Raccoon-njuse/media-agent-cli.git
cd media-agent-cli
uv sync
./scripts/install-global.sh --all
export PATH="$HOME/.local/bin:$PATH"
media-agent --help
```

The installer creates only symlinks: `$HOME/.local/bin/media-agent` and `$HOME/.codex/skills/media-agent-cli` by default. Use `MEDIA_AGENT_BIN_DIR`, `CODEX_HOME`, or `CODEX_SKILLS_DIR` to override them. Start a new Codex task after installing the Skill.

## Workflow

1. Run `media-agent doctor`; stop when the user has not completed a local login.
2. Inspect the supplied link and require an explicit selector for a multi-item result.
3. Use `inspect --with-media` before choosing a requested quality.
4. Run `download --dry-run`, verify the returned plan, then run the real download into an explicit local directory.
5. Treat stdout JSON and the process exit code as the contract. Do not expose account data, Cookies, signed URLs, or media outside the requested local workflow.

This product is a GPLv3 derivative of [ScottSloan/Bili23-Downloader](https://github.com/ScottSloan/Bili23-Downloader). See [NOTICE](../NOTICE), [UPSTREAM.md](../UPSTREAM.md), and [LICENSE](../LICENSE).
