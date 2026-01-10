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

# Kill processes on all used ports
kill_port 8001  # Athena MCP
kill_port 8002  # S3 Vectors MCP
kill_port 5001  # Flask Backend
kill_port 3000  # React Frontend