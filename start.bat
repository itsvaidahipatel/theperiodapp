@echo off
echo ========================================
echo   Starting Period GPT2 Application
echo ========================================

REM Check if backend virtual environment exists
if not exist "backend\venv" (
    echo Backend virtual environment not found. Creating one...
    cd backend
    python -m venv venv
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
    cd ..
)

REM Check if frontend node_modules exists
if not exist "frontend\node_modules" (
    echo Frontend dependencies not found. Installing...
    cd frontend
    call npm install
    cd ..
)

REM Start backend
echo Starting backend server on http://localhost:8000
cd backend
call venv\Scripts\activate.bat
start "Backend Server" cmd /k "uvicorn main:app --reload --host 0.0.0.0 --port 8000"
cd ..

REM Wait a moment for backend to start
timeout /t 2 /nobreak >nul

REM Start frontend
echo Starting frontend server on http://localhost:5173
cd frontend
start "Frontend Server" cmd /k "npm run dev"
cd ..

echo ========================================
echo Application is running!
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:5173
echo API Docs: http://localhost:8000/docs
echo ========================================
echo Close the windows to stop the servers
pause

