@echo off
chcp 65001 >nul
title Nha cua Bug - Live tuong tac TikTok
cd /d "%~dp0"

echo ============================================
echo   NHA CUA BUG - LIVE TUONG TAC TIKTOK
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo [LOI] Chua co Python. Hay cai Python 3.11+ tu python.org
  echo Nho tick o "Add Python to PATH" khi cai dat.
  pause
  exit /b 1
)

if not exist ".venv" (
  echo Lan dau chay: dang tao moi truong va cai thu vien, mat 1-2 phut...
  python -m venv .venv
  call ".venv\Scripts\activate.bat"
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
) else (
  call ".venv\Scripts\activate.bat"
)

echo.
echo Trang dieu khien se tu mo. San khau: http://lvh.me:3000/stage
echo De dung: dong cua so nay hoac Ctrl+C
echo.
start "" "http://localhost:3000"
python app.py
pause
