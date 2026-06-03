@echo off
title 🌙 DreamWeaver + pi
cd /d "E:\AI_Claude\OpenClaw DreamWeaver"

echo ========================================
echo   🌙 DreamWeaver + pi 集成启动
echo ========================================
echo.

rem ── Check / start DreamWeaver Server ──
netstat -ano | findstr ":8000" | findstr "LISTENING" >nul
if %errorlevel% neq 0 (
    echo 🚀 Starting DreamWeaver Server on :8000...
    start "DreamWeaver-Server" cmd /c "cd /d E:\AI_Claude\OpenClaw DreamWeaver && python -m openclaw_plugins.dreamweaver serve --port 8000"
    timeout /t 5 /nobreak >nul
) else (
    echo ✅ DreamWeaver Server already running on :8000
)

rem ── Open Dashboard (optional) ──
start "" "E:\AI_Claude\OpenClaw DreamWeaver\dashboard.html"

echo.
echo ✅ pi 扩展已安装: dreamweaver.ts
echo    LLM 可通过 8 个 dream_* 工具和 /dream 命令操作 DreamWeaver
echo.
echo    /dream status      — 查看当前梦境状态
echo    /dream start 母题  — 开始一个新梦
echo    /dream stop        — 停止当前梦境
echo    /dream history     — 查看历史梦境
echo.
echo 🚀 启动 pi...
echo.

pi
