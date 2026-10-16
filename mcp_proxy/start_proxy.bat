@echo off
REM Xbrain MCPO 代理启动/保活脚本（watchdog）
REM 每 30 秒检查一次 /health，异常则重启 uvicorn
cd /d "%~dp0.."
:loop
curl -s -o nul -w "%%{http_code}" http://127.0.0.1:8765/health 2>nul | findstr "200" >nul
if errorlevel 1 (
    echo [%date% %time%] (re)starting proxy >> mcp_proxy\proxy.log
    start /b "" C:\Python314\python.exe -m uvicorn main:app --app-dir mcp_proxy --host 127.0.0.1 --port 8765 >> mcp_proxy\proxy.log 2>&1
    timeout /t 5 /nobreak >nul
)
timeout /t 30 /nobreak >nul
goto loop
