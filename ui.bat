@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe ( echo Спершу запусти setup.bat & pause & exit /b 1 )
echo Перевіряю бібліотеки...
.venv\Scripts\python.exe -m pip install -q -r requirements.txt
echo Запускаю вебінтерфейс: http://localhost:8501
echo Щоб зупинити — закрий це вікно.
start "" cmd /c "timeout /t 6 >nul & start http://localhost:8501"
.venv\Scripts\python.exe -m streamlit run app.py --server.headless true --browser.gatherUsageStats false --client.toolbarMode minimal
pause
