"""
rain - дождь из символов (QULW RainVisual).
CLI:  rain [цвет] [--fps N] [--speed X] [--density X]
GUI:  настройки читаются из live_config.json.
"""

# QAnim
# Copyright (c) 2026 [ZigRain-hub]
# Licensed under the MIT License. See LICENSE file for details.

import random
import string

from qvis import (
    run, get_palette, COLOR_SCHEMES,
    read_live_config, LIVE_CONFIG_PATH,
)

POOL = string.ascii_letters + string.digits + "!@#$%^&*()"

#скорость падения (строк в секунду при speed=1.0)
BASE_SPEED = 6.0
# плотность: сколько капель на 1 колонку при density=1.0
BASE_DENSITY = 1.0


class Rain:
    schemes = list(COLOR_SCHEMES)
    def __init__(self, args=None):
        self.cfg = {
            "color": "matrix",
            "interval_ms": 33,
            "speed": 1.0,
            "density": 1.0,
        }
        if args is not None:
            if getattr(args, "color", None):
                self.cfg["color"] = args.color
            if getattr(args, "fps", None):
                self.cfg["interval_ms"] = max(1, int(1000 / max(1, args.fps)))
            if getattr(args, "speed", None) is not None:
                self.cfg["speed"] = float(args.speed)
            if getattr(args, "density", None) is not None:
                self.cfg["density"] = float(args.density)
        self.colors = get_palette(self.cfg["color"], "matrix")
        self._cur_color = self.cfg["color"]
        self.w, self.h = 80, 24
        self.drops = []
        self._last_live_read = 0.0
        self._last_live_mtime = 0.0
        self._last_size = (0, 0)

    def color(self, name):
        self.cfg["color"] = name
        self.colors = get_palette(name, "matrix")
        self._cur_color = name

    def _alloc_drops(self):
        cols, rows = self.w, self.h
        # количество капель зависит от density и ширины окна
        n = int(cols * BASE_DENSITY * max(0.05, self.cfg["density"]))
        n = max(10, min(500, n))
        self.drops = [
            [
                random.randint(0, max(0, cols - 1)),
                random.uniform(-rows, rows),
                self._rand_speed(),
                random.choice(POOL),
            ]
            for _ in range(n)
        ]

    def _rand_speed(self):
        # строк в секунду; разброс ±50%
        return random.uniform(0.5, 1.5) * BASE_SPEED * self.cfg["speed"] / 60.0
        # /60 - потому что tick() вызывается 60 раз в секунду,
        # при другом fps корректируется в tick() через dt
    def resize(self, cols, rows):
        self.w, self.h = cols, rows
        self._alloc_drops()
        self._last_size = (cols, rows)

    def _poll_live_config(self):
        import time
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
            c = live.get("rain", {})
            if not c:
                return
            new_color = c.get("color", self.cfg["color"])
            if new_color != self._cur_color:
                self.color(new_color)
            new_speed = float(c.get("speed", self.cfg["speed"]))
            new_density = float(c.get("density", self.cfg["density"]))
            self.cfg["interval_ms"] = int(c.get("interval_ms", self.cfg["interval_ms"]))

            changed = False
            if abs(new_speed - self.cfg["speed"]) > 1e-4:
                self.cfg["speed"] = new_speed
                # пересчитываем скорости
                for d in self.drops:
                    d[2] = self._rand_speed() * 60.0 / 60.0
                changed = True
            if abs(new_density - self.cfg["density"]) > 1e-4:
                self.cfg["density"] = new_density
                changed = True
            if changed:
                self._alloc_drops()
        except Exception as e:
            import sys
            print(f"[rain] live config: {e}", file=sys.stderr)

    def tick(self):
        self._poll_live_config()
        ms = max(1, int(self.cfg.get("interval_ms", 33)))
        dt = ms / 1000.0
        speed = self.cfg["speed"]
        for d in self.drops:
            # d[2] хранит скорость в «строках за кадр при 60 fps»;
            # пересчитываем на реальный dt
            d[1] += d[2] * 60.0 * dt * speed

            if d[1] > self.h + 3:
                d[0] = random.randint(0, max(0, self.w - 1))
                d[1] = random.uniform(-4, -1)
                d[3] = random.choice(POOL)

    def draw(self, s):
        n = len(self.colors)
        if n == 0:
            return
        for x, y, _, ch in self.drops:
            if 0 <= y < self.h:
                yi = int(y)
                col = self.colors[max(0, min(n - 1, int(y / self.h * (n - 1))))]
                s.text(x, yi, ch, col)

    def close(self):
        pass

def extra(ap):
    ap.add_argument("--speed", type=float, default=None, help="скорость (0.1..5)")
    ap.add_argument("--density", type=float, default=None, help="плотность (0.1..5)")

def main():
    run("rain", lambda a: Rain(a), 60, extra)

if __name__ == "__main__":
    main()