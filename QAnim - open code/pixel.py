"""
pixel - пиксельная плазма (QULW PixelVisual).
CLI:  pixel [цвет] [--fps N] [--speed X] [--scale N]
GUI:  настройки читаются из live_config.json.
"""

# QAnim
# Copyright (c) 2026 [ZigRain-hub]
# Licensed under the MIT License. See LICENSE file for details.

import time, sys
import numpy as np
from qvis import (
    run, get_palette, COLOR_SCHEMES,
    read_live_config, LIVE_CONFIG_PATH,
)

TAU = 6.28318


class Pixel:
    schemes = list(COLOR_SCHEMES)
    def __init__(self, args=None):
        self.cfg = {
            "color": "cyan",
            "interval_ms": 33,
            "speed": 1.0,
            "scale": 20,
        }
        if args is not None:
            if getattr(args, "color", None):
                self.cfg["color"] = args.color
            if getattr(args, "fps", None):
                self.cfg["interval_ms"] = max(1, int(1000 / max(1, args.fps)))
            if getattr(args, "speed", None) is not None:
                self.cfg["speed"] = float(args.speed)
            if getattr(args, "scale", None) is not None:
                self.cfg["scale"] = int(args.scale)
        self.time = 0.0
        self._cur_color = self.cfg["color"]
        self.colors = get_palette(self.cfg["color"], "cyan")
        self._last_live_read = 0.0
        self._last_live_mtime = 0.0
        self._build_grid(self.cfg["scale"])
        self.resize(80, 24)

    def _build_grid(self, scale):
        self.GW = max(4, min(80, int(scale)))
        self.GH = max(3, int(self.GW * 0.7))
        self.grid = np.zeros((self.GH, self.GW), int)
    def color(self, name):
        self.cfg["color"] = name
        self.colors = get_palette(name, "cyan")
        self._cur_color = name

    def resize(self, cols, rows):
        self.gx = np.arange(cols) * self.GW // max(1, cols)
        self.gy = np.arange(rows * 2) * self.GH // max(1, rows * 2)


    def _poll_live_config(self):
        now = time.time()
        if now - self._last_live_read < 0.2:
            return
        self._last_live_read = now
        try:
            if not LIVE_CONFIG_PATH.exists():
                return
            mtime = LIVE_CONFIG_PATH.stat().st_mtime
            if mtime == self._last_live_mtime:
                return
            self._last_live_mtime = mtime
            live = read_live_config()
            c = live.get("pixel", {})
            if not c:
                return
            new_color = c.get("color", self.cfg["color"])
            if new_color != self._cur_color:
                self.color(new_color)
            new_scale = int(c.get("scale", self.cfg["scale"]))
            if new_scale != self.cfg["scale"]:
                self.cfg["scale"] = new_scale
                self._build_grid(new_scale)

            self.cfg["speed"] = float(c.get("speed", self.cfg["speed"]))
            self.cfg["interval_ms"] = int(c.get("interval_ms", self.cfg["interval_ms"]))

        except Exception as e:
            print(f"[pixel] live config: {e}", file=sys.stderr)

    def tick(self):
        self._poll_live_config()
        ms = max(1, int(self.cfg.get("interval_ms", 33)))
        dt = ms / 1000.0
        speed = float(self.cfg["speed"])
        self.time += 0.02 * speed * (dt / 0.033)
        xs = np.arange(self.GW)[None, :] / self.GW
        ys = np.arange(self.GH)[:, None] / self.GH
        t = self.time
        val = xs * TAU + ys * TAU + t * 2.0 + 0.5 * xs * TAU + 0.3 * t
        self.grid = np.abs(
            128 + 127 * (0.5 + 0.5 * (np.mod(val, 2.0) - 1.0))
        ).astype(int)

    def draw(self, s):
        n = len(self.colors)
        if n == 0:
            return
        gx = np.clip(self.gx, 0, self.GW - 1)
        gy = np.clip(self.gy, 0, self.GH - 1)
        b = self.grid[np.ix_(gy, gx)]
        idx = np.clip((b / 255 * (n - 1)).astype(int), 0, n - 1)
        pal = self.colors
        s.set_pix([pal[i] if v > 150 else None
                   for v, i in zip(b.ravel().tolist(), idx.ravel().tolist())])

    def close(self):
        pass

def extra(ap):
    ap.add_argument("--speed", type=float, default=None)
    ap.add_argument("--scale", type=int, default=None)

def main():
    run("pixel", lambda a: Pixel(a), 60, extra)

if __name__ == "__main__":
    main()