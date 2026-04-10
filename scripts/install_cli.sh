#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

is_in_path() {
  local dir_path="$1"
  case ":$PATH:" in
    *":$dir_path:"*) return 0 ;;
    *) return 1 ;;
  esac
}

pick_rc_file() {
  local shell_name
  shell_name="$(basename "${SHELL:-}")"
  case "$shell_name" in
    zsh) printf '%s\n' "$HOME/.zshrc" ;;
    bash) printf '%s\n' "$HOME/.bashrc" ;;
    *) printf '%s\n' "$HOME/.profile" ;;
  esac
}

install_editable() {
  if [ -n "${VIRTUAL_ENV:-}" ]; then
    "$PYTHON_BIN" -m pip install -e "$ROOT_DIR"
  else
    "$PYTHON_BIN" -m pip install --user -e "$ROOT_DIR"
  fi
}

install_editable

if command -v mdtomd >/dev/null 2>&1; then
  echo "mdtomd 已可直接使用: $(command -v mdtomd)"
  exit 0
fi

USER_BASE="$("$PYTHON_BIN" -m site --user-base)"
USER_BIN="$USER_BASE/bin"
SCRIPT_PATH="$USER_BIN/mdtomd"

if [ ! -x "$SCRIPT_PATH" ]; then
  echo "未找到安装后的 mdtomd: $SCRIPT_PATH" >&2
  exit 1
fi

for candidate in /opt/homebrew/bin /usr/local/bin "$HOME/.local/bin" "$HOME/bin"; do
  if [[ "$candidate" == "$HOME/"* ]] && [ ! -d "$candidate" ]; then
    mkdir -p "$candidate"
  fi
  if is_in_path "$candidate" && [ -d "$candidate" ] && [ -w "$candidate" ]; then
    ln -sf "$SCRIPT_PATH" "$candidate/mdtomd"
    echo "已创建命令链接: $candidate/mdtomd -> $SCRIPT_PATH"
    echo "现在可直接使用: mdtomd"
    exit 0
  fi
done

RC_FILE="$(pick_rc_file)"
EXPORT_LINE="export PATH=\"$USER_BIN:\$PATH\""
touch "$RC_FILE"
if ! grep -Fq "$USER_BIN" "$RC_FILE"; then
  printf '\n%s\n' "$EXPORT_LINE" >> "$RC_FILE"
fi

echo "已写入 PATH 到 $RC_FILE"
echo "请重新打开终端，或先执行:"
echo "export PATH=\"$USER_BIN:\$PATH\""
