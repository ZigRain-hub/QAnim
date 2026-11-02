# QAnim
# Copyright (c) 2026 [ZigRain-hub]
# Licensed under the MIT License. See LICENSE file for details.

from setuptools import setup

VISUALS = ["cava", "rain", "cmatrix", "lava", "pipes", "pixel", "pclock"]

#формируем список "точек входа"
#заставит Python создать исполняемые файлы cava.exe, cmatrix.exe и тд в системе.
entry_points = {
    'console_scripts': [
        f'{name} = {name}:main' for name in VISUALS
    ]
}

setup(
    name="qanim",
    version="1.0.0",
    description="QAnim (Terminal Visuals)",
    author="Lovec",
    py_modules=VISUALS + ["qvis"], # указываем какие файлы копировать
    entry_points=entry_points,
    install_requires=[
        "PySide6-Essentials",
        "numpy",
        "psutil",
        "pyaudiowpatch",
        "sounddevice"
    ],
    python_requires='>=3.8',
)