@echo off
chcp 65001 > nul
:: ============================================================
:: build.bat  —  메신저 올인원 EXE 빌드 스크립트  v1.5.0
:: ============================================================
:: 실행 순서:
::   1. inject_token.py 실행 (PAT 주입 + .enc 생성 + SHA-256)
::   2. PyInstaller 로 EXE 빌드
::   3. 빌드 결과물 확인
::
:: 필요 환경:
::   pip install pyinstaller pycryptodome
::
:: 사용법:
::   build.bat <GITHUB_PAT> [AES_KEY|auto]
::   예: build.bat ghp_xxxx... auto
:: ============================================================

setlocal enabledelayedexpansion

set PAT=%~1
set AES=%~2

if "%PAT%"=="" (
    echo.
    echo [오류] GitHub PAT 를 첫 번째 인수로 전달하세요.
    echo 사용법: build.bat ^<GITHUB_PAT^> [AES_KEY^|auto]
    echo.
    pause
    exit /b 1
)

if "%AES%"=="" set AES=auto

:: 작업 디렉토리를 스크립트 위치 기준 부모(메신저올인원 루트)로 설정
cd /d "%~dp0.."

echo.
echo ============================================================
echo  메신저 올인원  EXE 빌드 시작
echo ============================================================
echo.

:: ── Step 1: inject_token.py 실행 ──────────────────────────────
echo [Step 1] PAT 주입 + 암호화...
python build\inject_token.py "%PAT%" "%AES%"
if errorlevel 1 (
    echo [오류] inject_token.py 실패
    pause
    exit /b 1
)
echo.

:: ── Step 2: PyInstaller 빌드 ──────────────────────────────────
echo [Step 2] PyInstaller EXE 빌드...
pyinstaller ^
    --onefile ^
    --noconsole ^
    --name "MessengerAllInOne" ^
    --icon "Config\icon.ico" ^
    --add-data "core\auth_checker.py;core" ^
    --add-data "_injected_auto_updater.py;." ^
    --add-data "Config;Config" ^
    --hidden-import "tkinter" ^
    --hidden-import "tkinter.ttk" ^
    --hidden-import "tkinter.messagebox" ^
    --hidden-import "tkinter.filedialog" ^
    --hidden-import "tkinter.simpledialog" ^
    --hidden-import "Crypto.Cipher.AES" ^
    --hidden-import "Crypto.Util.Padding" ^
    "messenger_allInOne_v1.6.2.py"

if errorlevel 1 (
    echo [오류] PyInstaller 빌드 실패
    pause
    exit /b 1
)
echo.

:: ── Step 3: 결과물 확인 ────────────────────────────────────────
echo [Step 3] 빌드 결과물 확인...
if exist "dist\MessengerAllInOne.exe" (
    echo   ✅ EXE 생성: dist\MessengerAllInOne.exe
) else (
    echo   ❌ EXE 없음
)

if exist "messenger_allInOne.enc" (
    echo   ✅ ENC 생성: messenger_allInOne.enc
) else (
    echo   ❌ ENC 없음
)

if exist "_injected_auto_updater.py" (
    del /q "_injected_auto_updater.py"
    echo   🗑  _injected_auto_updater.py 정리 완료
)

echo.
echo ============================================================
echo  배포 파일:
echo    dist\MessengerAllInOne.exe   (GitHub Release 에 업로드)
echo    messenger_allInOne.enc        (GitHub Release 에 업로드)
echo    build\version.json            (GitHub 레포에 push)
echo ============================================================
echo.
echo  사용자는 EXE + ENC 를 같은 폴더에 두고 실행하면 됩니다.
echo.
pause
