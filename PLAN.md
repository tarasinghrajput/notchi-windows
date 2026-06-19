# Plan: Notchi-style Claude Code Activity Panel for Windows Dynamic Island

---

## Phases at a Glance

| Phase | Goal | Deliverable |
|---|---|---|
| 1 | WSL hook wired up and sending payloads | Hook registered; test JSON arrives on port 8765 |
| 2 | Windows TCP listener running | `claude_monitor.py` installed; payloads received by Windows process |
| 3 | Claude panel visible in carousel | New panel renders with status/tool/elapsed |
| 4 | Auto-launch + packaging | App starts itself from WSL hook; EXE build updated |

---

## Context

The user has:
- **notchi** (macOS) — a Swift app that shows Claude Code activity (animated sprites) in the MacBook notch via a Unix socket
- **dynamic-island-for-windows** — a working Python/PyQt6 Windows overlay widget at `notchi-windows/main.py` with a feature carousel (perf, media, weather, calendar, month, basics)
- **WSL** — Claude Code runs inside WSL; the user wants the Windows Dynamic Island widget to show live Claude Code activity

A hook script already exists at `~/.claude/hooks/notchi-hook.sh` (4515 bytes, executable). It:
- Reads Claude Code hook events from stdin
- Normalizes them to a JSON payload
- Sends to `127.0.0.1:8765` (fallback: WSL nameserver IP)
- Already handles all 9 event types with correct status mapping

**What is missing:**
1. The hook is not registered in `~/.claude/settings.json`
2. The Windows app has no TCP listener on port 8765
3. The Windows app has no "Claude Code" panel in its carousel
4. The hook's `appDir` variable points to a non-existent path (`notchi-for-windows\windows`) — needs updating

## Architecture

```
WSL: Claude Code → notchi-hook.sh → Python TCP → 127.0.0.1:8765
Windows: DynamicIsland → ClaudeMonitor(QThread) → TCP server :8765 → Qt signal → Claude panel
```

The WSL-to-Windows bridge works because WSL2 port-forwards localhost automatically; `127.0.0.1:8765` in WSL reaches Windows. The hook already handles the nameserver fallback for non-mirrored WSL2 configs.

---

## Phase 1 — WSL Hook Registration

**Goal**: `notchi-hook.sh` fires for every Claude Code event and successfully sends payloads to port 8765. No Windows app changes yet — verify end-to-end with `nc` or a temporary listener.

### 1a. Fix hook's `appDir` in `~/.claude/hooks/notchi-hook.sh` (line 4)
Change:
```bash
appDir="C:\Users\72619\OneDrive\Documents\React Apps\notchi-for-windows\windows"
```
To:
```bash
appDir="C:\Users\72619\OneDrive\Documents\React Apps\notchi-windows"
```
This makes the hook auto-launch `notchi-windows\main.py` (via PowerShell) if the app isn't running. The `appRuntime` is already set to `"windows"`.

### 1b. Register hook in `~/.claude/settings.json`
Create `install-wsl-hook.sh` and run it from WSL. It uses `python3` JSON merge to add 9 event registrations pointing to `notchi-hook.sh` — preserving the existing `rtk-rewrite.sh` entry.

Events to register: `PreToolUse`, `PostToolUse`, `UserPromptSubmit`, `Stop`, `SubagentStop`, `SessionStart`, `SessionEnd`, `PermissionRequest`, `PreCompact`.

Each entry format:
```json
{ "matcher": "", "hooks": [{"type": "command", "command": "/home/tara/.claude/hooks/notchi-hook.sh"}] }
```

**Phase 1 verification**: Run `nc -l 8765` on Windows (or WSL), then type a Claude Code prompt. Confirm raw JSON arrives on the listener.

---

## Phase 2 — Windows TCP Listener (`claude_monitor.py`)

**Goal**: The Windows Dynamic Island process listens on port 8765, receives hook payloads, and logs/prints them. No visible UI change yet — just prove the data pipeline works end-to-end.

### 2a. New file: `claude_monitor.py`

A `QThread` subclass that runs a `socketserver.ThreadingTCPServer` on `0.0.0.0:8765`. Each connection = one hook event. Emits `event_received = pyqtSignal(dict)` so Qt main thread receives the payload safely.

Key design:
- `allow_reuse_address = True` (prevents "address in use" on restart)
- `handle_request()` loop with 1s timeout (allows clean shutdown via `self._is_running` flag)
- Binds to `0.0.0.0` so both 127.0.0.1 and the WSL nameserver IP work

```python
class ClaudeMonitor(QThread):
    event_received = pyqtSignal(dict)

    def __init__(self, port=8765, parent=None): ...
    def run(self): ...          # ThreadingTCPServer loop
    def _on_event(self, payload): self.event_received.emit(payload)
    def stop(self): ...         # sets _is_running=False, closes server, waits
```

### 2b. Wire into `main.py` (minimal — listener only)
In `setup_monitors()`, add:
```python
claude_port = self.settings.get("claude_port", 8765)
self.claude_monitor = ClaudeMonitor(port=claude_port, parent=self)
self.claude_monitor.event_received.connect(lambda ev: print("Claude event:", ev))
self.claude_monitor.start()
```
In `closeEvent()`, add `self.claude_monitor.stop()`.

**Phase 2 verification**: Start the Windows app, use Claude Code in WSL — raw JSON payloads print to the console. No panel yet.

---

## Phase 3 — Claude Code Panel in the Carousel

**Goal**: A "Claude Code" panel appears in the Dynamic Island carousel (7th slot, after "basics"). It shows live status: idle / tool name / thinking / waiting, with a colored status dot and elapsed timer. Background animates based on state.

### 3a. Modify `main.py`

**a. Imports** (top of file, replace the temporary `print` lambda with the real slot):
```python
from claude_monitor import ClaudeMonitor
from dataclasses import dataclass, field
import time as _time
```

**b. `ClaudeState` dataclass** (after `DEFAULT_TASKS`, before `ControlBall` class):
```python
@dataclass
class ClaudeState:
    status: str = "idle"
    tool_name: str = ""
    session_id: str = ""
    cwd: str = ""
    last_event_ts: float = field(default_factory=_time.time)

    def update_from_event(self, ev: dict): ...
    @property def elapsed_str(self) -> str: ...
    @property def dot_color(self) -> str: ...   # grey/blue/yellow/purple per status
    @property def status_label(self) -> str: ...  # "Idle" / "[Bash]" / "Thinking..." etc.
```

Status → color mapping:
- `idle` / `ended` → `#555555`
- `processing` / `running_tool` → `#0078FF`
- `waiting_for_input` → `#FFB800`
- `compacting` → `#9B59B6`

**c. `DynamicIsland.__init__` additions:**
```python
self.claude_state = ClaudeState()
self.CLAUDE_W, self.CLAUDE_H = 360, 120
self._claude_bg_opacity = 0.0
self.claude_bg_anim = QPropertyAnimation(self, b"claude_bg_opacity")
self.claude_bg_anim.setDuration(1200)
```
Add `"claude"` to `self.features` list (7th position, after `"basics"`).

**d. `pyqtProperty` for `claude_bg_opacity`** (alongside other animated opacity properties).

**e. `setup_monitors()` addition** (after `weather_monitor.start()`):
```python
claude_port = self.settings.get("claude_port", 8765)
self.claude_monitor = ClaudeMonitor(port=claude_port, parent=self)
self.claude_monitor.event_received.connect(self.update_claude_state)
self.claude_monitor.start()
```

**f. `init_ui()` addition:**
```python
self.claude_panel = self.create_claude_panel()
```
Add `self.claude_panel` to the hide-all lists (Idle state, Notify state) and to `content_layout`.

**g. `create_claude_panel()` new method:**
3-row layout:
- Row 1: `claude_dot` (10px colored circle) + "Claude Code" bold label
- Row 2: `claude_status_label` (22px bold — shows tool name / status)
- Row 3: `claude_meta_label` (10px muted — elapsed time + project dir name)

**h. `update_claude_state(ev: dict)` slot** + `_refresh_claude_panel_labels()` helper:
Called via Qt signal from `ClaudeMonitor`. Updates `self.claude_state` and refreshes label text + dot color.

**i. `update_content()` addition** (the 1s master timer already exists):
```python
if hasattr(self, 'claude_meta_label'):
    self._refresh_claude_panel_labels()
```
This ticks the "Xs ago" elapsed display every second.

**j. `update_feature_view()` additions:**
```python
self.claude_panel.setVisible(feature == "claude")
# In elif chain:
elif feature == "claude":
    self.status_text.setText("Claude Code")
    self.status_icon.setPixmap(qta.icon('mdi.robot', color='white').pixmap(18, 18))
```

**k. `execute_liquid_transition()` addition:**
```python
elif feature == "claude": w, h = self.CLAUDE_W, self.CLAUDE_H
```
And in the opacity animation block:
```python
set_bg_target(self.claude_bg_anim, self._claude_bg_opacity, 1.0 if feat == "claude" else 0.0)
```

**l. `paintEvent()` addition:**
```python
if self._claude_bg_opacity > 0.0:
    self.paint_claude_bg(painter, rect, radius)
```

**m. `paint_claude_bg()` new method:**
Dark blue-grey linear gradient base (matching Claude's brand). Reuses `self.weather_bg_phase` for animated blob movement. Status-dependent bloom colors (blue for working, yellow for waiting, purple for compacting). Uses `CompositionMode_Screen` for layered glow — same pattern as `paint_weather_bg()`.

**n. `closeEvent()` addition:**
```python
self.claude_monitor.stop()
```

**Phase 3 verification**: Scroll through the Dynamic Island carousel — Claude Code panel appears. Use Claude Code in WSL; watch the panel update live (tool name, status dot color, elapsed).

---

## Phase 4 — Auto-launch + Config + EXE Build

**Goal**: The hook auto-starts the Windows app if it isn't running. Config file is updated. EXE build includes the new monitor.

### 4a. Update `config.json`
Add `"claude_port": 8765` to the existing JSON object.

### 4b. Verify auto-launch
With `appDir` already fixed in Phase 1a, the hook calls `start_notchi_windows` which runs:
```powershell
Start-Process pythonw "main.py" -WindowStyle Hidden
```
Test by closing the Windows app and triggering a Claude Code event — the app should relaunch.

### 4c. Update `build_exe.ps1`
No new hidden-import flags needed (`socketserver` is stdlib). Verify `claude_monitor.py` is co-located and picked up by PyInstaller's automatic discovery.

**Phase 4 verification**: Build EXE with `build_exe.ps1`. Launch `DynamicIsland.exe`. Use Claude Code in WSL — Claude panel appears and updates.

---

## Key Files

| File | Action |
|---|---|
| `~/.claude/hooks/notchi-hook.sh` | Fix `appDir` path (line 4) |
| `~/.claude/settings.json` | Register hook for 9 event types (via `install-wsl-hook.sh`) |
| `claude_monitor.py` | Create — new TCP listener QThread |
| `main.py` | Modify — Claude panel, state, monitor wiring, paint |
| `config.json` | Add `claude_port` key |
| `install-wsl-hook.sh` | Create — WSL hook registration script |
