@echo off
echo Stopping Python processes...
powershell.exe -NoProfile -Command "Stop-Process -Name python -Force" 2>nul
timeout /t 1 /nobreak >nul
echo Starting server on port 8100...
cd /d C:\Users\Zhangwenye\Desktop\spring-data-agent\python-agent-v2
start "PythonAgentServer" cmd /c "python -m uvicorn app.main:app --host 0.0.0.0 --port 8100 --reload"
echo Server started. Check http://127.0.0.1:8100/docs
pause
