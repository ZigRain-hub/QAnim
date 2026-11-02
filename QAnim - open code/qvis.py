# QAnim
# Copyright (c) 2026 [ZigRain-hub]
# Licensed under the MIT License. See LICENSE file for details.

#qvis общее ядро консольных визуалов QULW
import sys, time, shutil, colorsys, argparse, threading, json
from pathlib import Path
import os

def _base_dir():
    """Папка exe в frozen-режиме, иначе папка исходника.
    live_config.json и cterm_size.txt должны лежать рядом с exe, а не в Temp."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent
try:
    import msvcrt
    import ctypes
    from ctypes import wintypes
except ImportError:
    msvcrt = None

if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).parent
else:
    APP_DIR = Path(__file__).parent.resolve()

# общая папка настроек для .py и .exe - %LOCALAPPDATA%\QAnim.
CONFIG_DIR = Path(os.environ.get("LOCALAPPDATA", str(APP_DIR))) / "QAnim"

LIVE_CONFIG_PATH = CONFIG_DIR / "live_config.json"



def _pal_hue(hue, sat=0.9, n=16, dark=0.04):
    out = []
    for i in range(n):
        t = i / (n - 1)
        v = dark + t * (1.0 - dark)
        s = max(0.0, min(1.0, sat * (1 - t * 0.3)))
        r, g, b = colorsys.hsv_to_rgb(hue % 1.0, s, v)
        out.append((int(r * 255), int(g * 255), int(b * 255)))
    return out


def _make_fire():
    stops = [(0.00, (0, 0, 0)), (0.10, (30, 0, 0)), (0.25, (90, 15, 0)),
             (0.45, (180, 50, 0)), (0.62, (240, 110, 15)), (0.78, (255, 180, 50)),
             (0.90, (255, 230, 130)), (1.00, (255, 255, 235))]
    out = []
    for i in range(16):
        t = i / 15.0
        for j in range(len(stops) - 1):
            t0, c0 = stops[j]
            t1, c1 = stops[j + 1]
            if t0 <= t <= t1:
                k = (t - t0) / max(t1 - t0, 1e-6)
                out.append(tuple(int(c0[m] + (c1[m] - c0[m]) * k) for m in range(3)))
                break
        else:
            out.append(stops[-1][1])
    return out


COLOR_SCHEMES = {
    "white": _pal_hue(0.0, 0.0), "blue": _pal_hue(0.60, 0.9), "cyan": _pal_hue(0.50, 0.85),
    "mint": _pal_hue(0.42, 0.7), "green": _pal_hue(0.33, 0.9), "matrix": _pal_hue(0.33, 1.0),
    "gold": _pal_hue(0.13, 0.95), "orange": _pal_hue(0.08, 0.95), "fire": _make_fire(),
    "red": _pal_hue(0.0, 0.9), "sunset": _pal_hue(0.03, 0.9), "pink": _pal_hue(0.92, 0.75),
    "purple": _pal_hue(0.75, 0.85), "neon": _pal_hue(0.83, 1.0), "ice": _pal_hue(0.55, 0.5),
}


def get_palette(name, fallback="blue"):
    return COLOR_SCHEMES.get(name) or COLOR_SCHEMES[fallback]

def _sgr(fg, bg):
    s = "\x1b[0m"
    if fg:
        s += "\x1b[38;2;%d;%d;%dm" % fg
    if bg:
        s += "\x1b[48;2;%d;%d;%dm" % bg
    return s

_last_good_size = None


def _term_size(use_file=False):
    global _last_good_size
    if use_file:
        try:
            size_file = _base_dir() / "cterm_size.txt"
            if size_file.exists():
                parts = size_file.read_text().split()
                if len(parts) == 2:
                    c, r = int(parts[0]), int(parts[1])
                    if c > 0 and r > 0:
                        _last_good_size = (c, r)
                        return c, r
                if _last_good_size:
                    return _last_good_size
        except Exception:
            if _last_good_size:
                return _last_good_size
    # обычный режим реальный размер окна cmd
    try:
        sz = shutil.get_terminal_size()
        return sz.columns, sz.lines
    except Exception:
        pass
    return 80, 24


class Screen:
    def __init__(self, cols, rows):
        self.cols, self.rows = cols, rows
        self.pw, self.ph = cols, rows * 2
        self.prev_lines = [""] * rows
        self.clear()
    def clear(self):
        self.ch = [None] * (self.cols * self.rows)
        self.fg = [None] * (self.cols * self.rows)
        self.pix = [None] * (self.pw * self.ph)

    def text(self, x, y, s, fg):
        if 0 <= y < self.rows:
            for i, c in enumerate(s):
                xx = x + i
                if 0 <= xx < self.cols:
                    k = y * self.cols + xx
                    self.ch[k] = c
                    self.fg[k] = fg

    def px(self, x, y, color):
        if 0 <= x < self.pw and 0 <= y < self.ph:
            self.pix[y * self.pw + x] = color

    def set_pix(self, flat):
        self.pix = flat

    def render(self):
        out, pix, pw, cols = [], self.pix, self.pw, self.cols
        for r in range(self.rows):
            line, last = [], None
            for c in range(cols):
                k = r * cols + c
                g = self.ch[k]
                if g is not None:
                    st = (self.fg[k], None)
                else:
                    top, bot = pix[2 * r * pw + c], pix[(2 * r + 1) * pw + c]
                    if top is None and bot is None:
                        st, g = (None, None), " "
                    elif bot is None:
                        st, g = (top, None), "▀"
                    elif top is None:
                        st, g = (bot, None), "▄"
                    elif top == bot:
                        st, g = (top, None), "█"
                    else:
                        st, g = (top, bot), "▀"
                if st != last:
                    line.append(_sgr(*st))
                    last = st
                line.append(g)
            while len(line) > 0 and line[-1] == " ":
                line.pop()
            out.append("".join(line) + "\x1b[K\x1b[0m")
        result = ""
        for i in range(len(out)):
            if i >= len(self.prev_lines) or out[i] != self.prev_lines[i]:
                result += f"\x1b[{i+1};1H{out[i]}"
                if i < len(self.prev_lines):
                    self.prev_lines[i] = out[i]
                else:
                    self.prev_lines.append(out[i])
        return result


def _enable_ansi():
    try:
        k = ctypes.windll.kernel32
        h = k.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        k.GetConsoleMode(h, ctypes.byref(mode))
        k.SetConsoleMode(h, mode.value | 0x0004)
    except Exception:
        pass


LIVE_CONFIG_PATH = _base_dir() / "live_config.json"

def write_live_config(data):
    try:
        LIVE_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        LIVE_CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print("[qvis] write_live_config:", e)

def read_live_config():
    try:
        if LIVE_CONFIG_PATH.exists():
            return json.loads(LIVE_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}

def run(name, make, default_fps=30, extra_args=None):
    ap = argparse.ArgumentParser(prog=name)
    ap.add_argument("--app-mode", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("color", nargs="?", help="цветовая схема")
    ap.add_argument("--fps", type=int, default=default_fps)
    ap.add_argument("--list", action="store_true")
    if extra_args:
        extra_args(ap)
    args = ap.parse_args()
    use_app_mode = getattr(args, "app_mode", False)
    cols, rows = _term_size(use_file=use_app_mode)
    vis = make(args)
    schemes = list(vis.schemes)
    if args.list:
        print(", ".join(schemes))
        vis.close()
        return
    i = 0
    if args.color:
        if args.color not in schemes:
            print("Нет такой схемы. Доступно:", ", ".join(schemes))
            vis.close()
            return
        i = schemes.index(args.color)
        vis.color(args.color)
    _enable_ansi()
    out = sys.stdout
    out.write("\x1b[2J\x1b[?25l\x1b[H")

    size, scr = None, None
    cand, stable = None, 0
    dt = 1.0 / max(1, args.fps)
    nxt = time.time()
    try:
        while True:
            while msvcrt.kbhit():
                k = msvcrt.getwch()
                if k in ("\x00", "\xe0"):
                    msvcrt.getwch()
                    continue
                if k in "qQ\x1b":
                    return
                if k in "cC":
                    i = (i + 1) % len(schemes)
                    vis.color(schemes[i])

            cols, rows = _term_size()
            rows = max(1, rows - 1)
            new = (cols, rows)
            if new != size:
                if scr is not None:
                    scr.prev_lines = [""] * scr.rows
                if new == cand:
                    stable += 1
                else:
                    cand, stable = new, 1
                if size is None or stable >= 2:
                    size, cand, stable = new, None, 0
                    scr = Screen(cols, rows)
                    vis.resize(cols, rows)
                    out.write("\x1b[2J")
            else:
                cand, stable = None, 0

            vis.tick()
            scr.clear()
            vis.draw(scr)

            out.write(scr.render())
            out.flush()

            nxt += dt
            d = nxt - time.time()
            if d > 0:
                time.sleep(d)
            else:
                nxt = time.time()
    except KeyboardInterrupt:
        pass
    finally:
        out.write("\x1b[0m\x1b[?25h\x1b[2J\x1b[H")
        out.flush()
        vis.close()