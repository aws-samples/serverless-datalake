# Data Discovery Agent

A multi-agent data discovery and analytics platform that connects to multiple database systems through Model Context Protocol (MCP) servers. The agent provides intelligent data exploration, automated dashboard generation, and comprehensive business analysis reports.

![Data Discovery Agent](https://img.shields.io/badge/Status-Production%20Ready-green)
![Python](https://img.shields.io/badge/Python-3.12+-blue)
![React](https://img.shields.io/badge/React-18.3+-blue)
![License](https://img.shields.io/badge/License-MIT-green)

## 🔄 How It Works - Complete Workflow

### 1. **User Query Initiation**
- User submits a natural language query through the React frontend
- Query is sent via WebSocket/REST API to the Flask backend
- System initializes session management and conversation tracking

### 2. **Orchestrator Agent Classification**
- **Orchestrator Agent** receives the user request
- Analyzes the query using advanced NLP to understand intent and requirements
- Classifies the problem type (data exploration, dashboard creation, analysis, etc.)
- Identifies the most appropriate specialist agent(s) to handle the request
- Creates an execution plan with ordered agent calls
- **Human-in-the-Loop**: Optionally presents the plan to user for confirmation (configurable)

### 3. **Specialist Agent Execution**
- **Specialist Agent** (Athena, Glue, EMR, MySQL, etc.) receives the enhanced query with context
- Agent explores available tools and database schemas systematically
- Calls relevant **MCP tools** to:
  - Discover database structures and tables
  - Execute queries and retrieve data
  - Perform data transformations
  - Generate insights and analysis

### 4. **Tool Approval Process** (Security Layer)
- If a tool requires approval (configurable per tool/risk level):
  - **Approval request** is sent back to the user via frontend
  - User can **approve**, **deny**, or set **"always approve"** for specific tools
  - System caches approval decisions for session efficiency
  - Tool execution proceeds only after approval

### 5. **Response Collection & Context Building**
- Agent responses are **accumulated** (not overwritten) to build comprehensive context
- Each subsequent agent receives the full context from previous agents
- System prevents redundant work by sharing discovered information
- **Data collection** happens across multiple database sources simultaneously

### 6. **Response Verification & Quality Check**
- **Verifier Agent** evaluates if the collected responses adequately answer the user's query
- Checks for:
  - Query completeness and accuracy
  - Data quality and consistency
  - Missing information or gaps
  - Tool execution errors
- Determines if additional agent calls are needed

### 7. **Dashboard Generation** (Optional)
- If dashboard creation is requested:
  - **Schema Analyzer Agent** suggests appropriate visualizations based on data characteristics
  - **Dashboard Designer Agent** processes and validates data for visualization
  - **HTML Generator Agent** creates interactive dashboards with Chart.js/D3.js
  - Generated dashboards are saved to `generated_dashboards/` directory

### 8. **Business Analysis & Summarization**
- **Response Summarizer** creates comprehensive business analysis reports
- Generates:
  - Executive summaries with key insights
  - Actionable recommendations
  - Risk assessments and trend analysis
  - HTML reports with visualizations
- Reports are saved to `generated_reports/` directory

### 9. **Final Response Delivery**
- **Summarized response** is sent back to the user in markdown format
- Includes:
  - Direct answers to the user's questions
  - Data insights and patterns discovered
  - Links to generated dashboards and reports
  - Recommendations for further analysis
- Real-time streaming updates keep user informed throughout the process

### 10. **Session Management & Cleanup**
- Conversation history is managed with configurable summarization
- Session data is persisted for continuity
- Resources are cleaned up appropriately
- Metrics and logs are recorded for monitoring

## 🔧 Key Technical Features

### **Multi-Agent Coordination**
- Agents work collaboratively, sharing context and avoiding duplicate work
- Sophisticated response accumulation prevents information loss
- Intelligent retry mechanisms handle failures gracefully

### **Security & Governance**
- Granular tool approval system with risk-based categorization
- Configurable approval requirements per tool/operation
- Session-based approval caching for user experience
- Comprehensive audit logging

### **Scalability & Performance**
- Configurable limits on dataset collection and processing
- Efficient conversation summarization for long sessions
- Streaming responses for real-time user feedback
- Resource cleanup and memory management

### **Extensibility**
- Plugin architecture for new database connectors
- Configurable agent behavior and rules
- Flexible visualization and reporting templates
- Easy integration with new MCP servers

---

## 🚀 Features

### 🤖 Multi-Agent Intelligence
- **Orchestrator Agent**: Coordinates multiple specialized agents for complex queries
- **Database Agents**: Specialized agents for different database systems (Athena, MySQL, ClickHouse, etc.)
- **Dashboard Builder**: Automatically generates interactive dashboards from collected data
- **Verifier Agent**: Ensures query completeness and data quality
- **Business Analyst**: Creates comprehensive analysis reports with actionable insights

### 📊 Dashboard Generation
- **Automatic Visualization**: Intelligently selects appropriate chart types based on data characteristics
- **Interactive Charts**: Built with Chart.js and D3.js for rich interactivity
- **Responsive Design**: Works seamlessly across desktop, tablet, and mobile devices
- **Export Capabilities**: Export dashboards as HTML, PDF, PNG, or CSV
- **Real-time Updates**: Live dashboard generation with streaming progress updates

### 🔍 Data Discovery
- **Natural Language Queries**: Ask questions in plain English about your data
- **Cross-Database Analysis**: Query multiple database systems simultaneously
- **Schema Discovery**: Automatically explore and understand database structures
- **Data Quality Assessment**: Identify data issues and provide recommendations
- **Pattern Recognition**: Discover trends and insights across datasets

### 🛠️ Database Connectivity
- **AWS Athena**: Query data lakes and S3-based analytics
- **AWS Glue**: Data catalog management and ETL operations
- **Amazon EMR**: Big data processing and analytics
- **MySQL**: Traditional relational database support
- **ClickHouse**: High-performance analytics database
- **Extensible Architecture**: Easy to add new database connectors via MCP

### 🎯 Business Intelligence
- **Automated Reports**: Generate comprehensive business analysis reports
- **Key Insights Extraction**: Identify the most important data points
- **Actionable Recommendations**: Specific steps based on data analysis
- **Risk Assessment**: Identify concerning trends and issues
- **Executive Summaries**: Concise overviews for stakeholders

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (React)                         │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐│
│  │   Chat Interface│ │   Dashboard     │ │   History       ││
│  │                 │ │   Viewer        │ │   Management    ││
│  └─────────────────┘ └─────────────────┘ └─────────────────┘│
└─────────────────────────────────────────────────────────────┘
                              │
                    WebSocket/REST API
                              │
┌─────────────────────────────────────────────────────────────┐
│                Backend (Flask + SocketIO)                   │
│  ┌─────────────────────────────────────────────────────────┐│
│  │              Multi-Agent Orchestrator                   ││
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐││
│  │  │Orchestrator │ │  Verifier   │ │  Dashboard Builder  │││
│  │  │   Agent     │ │   Agent     │ │      Agent          │││
│  │  └─────────────┘ └─────────────┘ └─────────────────────┘││
│  └─────────────────────────────────────────────────────────┘│
│                              │                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                MCP Client Layer                         ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
                              │
                        MCP Protocol
                              │
┌─────────────────────────────────────────────────────────────┐
│                    MCP Servers                              │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────┐│
│  │   Athena    │ │    Glue     │ │    MySQL    │ │   ...   ││
│  │   Server    │ │   Server    │ │   Server    │ │         ││
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────┘│
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                   Data Sources                              │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────┐│
│  │     S3      │ │  RDS/MySQL  │ │ ClickHouse  │ │   ...   ││
│  │ Data Lakes  │ │ Databases   │ │ Analytics   │ │         ││
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────┘│
└─────────────────────────────────────────────────────────────┘
```

## 📋 Prerequisites

### System Requirements
- **Python**: 3.12 or higher
- **Node.js**: 22.0 or higher
- **Memory**: Minimum 4GB RAM (8GB recommended)
- **Storage**: 2GB free space

### AWS Requirements (for AWS integrations)
- AWS CLI configured with appropriate credentials
- InstanceProfile role on the EC2 should have appropriate permissions for:
  - Amazon Athena (query execution, data catalog access)
  - AWS Glue (data catalog read/write, job management)
  - Amazon EMR (cluster management, job execution)
  - Amazon S3 (bucket access for query results and data)

### Database Access
- Network connectivity to target databases
- Appropriate database credentials and permissions
- For cloud databases: security group/firewall configurations

## 🚀 Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/aws-samples/serverless-datalake.git
cd data_discovery_agent
```

### 2. Backend Setup
### TODO Start the MCP before starting the backend. Work on a script to start entire system.
```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure MCP servers (see Configuration section)
cp mcp_servers.json.example mcp_servers.json
# Edit mcp_servers.json with your database configurations

# Start the backend
python app.py
```

### 3. Frontend Setup
```bash
# Navigate to frontend directory (in a new terminal)
cd frontend

# Install dependencies
npm install

# Start the development server
npm run dev
```

### 4. Access the Application
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:5000
- **Health Check**: http://localhost:5000/health

### Environment Variables

```bash
# AWS Configuration
export AWS_REGION=us-east-1
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
```

## 📖 Usage Guide

### Basic Data Exploration

1. **Start a Conversation**: Open the chat interface and ask natural language questions
   ```
   "Show me all tables in the sales database"
   "What are the top 10 customers by revenue this year?"
   "Create a dashboard showing monthly sales trends"
   ```

2. **Review Agent Plans**: The system will present an execution plan for approval
   - Review which agents will be used
   - Confirm or modify the approach
   - Monitor real-time progress

3. **Explore Results**: 
   - View data in structured tables
   - Generate interactive visualizations
   - Export results in multiple formats

## 🛠️ Development

### Project Structure
```
data_discovery_agent/
├── backend/                    # Python Flask backend
│   ├── config/                # Configuration management
│   ├── database/              # Database clients and MCP integration
│   ├── monitoring/            # Metrics and monitoring
│   ├── tests/                 # Backend tests
│   ├── logs/                  # Application logs
│   ├── app.py                 # Main Flask application
│   ├── requirements.txt       # Python dependencies
│   └── Dockerfile            # Backend container
├── frontend/                  # React frontend
│   ├── src/
│   │   ├── components/       # React components
│   │   ├── contexts/         # React contexts
│   │   ├── utils/           # Utility functions
│   │   └── App.js           # Main React app
│   ├── package.json         # Node.js dependencies
│   └── Dockerfile          # Frontend container
├── generated_dashboards/    # Generated dashboard files
├── generated_reports/       # Generated report files
└── requirements.txt        # Root dependencies
```

### Adding New Database Connectors

1. **Create MCP Server**: Implement MCP server for your database
2. **Configure Connection**: Add server configuration to `mcp_servers.json`
3. **Test Integration**: Verify connection and basic operations
4. **Add Specialized Rules**: Configure agent behavior for the database type

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Model Context Protocol](https://modelcontextprotocol.io/) for the standardized interface
- [Strands Agents](https://strandsagents.com/latest/) for the agent framework
- [Anthropic](https://anthropic.com/) for Claude AI models
- [AWS](https://aws.amazon.com/) for cloud infrastructure and services
- Open source community for various libraries and tools

---

**Built with ❤️ for data professionals who want to unlock insights faster**