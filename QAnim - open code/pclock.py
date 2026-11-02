"""
pclock - пиксельные часы (QULW PixelClock).
CLI:  pclock [цвет] [--fps N] [--tz Europe/Moscow] [--fmt HH:MM:SS.mmm]
              [--date 1] [--offset 0]
GUI:  настройки читаются из live_config.json.
"""

# QAnim
# Copyright (c) 2026 [ZigRain-hub]
# Licensed under the MIT License. See LICENSE file for details.

import time, sys, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from qvis import run, read_live_config, LIVE_CONFIG_PATH

DIGITS = {
    '0': ["111", "101", "101", "101", "111"], '1': ["001", "001", "001", "001", "001"],
    '2': ["111", "001", "111", "100", "111"], '3': ["111", "001", "111", "001", "111"],
    '4': ["101", "101", "111", "001", "001"], '5': ["111", "100", "111", "001", "111"],
    '6': ["111", "100", "111", "101", "111"], '7': ["111", "001", "001", "001", "001"],
    '8': ["111", "101", "111", "101", "111"], '9': ["111", "101", "111", "001", "001"],
    '.': ["0",   "0",   "0",   "0",   "1"],
    ':': ["0",   "1",   "0",   "1",   "0"],
    '-': ["000", "000", "111", "000", "000"],
    '+': ["010", "111", "010", "000", "000"],
}

SCHEMES = {
    "snow":   ((230, 230, 230), (120, 120, 120)),
    "fire":   ((255, 100, 50),  (200, 80, 40)),
    "purple": ((180, 100, 255), (140, 80, 200)),
    "green":  ((100, 255, 150), (80, 200, 120)),
    "blue":   ((100, 180, 255), (80, 140, 200)),
    "white":  ((255, 255, 255), (200, 200, 200)),
    "red":    ((255, 80, 80),   (200, 50, 50)),
    "gold":   ((255, 210, 80),  (200, 160, 50)),
    "cyan":   ((80, 230, 230),  (50, 180, 180)),
    "matrix": ((60, 220, 100),  (40, 170, 70)),
}


def _tz(name):
    try:
        return ZoneInfo(name) if name else None
    except (ZoneInfoNotFoundError, ValueError):
        return None


class Clock:
    schemes = list(SCHEMES)
    def __init__(self, args=None):
        self.cfg = {
            "color": "snow",
            "interval_ms": 200,
            "tz": "Europe/Moscow",
            "fmt": "HH:MM:SS",
            "date": "1",
            "date_fmt": "%a %b %d",
            "offset": 0,
        }
        if args is not None:
            if getattr(args, "color", None):
                self.cfg["color"] = args.color
            if getattr(args, "fps", None):
                self.cfg["interval_ms"] = max(1, int(1000 / max(1, args.fps)))
            if getattr(args, "tz", None):
                self.cfg["tz"] = args.tz
            if getattr(args, "fmt", None):
                self.cfg["fmt"] = args.fmt
            if getattr(args, "date", None) is not None:
                self.cfg["date"] = str(args.date)
            if getattr(args, "offset", None) is not None:
                self.cfg["offset"] = int(args.offset)
        self.active, self.date_c = SCHEMES["snow"]
        self.color(self.cfg["color"])
        self.time_s = self.date_s = ""
        self._last_live_read = 0.0
        self._last_live_mtime = 0.0

    def color(self, name):
        self.cfg["color"] = name
        self.active, self.date_c = SCHEMES.get(name, SCHEMES["snow"])

    def resize(self, cols, rows):
        pass

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
            c = live.get("pclock", {})
            if not c:
                return

            if c.get("color") and c["color"] != self.cfg["color"]:
                self.color(c["color"])
            self.cfg["interval_ms"] = int(c.get("interval_ms", self.cfg["interval_ms"]))
            self.cfg["tz"] = c.get("tz", self.cfg["tz"])
            self.cfg["fmt"] = c.get("fmt", self.cfg["fmt"])
            self.cfg["date"] = str(c.get("date", self.cfg["date"]))
            self.cfg["date_fmt"] = c.get("date_fmt", self.cfg["date_fmt"])
            self.cfg["offset"] = int(c.get("offset", self.cfg["offset"]))
        except Exception as e:
            print(f"[pclock] live config: {e}", file=sys.stderr)

    def _fmt(self):
        # переводим наш формат HH:MM:SS.mmm в strftime
        f = self.cfg["fmt"]
        f = f.replace("HH", "%H").replace("hh", "%I").replace("MM", "%M")
        f = f.replace("SS", "%S").replace("mmm", "%f")
        return f

    def tick(self):
        self._poll_live_config()
        tz = _tz(self.cfg["tz"])
        now = datetime.datetime.now(tz) if tz else datetime.datetime.now()
        if self.cfg["offset"]:
            now = now + datetime.timedelta(seconds=self.cfg["offset"])
        self.time_s = now.strftime(self._fmt())
        # обрезаем микросекунды
        if "mmm" in self.cfg["fmt"].lower() or "%f" in self._fmt():
            self.time_s = now.strftime(self._fmt())[:3 + len(
                now.strftime(self._fmt()).replace("%f", ""))] if False else \
                now.strftime(self._fmt()).replace(
                    f"{now.microsecond:06d}", f"{now.microsecond // 1000:03d}")

        self.date_s = now.strftime(self.cfg["date_fmt"])

    def draw(self, s):
        u = max(1, min(s.pw // max(1, len(self.time_s)) // 4,
                       s.ph // 8, 6))
        glyphs = []
        for ch in self.time_s:
            if ch.isdigit():
                glyphs.append(DIGITS.get(ch))
            elif ch in DIGITS:
                glyphs.append(DIGITS[ch])
            else:
                glyphs.append(None)
        cw = 3 * u
        gap = u
        total_w = len(glyphs) * (cw + gap)
        x0 = max(0, (s.pw - total_w) // 2)
        y0 = max(0, (s.ph - 5 * u - 3 * gap) // 2)
        for i, g in enumerate(glyphs):
            x = x0 + i * (cw + gap)
            if g is None:
                continue
            for r, row in enumerate(g):
                for k, bit in enumerate(row):
                    if bit == '1':
                        for dy in range(u):
                            for dx in range(u):
                                s.px(x + k * u + dx, y0 + r * u + dy, self.active)
        if str(self.cfg.get("date", "1")) not in ("0", "False", "false", ""):
            row = min(s.rows - 1, (y0 + 5 * u) // 2 + 2)
            s.text(max(0, (s.cols - len(self.date_s)) // 2), row,
                   self.date_s, self.date_c)

    def close(self):
        pass

def extra(ap):
    ap.add_argument("--tz", default=None, help="например Europe/Moscow")
    ap.add_argument("--fmt", default=None, help="HH:MM:SS.mmm")
    ap.add_argument("--date", default=None, help="1/0 - показывать дату")
    ap.add_argument("--offset", type=int, default=None, help="сек. смещение")

def main():
    run("pclock", lambda a: Clock(a), 5, extra)

if __name__ == "__main__":
    main()