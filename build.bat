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

if "%~1"=="1" goto BUILD_STANDARD
if "%~1"=="2" goto BUILD_NUITKA
if "%~1"=="3" goto BUILD_PYARMOR
if "%~1"=="auto" goto BUILD_STANDARD

:MENU
echo ========================================================
echo CHON PHUONG THUC DONG GOI:
echo ========================================================
echo 1. Build tieu chuan (PyInstaller) - Nhanh nhat, on dinh nhat [Mac dinh]
echo 2. Build bao mat Nuitka (C++) - Bao mat cao, can trinh bien dich C++
echo 3. Build bao mat PyArmor - Lam roi ma nguon
echo 0. Thoat
echo ========================================================
set choice=1
set /p choice="Nhap lua chon cua ban (0-3) [Nhan Enter de chon 1]: "

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

set FFMPEG_PYI_FLAGS=
if exist "ffmpeg.exe" (
    set FFMPEG_PYI_FLAGS=--add-binary "ffmpeg.exe;."
) else (
    echo [THONG BAO] Khong tim thay ffmpeg.exe trong thu muc goc. Se bo qua nhung binary ffmpeg.
)
if exist "ffprobe.exe" (
    set FFMPEG_PYI_FLAGS=%FFMPEG_PYI_FLAGS% --add-binary "ffprobe.exe;."
)

pyinstaller --noconfirm --clean --noconsole --onefile --name "OmniGrab" --icon="%~dp0assets\icon.ico" --add-data "ui;ui" --add-data "core;core" --add-data "assets;assets" %FFMPEG_PYI_FLAGS% --collect-all "playwright" --collect-all "faster_whisper" --collect-all "ctranslate2" --collect-all "curl_cffi" --collect-all "f2" --collect-all "pydub" --collect-all "gtts" --collect-all "deep_translator" --collect-all "cryptography" --collect-all "bs4" --collect-all "av" --hidden-import "PyQt6" --hidden-import "PyQt6.QtCore" --hidden-import "PyQt6.QtGui" --hidden-import "PyQt6.QtWidgets" --hidden-import "yt_dlp" --hidden-import "audioop" --hidden-import "requests" main.py
if errorlevel 1 (
    echo [LOI] Dong goi that bai!
    pause
    exit /b 1
)
:: Lam moi bo nho dem icon cua Windows de logo hien thi ngay lap tuc
ie4uinit.exe -show >nul 2>&1
echo.
echo DONG GOI THANH CONG! File thuc thi: dist\OmniGrab.exe
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

set FFMPEG_NUITKA_FLAGS=
if exist "ffmpeg.exe" (
    set FFMPEG_NUITKA_FLAGS=--include-data-files=ffmpeg.exe=ffmpeg.exe
) else (
    echo [THONG BAO] Khong tim thay ffmpeg.exe trong thu muc goc.
)
if exist "ffprobe.exe" (
    set FFMPEG_NUITKA_FLAGS=%FFMPEG_NUITKA_FLAGS% --include-data-files=ffprobe.exe=ffprobe.exe
)

echo [2/3] Bat dau bien dich ma nguon Python sang C++ (Co the mat 5-10 phut)...
nuitka --standalone --onefile --enable-plugin=pyqt6 --enable-plugin=playwright --include-package=yt_dlp --include-package=curl_cffi --include-package=f2 --include-package=faster_whisper --include-package=ctranslate2 --include-package=playwright --include-package=pydub --include-package=gtts --include-package=requests --include-package=av --include-package-data=f2 --include-package-data=curl_cffi --windows-icon-from-ico="%~dp0assets\icon.ico" --include-data-dir=assets=assets --include-data-dir=ui=ui --include-data-dir=core=core %FFMPEG_NUITKA_FLAGS% --windows-company-name="OmniGrab" --windows-product-name="OmniGrab" --windows-file-version=4.0.0.0 --windows-product-version=4.0.0.0 --windows-file-description="OmniGrab Video Downloader & AI Dubbing" --output-dir="dist" --output-filename="OmniGrab.exe" --remove-output --lto=no --windows-disable-console main.py
if errorlevel 1 (
    echo.
    echo [LOI] Bien dich that bai! Vui long kiem tra log.
    pause
    exit /b 1
)
copy /y "dist\OmniGrab.exe" "OmniGrab.exe" >nul 2>&1
:: Lam moi bo nho dem icon cua Windows de logo hien thi ngay lap tuc
ie4uinit.exe -show >nul 2>&1
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

set FFMPEG_PYARMOR_FLAGS=
if exist "ffmpeg.exe" (
    set FFMPEG_PYARMOR_FLAGS=--add-binary "..\ffmpeg.exe;."
)
if exist "ffprobe.exe" (
    set FFMPEG_PYARMOR_FLAGS=%FFMPEG_PYARMOR_FLAGS% --add-binary "..\ffprobe.exe;."
)

echo [3/3] Dang dong goi code da ma hoa bang PyInstaller...
cd dist_obfuscated
pyinstaller --noconfirm --clean --noconsole --onefile --name "OmniGrab_Protected" --icon "assets\icon.ico" --add-data "ui;ui" --add-data "assets;assets" %FFMPEG_PYARMOR_FLAGS% --collect-all "playwright" --collect-all "faster_whisper" --collect-all "ctranslate2" --collect-all "curl_cffi" --collect-all "f2" --collect-all "pydub" --collect-all "gtts" --collect-all "deep_translator" --collect-all "cryptography" --collect-all "bs4" --collect-all "av" --hidden-import "PyQt6" --hidden-import "PyQt6.QtCore" --hidden-import "PyQt6.QtGui" --hidden-import "PyQt6.QtWidgets" --hidden-import "yt_dlp" --hidden-import "audioop" --hidden-import "requests" main.py
if errorlevel 1 (
    echo [LOI] Dong goi that bai.
    pause
    exit /b 1
)
cd ..
echo DONG GOI THANH CONG! File dau ra: dist_obfuscated\dist\OmniGrab_Protected.exe
pause
exit /b 0
