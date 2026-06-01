@echo off
title 🌙 DreamWeaver
cd /d "E:\AI_Claude\OpenClaw DreamWeaver"

netstat -ano | findstr ":8000" | findstr "LISTENING" >nul
if %errorlevel% neq 0 (
    echo 🚀 Starting Server...
    start "" cmd /c "python -m openclaw_plugins.dreamweaver serve --port 8000"
    timeout /t 5 /nobreak >nul
) else (
    echo ✅ Server running
)
start "" "E:\AI_Claude\OpenClaw DreamWeaver\dashboard.html"
echo 🌙 Done
