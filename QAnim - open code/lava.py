"""
lava - лава-лампа, метаболы (QULW LavaVisual).
CLI:  lava [цвет] [--fps N] [--speed X] [--blobs N] [--heat X]
GUI:  настройки читаются из live_config.json.
"""

# QAnim
# Copyright (c) 2026 [ZigRain-hub]
# Licensed under the MIT License. See LICENSE file for details.
import math, random, time, sys
import numpy as np
from qvis import (
    run, get_palette, COLOR_SCHEMES,
    read_live_config, LIVE_CONFIG_PATH,
)


class Blob:
    def __init__(self, W, H):
        self.x = random.uniform(6, W - 6)
        self.y = random.uniform(H * 0.2, H * 0.8)
        self.vx = random.uniform(-0.02, 0.02)
        self.vy = 0.0
        self.r = random.uniform(4.0, 6.5)
        self.phase = random.uniform(0, 2 * math.pi)
        self.freq = random.uniform(0.06, 0.14)
        self.heat = random.uniform(0.3, 0.7)
        # индивидуальность движения
        self.personality = random.uniform(0.7, 1.3)   # отклик на тягу
        self.wander_phase = random.uniform(0, 2 * math.pi)
        self.wander_freq = random.uniform(0.03, 0.09)
        # для деления
        self.age = 0.0                                # сколько секунд живёт
        self.cool = random.uniform(3.0, 8.0)          # порог до деления
        self.gen = 0                                

class Lava:
    schemes = list(COLOR_SCHEMES)
    H = 32

    def __init__(self, args=None):
        self.cfg = {
            "color": "fire",
            "interval_ms": 33,
            "speed": 1.0,
            "blobs": 6,
            "heat": 1.0,
        }
        if args is not None:
            if getattr(args, "color", None):
                self.cfg["color"] = args.color
            if getattr(args, "fps", None):
                self.cfg["interval_ms"] = max(1, int(1000 / max(1, args.fps)))
            if getattr(args, "speed", None) is not None:
                self.cfg["speed"] = float(args.speed)
            if getattr(args, "blobs", None) is not None:
                self.cfg["blobs"] = int(args.blobs)
            if getattr(args, "heat", None) is not None:
                self.cfg["heat"] = float(args.heat)

        self.W, self.t, self.blobs = 32.0, 0.0, []
        self._cur_color = self.cfg["color"]
        self.color(self.cfg["color"])
        self._last_live_read = 0.0
        self._last_live_mtime = 0.0
        self.resize(80, 24)
        self.max_blobs = 40  

    def color(self, name):
        p = get_palette(name, "fire")
        self.solid = p[int(len(p) * 0.7)]
        self._cur_color = name
        self.cfg["color"] = name

    def resize(self, cols, rows):
        pw, ph = cols, rows * 2
        self.W = self.H * pw / ph
        self.X = ((np.arange(pw) + 0.5) / pw * self.W)[None, :]
        self.Y = ((np.arange(ph) + 0.5) / ph * self.H)[:, None]
        want = max(1, int(self.cfg["blobs"]))
        self.blobs = self.blobs[:want]
        while len(self.blobs) < want:
            self.blobs.append(Blob(self.W, self.H))
        for b in self.blobs:
            b.x = min(b.x, self.W - 1)

    def _apply_blobs_count(self, n):
        n = max(1, min(30, int(n)))
        if n == len(self.blobs):
            return
        if n < len(self.blobs):
            self.blobs = self.blobs[:n]
        else:
            while len(self.blobs) < n:
                self.blobs.append(Blob(self.W, self.H))

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
            c = live.get("lava", {})
            if not c:
                return
            new_color = c.get("color", self.cfg["color"])
            if new_color != self._cur_color:
                self.color(new_color)
            new_blobs = int(c.get("blobs", self.cfg["blobs"]))
            if new_blobs != self.cfg["blobs"]:
                self.cfg["blobs"] = new_blobs
                self._apply_blobs_count(new_blobs)
            self.cfg["speed"] = float(c.get("speed", self.cfg["speed"]))
            self.cfg["heat"] = float(c.get("heat", self.cfg["heat"]))
            self.cfg["interval_ms"] = int(c.get("interval_ms", self.cfg["interval_ms"]))
        except Exception as e:
            print(f"[lava] live config: {e}", file=sys.stderr)

    def tick(self):
        self._poll_live_config()
        ms = max(1, int(self.cfg.get("interval_ms", 33)))
        dt = ms / 1000.0
        k = dt / 0.0166                           #к 60 FPS
        speed = float(self.cfg["speed"])
        heat_mult = float(self.cfg["heat"])
        self.t += 0.03 * k * speed
        H, W = self.H, self.W
        t = self.t

        #движение
        for b in self.blobs:
            # тепло: у верха остывает, у низа греется
            if b.y < H * 0.5:
                b.heat -= 0.006 * k * heat_mult
            else:
                b.heat += 0.006 * k * heat_mult
            b.heat = max(0.0, min(1.0, b.heat))
            b.vy += -(b.heat - 0.5) * 0.09 * b.personality * k

            # рандомизация
            wx = math.sin(t * b.wander_freq * 6.0 + b.wander_phase) * 0.010
            wy = math.cos(t * b.wander_freq * 7.0 + b.wander_phase) * 0.010
            wx += random.uniform(-0.006, 0.006)
            wy += random.uniform(-0.006, 0.006)

            b.vx += (wx + random.uniform(-0.006, 0.006)) * k * speed
            b.vy += (wy + random.uniform(-0.006, 0.006)) * k * speed
            b.vy *= 0.965
            b.vx *= 0.97
        #интеграция + стенки
        for b in self.blobs:
            b.x += b.vx * k * speed
            b.y += b.vy * k * speed
            r = b.r + 1.2 * math.sin(t * b.freq + b.phase)
            if b.x < r:
                b.x, b.vx = r, abs(b.vx) * 0.4
            elif b.x > W - r:
                b.x, b.vx = W - r, -abs(b.vx) * 0.4
            if b.y < r:
                b.y, b.vy = r, abs(b.vy) * 0.3
            elif b.y > H - r:
                b.y, b.vy = H - r, -abs(b.vy) * 0.3

        # деление
        new_blobs = []
        for b in self.blobs:
            b.age += dt * speed

            if b.age >= b.cool and b.r > 3.0 and \
               len(self.blobs) + len(new_blobs) < self.max_blobs and b.gen < 3:
                # откалываем кусок
                ang = random.uniform(0, 2 * math.pi)
                off = b.r * 0.6
                child = Blob(W, H)
                child.x = max(2, min(W - 2, b.x + math.cos(ang) * off))
                child.y = max(2, min(H - 2, b.y + math.sin(ang) * off))
                child.vx = b.vx + math.cos(ang) * 0.05
                child.vy = b.vy + math.sin(ang) * 0.05
                child.r = max(2.5, b.r * random.uniform(0.55, 0.75))
                child.heat = b.heat
                child.phase = random.uniform(0, 2 * math.pi)
                child.freq = random.uniform(0.06, 0.14)
                child.personality = random.uniform(0.7, 1.3)
                child.wander_phase = random.uniform(0, 2 * math.pi)
                child.wander_freq = random.uniform(0.03, 0.09)
                child.age = 0.0
                child.cool = random.uniform(4.0, 9.0)
                child.gen = b.gen + 1
                b.r = max(3.0, b.r * 0.85)
                b.age = 0.0
                b.cool = random.uniform(4.0, 9.0)
                new_blobs.append(child)
        if new_blobs:
            self.blobs.extend(new_blobs)

    def draw(self, s):
        if not self.blobs:
            return
        val = 0.0
        for b in self.blobs:
            br = b.r + 1.2 * math.sin(self.t * b.freq + b.phase)
            val = val + (br * br) / (
                (self.X - b.x) ** 2 + (self.Y - b.y) ** 2 + br * br * 0.6
            )
        c = self.solid
        s.set_pix([c if m else None for m in (val > 0.75).ravel().tolist()])
    def close(self):
        pass

def extra(ap):
    ap.add_argument("--speed", type=float, default=None)
    ap.add_argument("--blobs", type=int, default=None)
    ap.add_argument("--heat", type=float, default=None)

def main():
    run("lava", lambda a: Lava(a), 60, extra)

if __name__ == "__main__":
    main()