# QAnim
# Copyright (c) 2026 [ZigRain-hub]
# Licensed under the MIT License. See LICENSE file for details.

import random
import string
import sys
import time

from qvis import (
    run, get_palette, COLOR_SCHEMES,
    read_live_config, LIVE_CONFIG_PATH,
)
POOL = string.ascii_letters + string.digits

BASE_SPEED = 14.0      # строк/сек при speed=1.0 и высоте = REFERENCE_ROWS
MAX_DT = 0.05          # защита от больших скачков времени (перетаскивание окна)
MAX_LEN = 18           # максимальная длина хвоста на опорной высоте
REFERENCE_ROWS = 54.0


def _lighten(c, k):
    return tuple(int(v + (255 - v) * k) for v in c)


class Drop:
    __slots__ = ("col", "pos", "speed", "length")

    def __init__(self, col):
        self.col = col
        self.pos = 0.0
        self.speed = BASE_SPEED
        self.length = 8

class Matrix:
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
                self.cfg["speed"] = max(0.05, float(args.speed))
            if getattr(args, "density", None) is not None:
                self.cfg["density"] = max(0.05, float(args.density))

        self._cur_color = None
        self.colors = []
        self.head_color = (255, 255, 255)
        self.trail_color = (200, 255, 200)
        self.tail_color = (100, 200, 100)
        self.color(self.cfg["color"])
        self.cols, self.rows = 0, 0
        self.grid = []        
        self.drops = []

        self._last_live_read = 0.0
        self._last_live_mtime = 0.0
        self.last_tick = time.perf_counter()
    #цвет
    def color(self, name):
        self.cfg["color"] = name
        self._cur_color = name
        self.colors = get_palette(name, "matrix")
        n = len(self.colors)
        self.head_color = _lighten(self.colors[-1], 0.55)
        self.trail_color = self.colors[min(n - 1, max(0, n - 3))]
        self.tail_color = self.colors[min(n - 1, max(0, n // 3))]

    #геометрия
    def resize(self, cols, rows):
        cols, rows = max(4, int(cols)), max(2, int(rows))
        if (cols, rows) == (self.cols, self.rows):
            return
        old = self.grid
        grid = []
        for c in range(cols):
            if c < len(old):
                col = old[c][:rows]
                col += [random.choice(POOL) for _ in range(rows - len(col))]
            else:
                col = [random.choice(POOL) for _ in range(rows)]
            grid.append(col)
        self.grid = grid
        if self.rows and rows != self.rows:
            ratio = rows / float(self.rows)
            for d in self.drops:
                d.pos *= ratio
                d.length = max(3, min(MAX_LEN, rows,
                                      int(round(d.length * ratio))))
        self.cols, self.rows = cols, rows

        self._sync_drops(initial=not self.drops)
        self.last_tick = time.perf_counter() 

    def _new_length(self):
        scale = (self.rows / REFERENCE_ROWS) if REFERENCE_ROWS else 1.0
        hi = max(3, min(MAX_LEN, int(round(MAX_LEN * scale)), self.rows))
        lo = max(3, min(hi, 5))
        return random.randint(lo, hi)

    def _respawn(self, d, initial=False):
        d.length = self._new_length()
        d.speed = BASE_SPEED * random.uniform(0.55, 1.45)
        if initial:
            d.pos = random.uniform(-self.rows * 0.5, self.rows)
        else:
            d.pos = -random.uniform(0, self.rows * 0.6)

    def _sync_drops(self, initial=False):
        target = max(1, int(round(self.cols * self.cfg["density"])))
        self.drops = [d for d in self.drops if d.col < self.cols]
        if len(self.drops) > target:          
            random.shuffle(self.drops)
            del self.drops[target:]
        if len(self.drops) < target:
            counts = [0] * self.cols
            for d in self.drops:
                counts[d.col] += 1
            while len(self.drops) < target:
                m = min(counts)
                col = random.choice([i for i, n in enumerate(counts) if n == m])
                counts[col] += 1
                d = Drop(col)
                self._respawn(d, initial=initial)
                self.drops.append(d)

    #config
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
            c = read_live_config().get("cmatrix", {})
            if not c:
                return
            name = c.get("color", self.cfg["color"])
            if name != self._cur_color:
                self.color(name)

            self.cfg["speed"] = max(0.05, float(c.get("speed", self.cfg["speed"])))
            self.cfg["interval_ms"] = int(c.get("interval_ms", self.cfg["interval_ms"]))
            density = max(0.05, float(c.get("density", self.cfg["density"])))
            if abs(density - self.cfg["density"]) > 1e-4:
                self.cfg["density"] = density
                if self.cols:
                    self._sync_drops()
        except Exception as e:
            print(f"[cmatrix] live config: {e}", file=sys.stderr)

    #симуляция
    def tick(self):
        self._poll_live_config()
        if not self.cols:
            return
        now = time.perf_counter()
        dt = min(max(now - self.last_tick, 0.0), MAX_DT)
        self.last_tick = now
        rows, grid = self.rows, self.grid
        spd = self.cfg["speed"]
        height_factor = (rows / REFERENCE_ROWS) if REFERENCE_ROWS else 1.0
        for d in self.drops:
            old_head = int(d.pos)
            d.pos += d.speed * spd * dt * height_factor
            new_head = int(d.pos)
            if new_head != old_head:
                col = grid[d.col]
                for y in range(max(old_head + 1, 0), min(new_head, rows - 1) + 1):
                    col[y] = random.choice(POOL)

            if d.pos - d.length > rows:        
                self._respawn(d)
        for _ in range(max(1, self.cols * rows // 500)):
            grid[random.randrange(self.cols)][random.randrange(rows)] = random.choice(POOL)

    #отрисовка
    def draw(self, s):
        pal = self.colors
        if not pal or not self.cols:
            return
        rows = min(self.rows, s.rows)
        cols = min(self.cols, s.cols)
        head_c = self.head_color
        trail_c = self.trail_color
        tail_c = self.tail_color
        for d in self.drops:
            if d.col >= cols:
                continue
            col = self.grid[d.col]
            head = int(d.pos)
            L = d.length
            for i in range(L):
                y = head - i
                if y < 0:
                    break
                if y >= rows:
                    continue
                if i == 0:
                    color = head_c
                elif i < 3:
                    color = trail_c
                else:
                    color = tail_c
                s.text(d.col, y, col[y], color)
    def close(self):
        pass

def extra(ap):
    ap.add_argument("--speed", type=float, default=None)
    ap.add_argument("--density", type=float, default=None)

def main():
    run("cmatrix", lambda a: Matrix(a), 30, extra)

if __name__ == "__main__":
    main()