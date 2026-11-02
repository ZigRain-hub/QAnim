"""
CAVA для QULW / qvis.
Захват системного звука Windows через WASAPI loopback.
 CLI:
    cava [цвет] [--fps N] [--bars N] [--gain X]
         [--source loopback|mic] [--autosens 0|1]

GUI: настройки читаются из live_config.json.
"""

# QAnim
# Copyright (c) 2026 [ZigRain-hub]
# Licensed under the MIT License. See LICENSE file for details.

import sys
import math
import random
import threading
import time

import numpy as np

from qvis import (
    run,
    get_palette,
    COLOR_SCHEMES,
    read_live_config,
    LIVE_CONFIG_PATH,
)

try:
    import sounddevice as sd
except ImportError:
    sd = None

try:
    import pyaudiowpatch as pyaudio
except ImportError:
    pyaudio = None


BLOCKS = " ▁▂▃▄▅▆▇█"

GAIN_MIN = 0.1
GAIN_MAX = 10.0


class Cava:
    schemes = list(COLOR_SCHEMES)
    def __init__(self, args=None):
        self.cfg = {
            "color": "fire",
            "gain": 1.0,
            "bars": 32,
            "interval_ms": 33,
            "source": "loopback",
            "device": "",
            "autosens": 1,
        }
        if args is not None:
            if getattr(args, "color", None):
                self.cfg["color"] = args.color
            if getattr(args, "source", None):
                self.cfg["source"] = args.source
            if getattr(args, "device", None):
                self.cfg["device"] = args.device
            if getattr(args, "bars", None) is not None:
                b = int(args.bars)
                self.cfg["bars"] = b if b > 0 else 32
            if getattr(args, "gain", None) is not None:
                self.cfg["gain"] = float(args.gain)
            if getattr(args, "autosens", None) is not None:
                self.cfg["autosens"] = int(args.autosens)
            if getattr(args, "fps", None):
                self.cfg["interval_ms"] = max(
                    1, int(1000 / max(1, args.fps))
                )

        self._bars = max(4, min(512, int(self.cfg["bars"] or 32)))
        self._alloc(self._bars)
        self.hann = np.hanning(2048).astype(np.float32)
        self.buf = np.zeros(2048, np.float32)
        self.lock = threading.Lock()
        self.fallback = True
        self.pa = None
        self.stream = None
        self._stop_flag = False
        self._last_live_read = 0.0
        self._last_live_mtime = 0.0
        self._cur_color = None
        # autosens
        self._sens = 1.0
        self._sens_slow = 1.0
        # punch
        self._energy_slow = 0.3
        self._punch = 0.0
        self._punch_t = 0.0
        self._drop = 0.0
        self._drop_t = 0.0
        self._apply_color(self.cfg["color"])
        if self.cfg["source"] == "loopback":
            self._open_loopback()
        else:
            self._open_mic(self.cfg["device"])

    # аудио
    def _open_loopback(self):
        self._close_audio()

        if pyaudio is None:
            print("[cava] Установи PyAudioWPatch для loopback", file=sys.stderr)
            self.fallback = True
            return
        try:
            self.pa = pyaudio.PyAudio()
            wasapi = self.pa.get_host_api_info_by_type(pyaudio.paWASAPI)
            output_index = wasapi["defaultOutputDevice"]
            speaker = self.pa.get_device_info_by_index(output_index)
            if not speaker.get("isLoopbackDevice", False):
                matched = None
                speaker_name = speaker["name"].lower()
                for device in self.pa.get_loopback_device_info_generator():
                    loop_name = device["name"].lower()
                    if speaker_name in loop_name or loop_name in speaker_name:
                        matched = device
                        break
                if matched is None:
                    raise RuntimeError(
                        "Не найден loopback для устройства " + speaker["name"]
                    )
                speaker = matched

            rate = int(speaker["defaultSampleRate"])
            channels = int(speaker["maxInputChannels"])
            if channels < 1:
                raise RuntimeError("Loopback-устройство не имеет входных каналов")

            def callback(in_data, frame_count, time_info, status):
                if self._stop_flag:
                    return (None, pyaudio.paComplete)
                if in_data:
                    samples = np.frombuffer(in_data, dtype=np.float32)
                    usable = (len(samples) // channels) * channels
                    samples = samples[:usable]
                    if samples.size:
                        mono = samples.reshape(-1, channels).mean(axis=1)
                        n = len(mono)
                        with self.lock:
                            if n >= len(self.buf):
                                self.buf[:] = mono[-len(self.buf):]
                            elif n > 0:
                                self.buf[:-n] = self.buf[n:]
                                self.buf[-n:] = mono
                return (None, pyaudio.paContinue)
            
            self.stream = self.pa.open(
                format=pyaudio.paFloat32,
                channels=channels,
                rate=rate,
                input=True,
                input_device_index=speaker["index"],
                frames_per_buffer=512,
                stream_callback=callback,
            )
            self.stream.start_stream()
            self.fallback = False
            print(f"[cava] Системный звук: {speaker['name']}", file=sys.stderr)
        except Exception as e:
            print(f"[cava] Ошибка loopback: {e}", file=sys.stderr)
            self._close_audio()
            self.fallback = True
    def _open_mic(self, device):
        self._close_audio()
        if sd is None:
            print("[cava] sounddevice не установлен", file=sys.stderr)
            self.fallback = True
            return
        dev = None
        if device:
            if str(device).isdigit():
                dev = int(device)
            else:
                for i, d in enumerate(sd.query_devices()):
                    if d["max_input_channels"] > 0 and str(device).lower() in d["name"].lower():
                        dev = i
                        break

        def callback(indata, frames, t, status):
            mono = indata.mean(axis=1)
            n = len(mono)
            with self.lock:
                if n >= len(self.buf):
                    self.buf[:] = mono[-len(self.buf):]
                elif n > 0:
                    self.buf[:-n] = self.buf[n:]
                    self.buf[-n:] = mono
        try:
            self.stream = sd.InputStream(
                samplerate=44100,
                blocksize=512,
                channels=1,
                dtype=np.float32,
                callback=callback,
                device=dev,
            )
            self.stream.start()
            self.fallback = False
        except Exception as e:
            print(f"[cava] Ошибка микрофона: {e}", file=sys.stderr)
            self.fallback = True

    def _close_audio(self):
        if self.stream is not None:
            try:
                if pyaudio is not None and isinstance(self.stream, pyaudio.Stream):
                    if self.stream.is_active():
                        self.stream.stop_stream()
                    self.stream.close()
                else:
                    self.stream.stop()
                    self.stream.close()
            except Exception:
                pass
            self.stream = None
        if self.pa is not None:
            try:
                self.pa.terminate()
            except Exception:
                pass
            self.pa = None

    #буферы 

    def _alloc(self, n):
        n = max(4, min(512, int(n)))
        self._bars = n
        self.smooth = np.zeros(n, np.float32)
        self.target = np.zeros(n, np.float32)
        self.peaks = np.zeros(n, np.float32)
        self.hold = np.zeros(n, np.int8)
        half = n // 2
        self.idx = []
        for i in range(half):
            f_lo = 20 * (2 ** (i / half * 8))
            f_hi = 20 * (2 ** ((i + 1) / half * 8))
            lo = min(int(f_lo / 43.07), 512)
            hi = max(lo + 1, min(int(f_hi / 43.07), 512))
            self.idx.append((lo, hi))

        # eq вес усиливаем бас
        self.eq_weights = np.ones(half, np.float32)
        if half >= 5:
            seg = half // 5
            weights = [1.4, 1.2, 1.0, 1.0, 1.6]
            for s in range(5):
                a = s * seg
                b = min((s + 1) * seg, half)
                self.eq_weights[a:b] = weights[s]

    def _apply_color(self, name):
        palette = get_palette(name, "blue")
        self.bottom = palette[5]
        self.top = palette[-1]
        self.peak_c = palette[-1]
        self._cur_color = name

    def color(self, name):
        self.cfg["color"] = name
        self._apply_color(name)
    def resize(self, cols, rows):
        want = int(self.cfg.get("bars", 0) or 0)
        if want > 0 and want != self._bars:
            self._realloc_interp(want)

    def _realloc_interp(self, n):
        old_smooth = self.smooth.copy()
        old_peaks = self.peaks.copy()
        self._alloc(n)
        if len(old_smooth):
            xp = np.linspace(0, 1, len(old_smooth))
            x = np.linspace(0, 1, n)
            self.smooth = np.interp(x, xp, old_smooth).astype(np.float32)
            self.peaks = np.interp(x, xp, old_peaks).astype(np.float32)

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

            live = read_live_config()
            c = live.get("cava", {})
            if not c:
                return
            new_color = c.get("color", self.cfg["color"])
            if new_color != self._cur_color:
                self._apply_color(new_color)
                self.cfg["color"] = new_color

            new_bars = int(c.get("bars", self.cfg["bars"]) or self.cfg["bars"])
            new_bars = max(4, min(512, new_bars))
            if new_bars != self._bars:
                self._realloc_interp(new_bars)
            self.cfg["bars"] = new_bars
            self.cfg["gain"] = float(c.get("gain", self.cfg["gain"]))
            self.cfg["interval_ms"] = int(c.get("interval_ms", self.cfg["interval_ms"]))
            self.cfg["autosens"] = int(c.get("autosens", self.cfg.get("autosens", 1)))
            new_src = c.get("source", self.cfg["source"])
            new_dev = str(c.get("device", self.cfg["device"]))
            if new_src != self.cfg["source"] or new_dev != self.cfg["device"]:
                self.cfg["source"] = new_src
                self.cfg["device"] = new_dev
                if new_src == "loopback":
                    self._open_loopback()
                else:
                    self._open_mic(new_dev)
        except Exception as e:
            print(f"[cava] Ошибка live config: {e}", file=sys.stderr)

    #спектр
    def _real(self):
        with self.lock:
            frame = self.buf.copy()
        frame -= frame.mean()
        mag = np.abs(np.fft.rfft(frame * self.hann, n=2048))
        half = self._bars // 2
        raw = np.zeros(half, np.float32)
        gain = float(self.cfg.get("gain", 1.0))
        gain = max(GAIN_MIN, min(GAIN_MAX, gain))
        noise_floor = 1e-4

        for i, (lo, hi) in enumerate(self.idx):
            lo = min(lo, len(mag) - 1)
            hi = min(hi, len(mag))
            if hi <= lo:
                continue
            val = float(mag[lo:hi].mean())
            val = max(val, noise_floor)
            db = 20 * math.log10(val + 1e-10)
            v = (db + 60) / 60.0
            raw[i] = v * gain    # без clip - можно > 1.0 но тут по желанию
        raw *= self.eq_weights

        # autosens
        if self.cfg.get("autosens", 1):
            avg = float(raw.mean())
            fps = 1000.0 / max(1, self.cfg.get("interval_ms", 33))
            alpha = 0.25 / max(1.0, fps)
            if self._sens_slow <= 0:
                self._sens_slow = avg if avg > 0 else 0.1
            self._sens_slow = self._sens_slow * (1.0 - alpha) + avg * alpha
            target_sens = 0.5 / max(1e-6, self._sens_slow)
            self._sens = self._sens * 0.95 + target_sens * 0.05
            self._sens = max(0.25, min(4.0, self._sens))

            raw *= self._sens
        # punch / drop
        energy = float(raw.mean())
        alpha_e = 0.03
        if self._energy_slow <= 0:
            self._energy_slow = max(0.1, energy)
        self._energy_slow = self._energy_slow * (1.0 - alpha_e) + energy * alpha_e
        dt = max(0.001, self.cfg.get("interval_ms", 33) / 1000.0)
        ratio = energy / max(1e-6, self._energy_slow)
        if self._punch_t <= 0 and self._drop_t <= 0:
            if ratio > 1.7:
                self._punch = min(1.0, (ratio - 1.7) * 1.2)
                self._punch_t = 0.7
            elif ratio < 0.35:
                self._drop = min(1.0, (0.35 - ratio) * 2.5)
                self._drop_t = 0.5
        if self._punch_t > 0:
            self._punch_t -= dt
            if self._punch_t <= 0:
                self._punch = 0.0
        if self._drop_t > 0:
            self._drop_t -= dt
            if self._drop_t <= 0:
                self._drop = 0.0
        if self._punch > 0:
            raw = raw * (1.0 + self._punch * 0.8)
        if self._drop > 0:
            raw = raw * (1.0 - self._drop * 0.9)
        raw = np.clip(raw, 0.0, 2.5)
        if self._bars % 2 == 0:
            self.target[:half] = raw[::-1]
            self.target[half:] = raw
        else:
            self.target[:half] = raw[::-1]
            self.target[half] = raw[-1]
            self.target[half + 1:] = raw

    def _fake(self):
        half = self._bars // 2
        v = np.clip(np.random.uniform(0.05, 0.35, half), 0.0, 1.0)

        if random.random() < 0.15 and half > 1:
            sp = random.randint(0, half - 1)
            v[sp] = random.uniform(0.7, 1.0)
            if sp > 0:
                v[sp - 1] = max(v[sp - 1], random.uniform(0.5, 0.8))
            if sp < half - 1:
                v[sp + 1] = max(v[sp + 1], random.uniform(0.5, 0.8))

        if self._bars % 2 == 0:
            self.target[:half] = v[::-1]
            self.target[half:] = v
        else:
            self.target[:half] = v[::-1]
            self.target[half] = v[-1]
            self.target[half + 1:] = v
    def tick(self):
        self._poll_live_config()

        if self.fallback:
            self._fake()
        else:
            self._real()
        rising = self.target > self.smooth
        attack = 0.55
        release = 0.08
        speed = np.where(rising, attack, release).astype(np.float32)
        self.smooth += (self.target - self.smooth) * speed
        higher = self.smooth > self.peaks
        self.peaks[higher] = self.smooth[higher]
        self.hold[higher] = 3
        self.hold[~higher] -= 1
        decay = self.hold <= 0
        self.peaks[decay] = np.maximum(self.smooth[decay], self.peaks[decay] * 0.9)
        self.hold[decay] = 0

    # - отрисовка

    def draw(self, s):
        rows, cols = s.rows, s.cols
        total = self._bars
        if total <= 0 or cols <= 0 or rows <= 0:
            return
        N = min(total, cols)
        if N < total:
            edges = np.linspace(0, total, N + 1)
            vals = np.empty(N, np.float32)
            pks = np.empty(N, np.float32)
            for j in range(N):
                lo = int(edges[j])
                hi = max(lo + 1, int(edges[j + 1]))
                vals[j] = self.smooth[lo:hi].max()
                pks[j] = self.peaks[lo:hi].max()
        else:
            vals, pks = self.smooth, self.peaks
        gap = 1 if cols >= N * 3 - 1 else 0
        usable = cols - gap * (N - 1)
        base = max(1, usable // N)
        rem = max(0, usable - base * N)

        widths = [base] * N
        if rem > 0:
            center = (N - 1) // 2
            order = [center]
            step = 1
            while len(order) < rem and step <= N:
                for d in (center + step, center - step):
                    if 0 <= d < N and len(order) < rem:
                        order.append(d)
                step += 1
            for idx in order[:rem]:
                widths[idx] += 1

        max_units = rows * 8
        x = 0
        for i in range(N):
            bw = widths[i]
            u = int(vals[i] * max_units)
            u = max(0, min(u, max_units))
            full, part = divmod(u, 8)

            for r in range(full + (1 if part else 0)):
                y = rows - 1 - r
                col = self.top if r * 8 >= u // 2 else self.bottom
                s.text(x, y, ("█" if r < full else BLOCKS[part]) * bw, col)
            pc = int(pks[i] * max_units) // 8
            if pc > full and pc < rows:
                s.text(x, rows - 1 - pc, "▂" * bw, self.peak_c)
            x += bw + gap

        if self.fallback:
            s.text(0, rows - 1, "[нет звука - демо]", (120, 120, 120))

    def close(self):
        self._stop_flag = True
        self._close_audio()


def extra(ap):
    ap.add_argument("--device", default="")
    ap.add_argument("--devices", action="store_true")
    ap.add_argument("--source", choices=["mic", "loopback"], default=None)
    ap.add_argument("--bars", type=int, default=None,
                    help="Число столбиков эквалайзера")
    ap.add_argument("--gain", type=float, default=None)
    ap.add_argument("--autosens", type=int, default=None,
                    help="Автосенс: 1 = вкл, 0 = выкл")


def make(args):
    if args.devices and sd:
        for i, d in enumerate(sd.query_devices()):
            if d["max_input_channels"] > 0:
                print(i, d["name"])
        sys.exit(0)
    return Cava(args)


def main():
    run("cava", lambda a: Cava(a), 60, extra)

if __name__ == "__main__":
    main()