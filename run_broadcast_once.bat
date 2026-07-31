@echo off
cd /d "%~dp0"
set "PYTHON_EXE=C:\Users\yaros\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if not exist "%PYTHON_EXE%" (
  echo Не найден встроенный Python runtime.
  pause
  exit /b 1
)

"%PYTHON_EXE%" -m app.main --mode broadcast-once
echo.
echo Разовая рассылка завершена.
pause
