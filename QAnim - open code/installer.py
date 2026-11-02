# QAnim
# Copyright (c) 2026 [ZigRain-hub]
# Licensed under the MIT License. See LICENSE file for details.

import os
import sys
import shutil
import subprocess
import zipfile
from pathlib import Path

def install():
    print("=" * 50)
    print("  Установка QAnim (без прав администратора)")
    print("=" * 50)

    # определяем базовую директорию
    if getattr(sys, 'frozen', False):
        base_dir = Path(sys._MEIPASS)
    else:
        base_dir = Path(__file__).parent
    archive_path = base_dir / "qanim_payload.zip"
    if not archive_path.exists():
        print("Ошибка: файлы программы не найдены.")
        input("Нажмите Enter...")
        sys.exit(1)

    # устанавливаем в local
    target_dir = Path(os.environ["LOCALAPPDATA"]) / "QAnim"
    print(f"Копирование в {target_dir}...")
    target_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(archive_path, 'r') as z:
        z.extractall(target_dir)
    print("Файлы скопированы.")

    #добавление команд в пользовательский PATH
    print("Настройка PATH...")
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Environment",
            0,
            winreg.KEY_ALL_ACCESS
        )
        try:
            path, _ = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            path = ""
        path_parts = path.split(";") if path else []
        if str(target_dir) not in path_parts:
            path_parts.append(str(target_dir))
            new_path = ";".join(path_parts)
            winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, new_path)
            print(" PATH обновлен.")
        else:
            print(" PATH уже содержит эту папку.")
        winreg.CloseKey(key)
    except Exception as e:
        print(f" Не удалось обновить PATH: {e}")
        print("Можешь добавить вручную: " + str(target_dir))

    # ярлык
    print(" Создание ярлыка...")
    try:
        desktop = Path(os.environ["USERPROFILE"]) / "Desktop"
        shortcut_path = desktop / "QAnim.lnk"
        target_exe = target_dir / "QAnim.exe"
        ps_script = f"""
        $ws = New-Object -ComObject WScript.Shell
        $s = $ws.CreateShortcut('{shortcut_path}')
        $s.TargetPath = '{target_exe}'
        $s.WorkingDirectory = '{target_dir}'
        $s.Save()
        """
        subprocess.run(["powershell", "-Command", ps_script], capture_output=True)
        print(" Ярлык создан.")
    except Exception as e:
        print(f" Не удалось создать ярлык: {e}")

    print("\n" + "=" * 50)
    print(" Установка завершена!")
    print(f" Программа установлена в: {target_dir}")
    print(" Ярлык QAnim добавлен на рабочий стол.")
    print(" Команды cava, cmatrix и т.д. теперь работают в терминале.")
    print(" Если терминал был открыт - перезапусти, чтобы подхватить PATH.")
    print("=" * 50)
    input("\nНажми Enter, чтобы выйти...")

if __name__ == "__main__":
    install()