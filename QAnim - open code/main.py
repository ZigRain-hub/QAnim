# QAnim
# Copyright (c) 2026 [ZigRain-hub]
# Licensed under the MIT License. See LICENSE file for details.


import sys, os, json, subprocess, time
from pathlib import Path
from collections import deque

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QSlider, QScrollArea, QFrame,
    QLineEdit, QStackedWidget, QMessageBox, QGraphicsOpacityEffect,
    QPlainTextEdit, QColorDialog
)
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QRect, QProcess
from PySide6.QtGui import QFont, QPainter, QColor, QPen, QPainterPath, QLinearGradient, QBrush, QRegion
from qframelesswindow import AcrylicWindow

if getattr(sys, "frozen", False):
    HERE = Path(sys.executable).parent.resolve()
else:
    HERE = Path(__file__).parent.resolve()
CONFIG_PATH = HERE / "qulw_config.json"
LIVE_PATH = HERE / "live_config.json"

# общая папка настроек: одна и та же для исходников и exe
CONFIG_DIR = Path(os.environ.get("LOCALAPPDATA", str(HERE))) / "QAnim"

VISUALS = ["cava", "rain", "cmatrix", "lava", "pipes", "pixel", "pclock"]

COLORS = ["white", "gray", "red", "orange", "gold", "yellow", "green", "mint",
          "cyan", "ice", "blue", "purple", "neon", "pink", "matrix",
          "fire", "sunset", "ocean", "rainbow", "cyberpunk", "toxic", "blood"]

DEFAULTS = {
    "cava":    {"color": "fire",   "interval_ms": 33, "gain": 1.0, "bars": 32, "source": "loopback", "device": ""},
    "rain":    {"color": "matrix", "interval_ms": 33, "speed": 1.0, "density": 1.0},
    "cmatrix": {"color": "matrix", "interval_ms": 33, "speed": 1.0, "density": 1.0},
    "lava":    {"color": "fire",   "interval_ms": 33, "speed": 1.0, "blobs": 6, "heat": 1.0},
    "pipes":   {"color": "mint",   "interval_ms": 33, "speed": 1.0, "count": 3, "length": 40},
    "pixel":   {"color": "cyan",   "interval_ms": 33, "speed": 1.0, "scale": 20},
    "pclock":  {"color": "snow",   "interval_ms": 200, "tz": "Europe/Moscow", "fmt": "HH:MM:SS", "date": "1", "date_fmt": "%a %b %d", "offset": 0},
}

def load_json(path, default):
    if path.exists():
        try: return json.loads(path.read_text(encoding="utf-8"))
        except Exception: pass
    return default

def save_json(path, data):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print("save_json:", e)

#виджеты 
class GlassCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            GlassCard {
                background: rgba(30, 30, 40, 0.6);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 12px;
            }
        """)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(15, 15, 15, 15)
        self.layout.setSpacing(10)

class CustomSlider(QWidget):
    def __init__(self, label, from_, to, value):
        super().__init__()
        self.setMinimumHeight(45)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        header = QHBoxLayout()
        self.lbl = QLabel(label)
        self.lbl.setStyleSheet("color: rgba(255,255,255,0.8); font-weight: bold; font-size: 12px; background: transparent;")
        self.val_lbl = QLabel(f"{value}")
        self.val_lbl.setStyleSheet("color: #a855f7; font-weight: bold; font-size: 12px; background: transparent;")
        header.addWidget(self.lbl)
        header.addStretch()
        header.addWidget(self.val_lbl)
        layout.addLayout(header)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(int(from_ * 10), int(to * 10))
        self.slider.setValue(int(value * 10))
        self.slider.setStyleSheet("""
            QSlider { background: transparent; }
            QSlider::groove:horizontal { height: 4px; background: rgba(255, 255, 255, 0.1); border-radius: 2px; }
            QSlider::sub-page:horizontal { background: #a855f7; border-radius: 2px; }
            QSlider::handle:horizontal { width: 14px; height: 14px; margin: -5px 0; background: white; border-radius: 7px; }
        """)
        self.slider.valueChanged.connect(self._on_change)
        layout.addWidget(self.slider)

    def _on_change(self, v):
        real_val = v / 10.0
        if real_val == int(real_val): real_val = int(real_val)
        else: real_val = round(real_val, 1)
        self.val_lbl.setText(f"{real_val}")

    def value(self): return self.slider.value() / 10.0
 
class RealTimeGraph(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(100)
        self.data = deque(maxlen=60)
        self.max_val = 60.0
        self.last_time = time.perf_counter()
        self.frames = 0
        self.fps = 60.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(100)

    def _tick(self):
        self.frames += 1
        now = time.perf_counter()
        dt = now - self.last_time
        if dt > 0.5:
            self.fps = self.frames / dt
            self.frames = 0
            self.last_time = now
            self.data.append(min(self.max_val, self.fps))
            self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor(20, 20, 30, 100))
        p.setPen(QPen(QColor(255, 255, 255, 20), 1))
        for i in range(1, 4):
            p.drawLine(0, h - (i * h / 4), w, h - (i * h / 4))
        if len(self.data) > 1:
            path = QPainterPath()
            path.moveTo(0, h)
            for i, val in enumerate(self.data):
                x = i * (w / len(self.data))
                y = h - (val / self.max_val * h)
                path.lineTo(x, y)
            path.lineTo(w, h)
            grad = QLinearGradient(0, 0, 0, h)
            grad.setColorAt(0, QColor(168, 85, 247, 150))
            grad.setColorAt(1, QColor(168, 85, 247, 0))
            p.setBrush(QBrush(grad))
            p.setPen(Qt.NoPen)
            p.drawPath(path)
            p.setPen(QPen(QColor(168, 85, 247), 2))
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)
        p.setPen(QColor(255, 255, 255, 200))
        p.setFont(QFont("Segoe UI", 9, QFont.Bold))
        p.drawText(10, 15, f"UI FPS: {int(self.fps)}")


#вкладки визуалов
class VisualTab(QWidget):
    def __init__(self, master, name, cfg):
        super().__init__(master)
        self.name = name
        self.cfg = cfg
        self.proc = None
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(20)

        # левая часть: настройки
        self.left_scroll = QScrollArea()
        self.left_scroll.setWidgetResizable(True)
        self.left_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.left_content = QWidget()
        self.left_content.setStyleSheet("background: transparent;")
        self.left_layout = QVBoxLayout(self.left_content)
        self.left_layout.setContentsMargins(0, 0, 0, 0)
        self.left_layout.setSpacing(15)
        self.left_scroll.setWidget(self.left_content)
        self.main_layout.addWidget(self.left_scroll, 3)
        # правая часть: график, лог, кнопки
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(15)
        # график
        graph_card = GlassCard()
        graph_card.layout.addWidget(QLabel("Performance", styleSheet="color: rgba(255,255,255,0.5); font-size: 11px; font-weight: bold; background: transparent;"))
        graph_card.layout.addWidget(RealTimeGraph())
        right_layout.addWidget(graph_card)
        # консоль (crash log)
        log_card = GlassCard()
        log_card.layout.addWidget(QLabel("Console / Crash Log", styleSheet="color: rgba(255,255,255,0.5); font-size: 11px; font-weight: bold; background: transparent;"))
        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setStyleSheet("background: rgba(0,0,0,0.3); color: #a855f7; border: none; border-radius: 6px; font-family: Consolas; font-size: 11px;")
        log_card.layout.addWidget(self.log_edit)
        right_layout.addWidget(log_card, 1)

        # кнопки
        btn_box = GlassCard()
        btn_lay = btn_box.layout
        btn_lay.setSpacing(10)

        def make_btn(text, color, hover):
            b = QPushButton(text)
            b.setStyleSheet(f"""
                QPushButton {{ background: {color}; color: white; border: none; border-radius: 8px; padding: 10px; font-weight: bold; }}
                QPushButton:hover {{ background: {hover}; }}
            """)
            return b

        self.btn_apply = make_btn("Применить", "rgba(168, 85, 247, 0.4)", "rgba(168, 85, 247, 0.8)")
        self.btn_apply.clicked.connect(self.apply)
        self.btn_start = make_btn("Запустить", "rgba(168, 85, 247, 0.4)", "rgba(168, 85, 247, 0.8)")
        self.btn_start.clicked.connect(self.start)
        self.btn_stop = make_btn("Остановить", "rgba(168, 85, 247, 0.4)", "rgba(168, 85, 247, 0.8)")
        self.btn_stop.clicked.connect(self.stop)
        btn_lay.addWidget(self.btn_apply)
        btn_lay.addWidget(self.btn_start)
        btn_lay.addWidget(self.btn_stop)

        right_layout.addWidget(btn_box)
        self.main_layout.addWidget(right_panel, 1)
        self.build(self.left_layout)

    def build(self, layout): pass
    def collect(self): return {}
    def extra_cmd_args(self): return {}

    def cmd_base(self):
        fps = max(1, 1000 // max(1, self.cfg["interval_ms"]))
        if getattr(sys, "frozen", False):
            # в exe - запускаем qanim-core.exe лежащий рядом с QAnim.exe
            cmd = [str(HERE / "qanim-core.exe"), self.name, self.cfg["color"],
                   "--fps", str(fps), "--app-mode"]
        else:
            # из исходников - как раньше
            cmd = [sys.executable, str(HERE / f"{self.name}.py"), self.cfg["color"],
                   "--fps", str(fps), "--app-mode"]
        for k, v in self.extra_cmd_args().items():
            cmd += [f"--{k}", str(v)]
        return cmd

    def apply(self):
        self.cfg.update(self.collect())
        live = load_json(LIVE_PATH, {})
        live[self.name] = self.cfg
        save_json(LIVE_PATH, live)
        full = load_json(CONFIG_PATH, {})
        full[self.name] = dict(self.cfg)
        save_json(CONFIG_PATH, full)
        self.log_edit.appendPlainText(f"[{time.strftime('%H:%M:%S')}] Настройки применены.")
        self.log_edit.ensureCursorVisible()

    def start(self):
        if self.proc is not None and self.proc.poll() is None:
            QMessageBox.information(self, "QAnim", f"{self.name} уже запущен")
            return
        self.apply()
        try:
            CREATE_NEW_CONSOLE = 0x00000010
            self.proc = subprocess.Popen(
                self.cmd_base(), creationflags=CREATE_NEW_CONSOLE,
                cwd=str(HERE), close_fds=True
            )
            self.log_edit.appendPlainText(f"[{time.strftime('%H:%M:%S')}] Запуск: {self.name} (pid={self.proc.pid})")
        except Exception as e:
            self.log_edit.appendPlainText(f"ОШИБКА ЗАПУСКА: {e}")

    def _watch_proc(self):
        if self.proc is None:
            return
        if self.proc.poll() is None:
            QTimer.singleShot(500, self._watch_proc)
            return
        self.proc = None
        self.log_edit.appendPlainText(
            f"[{time.strftime('%H:%M:%S')}] Процесс завершён.")

    def _read_pipe(self):
        if self.proc is None:
            return
        if self.proc.poll() is None:
            QTimer.singleShot(500, self._read_pipe)
        try:
            err = self.proc.stderr.read() if self.proc.stderr else ""
            if err and err.strip():
                self.log_edit.appendPlainText(f"STDERR:\n{err.strip()}")
        except Exception:
            pass
        self.proc = None
        self.log_edit.appendPlainText(
            f"[{time.strftime('%H:%M:%S')}] Процесс завершён.")

    def stop(self):
        if self.proc is not None and self.proc.poll() is None:
            try: self.proc.terminate()
            except Exception: pass
        self.proc = None
        self.log_edit.appendPlainText(f"[{time.strftime('%H:%M:%S')}] Остановлено.")
#вкладки
class CavaTab(VisualTab):
    def build(self, layout):
        card = GlassCard()
        card.layout.addWidget(QLabel("<b>Внешний вид</b>", styleSheet="color: white; background: transparent;"))

        self.color_combo = QComboBox()
        self.color_combo.addItems(COLORS)
        self.color_combo.setCurrentText(self.cfg.get("color", "fire"))
        self.color_combo.setStyleSheet("QComboBox { background: rgba(255,255,255,0.05); color: white; border: 1px solid rgba(255,255,255,0.1); border-radius: 6px; padding: 6px; }")
        card.layout.addWidget(self.color_combo)

        card.layout.addWidget(QLabel("<b>Источник</b>", styleSheet="color: white; background: transparent;"))
        self.src_combo = QComboBox()
        self.src_combo.addItems(["loopback", "mic"])
        self.src_combo.setCurrentText(self.cfg.get("source", "loopback"))
        self.src_combo.setStyleSheet("QComboBox { background: rgba(255,255,255,0.05); color: white; border: 1px solid rgba(255,255,255,0.1); border-radius: 6px; padding: 6px; }")
        card.layout.addWidget(self.src_combo)
        self.bars_slider = CustomSlider("Столбики", 4, 128, self.cfg.get("bars", 32))
        self.gain_slider = CustomSlider("Gain", 0.1, 5.0, self.cfg.get("gain", 1.0))
        card.layout.addWidget(self.bars_slider)
        card.layout.addWidget(self.gain_slider)
        layout.addWidget(card)
        layout.addStretch()

    def collect(self):
        return {"color": self.color_combo.currentText(), "source": self.src_combo.currentText(), "bars": int(self.bars_slider.value()), "gain": self.gain_slider.value()}
    def extra_cmd_args(self):
        return {"bars": self.cfg["bars"], "gain": self.cfg["gain"], "source": self.cfg["source"]}

class RainTab(VisualTab):
    def build(self, layout):
        card = GlassCard()
        card.layout.addWidget(QLabel("<b>Внешний вид</b>", styleSheet="color: white; background: transparent;"))

        self.color_combo = QComboBox()
        self.color_combo.addItems(COLORS)
        self.color_combo.setCurrentText(self.cfg.get("color", "matrix"))
        self.color_combo.setStyleSheet("QComboBox { background: rgba(255,255,255,0.05); color: white; border: 1px solid rgba(255,255,255,0.1); border-radius: 6px; padding: 6px; }")
        card.layout.addWidget(self.color_combo)
        self.speed_slider = CustomSlider("Скорость", 0.1, 5.0, self.cfg.get("speed", 1.0))
        self.density_slider = CustomSlider("Плотность", 0.1, 4.0, self.cfg.get("density", 1.0))
        card.layout.addWidget(self.speed_slider)
        card.layout.addWidget(self.density_slider)
        layout.addWidget(card)
        layout.addStretch()

    def collect(self):
        return {"color": self.color_combo.currentText(), "speed": self.speed_slider.value(), "density": self.density_slider.value()}

    def extra_cmd_args(self):
        return {"speed": self.cfg["speed"], "density": self.cfg["density"]}

class CMatrixTab(RainTab): pass #уже все есть (так как +- 500строка я делал импорт TAB_CLASSES) => нет смысла добовлять страницу по этому pass

class LavaTab(VisualTab):
    def build(self, layout):
        card = GlassCard()
        card.layout.addWidget(QLabel("<b>Внешний вид</b>", styleSheet="color: white; background: transparent;"))

        self.color_combo = QComboBox()
        self.color_combo.addItems(COLORS)
        self.color_combo.setCurrentText(self.cfg.get("color", "fire"))
        self.color_combo.setStyleSheet("QComboBox { background: rgba(255,255,255,0.05); color: white; border: 1px solid rgba(255,255,255,0.1); border-radius: 6px; padding: 6px; }")
        card.layout.addWidget(self.color_combo)
        self.speed_slider = CustomSlider("Скорость", 0.1, 5.0, self.cfg.get("speed", 1.0))
        self.blobs_slider = CustomSlider("Капли", 1, 20, self.cfg.get("blobs", 6))
        self.heat_slider = CustomSlider("Нагрев", 0.1, 3.0, self.cfg.get("heat", 1.0))
        card.layout.addWidget(self.speed_slider)
        card.layout.addWidget(self.blobs_slider)
        card.layout.addWidget(self.heat_slider)
        layout.addWidget(card)
        layout.addStretch()

    def collect(self):
        return {"color": self.color_combo.currentText(), "speed": self.speed_slider.value(), "blobs": int(self.blobs_slider.value()), "heat": self.heat_slider.value()}

    def extra_cmd_args(self):
        return {"speed": self.cfg["speed"], "blobs": self.cfg["blobs"], "heat": self.cfg["heat"]}

class PipesTab(VisualTab):
    def build(self, layout):
        card = GlassCard()
        card.layout.addWidget(QLabel("<b>Внешний вид</b>", styleSheet="color: white; background: transparent;"))
        self.color_combo = QComboBox()
        self.color_combo.addItems(COLORS)
        self.color_combo.setCurrentText(self.cfg.get("color", "mint"))
        self.color_combo.setStyleSheet("QComboBox { background: rgba(255,255,255,0.05); color: white; border: 1px solid rgba(255,255,255,0.1); border-radius: 6px; padding: 6px; }")
        card.layout.addWidget(self.color_combo)

        self.speed_slider = CustomSlider("Скорость", 0.1, 5.0, self.cfg.get("speed", 1.0))
        self.count_slider = CustomSlider("Трубы", 1, 15, self.cfg.get("count", 3))
        self.len_slider = CustomSlider("Длина", 10, 200, self.cfg.get("length", 40))
        card.layout.addWidget(self.speed_slider)
        card.layout.addWidget(self.count_slider)
        card.layout.addWidget(self.len_slider)
        layout.addWidget(card)
        layout.addStretch()

    def collect(self):
        return {"color": self.color_combo.currentText(), "speed": self.speed_slider.value(), "count": int(self.count_slider.value()), "length": int(self.len_slider.value())}

    def extra_cmd_args(self):
        return {"speed": self.cfg["speed"], "count": self.cfg["count"], "length": self.cfg["length"]}

class PixelTab(VisualTab):
    def build(self, layout):
        card = GlassCard()
        card.layout.addWidget(QLabel("<b>Внешний вид</b>", styleSheet="color: white; background: transparent;"))

        self.color_combo = QComboBox()
        self.color_combo.addItems(COLORS)
        self.color_combo.setCurrentText(self.cfg.get("color", "cyan"))
        self.color_combo.setStyleSheet("QComboBox { background: rgba(255,255,255,0.05); color: white; border: 1px solid rgba(255,255,255,0.1); border-radius: 6px; padding: 6px; }")
        card.layout.addWidget(self.color_combo)
        self.speed_slider = CustomSlider("Скорость", 0.1, 5.0, self.cfg.get("speed", 1.0))
        self.scale_slider = CustomSlider("Масштаб", 8, 60, self.cfg.get("scale", 20))
        card.layout.addWidget(self.speed_slider)
        card.layout.addWidget(self.scale_slider)
        layout.addWidget(card)
        layout.addStretch()

    def collect(self):
        return {"color": self.color_combo.currentText(), "speed": self.speed_slider.value(), "scale": int(self.scale_slider.value())}

    def extra_cmd_args(self):
        return {"speed": self.cfg["speed"], "scale": self.cfg["scale"]}

class PClockTab(VisualTab):
    def build(self, layout):
        card = GlassCard()
        card.layout.addWidget(QLabel("<b>Внешний вид</b>", styleSheet="color: white; background: transparent;"))
        clock_colors = ["snow", "fire", "purple", "green", "blue", "white", "red", "gold", "cyan", "matrix"]
        self.color_combo = QComboBox()
        self.color_combo.addItems(clock_colors)
        self.color_combo.setCurrentText(self.cfg.get("color", "snow"))
        self.color_combo.setStyleSheet("QComboBox { background: rgba(255,255,255,0.05); color: white; border: 1px solid rgba(255,255,255,0.1); border-radius: 6px; padding: 6px; }")
        card.layout.addWidget(self.color_combo)
        card.layout.addWidget(QLabel("<b>Часовой пояс</b>", styleSheet="color: white; background: transparent;"))
        self.tz_edit = QLineEdit(self.cfg.get("tz", "Europe/Moscow"))
        self.tz_edit.setStyleSheet("background: rgba(255,255,255,0.05); color: white; border: 1px solid rgba(255,255,255,0.1); border-radius: 6px; padding: 6px;")
        card.layout.addWidget(self.tz_edit)
        layout.addWidget(card)
        layout.addStretch()

    def collect(self):
        return {"color": self.color_combo.currentText(), "tz": self.tz_edit.text().strip()}

    def extra_cmd_args(self):
        return {"tz": self.cfg["tz"], "fmt": self.cfg["fmt"], "date": self.cfg["date"]}


#вкладка настроек интерфейса
class SettingsTab(QWidget):
    def __init__(self, parent_window):
        super().__init__(parent_window)
        self.main_win = parent_window
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        card = GlassCard()
        card.layout.addWidget(QLabel("<b>Оформление QAnim</b>", styleSheet="color: white; font-size: 16px; background: transparent;"))
        card.layout.addWidget(QLabel("Уровень блюра / Прозрачность (0 = стекло, 100 = сплошной)", styleSheet="color: rgba(255,255,255,0.6); background: transparent;"))
        self.blur_slider = QSlider(Qt.Horizontal)
        self.blur_slider.setRange(0, 100)
        self.blur_slider.setValue(10)
        self.blur_slider.setStyleSheet("QSlider::groove:horizontal { height: 4px; background: rgba(255,255,255,0.1); border-radius: 2px; } QSlider::sub-page:horizontal { background: #a855f7; } QSlider::handle:horizontal { width: 14px; height: 14px; margin: -5px 0; background: white; border-radius: 7px; }")
        self.blur_slider.valueChanged.connect(self._on_blur_change)
        card.layout.addWidget(self.blur_slider)
        card.layout.addWidget(QLabel("Цвет подложки (HEX)", styleSheet="color: rgba(255,255,255,0.6); background: transparent;"))
        self.color_edit = QLineEdit("14141e")
        self.color_edit.setStyleSheet("background: rgba(255,255,255,0.05); color: white; border: 1px solid rgba(255,255,255,0.1); border-radius: 6px; padding: 6px;")
        self.color_edit.textChanged.connect(self._on_color_change)
        card.layout.addWidget(self.color_edit)

        layout.addWidget(card)
        layout.addStretch()

    def _on_blur_change(self, val):
        alpha = int(255 * (1.0 - val / 100.0))
        alpha = max(1, min(255, alpha))
        hex_alpha = f"{alpha:02X}"
        hex_rgb = self.color_edit.text().strip()
        self.main_win.windowEffect.setAcrylicEffect(
            int(self.main_win.winId()),
            gradientColor=f"{hex_rgb}{hex_alpha}",
            enableShadow=True
        )

    def _on_color_change(self, text):
        if len(text) == 6:
            self._on_blur_change(self.blur_slider.value())

TAB_CLASSES = {
    "cava": CavaTab, "rain": RainTab, "cmatrix": CMatrixTab,
    "lava": LavaTab, "pipes": PipesTab, "pixel": PixelTab, "pclock": PClockTab,
}

class MainWindow(AcrylicWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QAnim")
        self.resize(950, 750)
        self.setMinimumSize(800, 600)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        if hasattr(self, "titleBar"): self.titleBar.hide()
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.cfg = load_json(CONFIG_PATH, {})
        for k, v in DEFAULTS.items(): self.cfg.setdefault(k, dict(v))
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(1, 1, 1, 1)
        main_layout.setSpacing(0)
        # top bar
        top_bar = QWidget()
        top_bar.setFixedHeight(50)
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(20, 0, 10, 0)
        title = QLabel("QAnim")
        title.setStyleSheet("color: white; font-size: 20px; font-weight: 900; letter-spacing: 2px; background: transparent;")
        top_layout.addWidget(title)
        top_layout.addStretch()

        def make_win_btn(text, hover_bg, click_func):
            btn = QPushButton(text)
            btn.setFixedSize(36, 28)
            btn.setStyleSheet(f"QPushButton {{ background: transparent; color: rgba(255,255,255,0.7); border: none; border-radius: 4px; font-size: 14px; }} QPushButton:hover {{ background: {hover_bg}; color: white; }}")
            btn.clicked.connect(click_func)
            return btn
        top_layout.addWidget(make_win_btn("—", "rgba(255,255,255,0.1)", self.showMinimized))
        top_layout.addWidget(make_win_btn("✕", "rgba(255,50,50,0.8)", self.close))
        main_layout.addWidget(top_bar)
        # nav bar
        nav_bar = QWidget()
        nav_bar.setFixedHeight(45)
        nav_layout = QHBoxLayout(nav_bar)
        nav_layout.setContentsMargins(20, 0, 20, 0)
        nav_layout.setSpacing(5)

        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background: transparent;")
        main_layout.addWidget(self.stack, 1)

        self.tabs_dict = {}
        self.tab_buttons = {}
        self._current_anim = None

        for name in VISUALS:
            cls = TAB_CLASSES.get(name, VisualTab)
            tab = cls(self, name, dict(self.cfg.get(name, DEFAULTS.get(name, {}))))
            self.stack.addWidget(tab)
            self.tabs_dict[name] = tab
            btn = QPushButton(name)
            btn.setFixedHeight(35)
            btn.setStyleSheet("QPushButton { background: transparent; color: rgba(255,255,255,0.4); border: none; border-radius: 8px; padding: 0 20px; font-weight: bold; font-size: 13px; } QPushButton:hover { color: rgba(255,255,255,0.8); background: rgba(255,255,255,0.05); }")
            btn.clicked.connect(lambda checked, n=name: self.switch_tab(n))
            nav_layout.addWidget(btn)
            self.tab_buttons[name] = btn

        # вкладка настроек
        self.settings_tab = SettingsTab(self)
        self.stack.addWidget(self.settings_tab)
        self.tabs_dict["Settings"] = self.settings_tab
        btn = QPushButton("Settings")
        btn.setFixedHeight(35)
        btn.setStyleSheet("QPushButton { background: transparent; color: rgba(255,255,255,0.4); border: none; border-radius: 8px; padding: 0 20px; font-weight: bold; font-size: 13px; } QPushButton:hover { color: rgba(255,255,255,0.8); background: rgba(255,255,255,0.05); }")
        btn.clicked.connect(lambda checked: self.switch_tab("Settings"))
        nav_layout.addWidget(btn)
        self.tab_buttons["Settings"] = btn
        nav_layout.addStretch()
        main_layout.addWidget(nav_bar)
        self.switch_tab(VISUALS[0])
        self.windowEffect.setAcrylicEffect(int(self.winId()), gradientColor="14141eDD", enableShadow=True)

    def switch_tab(self, name):
        target = self.tabs_dict[name]
        for t in self.tabs_dict.values():
            if t.graphicsEffect():
                t.setGraphicsEffect(None)

        effect = QGraphicsOpacityEffect(target)
        target.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity")
        anim.setDuration(200)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.finished.connect(lambda: target.setGraphicsEffect(None))
        self.stack.setCurrentWidget(target)
        anim.start()
        self._current_anim = anim
        for n, btn in self.tab_buttons.items():
            if n == name:
                btn.setStyleSheet("QPushButton { background: rgba(168, 85, 247, 0.15); color: #a855f7; border: none; border-radius: 8px; padding: 0 20px; font-weight: bold; font-size: 13px; }")
            else:
                btn.setStyleSheet("QPushButton { background: transparent; color: rgba(255,255,255,0.4); border: none; border-radius: 8px; padding: 0 20px; font-weight: bold; font-size: 13px; } QPushButton:hover { color: rgba(255,255,255,0.8); background: rgba(255,255,255,0.05); }")

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.windowHandle().startSystemMove()
            e.accept()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setCompositionMode(QPainter.CompositionMode_Clear)
        p.fillRect(self.rect(), Qt.transparent)
        rect = self.rect().adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(rect, 8, 8)
        p.setPen(QPen(QColor(255, 255, 255, 40), 1))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
        mask = QRegion(path.toFillPolygon().toPolygon())
        self.setMask(mask)

    def closeEvent(self, event):
        for t in self.tabs_dict.values():
            if hasattr(t, "stop"): t.stop()
        save_json(CONFIG_PATH, self.cfg)
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = MainWindow()
    w.show()
    sys.exit(app.exec())