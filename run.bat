@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe ( echo Спершу запусти setup.bat & pause & exit /b 1 )
echo Перевіряю бібліотеки...
.venv\Scripts\python.exe -m pip install -q -r requirements.txt
set /p Q="Введи питання до агента: "
.venv\Scripts\python.exe agent.py "%Q%"
pause
