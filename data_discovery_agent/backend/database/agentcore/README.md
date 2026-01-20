# Data Discovery Agent - AgentCore Deployment

This directory contains the AgentCore Runtime deployment for the Data Discovery Agent, which integrates Athena and S3Vectors MCP tools into a single Strands agent deployed on AWS Bedrock AgentCore.

## Overview

The Data Discovery Agent provides a unified interface for:
- **AWS Athena**: Query structured data in data lakes using SQL
- **AWS S3 Vectors**: Perform semantic search over vector embeddings

This agent is deployed separately from the main chatbot system and can be accessed via AgentCore Gateway.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Data Discovery Agent                      │
│                  (AgentCore Runtime)                         │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         Strands Agent (Claude Sonnet 4.0)            │  │
│  │                                                       │  │
│  │  ┌─────────────────┐    ┌──────────────────┐       │  │
│  │  │  Athena MCP     │    │  S3Vectors MCP   │       │  │
│  │  │  - List DBs     │    │  - List Buckets  │       │  │
│  │  │  - Query SQL    │    │  - Query Vectors │       │  │
│  │  │  - Get Metadata │    │  - Semantic Search│       │  │
│  │  └─────────────────┘    └──────────────────┘       │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
                  ┌──────────────────┐
                  │ AgentCore Gateway│
                  │  (MCP Protocol)  │
                  └──────────────────┘
                            │
                            ▼
                  ┌──────────────────┐
                  │  Cognito OAuth   │
                  │  Authentication  │
                  └──────────────────┘
```

## Files

- **`config.py`**: Configuration management for AgentCore deployment
- **`data_discovery_strands_agent.py`**: Main agent implementation with MCP tools
- **`deploy_agent.py`**: Deployment script for AgentCore Runtime
- **`test_agent.py`**: Test suite for the deployed agent
- **`requirements.txt`**: Python dependencies

## Installation

1. Install dependencies:
```bash
cd data_discovery_agent/backend/database/mcp/agentcore
pip install -r requirements.txt
```

2. Set `DEFAULT_S3_OUTPUT_LOCATION` and `WORKGROUP` as environment variables or in the config.json file

## Deployment

Deploy the agent to AgentCore Runtime:

```bash
python deploy_agent.py
```

This script will:
1. Load configuration from CloudFormation
2. Configure AgentCore Runtime with the agent
3. Build and deploy Docker container
4. Create AgentCore Gateway
5. Set up OAuth authentication
6. Generate and upload OpenAPI schema

**Note**: The deployment process takes several minutes as it builds and deploys the Docker container.

## Testing

After deployment, test the agentcore gateway:

```bash
python test_gateway.py
```
