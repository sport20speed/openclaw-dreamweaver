@echo off
title DreamWeaver - 停止服务
cd /d "E:\AI_Claude\OpenClaw DreamWeaver"

echo 正在停止 DreamWeaver Server...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%p >nul 2>&1
    if !errorlevel! equ 0 (
        echo ✅ Server 已停止 (PID: %%p)
    )
)
timeout /t 1 /nobreak >nul
echo 已完成
pause
