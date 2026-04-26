@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

rem ================================================================
rem  build.bat  —  메신저 올인원 PyInstaller 빌드 스크립트  v1.5.1
rem ================================================================
rem  사용법:
rem    build.bat
rem    → PAT 입력 프롬프트 표시 → inject_token.py 실행 → PyInstaller
rem
rem  사전 준비:
rem    pip install pyinstaller pycryptodome
rem ================================================================

echo.
echo ╔══════════════════════════════════════════════════════╗
echo ║    메신저 올인원  빌드 스크립트  v1.5.1              ║
echo ╚══════════════════════════════════════════════════════╝
echo.

rem ── 작업 디렉토리: 프로젝트 루트 ─────────────────────────────
cd /d "%~dp0.."
set ROOT=%CD%
set BUILD_DIR=%ROOT%\build
set SRC_FILE=%ROOT%\messenger_allInOne_v1.7.0.py
set ENC_FILE=%ROOT%\messenger_allInOne.enc
set VER_FILE=%BUILD_DIR%\version.json

echo  루트   : %ROOT%
echo  소스   : %SRC_FILE%
echo  출력   : %ENC_FILE%
echo.

rem ── PAT 입력 ─────────────────────────────────────────────────
echo [1/4] GitHub PAT 토큰을 입력하세요 (입력 내용은 화면에 표시되지 않음):
set /p "PAT_TOKEN=  PAT> "
if "!PAT_TOKEN!"=="" (
    echo   ❌ PAT 가 입력되지 않았습니다. 종료합니다.
    pause
    exit /b 1
)
echo   ✅ PAT 입력 완료

rem ── inject_token.py 실행 ─────────────────────────────────────
echo.
echo [2/4] PAT 난독화 + AES 암호화 실행...
python "%BUILD_DIR%\inject_token.py" ^
    --pat "!PAT_TOKEN!" ^
    --src "%SRC_FILE%" ^
    --out "%ENC_FILE%" ^
    --ver "%VER_FILE%"

if errorlevel 1 (
    echo   ❌ inject_token.py 실패. 종료합니다.
    pause
    exit /b 1
)

rem ── PyInstaller 빌드 ─────────────────────────────────────────
echo.
echo [3/4] PyInstaller 빌드 시작...
pyinstaller ^
    --onefile ^
    --noconsole ^
    --name "메신저올인원" ^
    --add-data "%ROOT%\core\auto_updater.py;core" ^
    --add-data "%ROOT%\core\auth_checker.py;core" ^
    --add-data "%ROOT%\core\login_window.py;core" ^
    --add-data "%ENC_FILE%;." ^
    --add-data "%ROOT%\Config;Config" ^
    --hidden-import "tkinter" ^
    --hidden-import "tkinter.ttk" ^
    --hidden-import "tkinter.messagebox" ^
    --hidden-import "Crypto.Cipher.AES" ^
    --hidden-import "Crypto.Util.Padding" ^
    "%ROOT%\messenger_allInOne_v1.7.0.py"

if errorlevel 1 (
    echo   ❌ PyInstaller 빌드 실패. 종료합니다.
    pause
    exit /b 1
)

rem ── version.json → dist 복사 ─────────────────────────────────
echo.
echo [4/4] version.json 을 dist/ 에 복사...
copy /y "%VER_FILE%" "%ROOT%\dist\version.json" >nul
copy /y "%ENC_FILE%" "%ROOT%\dist\messenger_allInOne.enc" >nul

echo.
echo ╔══════════════════════════════════════════════════════╗
echo ║  ✅  빌드 완료!                                      ║
echo ╠══════════════════════════════════════════════════════╣
echo ║  배포 파일 (dist\ 폴더):                            ║
echo ║    - 메신저올인원.exe                                ║
echo ║    - messenger_allInOne.enc                          ║
echo ║    - version.json                                    ║
echo ╠══════════════════════════════════════════════════════╣
echo ║  GitHub 에 올릴 파일:                               ║
echo ║    - messenger_allInOne.enc  (최신 버전 .enc)        ║
echo ║    - version.json            (버전 정보)             ║
echo ║                                                      ║
echo ║  ⚠ PAT 평문 / AES 키는 절대 올리지 마세요!          ║
echo ╚══════════════════════════════════════════════════════╝
echo.
pause
