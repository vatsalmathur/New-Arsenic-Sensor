@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
	echo AquaSentry virtual environment not found.
	echo Run: python -m venv .venv
	echo Then: .venv\Scripts\python.exe -m pip install -r requirements.txt
	pause
	exit /b 1
)

start "AquaSentry API" /D "%~dp0" ".venv\Scripts\python.exe" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
start "AquaSentry Website" /D "%~dp0frontend" ".venv\Scripts\python.exe" -m http.server 8001

timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:8001/index.html"

echo AquaSentry is running.
echo Website: http://127.0.0.1:8001/index.html
echo API docs: http://127.0.0.1:8000/docs
echo Close the two server windows to stop AquaSentry.
pause
