# Data Discovery Agent

A multi-agent data discovery and analytics platform that connects to multiple database systems through Model Context Protocol (MCP) servers. The agent provides intelligent data exploration, automated dashboard generation, and comprehensive business analysis reports.

![Data Discovery Agent](https://img.shields.io/badge/Status-Production%20Ready-green)
![Python](https://img.shields.io/badge/Python-3.12+-blue)
![React](https://img.shields.io/badge/React-18.3+-blue)
![License](https://img.shields.io/badge/License-MIT-green)

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