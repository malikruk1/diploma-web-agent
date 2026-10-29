@echo off
chcp 65001 >nul
cd /d "%~dp0"
setlocal

set "PYDIR=D:\Python312"
set "PYURL=https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe"
set "PYEXE=%TEMP%\python-3.12.10-amd64.exe"

rem ---- 1. Знаходимо або встановлюємо Python ----
set "PY="
if exist "%PYDIR%\python.exe" set "PY=%PYDIR%\python.exe"
if not defined PY where python >nul 2>&1 && python --version >nul 2>&1 && set "PY=python"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"

if not defined PY (
  echo Python не знайдено.
  echo Завантажую Python 3.12 з python.org ^(~25 МБ^)...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol='Tls12'; Invoke-WebRequest -Uri '%PYURL%' -OutFile '%PYEXE%' -UseBasicParsing"
  if not exist "%PYEXE%" ( echo [ПОМИЛКА] Не вдалося завантажити Python & goto :manual )
  echo Встановлюю Python у %PYDIR% ^(1-2 хвилини, вікон не буде^)...
  "%PYEXE%" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_launcher=0 TargetDir="%PYDIR%"
  if exist "%PYDIR%\python.exe" set "PY=%PYDIR%\python.exe"
)

if not defined PY goto :manual

echo Використовую Python: %PY%

rem ---- 2. Віртуальне середовище в цій папці ----
if not exist .venv\Scripts\python.exe (
  echo Створюю віртуальне середовище...
  "%PY%" -m venv .venv
  if errorlevel 1 ( echo [ПОМИЛКА] Не вдалося створити .venv & pause & exit /b 1 )
)

rem ---- 3. Бібліотеки ----
echo Встановлюю бібліотеки ^(1-3 хвилини^)...
.venv\Scripts\python.exe -m pip install --upgrade pip >nul
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 ( echo [ПОМИЛКА] Не вдалося встановити бібліотеки & pause & exit /b 1 )

rem ---- 4. Файл з ключами ----
if not exist .env copy .env.example .env >nul

echo.
echo ================================================
echo Готово! Відкрий файл .env Блокнотом, впиши ключ
echo у рядок OPENAI_API_KEY= і запусти run.bat
echo ================================================
pause
exit /b 0

:manual
echo.
echo [ПОМИЛКА] Не вдалося встановити Python автоматично.
echo Встанови вручну з https://www.python.org/downloads/
echo і постав галочку "Add python.exe to PATH". Потім запусти setup.bat ще раз.
pause
exit /b 1
