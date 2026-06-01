@echo off
title DreamWeaver
cd /d "E:\AI_Claude\OpenClaw DreamWeaver"

echo ========================================
echo  🌙 DreamWeaver 梦境自主进化引擎
echo ========================================
echo.

REM 检查是否已有服务在运行
netstat -ano | findstr ":8000" | findstr "LISTENING" >nul
if %errorlevel% equ 0 (
    echo ✅ API Server 已在运行 (端口 8000)
) else (
    echo 🚀 启动 API Server (DeepSeek V4 Pro)...
    start "DreamWeaver-Server" cmd /c "python -m openclaw_plugins.dreamweaver serve --port 8000 & pause"
    echo 等待 6 秒让服务启动...
    timeout /t 6 /nobreak >nul
)

REM 打开 Dashboard
echo 📊 打开控制面板...
start "" "E:\AI_Claude\OpenClaw DreamWeaver\dashboard.html"

echo.
echo ========================================
echo   Server: http://127.0.0.1:8000
echo   Docs:   http://127.0.0.1:8000/docs
echo   Panel:  dashboard.html
echo ========================================
echo.
pause
