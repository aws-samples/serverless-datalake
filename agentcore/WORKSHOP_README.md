# AgentCore MCP Deployment Workshop

## Overview

This workshop notebook (`AgentCore_MCP_Deployment.ipynb`) provides a step-by-step guide to deploying Model Context Protocol (MCP) servers to AWS Bedrock AgentCore Gateway.

## What's New

The notebook has been restructured from the original `deploy_agent.py` script to be more educational and workshop-friendly:

### Key Improvements

1. **Clear Structure** - Each step is in its own cell with detailed markdown explanations
2. **Educational Content** - Explains WHY each step is needed, not just HOW
3. **Visual Aids** - ASCII diagrams showing architecture and authentication flow
4. **Progress Tracking** - Clear indication of what's happening at each stage
5. **Time Estimates** - Lets users know when to expect longer operations
6. **Troubleshooting** - Common issues and solutions included
7. **Next Steps** - Guidance on what to do after deployment

### Workshop Structure

The notebook is organized into 11 main steps:

1. **Install Dependencies** - Set up required packages
2. **Import & Configure** - Initialize environment
3. **Load Configuration** - Read config.json settings
4. **Create IAM Roles** - Set up Gateway and Runtime roles
5. **Create Cognito Pools** - Configure authentication
6. **Create Gateway** - Deploy the AgentCore Gateway
7. **Deploy Athena MCP** - Deploy data lake query server
8. **Deploy S3Vectors MCP** - Deploy semantic search server
9. **Create OAuth Provider** - Set up Gateway-to-Runtime auth
10. **Create Gateway Targets** - Connect MCP servers to Gateway
11. **Verify Deployment** - Confirm everything works

### Running the Workshop

```bash
# Open the notebook in Jupyter
jupyter notebook AgentCore_MCP_Deployment.ipynb

# Or use JupyterLab
jupyter lab AgentCore_MCP_Deployment.ipynb
```

### Prerequisites

- AWS Account with appropriate permissions
- Python 3.9+
- AWS CLI configured
- `config.json` file with your settings:
  ```json
  {
    "DEFAULT_S3_OUTPUT_LOCATION": "s3://your-bucket/athena-results/",
    "WORKGROUP": "your-workgroup"
  }
  ```

### Time Required

- **Total Time**: 30-45 minutes
- **Active Time**: 10-15 minutes (rest is waiting for deployments)
- **Longest Steps**: Steps 7 & 8 (MCP server deployments, 5-10 min each)

### Output

After completion, you'll have:

- ✅ Fully deployed AgentCore Gateway
- ✅ Two MCP servers (Athena + S3Vectors)
- ✅ Complete authentication setup
- ✅ `deployment_info.json` with all connection details

### Differences from Original Script

| Original `deploy_agent.py` | New Workshop Notebook |
|----------------------------|----------------------|
| Single `main()` function | 11 separate, executable cells |
| Minimal explanations | Detailed markdown documentation |
| Command-line script | Interactive Jupyter notebook |
| All-or-nothing execution | Step-by-step with pauses |
| No visual aids | Architecture diagrams included |
| Technical focus | Educational focus |

### Regenerating the Notebook

If you need to regenerate the notebook:

```bash
python create_workshop_notebook.py
```

This will recreate `AgentCore_MCP_Deployment.ipynb` with the latest structure.

## Support

For issues or questions:
1. Check the Troubleshooting section in the notebook
2. Review CloudWatch logs for detailed error messages
3. Verify IAM permissions and Cognito configuration

## Resources

- [AWS Bedrock AgentCore Documentation](https://docs.aws.amazon.com/bedrock/)
- [Model Context Protocol Specification](https://modelcontextprotocol.io/)
- [AgentCore Starter Toolkit](https://github.com/awslabs/amazon-bedrock-agentcore-samples)
