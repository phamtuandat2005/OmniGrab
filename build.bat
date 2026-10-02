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
echo Dang dong goi tieu chuan voi PyInstaller...
pip install pyinstaller --quiet --upgrade
pyinstaller --noconfirm --clean --noconsole --onedir --name "OmniGrab" --icon "assets\icon.ico" --add-data "ui;ui" --add-data "core;core" --add-data "assets;assets" --hidden-import "PyQt6" --hidden-import "PyQt6.QtCore" --hidden-import "PyQt6.QtGui" --hidden-import "PyQt6.QtWidgets" --hidden-import "yt_dlp" main.py
if errorlevel 1 (
    echo [LOI] Dong goi that bai!
    pause
    exit /b 1
)
echo.
echo DONG GOI THANH CONG! Thu muc dau ra: dist\OmniGrab
echo QUAN TRONG: Dat ffmpeg.exe vao thu muc dist\OmniGrab de ho tro ghep video.
pause
exit /b 0


:BUILD_NUITKA
echo.
echo [1/3] Kiem tra Nuitka...
pip install nuitka --quiet
if errorlevel 1 (
    echo [LOI] Khong the cai dat Nuitka.
    pause
    exit /b 1
)
echo [2/3] Bat dau bien dich ma nguon Python sang C++ (Co the mat nhieu phut)...
nuitka --standalone --onefile --enable-plugin=pyqt6 --include-package=yt_dlp --windows-icon-from-ico=assets\icon.ico --include-data-dir=assets=assets --include-data-dir=ui=ui --remove-output --lto=yes --windows-disable-console main.py
if errorlevel 1 (
    echo.
    echo [LOI] Bien dich that bai! Vui long kiem tra log C++ compiler.
    echo Goi y: Ban co the can cai dat MinGW64 hoac MSVC (Visual Studio).
    pause
    exit /b 1
)
echo.
echo [3/3] Bien dich thanh cong! File thuc thi: main.exe
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
pyinstaller --noconfirm --clean --noconsole --onedir --name "OmniGrab_Protected" --icon "assets\icon.ico" --add-data "ui;ui" --add-data "assets;assets" --hidden-import "PyQt6" --hidden-import "PyQt6.QtCore" --hidden-import "PyQt6.QtGui" --hidden-import "PyQt6.QtWidgets" --hidden-import "yt_dlp" main.py
if errorlevel 1 (
    echo [LOI] Dong goi that bai.
    pause
    exit /b 1
)
cd ..
echo DONG GOI THANH CONG! Thu muc dau ra: dist_obfuscated\dist\OmniGrab_Protected\
pause
exit /b 0
