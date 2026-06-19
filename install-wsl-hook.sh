#!/usr/bin/env bash
#
# install-wsl-hook.sh
# Registers notchi-hook.sh in ~/.claude/settings.json for all Claude Code
# hook events so the Windows Dynamic Island gets live activity updates.
#
# Safe to run multiple times (idempotent). Preserves existing hook entries.

set -euo pipefail

HOOK_PATH="${HOME}/.claude/hooks/notchi-hook.sh"
SETTINGS="${HOME}/.claude/settings.json"

if [[ ! -f "$HOOK_PATH" ]]; then
    echo "ERROR: hook not found at $HOOK_PATH"
    echo "Install notchi-hook.sh into ~/.claude/hooks/ first."
    exit 1
fi

if [[ ! -x "$HOOK_PATH" ]]; then
    echo "Making hook executable: $HOOK_PATH"
    chmod +x "$HOOK_PATH"
fi

if [[ ! -f "$SETTINGS" ]]; then
    echo "Creating new settings file: $SETTINGS"
    echo '{}' > "$SETTINGS"
fi

echo "Patching $SETTINGS ..."

python3 - "$SETTINGS" "$HOOK_PATH" <<'PYEOF'
import json
import sys

settings_path = sys.argv[1]
hook_path = sys.argv[2]

with open(settings_path) as f:
    cfg = json.load(f)

hooks = cfg.setdefault("hooks", {})

EVENT_TYPES = [
    "PreToolUse", "PostToolUse", "UserPromptSubmit",
    "Stop", "SubagentStop", "SessionStart", "SessionEnd",
    "PermissionRequest", "PreCompact",
]

hook_entry = {"type": "command", "command": hook_path}
added = 0

for event in EVENT_TYPES:
    handlers = hooks.setdefault(event, [])
    already = any(
        h.get("command") == hook_path
        for group in handlers
        for h in group.get("hooks", [])
    )
    if not already:
        handlers.append({"matcher": "", "hooks": [hook_entry]})
        added += 1

with open(settings_path, "w") as f:
    json.dump(cfg, f, indent=2)

print(f"Done. Registered notchi-hook.sh for {added} new event(s); "
      f"{len(EVENT_TYPES) - added} already present.")
PYEOF

echo "Hook registration complete."
