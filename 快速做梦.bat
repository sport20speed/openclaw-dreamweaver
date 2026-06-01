@echo off
title DreamWeaver - 快速做梦
cd /d "E:\AI_Claude\OpenClaw DreamWeaver"

set /p motif="请输入母题（直接回车用'提升日常工作效率'）: "
if "%motif%"=="" set motif=提升日常工作效率

echo.
echo 🌙 梦境启动: %motif%
echo.

python -m openclaw_plugins.dreamweaver run --motif "%motif%" --iterations 3 --output .\%motif%.json

echo.
echo ✅ 完成！结果已保存到 %motif%.json
pause
