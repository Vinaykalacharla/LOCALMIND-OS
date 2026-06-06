#!/usr/bin/env bash

set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

BACKEND_PORT=8000
FRONTEND_PORT=3001
FRONTEND_ALREADY_RUNNING=0
BACKEND_ALREADY_RUNNING=0

PY_EXE="$BACKEND_DIR/.venv/bin/python"
NODE_EXE="$(command -v node || true)"

echo ""
echo "LocalMind OS launcher"
echo "====================="

if [ ! -f "$PY_EXE" ]; then
    echo "[error] Backend virtual environment not found: $PY_EXE"
    exit 1
fi

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    echo "[error] Frontend dependencies are missing: $FRONTEND_DIR/node_modules"
    exit 1
fi

is_port_listening() {
    if command -v lsof >/dev/null 2>&1; then
        lsof -i :$1 -sTCP:LISTEN >/dev/null 2>&1
    elif command -v netstat >/dev/null 2>&1; then
        netstat -tuln | grep ":$1 " >/dev/null 2>&1
    else
        # Fallback if neither lsof nor netstat is available
        nc -z localhost $1 >/dev/null 2>&1
    fi
    return $?
}

if is_port_listening $BACKEND_PORT; then
    BACKEND_ALREADY_RUNNING=1
fi

if is_port_listening 3001; then
    FRONTEND_PORT=3001
    FRONTEND_ALREADY_RUNNING=1
elif is_port_listening 3000; then
    FRONTEND_PORT=3000
    FRONTEND_ALREADY_RUNNING=1
fi

if [ ! -f "$FRONTEND_DIR/.next/BUILD_ID" ]; then
    echo "[build] Frontend production build missing. Running next build..."
    pushd "$FRONTEND_DIR" >/dev/null
    if ! npm run build; then
        popd >/dev/null
        echo "[error] Frontend build failed."
        exit 1
    fi
    popd >/dev/null
fi

if [ "$BACKEND_ALREADY_RUNNING" = "1" ]; then
    echo "[info] Backend already running on http://localhost:$BACKEND_PORT"
else
    echo "[start] Launching backend on http://localhost:$BACKEND_PORT"
    if [ -f "$BACKEND_DIR/run_backend.sh" ]; then
        bash "$BACKEND_DIR/run_backend.sh" &
    else
        pushd "$BACKEND_DIR" >/dev/null
        "$PY_EXE" -m uvicorn app.main:app --host 127.0.0.1 --port $BACKEND_PORT &
        popd >/dev/null
    fi

    echo "[wait] Waiting for backend..."
    WAIT_RETRIES=40
    while ! is_port_listening $BACKEND_PORT; do
        WAIT_RETRIES=$((WAIT_RETRIES-1))
        if [ $WAIT_RETRIES -le 0 ]; then
            echo "[error] Backend did not start on port $BACKEND_PORT."
            exit 1
        fi
        sleep 0.5
    done
fi

if [ "$FRONTEND_ALREADY_RUNNING" = "1" ]; then
    echo "[info] Frontend already running on http://localhost:$FRONTEND_PORT"
else
    echo "[start] Launching frontend on http://localhost:$FRONTEND_PORT"
    pushd "$FRONTEND_DIR" >/dev/null
    npm run start -- -p $FRONTEND_PORT &
    popd >/dev/null

    echo "[wait] Waiting for frontend..."
    WAIT_RETRIES=40
    while ! is_port_listening $FRONTEND_PORT; do
        WAIT_RETRIES=$((WAIT_RETRIES-1))
        if [ $WAIT_RETRIES -le 0 ]; then
            echo "[error] Frontend did not start on port $FRONTEND_PORT."
            exit 1
        fi
        sleep 0.5
    done
fi

echo ""
echo "LocalMind OS is running."
echo "Frontend: http://localhost:$FRONTEND_PORT"
echo "Backend:  http://localhost:$BACKEND_PORT"
echo "Docs:     http://localhost:$BACKEND_PORT/docs"
echo ""
echo "If the vault is locked, unlock it in the browser to continue."
