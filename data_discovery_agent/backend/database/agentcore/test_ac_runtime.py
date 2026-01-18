import boto3
import json
from botocore.exceptions import ClientError

# Initialize the Bedrock AgentCore client
client = boto3.client('bedrock-agentcore', region_name='us-east-1')
runtime_arn = 'arn:aws:bedrock-agentcore:us-east-1:444206144756:runtime/s3vectors_mcp_serv-osYSNhCy2h'


def call_mcp(method, params=None):
    """
    Call an MCP method on the agent runtime.
    
    Args:
        method: The MCP method to call (e.g., 'tools/list', 'tools/call')
        params: Optional parameters for the method
    
    Returns:
        The result from the MCP response
    """
    if params is None:
        params = {}

    payload = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params
    }).encode()

    try:
        response = client.invoke_agent_runtime(
            agentRuntimeArn=runtime_arn,
            payload=payload,
            qualifier='DEFAULT',
            contentType='application/json',
            accept='application/json, text/event-stream'
        )

        raw = response['response'].read().decode()
        json_data = json.loads(raw[raw.find('{'):])
        return json_data['result']

    except ClientError as e:
        print(f"\n{'=' * 60}")
        print("Error Response:")
        print(json.dumps(e.response, indent=2, default=str))
        print(f"{'=' * 60}\n")
        raise


def main():
    # List available tools
    print("=== Available Tools ===")
    tools_result = call_mcp("tools/list")
    for tool in tools_result['tools']:
        print(f"  {tool['name']}: {tool['description']}")
    print()

    # Example: Call greet_user tool
    print("list_vector_buckets()")
    greet_result = call_mcp("tools/call", {
        "name": "list_vector_buckets"
    })
    print(greet_result)


if __name__ == "__main__":
    main()
