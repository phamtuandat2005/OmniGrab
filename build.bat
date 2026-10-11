@echo off
chcp 65001 >nul 2>&1
title OmniGrab - Trinh quan ly dong goi (Build Manager)

echo ========================================================
echo        OmniGrab - Trinh quan ly dong goi ung dung
echo ========================================================
echo.

:: 1. Kiem tra Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [LOI] Khong tim thay Python. Hay cai dat Python 3.10+ truoc.
    pause
    exit /b 1
)

:: 2. Kiem tra/Thiet lap moi truong ao (venv)
if exist "venv\Scripts\activate.bat" (
    echo [1/2] Phat hien moi truong ao da ton tai. Dang kich hoat...
    call "venv\Scripts\activate.bat"
) else (
    echo [1/2] Chua co moi truong ao. Dang tao moi...
    python -m venv venv
    if errorlevel 1 (
        echo [LOI] Khong the tao moi truong ao. Kiem tra cai dat Python.
        pause
        exit /b 1
    )
    call "venv\Scripts\activate.bat"
    echo        Da tao va kich hoat moi truong ao tai: venv
)

:: 3. Cai dat thu vien vao venv
echo [2/2] Dang cai dat thu vien phu thuoc...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [LOI] Khong the cai dat thu vien. Kiem tra ket noi mang.
    pause
    exit /b 1
)
echo.

:MENU
echo ========================================================
echo CHON PHUONG THUC DONG GOI:
echo ========================================================
echo 1. Build tieu chuan (PyInstaller) - Nhanh nhat, khong bao mat
echo 2. Build bao mat Nuitka (C++) - Bao mat cao, can trinh bien dich C++
echo 3. Build bao mat PyArmor - Lam roi ma nguon
echo 0. Thoat
echo ========================================================
set /p choice="Nhap lua chon cua ban (0-3): "

if "%choice%"=="1" goto BUILD_STANDARD
if "%choice%"=="2" goto BUILD_NUITKA
if "%choice%"=="3" goto BUILD_PYARMOR
if "%choice%"=="0" exit /b 0

echo Lua chon khong hop le!
echo.
goto MENU


:BUILD_STANDARD
echo.
echo Dang dong goi tieu chuan voi PyInstaller (--onefile)...
pip install pyinstaller --quiet --upgrade
pyinstaller --noconfirm --clean --noconsole --onefile --name "OmniGrab" --icon "assets\icon.ico" --add-data "ui;ui" --add-data "core;core" --add-data "assets;assets" --add-binary "ffmpeg.exe;." --add-binary "ffprobe.exe;." --collect-all "playwright" --collect-all "faster_whisper" --collect-all "ctranslate2" --collect-all "curl_cffi" --collect-all "f2" --collect-all "pydub" --collect-all "gtts" --hidden-import "PyQt6" --hidden-import "PyQt6.QtCore" --hidden-import "PyQt6.QtGui" --hidden-import "PyQt6.QtWidgets" --hidden-import "yt_dlp" --hidden-import "audioop" main.py
if errorlevel 1 (
    echo [LOI] Dong goi that bai!
    pause
    exit /b 1
)
echo.
echo DONG GOI THANH CONG! File thuc thi: dist\OmniGrab.exe
echo (Da tich hop san ffmpeg vao ben trong file exe)
pause
exit /b 0


:BUILD_NUITKA
echo.
echo [1/3] Kiem tra Nuitka & zstandard...
pip install nuitka zstandard --quiet
if errorlevel 1 (
    echo [LOI] Khong the cai dat Nuitka.
    pause
    exit /b 1
)
echo [2/3] Bat dau bien dich ma nguon Python sang C++ (Co the mat 5-10 phut)...
nuitka --standalone --onefile --enable-plugin=pyqt6 --enable-plugin=playwright --include-package=yt_dlp --include-package=curl_cffi --include-package=f2 --include-package=faster_whisper --include-package=ctranslate2 --include-package=playwright --include-package=pydub --include-package=gtts --include-package=requests --include-package=av --windows-icon-from-ico=assets\icon.ico --include-data-dir=assets=assets --include-data-dir=ui=ui --include-data-dir=core=core --include-data-files=ffmpeg.exe=ffmpeg.exe --include-data-files=ffprobe.exe=ffprobe.exe --windows-company-name="OmniGrab" --windows-product-name="OmniGrab" --windows-file-version=4.0.0.0 --windows-product-version=4.0.0.0 --windows-file-description="OmniGrab Video Downloader & AI Dubbing" --output-dir="dist" --output-filename="OmniGrab.exe" --remove-output --lto=no --windows-disable-console main.py
if errorlevel 1 (
    echo.
    echo [LOI] Bien dich that bai! Vui long kiem tra log.
    pause
    exit /b 1
)
copy /y "dist\OmniGrab.exe" "OmniGrab.exe" >nul 2>&1
echo.
echo [3/3] Bien dich C++ thanh cong! File thuc thi: dist\OmniGrab.exe (va OmniGrab.exe tai thu muc goc)
pause
exit /b 0


:BUILD_PYARMOR
echo.
echo [1/3] Cai dat PyArmor va PyInstaller...
pip install pyarmor pyinstaller --quiet --upgrade
if errorlevel 1 (
    echo [LOI] Khong the cai dat PyArmor.
    pause
    exit /b 1
)
echo [2/3] Dang ma hoa thu muc core/ bang PyArmor...
if exist "dist_obfuscated" rmdir /s /q "dist_obfuscated"
pyarmor gen -O dist_obfuscated -r core main.py
xcopy /s /i /y ui dist_obfuscated\ui >nul
xcopy /s /i /y assets dist_obfuscated\assets >nul

echo [3/3] Dang dong goi code da ma hoa bang PyInstaller...
cd dist_obfuscated
pyinstaller --noconfirm --clean --noconsole --onefile --name "OmniGrab_Protected" --icon "assets\icon.ico" --add-data "ui;ui" --add-data "assets;assets" --add-binary "..\ffmpeg.exe;." --add-binary "..\ffprobe.exe;." --collect-all "curl_cffi" --collect-all "f2" --collect-all "pydub" --collect-all "gtts" --hidden-import "PyQt6" --hidden-import "PyQt6.QtCore" --hidden-import "PyQt6.QtGui" --hidden-import "PyQt6.QtWidgets" --hidden-import "yt_dlp" --hidden-import "audioop" main.py
if errorlevel 1 (
    echo [LOI] Dong goi that bai.
    pause
    exit /b 1
)
cd ..
echo DONG GOI THANH CONG! File dau ra: dist_obfuscated\dist\OmniGrab_Protected.exe
pause
exit /b 0
