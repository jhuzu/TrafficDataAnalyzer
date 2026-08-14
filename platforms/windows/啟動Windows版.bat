@echo off
chcp 65001 >nul
setlocal
set "PROJECT_ROOT=%~dp0..\.."
cd /d "%PROJECT_ROOT%"

if not exist ".venv\Scripts\python.exe" (
  echo [錯誤] 尚未安裝必要套件，現在將開啟安裝程式。
  call "%~dp0安裝Windows依賴.bat"
  if errorlevel 1 exit /b 1
)

.venv\Scripts\python.exe -c "import openpyxl, pptx, PIL" >nul 2>nul || (
  echo [錯誤] 套件不完整，現在將重新安裝。
  call "%~dp0安裝Windows依賴.bat"
  if errorlevel 1 exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue) { exit 1 }"
if errorlevel 1 (
  echo [資訊] 工具已經在執行，現在開啟瀏覽器。
  start "" http://127.0.0.1:8765
  exit /b 0
)

start "" http://127.0.0.1:8765
.venv\Scripts\python.exe web_server.py
