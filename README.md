# notchi-windows

A fluid, animated Dynamic Island for Windows with live Claude Code activity — a mashup of two macOS projects brought to Windows.

## Built On

| Project | What it contributes |
|---|---|
| [dynamic-island-for-windows](https://github.com/rajsriv/dynamic-island-for-windows) | The Dynamic Island concept — a floating pill at the top of the screen that expands to show system info, media, and notifications |
| [notchi](https://github.com/sk-ruban/notchi) | The Claude Code hook integration — a notch-style widget that tracks Claude Code sessions and shows a mascot that reacts to Claude's state |

This project merges both ideas into a single PyQt6 app: a Windows Dynamic Island that also monitors Claude Code sessions in real time.

---

## What It Does

A black pill sits centered at the top of your screen, flush with the top edge. Hovering expands it into a panel that cycles through:

- **System performance** — CPU, RAM, disk usage, network speeds
- **Media controls** — Now-playing track with prev/play/next buttons, album-accent animations
- **Weather** — Current temperature, condition, and a 5-slot hourly forecast (via Open-Meteo)
- **Tasks / Next Up** — A lightweight to-do list you can edit in-place inside the island
- **Month progress** — Dot-grid showing how far through the current month you are
- **Basics** — Quick-launch buttons for Shutdown, Restart, Sleep, File Explorer, Task Manager, Chrome, YouTube, CMD
- **Claude Code** — Live status panel with a mascot sprite that changes expression based on what Claude is doing

### Claude Code Integration

When Claude Code is active, the island shows a mini mascot sprite in the collapsed pill. Hover to see the full Claude panel, which displays:

- A color-coded status dot (blue = working, amber = waiting for input, purple = compacting, grey = idle)
- A status label (`Thinking...`, `[Bash]`, `Waiting`, `Compacting`, etc.)
- How long ago the last event fired, and the current working directory
- A sprite whose emotion tracks Claude's mood: happy when working, sad when waiting too long, waving on session start, sleeping when idle

The integration works through a Claude Code hook that fires on every event (`PreToolUse`, `PostToolUse`, `Stop`, etc.) and sends a JSON payload over TCP to port 8765 (configurable).

### Visual Features

- **Fluid Blobs** / **Glow Sweep** / **Neon Border** — three animation styles for the media panel, using the album art's dominant color
- **Charging ears** — when you plug in power, energy beams shoot out both sides of the pill
- **Shine sweep** — a light flare when the island expands
- **Notch Nook** style — an alternative shape with curved edges that mimics a display notch
- Picks up your Windows accent color automatically from the registry

---

## Requirements

- Windows 10/11
- Python 3.12+
- Claude Code (for the Claude integration; optional)
- WSL (for the hook script; optional)

---

## Installation

### 1. Clone and install dependencies

```powershell
git clone https://github.com/tarasinghrajput7261/notchi-windows
cd notchi-windows
pip install -r requirements.txt
```

### 2. Run

```powershell
python main.py
```

The app registers itself in `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` on first launch so it starts with Windows automatically.

### 3. Configure location (optional)

Edit `config.json` to set your city and coordinates for weather:

```json
{
  "location": "Your City, Country",
  "lat": 28.6139,
  "lon": 77.2090
}
```

Or right-click the island and choose **Change Location** from the context menu.

---

## Claude Code Hook Setup (WSL)

This wires up Claude Code so the island tracks your sessions live.

### 1. Copy the hook script

```bash
mkdir -p ~/.claude/hooks
cp /mnt/c/path/to/notchi-windows/notchi-hook.sh ~/.claude/hooks/notchi-hook.sh
chmod +x ~/.claude/hooks/notchi-hook.sh
```

### 2. Register it with Claude Code

```bash
bash /mnt/c/path/to/notchi-windows/install-wsl-hook.sh
```

This patches `~/.claude/settings.json` to call the hook on all Claude Code events. It is idempotent — safe to run multiple times.

### 3. Verify

Start a Claude Code session. The island pill should show the Claude mascot. Hover to see the full status panel.

The hook sends events to `localhost:8765` by default. Change `claude_port` in `config.json` if you need a different port.

---

## Configuration (`config.json`)

| Key | Default | Description |
|---|---|---|
| `location` | `"Varanasi, India"` | City name shown in the weather panel |
| `lat` / `lon` | `25.317` / `83.010` | Coordinates for the weather API |
| `claude_port` | `8765` | TCP port the Claude hook sends events to |
| `compatibility_mode` | `false` | Disables some transparency effects if you see rendering artifacts |
| `island_style` | `"Default"` | `"Default"` (rounded pill) or `"Notch Nook"` (notch shape) |
| `animation_style` | `"Fluid Blobs"` | `"Fluid Blobs"`, `"Glow Sweep"`, or `"Neon Border"` |
| `tasks` | sample tasks | Array of `{name, category, time, color}` objects |

---

## How It Works

```
Claude Code (WSL)
    │
    └─ hook fires on every event
         │
         └─ notchi-hook.sh sends JSON over TCP → Windows localhost:8765
                                                        │
                                                  ClaudeMonitor (Python thread)
                                                        │
                                                  DynamicIsland (PyQt6 main thread)
                                                        │
                                              ┌─────────┴──────────┐
                                        SpriteWidget          Panel labels
                                     (mascot emotion)      (status / cwd / elapsed)
```

Other monitors run as background QThreads and emit Qt signals back to the main widget:

| Monitor | Data |
|---|---|
| `PerfMonitor` | CPU %, RAM %, disk %, network speeds via psutil |
| `MediaMonitor` | Now-playing via Windows Media session API (winsdk) |
| `WeatherMonitor` | Temperature + hourly forecast via Open-Meteo (no API key needed) |
| `NotificationMonitor` | Windows toast notifications via WinRT |
| `KeyLockMonitor` | Caps Lock / Num Lock state changes |

The main widget (`DynamicIsland`) runs a 16 ms animation timer for smooth gradients and a 1 s content timer for clock and label updates. Island size transitions use `QPropertyAnimation` with `OutExpo` easing.

---

## Building an Executable

```powershell
.\build_exe.ps1
```

This uses PyInstaller to produce a self-contained `.exe` in `dist/`.

---

## License

MIT
