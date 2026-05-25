@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT_DIR=%~dp0"
if "%ROOT_DIR:~-1%"=="\" set "ROOT_DIR=%ROOT_DIR:~0,-1%"

set "BACKEND_DIR=%ROOT_DIR%\backend"
set "FRONTEND_DIR=%ROOT_DIR%\frontend"
set "BACKEND_PORT=8000"
set "FRONTEND_PORT=3001"
set "FRONTEND_ALREADY_RUNNING=0"

set "PY_EXE=%BACKEND_DIR%\.venv\Scripts\python.exe"
set "NODE_EXE=C:\Program Files\nodejs\node.exe"
set "NEXT_BIN=%FRONTEND_DIR%\node_modules\next\dist\bin\next"

echo.
echo LocalMind OS launcher
echo =====================

if not exist "%PY_EXE%" (
  echo [error] Backend virtual environment not found: "%PY_EXE%"
  exit /b 1
)

if not exist "%FRONTEND_DIR%\node_modules" (
  echo [error] Frontend dependencies are missing: "%FRONTEND_DIR%\node_modules"
  exit /b 1
)

call :is_port_listening %BACKEND_PORT%
set "BACKEND_ALREADY_RUNNING=0"
if not errorlevel 1 set "BACKEND_ALREADY_RUNNING=1"
call :ensure_frontend_port

if not exist "%FRONTEND_DIR%\.next\BUILD_ID" (
  echo [build] Frontend production build missing. Running next build...
  pushd "%FRONTEND_DIR%" >nul
  call npm run build
  if errorlevel 1 (
    popd >nul
    echo [error] Frontend build failed.
    exit /b 1
  )
  popd >nul
)

if "%BACKEND_ALREADY_RUNNING%"=="1" (
  echo [info] Backend already running on http://localhost:%BACKEND_PORT%
) else (
  echo [start] Launching backend on http://localhost:%BACKEND_PORT%
  start "LocalMind Backend" /min cmd /c ""%BACKEND_DIR%\run_backend.cmd""

echo [wait] Waiting for backend...
  call :wait_for_port %BACKEND_PORT% 40
  if errorlevel 1 (
    echo [error] Backend did not start on port %BACKEND_PORT%.
    exit /b 1
  )
)

if "%FRONTEND_ALREADY_RUNNING%"=="1" (
  echo [info] Frontend already running on http://localhost:%FRONTEND_PORT%
) else (
  echo [start] Launching frontend on http://localhost:%FRONTEND_PORT%
  start "" /min /D "%FRONTEND_DIR%" "%NODE_EXE%" "%NEXT_BIN%" start -p %FRONTEND_PORT%

  echo [wait] Waiting for frontend...
  call :wait_for_port %FRONTEND_PORT% 40
  if errorlevel 1 (
    echo [error] Frontend did not start on port %FRONTEND_PORT%.
    exit /b 1
  )
)

echo.
echo LocalMind OS is running.
echo Frontend: http://localhost:%FRONTEND_PORT%
echo Backend:  http://localhost:%BACKEND_PORT%
echo Docs:     http://localhost:%BACKEND_PORT%/docs
echo.
echo If the vault is locked, unlock it in the browser to continue.
exit /b 0

:ensure_frontend_port
call :is_port_listening 3001
if not errorlevel 1 (
  set "FRONTEND_PORT=3001"
  set "FRONTEND_ALREADY_RUNNING=1"
  goto :eof
)

call :is_port_listening 3000
if not errorlevel 1 (
  set "FRONTEND_PORT=3000"
  set "FRONTEND_ALREADY_RUNNING=1"
  goto :eof
)

set "FRONTEND_PORT=3001"
set "FRONTEND_ALREADY_RUNNING=0"
goto :eof

:ensure_port_free
call :is_port_listening %1
if errorlevel 1 goto :eof
echo [info] Port %1 is already in use. Reusing the existing listener.
goto :eof

:is_port_listening
netstat -ano | findstr /r /c:":%1 .*LISTENING" >nul 2>&1
exit /b %errorlevel%

:wait_for_port
set "WAIT_PORT=%~1"
set /a "WAIT_RETRIES=%~2"
:wait_loop
call :is_port_listening %WAIT_PORT%
if not errorlevel 1 exit /b 0
set /a WAIT_RETRIES-=1
if !WAIT_RETRIES! LEQ 0 exit /b 1
ping 127.0.0.1 -n 2 >nul
goto :wait_loop
