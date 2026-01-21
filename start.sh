#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Starting PeriodCycle.AI Application${NC}"
echo -e "${BLUE}  Local Development Environment${NC}"
echo -e "${BLUE}========================================${NC}"

# Function to cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}Shutting down servers...${NC}"
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    exit
}

# Trap Ctrl+C and call cleanup
trap cleanup INT TERM

# Check if backend virtual environment exists
if [ ! -d "backend/venv" ]; then
    echo -e "${YELLOW}Backend virtual environment not found. Creating one...${NC}"
    cd backend
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    cd ..
else
    echo -e "${GREEN}✓ Backend virtual environment found${NC}"
fi

# Check if frontend node_modules exists
if [ ! -d "frontend/node_modules" ]; then
    echo -e "${YELLOW}Frontend dependencies not found. Installing...${NC}"
    cd frontend
    npm install
    cd ..
else
    echo -e "${GREEN}✓ Frontend dependencies found${NC}"
fi

# Check for environment files (optional, just warn)
if [ ! -f "backend/.env" ]; then
    echo -e "${YELLOW}⚠ Backend .env file not found.${NC}"
    echo -e "${CYAN}  Copy backend/.env.example to backend/.env and fill in your values${NC}"
    echo -e "${CYAN}  This is required for the application to work properly${NC}"
fi

if [ ! -f "frontend/.env.local" ]; then
    echo -e "${CYAN}ℹ Frontend .env.local not found. Using default (http://localhost:8000)${NC}"
    echo -e "${CYAN}  Copy frontend/.env.local.example to frontend/.env.local to customize${NC}"
fi

# Start backend
echo -e "${GREEN}Starting backend server on http://localhost:8000${NC}"
cd backend
source venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
cd ..

# Wait a moment for backend to start
sleep 2

# Start frontend
echo -e "${GREEN}Starting frontend server on http://localhost:5173${NC}"
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}✓ Application is running!${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "${CYAN}Frontend: http://localhost:5173${NC}"
echo -e "${CYAN}Backend:  http://localhost:8000${NC}"
echo -e "${CYAN}API Docs: http://localhost:8000/docs${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "${YELLOW}💡 Tip: Make changes to your code and see them update instantly!${NC}"
echo -e "${YELLOW}💡 Tip: No need to push to GitHub to test locally${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop both servers${NC}"
echo -e "${BLUE}========================================${NC}"

# Wait for both processes
wait

