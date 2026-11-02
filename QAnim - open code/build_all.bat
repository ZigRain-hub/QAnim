@echo off

rem# QAnim
rem# Copyright (c) 2026 [ZigRain-hub]
rem# Licensed under the MIT License. See LICENSE file for details.
rem ============================================================
rem  build_all.bat - сборка QAnim в exe в один клик
rem  Положи РЯДОМ с .py файлами проекта (qvis.py, main.py, ...)
rem  Запуск:  build_all.bat          - обычная сборка
rem           build_all.bat clean    - снести venv и собрать с нуля
rem           build_all.bat noupx    - без UPX-сжатия
rem ============================================================
chcp 65001 >nul
cd /d "%~dp0"


if /i "%1"=="clean" (
    echo [0/9] Чищу старый venv и результаты сборки...
    rmdir /s /q .venv-build 2>nul
    rmdir /s /q build 2>nul
    rmdir /s /q dist 2>nul
)
set NOUPX=0
if /i "%1"=="noupx" set NOUPX=1

echo [1/9] Python:
python -V || goto :err
python -c "import sys;sys.exit(0 if sys.maxsize>2**32 else 1)" || (
    echo ОШИБКА: нужен 64-битный Python
    goto :err
)

if exist .venv-build\Scripts\activate.bat (
    echo [2/9] venv уже есть ^(снести: build_all.bat clean^)
) else (
    echo [2/9] Создаю ЧИСТЫЙ venv — критично для размера!
    python -m venv .venv-build || goto :err
)
call .venv-build\Scripts\activate.bat || goto :err

echo [3/9] Зависимости (PySide6-Essentials качается ~2 мин при первом запуске)...
python -m pip install --upgrade pip >nul 2>nul
pip install --disable-pip-version-check -q pyinstaller numpy pyaudiowpatch sounddevice PySide6-Essentials PySideSix-Frameless-Window || goto :err
pip show PySide6-Essentials >nul 2>nul || (
    echo ОШИБКА: PySide6-Essentials не установился
    goto :err
)

rem UPX 
set UPXOPT=--upx-exclude "python*.dll" --upx-exclude "vcruntime*.dll" --upx-exclude "ucrtbase.dll"
set UPXDIR=
if "%NOUPX%"=="1" (
    echo [4/9] UPX отключён ^(build_all.bat noupx^)
    goto :upx_done
)
where upx >nul 2>nul
if not errorlevel 1 (
    echo [4/9] UPX найден в PATH — включаю сжатие
    set UPXDIR=PATH
    goto :upx_done
)
if exist upx.exe (
    echo [4/9] UPX найден рядом со скриптом — включаю сжатие
    set UPXDIR=.
    goto :upx_done
)
echo [4/9] UPX не найден — сборка будет крупнее на ~30%%
echo       Положи upx.exe рядом со скриптом и перезапусти
:upx_done
if "%UPXDIR%"=="." set UPXOPT=--upx-dir . %UPXOPT%

rem ядро: все 7 визуалов в одном exe 
echo [5/9] Собираю qanim-core.exe...
pyinstaller --noconfirm --onefile --console --name qanim-core qanim_core.py ^
  --collect-all pyaudiowpatch --collect-all sounddevice ^
  --exclude-module PySide6 --exclude-module PyQt5 --exclude-module PyQt6 ^
  --exclude-module tkinter --exclude-module matplotlib --exclude-module scipy ^
  --exclude-module pandas --exclude-module psutil --exclude-module IPython ^
  --exclude-module pytest --exclude-module numpy.f2py %UPXOPT% || goto :err

rem GUI 
echo [6/9] Собираю QAnim.exe...
pyinstaller --noconfirm --onefile --windowed --name QAnim main.py ^
  --collect-all qframelesswindow ^
  --exclude-module numpy --exclude-module sounddevice --exclude-module pyaudiowpatch ^
  --exclude-module tkinter %UPXOPT% || goto :err

rem payload: exe + шимы команд
echo [7/9] Payload: шимы + zip...
if exist dist\payload rmdir /s /q dist\payload
mkdir dist\payload
move /y dist\QAnim.exe dist\payload\ >nul || goto :err
move /y dist\qanim-core.exe dist\payload\ >nul || goto :err
call :shim cava
call :shim rain
call :shim cmatrix
call :shim lava
call :shim pipes
call :shim pixel
call :shim pclock
powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path dist\payload\* -DestinationPath qanim_payload.zip -Force" || goto :err

rem установщик
echo [8/9] Собираю QAnim-Installer.exe...
pyinstaller --noconfirm --onefile --name QAnim-Installer --add-data "qanim_payload.zip;." installer.py %UPXOPT% || goto :err

rem чистка временных файлов
rmdir /s /q build 2>nul
del /q qanim_payload.zip 2>nul

echo.
echo Готово. Ставится: dist\QAnim-Installer.exe
echo Содержимое: dist\payload\ ^(QAnim.exe + qanim-core.exe + 7 .cmd^)
pause
exit /b 0

rem шим-команда для PATH
:shim
> dist\payload\%1.cmd echo @echo off
>> dist\payload\%1.cmd echo "%%~dp0qanim-core.exe" %1 %%
exit /b 0

:err
echo.
echo === ОШИБКА СБОРКИ — см. текст выше ===
pause
exit /b 1
