#точка входа qanim-core.exe: один exe на все визуалы.
# QAnim
# Copyright (c) 2026 [ZigRain-hub]
# Licensed under the MIT License. See LICENSE file for details.
import sys
import traceback

import cava
import cmatrix
import rain
import lava
import pipes
import pixel
import pclock

MODS = {
    "cava": cava,
    "cmatrix": cmatrix,
    "rain": rain,
    "lava": lava,
    "pipes": pipes,
    "pixel": pixel,
    "pclock": pclock,
}

def main():
    args = sys.argv[1:]
    if not args or args[0] not in MODS:
        print("QAnim core. Использование: qanim-core <"
              + "|".join(MODS) + "> [цвет] [опции]")
        return
    name, rest = args[0], args[1:]
    sys.argv = [name] + rest
    MODS[name].main()

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException:
        traceback.print_exc()
        try:
            input("\n[ОШИБКА] Нажми Enter, чтобы закрыть...")
        except Exception:
            pass