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

## Prerequisites

1. **AWS CloudFormation Stack**: The infrastructure lookup workshop stack must be deployed
   - Stack name: `workshop-core-infra-template`
   - Required outputs:
     - `AgentCoreRuntimeExecutionRoleArn`
     - `AgentGatewayClientId`
     - `AgentGatewayClientSecret`
     - `AgentGatewayTokenURL`
     - `AgentGatewayDiscoveryUrl`
     - `AgentCoreGenericGatewayRoleArn`
     - `AgentGatewayS3Bucket`

2. **Running MCP Servers**: Athena and S3Vectors MCP servers must be running
   - Athena MCP: `http://localhost:8001/mcp`
   - S3Vectors MCP: `http://localhost:8002/mcp`

3. **AWS Credentials**: Configured with appropriate permissions for:
   - Bedrock AgentCore
   - CloudFormation
   - S3
   - Cognito

## Installation

1. Install dependencies:
```bash
cd data_discovery_agent/backend/database/mcp/agentcore
pip install -r requirements.txt
```

2. Set up configuration:

**Option A: Automatic setup from CloudFormation**
```bash
python setup_config.py
```
This will automatically populate `config.json` from your CloudFormation stack outputs.

**Option B: Manual setup**
```bash
# Copy the example config
cp config.example.json config.json

# Edit config.json and fill in your values
nano config.json
```

Required configuration values:
- `cognito.client_id` - From CloudFormation output: `AgentGatewayClientId`
- `cognito.client_secret` - From CloudFormation output: `AgentGatewayClientSecret`
- `cognito.token_url` - From CloudFormation output: `AgentGatewayTokenURL`
- `cognito.discovery_url` - From CloudFormation output: `AgentGatewayDiscoveryUrl`
- `agentcore.runtime_execution_role_arn` - From CloudFormation output: `AgentCoreRuntimeExecutionRoleArn`
- `agentcore.gateway_iam_role_arn` - From CloudFormation output: `AgentCoreGenericGatewayRoleArn`
- `s3.gateway_schema_bucket` - From CloudFormation output: `AgentGatewayS3Bucket`

3. Ensure MCP servers are running:
```bash
# In separate terminals
cd data_discovery_agent/backend/database/mcp
python athena_mcp.py
python s3vectors_mcp.py
```

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

After deployment, test the agent:

```bash
python test_agent.py
```

The test script will:
1. Obtain Cognito OAuth token
2. Run predefined test queries
3. Enter interactive mode for custom queries

### Example Test Queries

```
- "List all databases available in Athena"
- "What vector buckets are available in S3 Vectors?"
- "Show me the tables in the sales database"
- "Search for documents about AWS security best practices"
```

## Configuration

### Environment Variables

Set these in your environment or `.env` file:

```bash
# AWS Configuration
AWS_REGION=us-east-1

# MCP Server URLs (if different from defaults)
ATHENA_MCP_URL=http://localhost:8001/mcp
S3VECTORS_MCP_URL=http://localhost:8002/mcp

# Athena Configuration
DEFAULT_S3_OUTPUT_LOCATION=s3://your-bucket/athena-results/

# CloudFormation Stack
CF_STACK_NAME=workshop-core-infra-template
```

### Agent Configuration

Modify `config.py` to customize:
- Agent name
- Model ID (default: Claude Sonnet 4.0)
- Region
- CloudFormation stack name

## Integration with Main Chatbot

This AgentCore deployment is **separate** from the main chatbot system. To integrate:

1. **Add Gateway URL to MCP servers configuration**:
```json
{
  "data_discovery_agentcore": {
    "name": "Data Discovery Agent",
    "transportType": "sse",
    "url": "https://bedrock-agentcore.us-east-1.amazonaws.com/gateways/{gateway-id}",
    "headers": {
      "Authorization": "Bearer {cognito-token}"
    },
    "agent_type": "Data Discovery",
    "description": "Unified agent for Athena and S3Vectors data discovery"
  }
}
```

2. **Handle OAuth token refresh** in your main chatbot system

## Troubleshooting

### Deployment Issues

**Problem**: CloudFormation stack not found
```
Solution: Ensure the workshop-core-infra-template stack is deployed
```

**Problem**: MCP servers not accessible
```
Solution: Verify MCP servers are running on localhost:8001 and localhost:8002
```

**Problem**: Docker build fails
```
Solution: Check Docker is installed and running
```

### Runtime Issues

**Problem**: Agent returns authentication errors
```
Solution: Verify Cognito credentials are correct and token is not expired
```

**Problem**: Agent cannot access MCP tools
```
Solution: Ensure MCP server URLs are accessible from AgentCore Runtime
Note: You may need to deploy MCP servers to accessible endpoints
```

## Security Considerations

1. **Read-Only Operations**: The agent only performs read-only operations
2. **OAuth Authentication**: All requests require valid Cognito OAuth tokens
3. **IAM Roles**: AgentCore Runtime uses restricted IAM roles
4. **Tool Consent Bypass**: Enabled for smoother UX (safe due to read-only operations)

## Cost Considerations

- **AgentCore Runtime**: Charged per invocation and compute time
- **Bedrock Model**: Claude Sonnet 4.0 usage charges
- **Data Transfer**: S3 and network transfer costs
- **Athena Queries**: Charged per data scanned

## Next Steps

1. **Monitor Performance**: Use CloudWatch to monitor agent performance
2. **Add More Tools**: Extend with additional MCP tools as needed
3. **Optimize Prompts**: Refine system prompts for better responses
4. **Scale**: Configure auto-scaling for production workloads

## Support

For issues or questions:
1. Check CloudWatch logs for AgentCore Runtime
2. Review MCP server logs
3. Verify CloudFormation stack outputs
4. Test MCP servers independently

## References

- [AWS Bedrock AgentCore Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-agentcore.html)
- [Strands SDK Documentation](https://github.com/awslabs/strands)
- [Infrastructure Lookup Agent Workshop](../../../infrastructure_lookup_agent/)
