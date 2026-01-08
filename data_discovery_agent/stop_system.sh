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

# Kill any existing process on port 5000
kill_port 5000
kill_port 3000