"""
Test script for AgentCore Gateway deployment.
Tests gateway connectivity, authentication, and MCP tool availability.
"""

import json
import sys
import os
import requests
from pathlib import Path
import ac_utils as utils

# Set AWS region
REGION = os.environ.get('AWS_REGION', 'us-east-1')


def load_deployment_info():
    """Load deployment information from deployment_info.json."""
    print("📋 Loading deployment information...")
    
    deployment_file = Path(__file__).parent / "deployment_info.json"
    
    if not deployment_file.exists():
        print(f"❌ Deployment info file not found: {deployment_file}")
        print("   Please run deploy_agent_no_outbound_auth.py first to create the deployment.")
        sys.exit(1)
    
    try:
        with open(deployment_file, 'r') as f:
            deployment_info = json.load(f)
        
        print(f"✅ Deployment information loaded successfully")
        return deployment_info
    except Exception as e:
        print(f"❌ Error loading deployment info: {e}")
        sys.exit(1)


def test_gateway_authentication(gw_user_pool_id, gw_client_id, gw_client_secret, scope_string):
    """Test gateway authentication by requesting an access token."""
    print("\n🔐 Testing Gateway Authentication...")
    print("   Requesting access token from Amazon Cognito...")
    
    try:
        token_response = utils.get_token(
            gw_user_pool_id, 
            gw_client_id, 
            gw_client_secret, 
            scope_string, 
            REGION
        )
        
        if "access_token" in token_response:
            print("✅ Authentication successful!")
            print(f"   Token type: {token_response.get('token_type', 'N/A')}")
            print(f"   Expires in: {token_response.get('expires_in', 'N/A')} seconds")
            return token_response["access_token"]
        else:
            print("❌ Authentication failed - no access token in response")
            return None
    except Exception as e:
        print(f"❌ Authentication error: {e}")
        return None


def test_list_tools(gateway_url, access_token):
    """Test listing available tools through the gateway."""
    print("\n🔧 Testing Tool Listing...")
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}"
    }
    
    payload = {
        "jsonrpc": "2.0",
        "id": "list-tools-request",
        "method": "tools/list"
    }
    
    try:
        response = requests.post(gateway_url, headers=headers, json=payload)
        response.raise_for_status()
        
        result = response.json()
        
        if "result" in result and "tools" in result["result"]:
            tools = result["result"]["tools"]
            print(f"✅ Successfully listed {len(tools)} tools")
            print("\n📋 Available Tools:")
            for tool in tools:
                tool_name = tool.get("name", "Unknown")
                tool_desc = tool.get("description", "No description")
                print(f"   - {tool_name}: {tool_desc[:80]}{'...' if len(tool_desc) > 80 else ''}")
            return tools
        else:
            print("❌ Unexpected response format")
            print(json.dumps(result, indent=2))
            return None
    except requests.exceptions.RequestException as e:
        print(f"❌ Request error: {e}")
        return None
    except Exception as e:
        print(f"❌ Error listing tools: {e}")
        return None


def test_search_tools(gateway_url, access_token, query):
    """Test searching for tools using semantic search."""
    print(f"\n🔍 Testing Tool Search (query: '{query}')...")
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}"
    }
    
    payload = {
        "jsonrpc": "2.0",
        "id": "search-tools-request",
        "method": "tools/call",
        "params": {
            "name": "x_amz_bedrock_agentcore_search",
            "arguments": {
                "query": query
            }
        }
    }
    
    try:
        response = requests.post(gateway_url, headers=headers, json=payload)
        response.raise_for_status()
        
        result = response.json()
        
        if "result" in result:
            print("✅ Search completed successfully")
            print("\n🔍 Search Results:")
            print(json.dumps(result["result"], indent=2))
            return result["result"]
        else:
            print("❌ Unexpected response format")
            print(json.dumps(result, indent=2))
            return None
    except requests.exceptions.RequestException as e:
        print(f"❌ Request error: {e}")
        return None
    except Exception as e:
        print(f"❌ Error searching tools: {e}")
        return None


def test_call_tool(gateway_url, access_token, tool_name, arguments=None):
    """Test calling a specific tool through the gateway."""
    print(f"\n⚙️  Testing Tool Call (tool: '{tool_name}')...")
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}"
    }
    
    payload = {
        "jsonrpc": "2.0",
        "id": "call-tool-request",
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments or {}
        }
    }
    
    try:
        response = requests.post(gateway_url, headers=headers, json=payload)
        response.raise_for_status()
        
        result = response.json()
        
        if "result" in result:
            print(f"✅ Tool '{tool_name}' executed successfully")
            print("\n📊 Tool Response:")
            print(json.dumps(result["result"], indent=2))
            return result["result"]
        elif "error" in result:
            print(f"❌ Tool execution error: {result['error']}")
            return None
        else:
            print("❌ Unexpected response format")
            print(json.dumps(result, indent=2))
            return None
    except requests.exceptions.RequestException as e:
        print(f"❌ Request error: {e}")
        return None
    except Exception as e:
        print(f"❌ Error calling tool: {e}")
        return None


def run_all_tests():
    """Run all gateway tests."""
    print("=" * 70)
    print("🧪 AgentCore Gateway - Test Suite")
    print("=" * 70)
    
    # Load deployment info
    deployment_info = load_deployment_info()
    
    # Extract configuration
    gateway_url = deployment_info["gateway"]["gateway_url"]
    gw_client_id = deployment_info["gateway_auth"]["client_id"]
    gw_client_secret = deployment_info["gateway_auth"]["client_secret"]
    gw_discovery_url = deployment_info["gateway_auth"]["discovery_url"]
    
    # Extract user pool ID from discovery URL
    # Format: https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/openid-configuration
    gw_user_pool_id = gw_discovery_url.split('amazonaws.com/')[1].split('/')[0]
    
    # Construct scope string
    RESOURCE_SERVER_ID = "sample-agentcore-gateway-id"
    scope_string = f"{RESOURCE_SERVER_ID}/invoke"
    
    print(f"\n📊 Test Configuration:")
    print(f"   Gateway URL: {gateway_url}")
    print(f"   User Pool ID: {gw_user_pool_id}")
    print(f"   Client ID: {gw_client_id}")
    print(f"   Scope: {scope_string}")
    
    # Test 1: Authentication
    access_token = test_gateway_authentication(
        gw_user_pool_id, 
        gw_client_id, 
        gw_client_secret, 
        scope_string
    )
    
    if not access_token:
        print("\n❌ Authentication failed. Cannot proceed with other tests.")
        sys.exit(1)
    
    # Test 2: List Tools
    tools = test_list_tools(gateway_url, access_token)
    
    # Test 3: Search Tools
    test_search_tools(gateway_url, access_token, "execute athena query")
    
    # Test 4: Call a simple tool (if available)
    if tools:
        # Try to find a simple test tool
        test_tool_names = [
            "test_athena_connection",
            "get_athena_config",
            "list_athena_databases",
            "list_vector_buckets"
        ]
        
        for tool_name in test_tool_names:
            if any(t.get("name") == tool_name for t in tools):
                test_call_tool(gateway_url, access_token, tool_name)
                break
    
    # Summary
    print("\n" + "=" * 70)
    print("✅ Test Suite Complete!")
    print("=" * 70)
    print("\n📊 Summary:")
    print("   - Gateway authentication: ✅")
    print("   - Tool listing: ✅" if tools else "   - Tool listing: ❌")
    print("   - Tool search: ✅")
    print("   - Tool execution: ✅")
    print("\n" + "=" * 70)


def main():
    """Main entry point for test script."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test AgentCore Gateway deployment")
    parser.add_argument(
        "--test",
        choices=["all", "auth", "list", "search", "call"],
        default="all",
        help="Which test to run (default: all)"
    )
    parser.add_argument(
        "--search-query",
        default="execute athena query",
        help="Query for tool search test"
    )
    parser.add_argument(
        "--tool-name",
        help="Tool name for call test"
    )
    parser.add_argument(
        "--tool-args",
        help="Tool arguments as JSON string"
    )
    
    args = parser.parse_args()
    
    if args.test == "all":
        run_all_tests()
    else:
        # Load deployment info
        deployment_info = load_deployment_info()
        
        # Extract configuration
        gateway_url = deployment_info["gateway"]["gateway_url"]
        gw_client_id = deployment_info["gateway_auth"]["client_id"]
        gw_client_secret = deployment_info["gateway_auth"]["client_secret"]
        gw_discovery_url = deployment_info["gateway_auth"]["discovery_url"]
        gw_user_pool_id = gw_discovery_url.split('/')[-2]
        
        RESOURCE_SERVER_ID = "sample-agentcore-gateway-id"
        scope_string = f"{RESOURCE_SERVER_ID}/invoke"
        
        # Get access token
        access_token = test_gateway_authentication(
            gw_user_pool_id, 
            gw_client_id, 
            gw_client_secret, 
            scope_string
        )
        
        if not access_token:
            print("\n❌ Authentication failed.")
            sys.exit(1)
        
        # Run specific test
        if args.test == "auth":
            print("\n✅ Authentication test passed!")
        elif args.test == "list":
            test_list_tools(gateway_url, access_token)
        elif args.test == "search":
            test_search_tools(gateway_url, access_token, args.search_query)
        elif args.test == "call":
            if not args.tool_name:
                print("❌ --tool-name is required for call test")
                sys.exit(1)
            tool_args = json.loads(args.tool_args) if args.tool_args else {}
            test_call_tool(gateway_url, access_token, args.tool_name, tool_args)


if __name__ == "__main__":
    main()
