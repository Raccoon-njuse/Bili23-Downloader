#!/usr/bin/env sh
# Register the source-tree CLI and Codex Skill without copying project files.
set -eu

usage() {
    cat <<'EOF'
Usage: ./scripts/install-global.sh [--all|--cli|--skill|--uninstall]

Registers source-tree symlinks for macOS and Linux:
  --all        Register both the bili23 command and Codex Skill (default).
  --cli        Register only the bili23 command.
  --skill      Register only the Codex Skill.
  --uninstall  Remove links created for this source checkout.

Environment overrides:
  BILI23_BIN_DIR    Command directory, default: $HOME/.local/bin
  CODEX_HOME        Codex home, default: $HOME/.codex
  CODEX_SKILLS_DIR  Skill directory, default: $CODEX_HOME/skills
EOF
}

MODE=${1:---all}
if [ "$#" -gt 1 ]; then
    usage >&2
    exit 2
fi

case "$MODE" in
    --all|--cli|--skill|--uninstall) ;;
    -h|--help)
        usage
        exit 0
        ;;
    *)
        usage >&2
        exit 2
        ;;
esac

if [ -z "${HOME:-}" ]; then
    echo "HOME is required to register global paths." >&2
    exit 1
fi

SOURCE_PATH=$0
case "$SOURCE_PATH" in
    */*) ;;
    *) SOURCE_PATH=$(command -v "$SOURCE_PATH") ;;
esac

while [ -L "$SOURCE_PATH" ]; do
    SOURCE_DIR=$(CDPATH= cd -P "$(dirname "$SOURCE_PATH")" && pwd)
    LINK_TARGET=$(readlink "$SOURCE_PATH")
    case "$LINK_TARGET" in
        /*) SOURCE_PATH=$LINK_TARGET ;;
        *) SOURCE_PATH=$SOURCE_DIR/$LINK_TARGET ;;
    esac
done

PROJECT_DIR=$(CDPATH= cd -P "$(dirname "$SOURCE_PATH")/.." && pwd)
CLI_SOURCE="$PROJECT_DIR/bili23"
SKILL_SOURCE="$PROJECT_DIR/.agents/skills/bili23-cli"
BIN_DIR=${BILI23_BIN_DIR:-"$HOME/.local/bin"}
CODEX_ROOT=${CODEX_HOME:-"$HOME/.codex"}
SKILLS_DIR=${CODEX_SKILLS_DIR:-"$CODEX_ROOT/skills"}
CLI_LINK="$BIN_DIR/bili23"
SKILL_LINK="$SKILLS_DIR/bili23-cli"

link_source() {
    source_path=$1
    link_path=$2

    mkdir -p "$(dirname "$link_path")"
    if [ -L "$link_path" ]; then
        if [ "$(readlink "$link_path")" = "$source_path" ]; then
            printf 'Already registered: %s\n' "$link_path"
            return 0
        fi

        printf 'Refusing to replace existing symlink: %s\n' "$link_path" >&2
        return 1
    fi

    if [ -e "$link_path" ]; then
        printf 'Refusing to replace existing path: %s\n' "$link_path" >&2
        return 1
    fi

    ln -s "$source_path" "$link_path"
    printf 'Registered: %s -> %s\n' "$link_path" "$source_path"
}

unlink_source() {
    source_path=$1
    link_path=$2

    if [ ! -L "$link_path" ]; then
        if [ -e "$link_path" ]; then
            printf 'Not removing non-symlink path: %s\n' "$link_path" >&2
            return 1
        fi

        return 0
    fi

    if [ "$(readlink "$link_path")" != "$source_path" ]; then
        printf 'Not removing symlink owned by another source: %s\n' "$link_path" >&2
        return 1
    fi

    rm "$link_path"
    printf 'Unregistered: %s\n' "$link_path"
}

if [ "$MODE" = "--uninstall" ]; then
    unlink_source "$CLI_SOURCE" "$CLI_LINK"
    unlink_source "$SKILL_SOURCE" "$SKILL_LINK"
    exit 0
fi

if [ "$MODE" = "--all" ] || [ "$MODE" = "--cli" ]; then
    if [ ! -x "$PROJECT_DIR/.venv/bin/python" ]; then
        printf 'Missing %s/.venv/bin/python. Run uv sync in the source checkout first.\n' "$PROJECT_DIR" >&2
        exit 1
    fi

    link_source "$CLI_SOURCE" "$CLI_LINK"
fi

if [ "$MODE" = "--all" ] || [ "$MODE" = "--skill" ]; then
    if [ ! -f "$SKILL_SOURCE/SKILL.md" ]; then
        printf 'Missing canonical Skill at %s.\n' "$SKILL_SOURCE" >&2
        exit 1
    fi

    link_source "$SKILL_SOURCE" "$SKILL_LINK"
fi

printf '\nEnsure %s is on PATH, then start a new Codex task after installing the Skill.\n' "$BIN_DIR"
