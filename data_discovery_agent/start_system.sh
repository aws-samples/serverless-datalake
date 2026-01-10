#!/bin/bash

# MCP Dashboard System Startup Script
# This script starts all components of the MCP Dashboard system

set -e

# Show usage if help is requested
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo "🚀 MCP Dashboard System Startup Script"
    echo "======================================"
    echo ""
    echo "Usage:"
    echo "  ./start_system.sh              - Start all services with logs saved to files"
    echo "  ./start_system.sh --show-logs  - Start all services and show logs in real-time"
    echo "  ./start_system.sh --quiet      - Start all services with minimal logging"
    echo "  ./start_system.sh --help       - Show this help message"
    echo ""
    echo "Services:"
    echo "  - Athena MCP (port 8001)"
    echo "  - S3 Vectors MCP (port 8002)"
    echo "  - Flask Backend (port 5001)"
    echo "  - React Frontend (port 3000)"
    echo ""
    exit 0
fi

# Set logging level and show logs flag
LOGGING_LEVEL="ERROR"
SHOW_LOGS=false

if [ "$1" = "--quiet" ]; then
    LOGGING_LEVEL="CRITICAL"
    echo -e "${YELLOW}Running in quiet mode with minimal logging${NC}"
elif [ "$1" = "--show-logs" ]; then
    LOGGING_LEVEL="INFO"
    SHOW_LOGS=true
    echo -e "${YELLOW}Running with real-time log display${NC}"
fi

# Export logging level for Python applications
export PYTHONLOG=$LOGGING_LEVEL

# Create backend logs directory if it doesn't exist
mkdir -p logs

echo "🚀 Starting MCP Dashboard System..."
echo "=================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to check if a port is in use
check_port() {
    if lsof -Pi :$1 -sTCP:LISTEN -t >/dev/null ; then
        return 0
    else
        return 1
    fi
}

# Function to wait for a service to be ready
wait_for_service() {
    local port=$1
    local service_name=$2
    local max_attempts=30
    local attempt=1
    
    echo -e "${BLUE}Waiting for $service_name to be ready on port $port...${NC}"
    
    while [ $attempt -le $max_attempts ]; do
        if check_port $port; then
            echo -e "${GREEN}✅ $service_name is ready!${NC}"
            return 0
        fi
        
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    echo -e "${RED}❌ $service_name failed to start within $((max_attempts * 2)) seconds${NC}"
    return 1
}

# Check if required directories exist
if [ ! -d "backend" ]; then
    echo -e "${RED}❌ backend directory not found${NC}"
    exit 1
fi

if [ ! -d "frontend" ]; then
    echo -e "${RED}❌ frontend directory not found${NC}"
    exit 1
fi

# Check if MCP startup scripts exist
if [ ! -f "backend/start_athena_mcp.py" ]; then
    echo -e "${RED}❌ Athena MCP startup script not found${NC}"
    exit 1
fi

if [ ! -f "backend/start_s3vectors_mcp.py" ]; then
    echo -e "${RED}❌ S3 Vectors MCP startup script not found${NC}"
    exit 1
fi

# Check if Python is available
if ! command -v python &> /dev/null; then
    echo -e "${RED}❌ Python 3 is not installed${NC}"
    exit 1
fi

# Check if Node.js is available
if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ Node.js is not installed${NC}"
    exit 1
fi

# Check if npm is available
if ! command -v npm &> /dev/null; then
    echo -e "${RED}❌ npm is not installed${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Prerequisites check passed${NC}"

# Function to start a service in the background
start_service() {
    local name=$1
    local command=$2
    local log_file="backend/logs/${name}.log"
    
    # Create backend logs directory if it doesn't exist
    mkdir -p backend/logs
    
    echo -e "${BLUE}Starting $name...${NC}"
    
    if [ "$SHOW_LOGS" = true ]; then
        # Start the service and show logs in real-time
        eval "$command 2>&1 | tee $log_file &"
    else
        # Start the service and redirect output to log file only
        eval "$command > $log_file 2>&1 &"
    fi
    
    echo $! > "backend/logs/${name}.pid"
}

# Function to stop a service
stop_service() {
    local name=$1
    local pid_file=""
    
    if [ "$name" = "athena-mcp-server" ]; then
        pid_file="backend/logs/${name}.pid"
    else
        pid_file="backend/logs/${name}.pid"
    fi
    
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if kill -0 $pid 2>/dev/null; then
            echo -e "${YELLOW}Stopping $name (PID: $pid)...${NC}"
            kill $pid
            rm "$pid_file"
        fi
    fi
}

# Function to kill any process running on a specific port
kill_port() {
    local port=$1
    local pids=$(lsof -ti:$port 2>/dev/null)
    
    if [ ! -z "$pids" ]; then
        echo -e "${YELLOW}Killing processes running on port $port...${NC}"
        echo "$pids" | xargs kill -9
        sleep 1
        echo -e "${GREEN}✅ Port $port is now free${NC}"
    else
        echo -e "${GREEN}✅ Port $port is already free${NC}"
    fi
}

# Function to show logs in real-time
show_logs() {
    local name=$1
    local log_file="logs/${name}.log"
    
    if [ -f "$log_file" ]; then
        echo -e "${BLUE}📋 Showing logs for $name:${NC}"
        echo -e "${BLUE}================================${NC}"
        tail -f "$log_file" &
        local tail_pid=$!
        echo $tail_pid > "logs/${name}-tail.pid"
    else
        echo -e "${RED}❌ Log file not found for $name${NC}"
    fi
}

# Function to cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}🛑 Shutting down services...${NC}"
    
    # Stop tail processes
    for tail_pid_file in backend/logs/*-tail.pid; do
        if [ -f "$tail_pid_file" ]; then
            local tail_pid=$(cat "$tail_pid_file")
            if kill -0 $tail_pid 2>/dev/null; then
                kill $tail_pid
            fi
            rm "$tail_pid_file"
        fi
    done
    
    # Stop main services
    stop_service "athena-mcp-server"
    stop_service "s3vectors-mcp-server"
    stop_service "flask-backend"
    stop_service "react-frontend"
    echo -e "${GREEN}✅ All services stopped${NC}"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Start MCP Servers
echo -e "\n${BLUE}📡 Starting MCP Servers...${NC}"

# Kill any existing processes on MCP ports
kill_port 8001
kill_port 8002

# Start Athena MCP Server
cd backend
# Create logs directory in current directory (backend/)
mkdir -p logs
echo -e "${BLUE}Starting athena-mcp-server...${NC}"

if [ "$SHOW_LOGS" = true ]; then
    # Start the service and show logs in real-time
    eval "PYTHONLOG=$LOGGING_LEVEL python start_athena_mcp.py 2>&1 | tee logs/athena-mcp-server.log &"
else
    # Start the service and redirect output to log file only
    eval "PYTHONLOG=$LOGGING_LEVEL python start_athena_mcp.py > logs/athena-mcp-server.log 2>&1 &"
fi

echo $! > "logs/athena-mcp-server.pid"

# Start S3 Vectors MCP Server
echo -e "${BLUE}Starting s3vectors-mcp-server...${NC}"

if [ "$SHOW_LOGS" = true ]; then
    # Start the service and show logs in real-time
    eval "PYTHONLOG=$LOGGING_LEVEL python start_s3vectors_mcp.py 2>&1 | tee logs/s3vectors-mcp-server.log &"
else
    # Start the service and redirect output to log file only
    eval "PYTHONLOG=$LOGGING_LEVEL python start_s3vectors_mcp.py > logs/s3vectors-mcp-server.log 2>&1 &"
fi

echo $! > "logs/s3vectors-mcp-server.pid"
cd ..

# Wait for MCP servers to be ready
wait_for_service 8001 "Athena MCP Server"
wait_for_service 8002 "S3 Vectors MCP Server"

echo -e "${GREEN}✅ MCP Servers are running${NC}"

# Start Flask Backend
echo -e "\n${BLUE}🔧 Starting Flask Backend...${NC}"

# Kill any existing process on port 5001
kill_port 5001
kill_port 3000
cd backend
start_service "flask-backend" "PYTHONLOG=$LOGGING_LEVEL python app.py"
cd ..

# Wait for backend to be ready
wait_for_service 5001 "Flask Backend"

# Start React Frontend
echo -e "\n${BLUE}🎨 Starting React Frontend...${NC}"
cd frontend
start_service "react-frontend" "npm run dev"
cd ..

# Wait for frontend to be ready
wait_for_service 3000 "React Frontend"

echo -e "\n${GREEN}🎉 MCP Dashboard System is ready!${NC}"
echo -e "${BLUE}================================${NC}"
echo -e "${GREEN}Frontend:${NC} http://localhost:3000"
echo -e "${GREEN}Backend API:${NC} http://localhost:5001"
echo -e "${GREEN}Athena MCP:${NC} http://localhost:8001/mcp"
echo -e "${GREEN}S3 Vectors MCP:${NC} http://localhost:8002/mcp"

if [ "$SHOW_LOGS" = true ]; then
    echo -e "\n${BLUE}📋 Showing real-time logs (Press Ctrl+C to stop all services):${NC}"
    echo -e "${BLUE}================================================================${NC}"
    
    # Build list of existing log files from backend/logs directory
    log_files=()
    
    # Check for service-specific logs
    for service in "flask-backend" "react-frontend"; do
        log_file="backend/logs/${service}.log"
        if [ -f "$log_file" ]; then
            log_files+=("$log_file")
        fi
    done
    
    # Check for Athena and S3 Vectors MCP server logs (in backend/logs/)
    if [ -f "backend/logs/athena-mcp-server.log" ]; then
        log_files+=("backend/logs/athena-mcp-server.log")
    fi
    
    if [ -f "backend/logs/s3vectors-mcp-server.log" ]; then
        log_files+=("backend/logs/s3vectors-mcp-server.log")
    fi
    
    # Check for existing backend logs
    for existing_log in "logs/backend.log" "logs/database_mcp_clients.log" "logs/athena_mcp.log" "logs/s3vectors_mcp.log"; do
        if [ -f "$existing_log" ]; then
            log_files+=("$existing_log")
        fi
    done
    
    # Remove duplicates
    log_files=($(printf "%s\n" "${log_files[@]}" | sort -u))
    
    # Only tail if we have log files
    if [ ${#log_files[@]} -gt 0 ]; then
        echo -e "${GREEN}Tailing available log files: ${log_files[*]}${NC}"
        tail -f "${log_files[@]}" &
        local tail_pid=$!
        echo $tail_pid > "logs/combined-tail.pid"
    else
        echo -e "${RED}❌ No log files available to tail${NC}"
    fi
else
    echo -e "\n${YELLOW}Press Ctrl+C to stop all services${NC}"
    echo -e "${BLUE}To view logs in real-time, restart with: ./start_system.sh --show-logs${NC}"
    echo -e "${BLUE}Available log files: logs/backend.log, logs/database_mcp_clients.log, logs/athena_mcp.log, logs/s3vectors_mcp.log${NC}"
fi

# Keep the script running
while true; do
    sleep 1
done 