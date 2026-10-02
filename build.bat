@echo off
chcp 65001 >nul 2>&1
title OmniGrab - Dong goi ung dung

echo.
echo ========================================================
echo        OmniGrab - Kich ban dong goi ung dung
echo ========================================================
echo.

:: Kiem tra Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [LOI] Khong tim thay Python. Hay cai dat Python 3.10+ truoc.
    pause
    exit /b 1
)

:: Kiem tra/Thiet lap moi truong ao (venv)
if exist "venv\Scripts\activate.bat" (
    echo [1/4] Phat hien moi truong ao da ton tai. Dang kich hoat...
    call "venv\Scripts\activate.bat"
) else (
    echo [1/4] Chua co moi truong ao. Dang tao moi...
    python -m venv venv
    if errorlevel 1 (
        echo [LOI] Khong the tao moi truong ao. Kiem tra cai dat Python.
        pause
        exit /b 1
    )
    call "venv\Scripts\activate.bat"
    echo        Da tao va kich hoat moi truong ao tai: venv
)

:: Cai dat thu vien vao venv
echo [2/4] Dang cai dat thu vien phu thuoc...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [LOI] Khong the cai dat thu vien. Kiem tra ket noi mang.
    pause
    exit /b 1
)

echo [3/4] Dang kiem tra PyInstaller...
pip install pyinstaller --quiet --upgrade

echo [4/4] Dang dong goi ung dung...
echo.

:: Dong goi voi PyInstaller
pyinstaller --noconfirm --clean --noconsole --onedir --name "OmniGrab" --icon "assets\icon.ico" --add-data "ui;ui" --add-data "core;core" --add-data "assets;assets" --hidden-import "PyQt6" --hidden-import "PyQt6.QtCore" --hidden-import "PyQt6.QtGui" --hidden-import "PyQt6.QtWidgets" --hidden-import "yt_dlp" main.py

if errorlevel 1 (
    echo.
    echo [LOI] Dong goi that bai. Xem log o tren de biet chi tiet.
    pause
    exit /b 1
)

echo.
echo ========================================================
echo            DONG GOI THANH CONG!
echo --------------------------------------------------------
echo   Thu muc dau ra: dist\OmniGrab
echo.
echo   QUAN TRONG: Dat ffmpeg.exe vao thu muc dist\OmniGrab
echo   de ho tro ghep video Facebook.
echo.
echo   Tai ffmpeg: https://ffmpeg.org/download.html
echo ========================================================
echo.
pause
