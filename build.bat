@echo off
chcp 65001 >nul 2>&1
title OmniGrab - Trinh quan ly dong goi (Build Manager)
cd /d "%~dp0"

echo ========================================================
echo        OmniGrab - Trinh quan ly dong goi ung dung
echo ========================================================
echo.

:: FFmpeg va FFprobe bat buoc cho ban phat hanh Windows.
set "FFMPEG_SOURCE="
set "FFPROBE_SOURCE="
if exist "ffmpeg.exe" set "FFMPEG_SOURCE=%CD%\ffmpeg.exe"
if not defined FFMPEG_SOURCE if exist "tools\ffmpeg\bin\ffmpeg.exe" set "FFMPEG_SOURCE=%CD%\tools\ffmpeg\bin\ffmpeg.exe"
if not defined FFMPEG_SOURCE for /f "delims=" %%I in ('where ffmpeg.exe 2^>nul') do if not defined FFMPEG_SOURCE set "FFMPEG_SOURCE=%%~fI"
if exist "ffprobe.exe" set "FFPROBE_SOURCE=%CD%\ffprobe.exe"
if not defined FFPROBE_SOURCE if exist "tools\ffmpeg\bin\ffprobe.exe" set "FFPROBE_SOURCE=%CD%\tools\ffmpeg\bin\ffprobe.exe"
if not defined FFPROBE_SOURCE for /f "delims=" %%I in ('where ffprobe.exe 2^>nul') do if not defined FFPROBE_SOURCE set "FFPROBE_SOURCE=%%~fI"
if not defined FFMPEG_SOURCE (
    echo [LOI] Khong tim thay ffmpeg.exe. Hay dat file vao thu muc goc hoac tools\ffmpeg\bin.
    pause
    exit /b 1
)
if not defined FFPROBE_SOURCE (
    echo [LOI] Khong tim thay ffprobe.exe. Can bo FFmpeg day du co ca hai binary.
    echo        Dat ffprobe.exe vao thu muc goc hoac tools\ffmpeg\bin.
    pause
    exit /b 1
)
echo [OK] Da tim thay ca ffmpeg.exe va ffprobe.exe.
"%FFMPEG_SOURCE%" -version >nul 2>&1
if errorlevel 1 (
    echo [LOI] ffmpeg.exe khong chay duoc. Hay thay bang binary FFmpeg Windows day du.
    pause
    exit /b 1
)
"%FFPROBE_SOURCE%" -version >nul 2>&1
if errorlevel 1 (
    echo [LOI] ffprobe.exe khong chay duoc. Hay lay ffprobe.exe cung bo voi ffmpeg.exe.
    pause
    exit /b 1
)
set "OMNIGRAB_FFMPEG_SOURCE=%FFMPEG_SOURCE%"
set "OMNIGRAB_FFPROBE_SOURCE=%FFPROBE_SOURCE%"
python -c "import os,subprocess,sys; paths=[os.environ['OMNIGRAB_FFMPEG_SOURCE'],os.environ['OMNIGRAB_FFPROBE_SOURCE']]; versions=[subprocess.run([p,'-version'],capture_output=True,text=True,check=True).stdout.splitlines()[0].split('version ',1)[1].split(' ',1)[0] for p in paths]; print('FFmpeg versions:', ' / '.join(versions)); sys.exit(versions[0] != versions[1])"
if errorlevel 1 (
    echo [LOI] ffmpeg va ffprobe khong cung phien ban.
    echo        Hay lay ca hai file tu cung mot goi FFmpeg.
    pause
    exit /b 1
)
echo.

:: 1. Kiem tra Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [LOI] Khong tim thay Python. Hay cai dat Python 3.10+ truoc.
    pause
    exit /b 1
)
python -c "import struct,sys; sys.exit(0 if sys.version_info >= (3,10) and struct.calcsize('P') == 8 else 1)"
if errorlevel 1 (
    echo [LOI] Can Python 3.10 tro len ban 64-bit de tao bo cai Windows x64.
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
echo 1. Tao ban phat hanh Windows (PyInstaller + FFmpeg + Chromium + Whisper + installer) [Mac dinh]
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
call :PREPARE_RUNTIME
if errorlevel 1 exit /b 1
echo.
echo Dang dong goi ban phat hanh day du voi PyInstaller...
pip install pyinstaller --quiet --upgrade

pyinstaller --noconfirm --clean --noconsole --onedir --name "OmniGrab" --distpath "dist_release" --workpath "build_release_pyinstaller" --icon="%~dp0assets\icon.ico" --add-data "ui;ui" --add-data "core;core" --add-data "assets;assets" --add-binary "%FFMPEG_SOURCE%;." --add-binary "%FFPROBE_SOURCE%;." --add-data "%PLAYWRIGHT_BROWSERS_PATH%;playwright-browsers" --add-data "%WHISPER_MODEL_DIR%;models/faster-whisper-base" --collect-all "playwright" --collect-all "faster_whisper" --collect-all "ctranslate2" --collect-all "curl_cffi" --collect-all "f2" --collect-all "pydub" --collect-all "gtts" --collect-all "deep_translator" --collect-all "cryptography" --collect-all "bs4" --collect-all "av" --collect-all "onnxruntime" --hidden-import "PyQt6" --hidden-import "PyQt6.QtCore" --hidden-import "PyQt6.QtGui" --hidden-import "PyQt6.QtWidgets" --hidden-import "yt_dlp" --hidden-import "audioop" --hidden-import "audioop_lts" --hidden-import "requests" main.py
if errorlevel 1 (
    echo [LOI] Dong goi that bai!
    pause
    exit /b 1
)
copy /y "%FFMPEG_SOURCE%" "dist_release\OmniGrab\ffmpeg.exe" >nul 2>&1
copy /y "%FFPROBE_SOURCE%" "dist_release\OmniGrab\ffprobe.exe" >nul 2>&1
if not exist "dist_release\OmniGrab\_internal\ffmpeg.exe" copy /y "%FFMPEG_SOURCE%" "dist_release\OmniGrab\_internal\ffmpeg.exe" >nul 2>&1
if not exist "dist_release\OmniGrab\_internal\ffprobe.exe" copy /y "%FFPROBE_SOURCE%" "dist_release\OmniGrab\_internal\ffprobe.exe" >nul 2>&1
if not exist "dist_release\OmniGrab\_internal\models\faster-whisper-base\model.bin" (
    echo [LOI] Ban build thieu mo hinh Whisper base.
    pause
    exit /b 1
)
set "BUNDLED_CHROMIUM="
for /r "dist_release\OmniGrab\_internal\playwright-browsers" %%F in (chrome.exe) do if exist "%%F" set "BUNDLED_CHROMIUM=%%F"
if not defined BUNDLED_CHROMIUM (
    echo [LOI] Ban build thieu Chromium cua Playwright.
    pause
    exit /b 1
)
:: Lam moi bo nho dem icon cua Windows de logo hien thi ngay lap tuc
ie4uinit.exe -show >nul 2>&1
echo.
echo DONG GOI THANH CONG! Bo phat hanh: dist_release\OmniGrab\
echo File chay: dist_release\OmniGrab\OmniGrab.exe
echo Da kem FFmpeg, FFprobe, Chromium va mo hinh Whisper base.
set "ISCC="
for /f "delims=" %%I in ('where ISCC.exe 2^>nul') do if not defined ISCC set "ISCC=%%~fI"
if not defined ISCC if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%LOCALAPPDATA%\Programs\Inno Setup 7\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 7\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 7\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 7\ISCC.exe"
if not defined ISCC (
    echo [CANH BAO] Khong tim thay Inno Setup Compiler (ISCC.exe).
    echo Thu muc dist_release\OmniGrab\ da san sang, nhung chua tao file cai dat .exe.
    echo Cai Inno Setup 6 tren may dong goi, sau do chay lai build.bat.
    pause
    exit /b 2
)
if not exist "dist_installer" mkdir "dist_installer"
echo Dang tao file cai dat Windows...
call "%ISCC%" /Qp /DAppDistDir=dist_release setup.iss
if errorlevel 1 (
    echo [LOI] Inno Setup khong tao duoc installer.
    pause
    exit /b 1
)
if not exist "dist_installer\OmniGrab.Setup.4.0.0.exe" (
    echo [LOI] Khong tim thay file installer sau khi bien dich.
    pause
    exit /b 1
)
echo FILE CAI DAT: dist_installer\OmniGrab.Setup.4.0.0.exe
pause
exit /b 0


:BUILD_NUITKA
call :PREPARE_RUNTIME
if errorlevel 1 exit /b 1
echo.
echo [1/3] Kiem tra Nuitka & zstandard...
pip install nuitka zstandard --quiet
if errorlevel 1 (
    echo [LOI] Khong the cai dat Nuitka.
    pause
    exit /b 1
)

echo [2/3] Bat dau bien dich ma nguon Python sang C++ (Co the mat 5-10 phut)...
nuitka --standalone --onefile --enable-plugin=pyqt6 --enable-plugin=playwright --include-package=yt_dlp --include-package=curl_cffi --include-package=f2 --include-package=faster_whisper --include-package=ctranslate2 --include-package=playwright --include-package=pydub --include-package=gtts --include-package=requests --include-package=av --include-package-data=f2 --include-package-data=curl_cffi --windows-icon-from-ico="%~dp0assets\icon.ico" --include-data-dir=assets=assets --include-data-dir=ui=ui --include-data-dir=core=core --include-data-dir="%PLAYWRIGHT_BROWSERS_PATH%=playwright-browsers" --include-data-dir="%WHISPER_MODEL_DIR%=models/faster-whisper-base" --include-data-files="%FFMPEG_SOURCE%=ffmpeg.exe" --include-data-files="%FFPROBE_SOURCE%=ffprobe.exe" --windows-company-name="OmniGrab" --windows-product-name="OmniGrab" --windows-file-version=4.0.0.0 --windows-product-version=4.0.0.0 --windows-file-description="OmniGrab Video Downloader & AI Dubbing" --output-dir="dist" --output-filename="OmniGrab.exe" --remove-output --lto=no --windows-disable-console main.py
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
call :PREPARE_RUNTIME
if errorlevel 1 exit /b 1
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
pyinstaller --noconfirm --clean --noconsole --onefile --name "OmniGrab_Protected" --icon "assets\icon.ico" --add-data "ui;ui" --add-data "assets;assets" --add-binary "%FFMPEG_SOURCE%;." --add-binary "%FFPROBE_SOURCE%;." --add-data "%PLAYWRIGHT_BROWSERS_PATH%;playwright-browsers" --add-data "%WHISPER_MODEL_DIR%;models/faster-whisper-base" --collect-all "playwright" --collect-all "faster_whisper" --collect-all "ctranslate2" --collect-all "curl_cffi" --collect-all "f2" --collect-all "pydub" --collect-all "gtts" --collect-all "deep_translator" --collect-all "cryptography" --collect-all "bs4" --collect-all "av" --hidden-import "PyQt6" --hidden-import "PyQt6.QtCore" --hidden-import "PyQt6.QtGui" --hidden-import "PyQt6.QtWidgets" --hidden-import "yt_dlp" --hidden-import "audioop" --hidden-import "requests" main.py
if errorlevel 1 (
    echo [LOI] Dong goi that bai.
    pause
    exit /b 1
)
cd ..
echo DONG GOI THANH CONG! File dau ra: dist_obfuscated\dist\OmniGrab_Protected.exe
pause
exit /b 0


:PREPARE_RUNTIME
set "BUILD_RUNTIME=%CD%\build_runtime"
set "PLAYWRIGHT_BROWSERS_PATH=%BUILD_RUNTIME%\playwright-browsers"
set "WHISPER_MODEL_DIR=%BUILD_RUNTIME%\models\faster-whisper-base"
mkdir "%PLAYWRIGHT_BROWSERS_PATH%" 2>nul
mkdir "%WHISPER_MODEL_DIR%" 2>nul

echo Kiem tra Chromium di kem ung dung...
set "FOUND_CHROME="
for /r "%PLAYWRIGHT_BROWSERS_PATH%" %%F in (chrome.exe) do if exist "%%F" set "FOUND_CHROME=%%F"
if not defined FOUND_CHROME (
    if exist "%LOCALAPPDATA%\ms-playwright\chromium-*\chrome-win64\chrome.exe" (
        echo [INFO] Sao chep Chromium tu cache he thong...
        xcopy /s /i /y "%LOCALAPPDATA%\ms-playwright\chromium-*" "%PLAYWRIGHT_BROWSERS_PATH%\chromium-local" >nul 2>&1
    )
)
for /r "%PLAYWRIGHT_BROWSERS_PATH%" %%F in (chrome.exe) do if exist "%%F" set "FOUND_CHROME=%%F"
if not defined FOUND_CHROME (
    echo Dang tai Chromium qua Playwright...
    set "PLAYWRIGHT_BROWSERS_PATH=%PLAYWRIGHT_BROWSERS_PATH%"
    python -m playwright install chromium
)
for /r "%PLAYWRIGHT_BROWSERS_PATH%" %%F in (chrome.exe) do if exist "%%F" set "FOUND_CHROME=%%F"
if not defined FOUND_CHROME (
    echo [LOI] Khong tim thay Chromium cho Playwright.
    exit /b 1
)
echo [OK] Chromium da san sang.

echo Kiem tra mo hinh AI Whisper base...
if not exist "%WHISPER_MODEL_DIR%\model.bin" (
    echo Dang chuan bi mo hinh Whisper base...
    python -c "from faster_whisper.utils import download_model; download_model('base', output_dir=r'%WHISPER_MODEL_DIR%')"
)
if not exist "%WHISPER_MODEL_DIR%\model.bin" (
    echo [LOI] Khong tim thay model.bin cua mo hinh Whisper.
    exit /b 1
)
echo [OK] Mo hinh Whisper base da san sang.
exit /b 0
