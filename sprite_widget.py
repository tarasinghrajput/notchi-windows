"""Animated pixel-sprite widget for the Claude Code panel.

Port of notchi's macOS SpriteSheetView/SessionSpriteView to PyQt6. Sprite sheets
are horizontal strips of square frames (frame size == sheet height); the frame
count is inferred from the sheet dimensions, exactly like NotchiState's
`inferredFrameCount`. Sheets are named `claude_<task>_<emotion>.png`.
"""

import os
import sys

from PyQt6.QtCore import QTimer, QRect
from PyQt6.QtGui import QPainter, QPixmap
from PyQt6.QtWidgets import QWidget


def _assets_base() -> str:
    """Resolve the sprites directory for both PyInstaller and dev runs."""
    # PyInstaller --onefile extracts bundled data to _MEIPASS.
    meipass = getattr(sys, "_MEIPASS", None)
    candidates = []
    if meipass:
        candidates.append(meipass)
    if getattr(sys, "frozen", False):
        candidates.append(os.path.dirname(sys.executable))
    candidates.append(os.path.dirname(os.path.abspath(__file__)))
    for base in candidates:
        path = os.path.join(base, "assets", "sprites")
        if os.path.isdir(path):
            return path
    # Fall back to a path next to this file even if it doesn't exist yet.
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "sprites")


# Claude Code status (from the WSL hook) -> notchi sprite task.
STATUS_TO_TASK = {
    "idle": "idle",
    "processing": "working",
    "running_tool": "working",
    "waiting_for_input": "waiting",
    "compacting": "compacting",
    "ended": "sleeping",
}

# Loop frames-per-second per task, matching NotchiState.animationFPS.
# (animationFPS = frameCount / loopDuration; these are the resulting rates.)
TASK_FPS = {
    "idle": 3.0,
    "working": 4.0,
    "waiting": 3.0,
    "compacting": 6.0,
    "sleeping": 2.0,
    "waving": 9.6,   # 25 frames over launchWaveDuration (~2.6s)
}

# Expressive idle sheets play faster on macOS (expressiveSpriteTargetFPS).
_EXPRESSIVE_IDLE_FPS = 7.0


class SpriteWidget(QWidget):
    """Renders a looping pixel sprite for the current Claude task/emotion."""

    def __init__(self, size: int = 56, parent=None):
        super().__init__(parent)
        self._sprite_dir = _assets_base()
        self._size = size
        self.setFixedSize(size, size)

        self._sheet: QPixmap | None = None
        self._frame_count = 1
        self._frame_size = 1
        self._current_frame = 0
        self._mirrored = False
        self._sheet_name = ""
        self._current_fps = 0.0
        self._pixmap_cache: dict[str, QPixmap] = {}

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance)

        self.set_sprite("idle", "neutral")

    # --- public API --------------------------------------------------------
    def set_sprite(self, task: str, emotion: str = "neutral", mirrored: bool = False):
        """Switch to the sheet for (task, emotion), resolving fallbacks."""
        name = self._resolve_sheet_name(task, emotion)
        fps = self._fps_for(task, emotion)

        # Nothing changed -> don't restart the animation (keeps the loop smooth).
        if name == self._sheet_name and fps == self._current_fps and mirrored == self._mirrored:
            return

        self._mirrored = mirrored
        if name != self._sheet_name:
            self._load_sheet(name)
            self._sheet_name = name
            self._current_frame = 0

        self._current_fps = fps
        interval = max(1, int(1000.0 / fps)) if fps > 0 else 0
        if interval and self._frame_count > 1:
            self._timer.start(interval)
        else:
            self._timer.stop()
        self.update()

    def set_status(self, status: str, emotion: str = "neutral"):
        """Convenience: map a Claude Code status string to a sprite task."""
        self.set_sprite(STATUS_TO_TASK.get(status, "idle"), emotion)

    # --- internals ---------------------------------------------------------
    def _resolve_sheet_name(self, task: str, emotion: str) -> str:
        # Exact -> idle+emotion -> idle_neutral (mirrors NotchiState.spriteSheetName).
        for candidate in (f"claude_{task}_{emotion}",
                          f"claude_idle_{emotion}",
                          "claude_idle_neutral"):
            if os.path.exists(os.path.join(self._sprite_dir, candidate + ".png")):
                return candidate
        return "claude_idle_neutral"

    def _fps_for(self, task: str, emotion: str) -> float:
        if task == "idle" and emotion in ("happy", "elated"):
            return _EXPRESSIVE_IDLE_FPS
        return TASK_FPS.get(task, 3.0)

    def _load_sheet(self, name: str):
        if name in self._pixmap_cache:
            self._sheet = self._pixmap_cache[name]
        else:
            path = os.path.join(self._sprite_dir, name + ".png")
            pm = QPixmap(path)
            self._pixmap_cache[name] = pm
            self._sheet = pm

        if self._sheet is None or self._sheet.isNull():
            self._frame_count = 1
            self._frame_size = self._size
            return

        h = self._sheet.height()
        self._frame_size = h if h > 0 else self._size
        self._frame_count = max(1, round(self._sheet.width() / self._frame_size))

    def _advance(self):
        if self._frame_count <= 1:
            return
        self._current_frame = (self._current_frame + 1) % self._frame_count
        self.update()

    def paintEvent(self, event):
        if self._sheet is None or self._sheet.isNull():
            return
        painter = QPainter(self)
        # Pixel art: keep edges crisp.
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)

        col = self._current_frame  # single-row strips
        src = QRect(col * self._frame_size, 0, self._frame_size, self._frame_size)
        dst = QRect(0, 0, self.width(), self.height())

        if self._mirrored:
            painter.translate(self.width(), 0)
            painter.scale(-1, 1)
        painter.drawPixmap(dst, self._sheet, src)
