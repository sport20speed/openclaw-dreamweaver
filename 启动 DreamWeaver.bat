@echo off
title 🌙 DreamWeaver
cd /d "E:\AI_Claude\OpenClaw DreamWeaver"

echo ========================================
echo   🌙 DreamWeaver · 午夜天文台
echo ========================================

netstat -ano | findstr ":8000" | findstr "LISTENING" >nul
if %errorlevel% neq 0 (
    echo 🚀 Starting Server...
    start "DreamWeaver-Server" cmd /c "cd /d E:\AI_Claude\OpenClaw DreamWeaver && python -m openclaw_plugins.dreamweaver serve --port 8000"
    timeout /t 5 /nobreak >nul
) else (
    echo ✅ Server already running
)
start "" "E:\AI_Claude\OpenClaw DreamWeaver\dashboard.html"
echo 🌙 Done
timeout /t 2 /nobreak >nul
