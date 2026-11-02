"""
pipes - трубы (QULW PipesVisual). Тонкие линии, честная смерть при столкновении.
CLI:  pipes [цвет] [--fps N] [--speed X] [--count N] [--length N]
GUI:  настройки читаются из live_config.json.
"""

# QAnim
# Copyright (c) 2026 [ZigRain-hub]
# Licensed under the MIT License. See LICENSE file for details.

import random, time, sys
from qvis import (
    run, get_palette, COLOR_SCHEMES,
    read_live_config, LIVE_CONFIG_PATH,
)

DX, DY = [1, 0, -1, 0], [0, 1, 0, -1]


class Pipe:
    def __init__(self, x, y, d, max_segs):
        self.segs = [(x, y)]
        self.alive = True
        self.max = max_segs
        self.dir = d
        self.hx, self.hy = x, y


class Pipes:
    schemes = list(COLOR_SCHEMES)
    def __init__(self, args=None):
        self.cfg = {
            "color": "mint",
            "interval_ms": 33,
            "speed": 1.0,
            "count": 3,
            "length": 40,
        }
        if args is not None:
            if getattr(args, "color", None):
                self.cfg["color"] = args.color
            if getattr(args, "fps", None):
                self.cfg["interval_ms"] = max(1, int(1000 / max(1, args.fps)))
            if getattr(args, "speed", None) is not None:
                self.cfg["speed"] = float(args.speed)
            if getattr(args, "count", None) is not None:
                self.cfg["count"] = int(args.count)
            if getattr(args, "length", None) is not None:
                self.cfg["length"] = int(args.length)

        #Сетка в полублоках: W колонок, H = rows*2
        self.W, self.H = 80, 40
        self.pipes = []
        self.grid = set()
        self._cur_color = self.cfg["color"]
        self.color(self.cfg["color"])
        self._last_live_read = 0.0
        self._last_live_mtime = 0.0
        self._ms_accum = 0.0
        self.resize(80, 24)

    def color(self, name):
        p = get_palette(name, "mint")
        self.body = p[len(p) // 2]
        self.head = p[-1]
        self._cur_color = name
        self.cfg["color"] = name

    def resize(self, cols, rows):
        #Считаем
        newW = max(6, cols)
        newH = max(6, rows * 2)
        if newW == self.W and newH == self.H:
            return
        self.W, self.H = newW, newH
        alive = []
        for p in self.pipes:
            p.segs = [(x, y) for (x, y) in p.segs
                      if 0 <= x < self.W and 0 <= y < self.H]
            if p.segs:
                p.hx, p.hy = p.segs[-1]
                alive.append(p)
        self.pipes = alive
        self._rebuild_grid()
        self._fill()

    def _rebuild_grid(self):
        self.grid = set()
        for p in self.pipes:
            self.grid.update(p.segs)

    def _spawn(self, avoid=None):
        if self.W < 6 or self.H < 6:
            return
        for _ in range(80):
            x = random.randint(2, self.W - 3)
            y = random.randint(2, self.H - 3)
            if (x, y) in self.grid:
                continue
            too_close = False
            for p in self.pipes:
                if abs(p.hx - x) + abs(p.hy - y) < 5:
                    too_close = True
                    break
            if too_close:
                continue
            self.pipes.append(Pipe(x, y, random.randint(0, 3),
                                   max(5, self.cfg["length"])))
            self.grid.add((x, y))
            return

    def _fill(self):
        target = max(1, int(self.cfg["count"]))
        for _ in range(30):
            if len(self.pipes) >= target:
                break
            self._spawn()

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
            c = live.get("pipes", {})
            if not c:
                return
            new_color = c.get("color", self.cfg["color"])
            if new_color != self._cur_color:
                self.color(new_color)
            self.cfg["speed"] = float(c.get("speed", self.cfg["speed"]))
            self.cfg["length"] = int(c.get("length", self.cfg["length"]))
            self.cfg["count"] = int(c.get("count", self.cfg["count"]))
            self.cfg["interval_ms"] = int(c.get("interval_ms", self.cfg["interval_ms"]))
            for p in self.pipes:
                p.max = max(5, self.cfg["length"])
            self._fill()
        except Exception as e:
            print(f"[pipes] live config: {e}", file=sys.stderr)

    def tick(self):
        self._poll_live_config()
        ms = max(1, int(self.cfg.get("interval_ms", 33)))
        dt = ms / 1000.0
        speed = float(self.cfg["speed"])
        self._ms_accum += speed * dt * 60.0
        steps = int(self._ms_accum)
        self._ms_accum -= steps
        steps = min(steps, 6)
        for _ in range(steps):
            self._step_once()

    def _step_once(self):
        occupied = set()
        for p in self.pipes:
            occupied.update(p.segs)
        planned = {}    
        claimed = set() 

        for p in self.pipes:
            if not p.alive or len(p.segs) >= p.max:
                p.alive = False
                continue
            back = (p.dir + 2) % 4
            options = []
            for d in range(4):
                if d == back:
                    continue
                nx, ny = p.hx + DX[d], p.hy + DY[d]
                if not (0 <= nx < self.W and 0 <= ny < self.H):
                    continue
                if (nx, ny) in occupied or (nx, ny) in claimed:
                    continue
                options.append((d, nx, ny))

            straight = None
            for d, nx, ny in options:
                if d == p.dir:
                    straight = (d, nx, ny)
                    break
            if straight is None and not options:
                p.alive = False
                continue
            choice = None
            if straight and random.random() > 0.3:
                choice = straight
            else:
                choice = random.choice(options) if options else straight
            d, nx, ny = choice
            p.dir = d
            planned[id(p)] = (nx, ny)
            claimed.add((nx, ny))

        #Двигаем тех кто выжил
        survivors = []
        for p in self.pipes:
            if not p.alive:
                continue
            if id(p) in planned:
                nx, ny = planned[id(p)]
                if (nx, ny) in self.grid and (nx, ny) not in p.segs:
                    # столкновение
                    p.alive = False
                    continue
                p.hx, p.hy = nx, ny
                p.segs.append((nx, ny))
                survivors.append(p)
            else:
                p.alive = False
        self.pipes = survivors
        self._rebuild_grid()
        self._fill()

    def draw(self, s):
        for p in self.pipes:
            last = len(p.segs) - 1
            for i, (x, y) in enumerate(p.segs):
                col = self.head if i == last else self.body
                s.px(x, y, col)

    def close(self):
        pass

def extra(ap):
    ap.add_argument("--speed", type=float, default=None)
    ap.add_argument("--count", type=int, default=None)
    ap.add_argument("--length", type=int, default=None)

def main():
    run("pipes", lambda a: Pipes(a), 60, extra)

if __name__ == "__main__":
    main()