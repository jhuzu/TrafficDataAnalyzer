@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [錯誤] 尚未安裝必要套件，現在將開啟安裝程式。
  call "安裝Windows依賴.bat"
  if errorlevel 1 exit /b 1
)

.venv\Scripts\python.exe -c "import openpyxl, pptx, PIL" >nul 2>nul || (
  echo [錯誤] 套件不完整，現在將重新安裝。
  call "安裝Windows依賴.bat"
  if errorlevel 1 exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue) { exit 1 }"
if errorlevel 1 (
  echo [錯誤] 8765 連接埠已被其他程式使用。請先關閉另一個工具視窗後再試。
  pause
  exit /b 1
)

start "" http://127.0.0.1:8765
.venv\Scripts\python.exe web_server.py
