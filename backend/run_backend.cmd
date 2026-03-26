@echo off
setlocal

set "APP_DIR=C:\Users\vinay\OneDrive\Desktop\LOCALMIND OS\backend"
set "PY_EXE=%APP_DIR%\.venv\Scripts\python.exe"
set "LOG_OUT=%APP_DIR%\server.out.log"
set "LOG_ERR=%APP_DIR%\server.err.log"

cd /d "%APP_DIR%"

if not exist "%PY_EXE%" (
  echo Python virtual environment not found: %PY_EXE%>>"%LOG_ERR%"
  exit /b 1
)

"%PY_EXE%" -m uvicorn main:app --host 0.0.0.0 --port 8000 1>>"%LOG_OUT%" 2>>"%LOG_ERR%"

endlocal
