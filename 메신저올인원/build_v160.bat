@echo off
setlocal enabledelayedexpansion
chcp 65001 > nul

echo.
echo ===========================================================
echo   메신저올인원 v1.60  --  EXE 빌드 스크립트
echo ===========================================================
echo.

:: ---- 0. 경로 설정 -----------------------------------------
::  ROOT_DIR = 이 bat 파일이 있는 폴더 (= py 파일, spec 파일 위치)
set "ROOT_DIR=%~dp0"
set "APP_FOLDER=메신저올인원"
set "DIST_DIR=%ROOT_DIR%dist\%APP_FOLDER%"
set "RELEASE_DIR=%ROOT_DIR%release"
set "RELEASE_ZIP=%RELEASE_DIR%\%APP_FOLDER%_v1.60.zip"

echo   ROOT_DIR : %ROOT_DIR%
echo   DIST_DIR : %DIST_DIR%
echo.

:: ---- 1. PyInstaller 설치 확인 ----------------------------
echo [1/5] PyInstaller 확인...
pyinstaller --version > nul 2>&1
if errorlevel 1 (
    echo   [!] PyInstaller 미설치 -- pip 으로 설치합니다...
    pip install pyinstaller
    if errorlevel 1 (
        echo   [X] PyInstaller 설치 실패. pip 환경을 확인하세요.
        pause & exit /b 1
    )
)
echo   [OK] PyInstaller 준비 완료

:: ---- 2. 이전 빌드 정리 -----------------------------------
echo [2/5] 이전 빌드 정리...
if exist "%DIST_DIR%" rmdir /s /q "%DIST_DIR%"
if exist "%ROOT_DIR%build" rmdir /s /q "%ROOT_DIR%build"
echo   [OK] 정리 완료

:: ---- 3. PyInstaller 빌드 ---------------------------------
echo [3/5] PyInstaller 빌드 시작 (시간이 걸릴 수 있습니다)...

:: 스크립트 루트로 이동 후 빌드 -> SPECPATH/CWD 가 ROOT_DIR 로 확정됨
cd /d "%ROOT_DIR%"
pyinstaller messenger_v160.spec --distpath "%ROOT_DIR%dist" --workpath "%ROOT_DIR%build"

if errorlevel 1 (
    echo   [X] 빌드 실패. 위 오류 메시지를 확인하세요.
    pause & exit /b 1
)
echo   [OK] 빌드 완료

:: ---- 4. Config 폴더 복사 ---------------------------------
echo [4/5] Config 폴더 처리...
if not exist "%ROOT_DIR%Config" (
    echo   [!] Config 폴더 없음 -- 빈 Config 폴더 생성...
    mkdir "%DIST_DIR%\Config\templates"
    mkdir "%DIST_DIR%\Config\jobs"
    mkdir "%DIST_DIR%\Config\presets"
    echo   [OK] 빈 Config 폴더 생성 완료
) else (
    xcopy /e /i /y "%ROOT_DIR%Config" "%DIST_DIR%\Config" > nul
    if errorlevel 1 (
        echo   [X] Config 복사 실패.
        pause & exit /b 1
    )
    echo   [OK] Config 복사 완료
)

:: ---- 5. ZIP 패키징 ---------------------------------------
echo [5/5] ZIP 패키징...
if not exist "%RELEASE_DIR%" mkdir "%RELEASE_DIR%"

powershell -nologo -noprofile -ExecutionPolicy Bypass ^
    -File "%ROOT_DIR%make_zip.ps1" ^
    -SrcDir "%DIST_DIR%" ^
    -DestZip "%RELEASE_ZIP%"

if errorlevel 1 (
    echo   [!] ZIP 생성 실패 -- dist\%APP_FOLDER%\ 폴더를 직접 압축하세요.
) else (
    echo   [OK] ZIP 생성 완료 : release\%APP_FOLDER%_v1.60.zip
)

echo.
echo ===========================================================
echo   [완료] 빌드 성공!
echo   결과 : release\%APP_FOLDER%_v1.60.zip
echo   테스트 후 메신저올인원.exe 를 배포하세요.
echo ===========================================================
echo.
pause
