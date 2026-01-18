"""
Deploy MCP Servers (Athena and S3Vectors) to AgentCore Gateway as targets.
Based on: https://github.com/awslabs/amazon-bedrock-agentcore-samples/blob/main/01-tutorials/02-AgentCore-gateway/05-mcp-server-as-a-target/01-mcp-server-target.ipynb
"""

import boto3
import json
import sys
import os
import logging
from pathlib import Path
from bedrock_agentcore_starter_toolkit import Runtime
from boto3.session import Session
import ac_utils as utils

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler()]
)
logging.getLogger("strands").setLevel(logging.INFO)

# Set AWS region
os.environ['AWS_DEFAULT_REGION'] = os.environ.get('AWS_REGION', 'us-east-1')
REGION = os.environ['AWS_DEFAULT_REGION']


def load_config():
    """Load configuration from config.json file."""
    print("📋 Loading configuration from config.json...")
    
    config_path = Path(__file__).parent / "config.json"
    
    if not config_path.exists():
        print(f"❌ Configuration file not found: {config_path}")
        sys.exit(1)
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        print(f"✅ Configuration loaded successfully")
        return config
    except Exception as e:
        print(f"❌ Error loading configuration: {e}")
        sys.exit(1)


def create_runtime_execution_role():
    """Create or update IAM role for AgentCore Runtime with Athena and S3Vectors permissions."""
    print("\n🔐 Creating/Updating IAM role for AgentCore Runtime...")
    
    role_name = "agentcore-runtime-mcp-data-role"
    iam_client = boto3.client('iam')
    
    try:
        # Try to get existing role first
        try:
            response = iam_client.get_role(RoleName=role_name)
            role_arn = response['Role']['Arn']
            print(f"⚠️  Role '{role_name}' already exists - updating policies...")
            
            # Delete all existing inline policies
            try:
                policies = iam_client.list_role_policies(RoleName=role_name, MaxItems=100)
                for policy_name in policies.get('PolicyNames', []):
                    iam_client.delete_role_policy(RoleName=role_name, PolicyName=policy_name)
                    print(f"   Deleted old policy: {policy_name}")
            except Exception as e:
                print(f"   Warning: Could not delete old policies: {e}")
            
            # Recreate with updated permissions
            agentcore_runtime_iam_role = utils.create_agentcore_runtime_role_with_data_permissions("mcp-data")
            role_arn = agentcore_runtime_iam_role['Role']['Arn']
            print(f"✅ Runtime IAM role updated: {role_arn}")
            return role_arn
            
        except iam_client.exceptions.NoSuchEntityException:
            # Role doesn't exist, create it
            print(f"   Role '{role_name}' not found, creating new one...")
            agentcore_runtime_iam_role = utils.create_agentcore_runtime_role_with_data_permissions("mcp-data")
            role_arn = agentcore_runtime_iam_role['Role']['Arn']
            print(f"✅ Runtime IAM role created: {role_arn}")
            return role_arn
    except Exception as e:
        print(f"❌ Error with Runtime IAM role: {e}")
        sys.exit(1)


def create_gateway_iam_role():
    """Create or update IAM role for the Gateway to assume."""
    print("\n🔐 Creating/Updating IAM role for AgentCore Gateway...")
    
    role_name = "ac-gw-mcp-role"
    iam_client = boto3.client('iam')
    
    try:
        # Try to get existing role first
        try:
            response = iam_client.get_role(RoleName=role_name)
            role_arn = response['Role']['Arn']
            print(f"⚠️  Role '{role_name}' already exists - updating policies...")
            
            # Delete all existing inline policies
            try:
                policies = iam_client.list_role_policies(RoleName=role_name, MaxItems=100)
                for policy_name in policies.get('PolicyNames', []):
                    iam_client.delete_role_policy(RoleName=role_name, PolicyName=policy_name)
                    print(f"   Deleted old policy: {policy_name}")
            except Exception as e:
                print(f"   Warning: Could not delete old policies: {e}")
            
            # Recreate with updated permissions
            agentcore_gateway_iam_role = utils.create_agentcore_gateway_role(role_name)
            role_arn = agentcore_gateway_iam_role['Role']['Arn']
            print(f"✅ Gateway IAM role updated: {role_arn}")
            return role_arn
            
        except iam_client.exceptions.NoSuchEntityException:
            # Role doesn't exist, create it
            print(f"   Role '{role_name}' not found, creating new one...")
            agentcore_gateway_iam_role = utils.create_agentcore_gateway_role(role_name)
            role_arn = agentcore_gateway_iam_role['Role']['Arn']
            print(f"✅ Gateway IAM role created: {role_arn}")
            return role_arn
    except Exception as e:
        print(f"❌ Error with Gateway IAM role: {e}")
        sys.exit(1)


def create_cognito_pool_for_gateway():
    """Create or get existing Amazon Cognito Pool for inbound authorization to Gateway."""
    print("\n🔑 Creating/Getting Cognito Pool for Gateway (Inbound Auth)...")
    
    USER_POOL_NAME = "sample-agentcore-gateway-pool"
    RESOURCE_SERVER_ID = "sample-agentcore-gateway-id"
    RESOURCE_SERVER_NAME = "sample-agentcore-gateway-name"
    CLIENT_NAME = "sample-agentcore-gateway-client"
    SCOPES = [
        {
            "ScopeName": "invoke",
            "ScopeDescription": "Scope for invoking the agentcore gateway"
        },
    ]
    
    scope_names = [f"{RESOURCE_SERVER_ID}/{scope['ScopeName']}" for scope in SCOPES]
    scope_string = " ".join(scope_names)
    
    cognito = boto3.client("cognito-idp", region_name=REGION)
    
    try:
        # Create or retrieve user pool (utils function already handles this)
        gw_user_pool_id = utils.get_or_create_user_pool(cognito, USER_POOL_NAME)
        print(f"   User Pool ID: {gw_user_pool_id}")
        
        # Create or retrieve resource server (utils function already handles this)
        utils.get_or_create_resource_server(
            cognito, gw_user_pool_id, RESOURCE_SERVER_ID, RESOURCE_SERVER_NAME, SCOPES
        )
        print("   Resource server ensured")
        
        # Create or retrieve M2M client (utils function already handles this)
        gw_client_id, gw_client_secret = utils.get_or_create_m2m_client(
            cognito, gw_user_pool_id, CLIENT_NAME, RESOURCE_SERVER_ID, scope_names
        )
        
        # Get discovery URL
        gw_cognito_discovery_url = f'https://cognito-idp.{REGION}.amazonaws.com/{gw_user_pool_id}/.well-known/openid-configuration'
        
        print(f"✅ Gateway Cognito Pool ready")
        print(f"   Client ID: {gw_client_id}")
        print(f"   Discovery URL: {gw_cognito_discovery_url}")
        
        return {
            "user_pool_id": gw_user_pool_id,
            "client_id": gw_client_id,
            "client_secret": gw_client_secret,
            "discovery_url": gw_cognito_discovery_url,
            "scope_string": scope_string
        }
    except Exception as e:
        print(f"⚠️  Error with Cognito Pool: {e}")
        print(f"   Continuing with execution...")
        raise


def create_cognito_pool_for_runtime():
    """Create or get existing Amazon Cognito Pool for inbound authorization to Runtime (outbound for Gateway)."""
    print("\n🔑 Creating/Getting Cognito Pool for Runtime (Outbound Auth for Gateway)...")
    
    USER_POOL_NAME = "sample-agentcore-runtime-pool"
    RESOURCE_SERVER_ID = "sample-agentcore-runtime-id"
    RESOURCE_SERVER_NAME = "sample-agentcore-runtime-name"
    CLIENT_NAME = "sample-agentcore-runtime-client"
    SCOPES = [
        {
            "ScopeName": "invoke",
            "ScopeDescription": "Scope for invoking the agentcore runtime"
        },
    ]
    
    scope_names = [f"{RESOURCE_SERVER_ID}/{scope['ScopeName']}" for scope in SCOPES]
    scope_string = " ".join(scope_names)
    
    cognito = boto3.client("cognito-idp", region_name=REGION)
    
    try:
        # Create or retrieve user pool (utils function already handles this)
        runtime_user_pool_id = utils.get_or_create_user_pool(cognito, USER_POOL_NAME)
        print(f"   User Pool ID: {runtime_user_pool_id}")
        
        # Create or retrieve resource server (utils function already handles this)
        utils.get_or_create_resource_server(
            cognito, runtime_user_pool_id, RESOURCE_SERVER_ID, RESOURCE_SERVER_NAME, SCOPES
        )
        print("   Resource server ensured")
        
        # Create or retrieve M2M client (utils function already handles this)
        runtime_client_id, runtime_client_secret = utils.get_or_create_m2m_client(
            cognito, runtime_user_pool_id, CLIENT_NAME, RESOURCE_SERVER_ID, scope_names
        )
        
        # Get discovery URL
        runtime_cognito_discovery_url = f'https://cognito-idp.{REGION}.amazonaws.com/{runtime_user_pool_id}/.well-known/openid-configuration'
        
        print(f"✅ Runtime Cognito Pool ready")
        print(f"   Client ID: {runtime_client_id}")
        print(f"   Discovery URL: {runtime_cognito_discovery_url}")
        
        return {
            "user_pool_id": runtime_user_pool_id,
            "client_id": runtime_client_id,
            "client_secret": runtime_client_secret,
            "discovery_url": runtime_cognito_discovery_url,
            "scope_string": scope_string
        }
    except Exception as e:
        print(f"⚠️  Error with Runtime Cognito Pool: {e}")
        print(f"   Continuing with execution...")
        raise


def create_agentcore_gateway(gateway_role_arn, gw_cognito_config):
    """Create the AgentCore Gateway or get existing one."""
    print("\n🌐 Creating/Getting AgentCore Gateway...")
    
    gateway_name = 'ac-gateway-mcp-server'
    
    try:
        gateway_client = boto3.client('bedrock-agentcore-control', region_name=REGION)
        
        # Try to list existing gateways to see if one with this name exists
        try:
            list_response = gateway_client.list_gateways()
            existing_gateways = list_response.get('items', [])  # API returns 'items' not 'gateways'
            
            for gateway in existing_gateways:
                if gateway.get('name') == gateway_name:
                    gateway_id = gateway.get('gatewayId')
                    # Get full gateway details to get the URL
                    gateway_details = gateway_client.get_gateway(gatewayIdentifier=gateway_id)
                    gateway_url = gateway_details.get('gatewayUrl')
                    print(f"✅ Using existing Gateway")
                    print(f"   Gateway ID: {gateway_id}")
                    print(f"   Gateway URL: {gateway_url}")
                    return {
                        "gateway_id": gateway_id,
                        "gateway_url": gateway_url
                    }
        except Exception as list_error:
            print(f"   Could not list gateways: {list_error}")
        
        # Gateway doesn't exist, create it
        print(f"   Gateway '{gateway_name}' not found, creating new one...")
        
        auth_config = {
            "customJWTAuthorizer": {
                "allowedClients": [gw_cognito_config["client_id"]],
                "discoveryUrl": gw_cognito_config["discovery_url"]
            }
        }
        
        create_response = gateway_client.create_gateway(
            name=gateway_name,
            roleArn=gateway_role_arn,
            protocolType='MCP',
            protocolConfiguration={
                'mcp': {
                    'supportedVersions': ['2025-03-26'],
                    'searchType': 'SEMANTIC'
                }
            },
            authorizerType='CUSTOM_JWT',
            authorizerConfiguration=auth_config,
            description='AgentCore Gateway with MCP Server targets (Athena + S3Vectors)'
        )
        
        gateway_id = create_response["gatewayId"]
        gateway_url = create_response["gatewayUrl"]
        
        print(f"✅ Gateway created successfully")
        print(f"   Gateway ID: {gateway_id}")
        print(f"   Gateway URL: {gateway_url}")
        
        return {
            "gateway_id": gateway_id,
            "gateway_url": gateway_url
        }
    except Exception as e:
        print(f"❌ Error with Gateway: {e}")
        sys.exit(1)


def deploy_mcp_server_to_runtime(mcp_file, agent_name, runtime_role_arn, runtime_cognito_config, config, env_vars=None):
    """
    Deploy an MCP server to AgentCore Runtime.
    
    Args:
        mcp_file: Name of the MCP server file (e.g., 'athena_mcp.py')
        agent_name: Name for the agent
        runtime_role_arn: ARN of the IAM role for Runtime execution
        runtime_cognito_config: Runtime Cognito configuration
        config: Application configuration
        env_vars: Optional environment variables to set
    
    Returns:
        Dictionary with agent_arn, agent_id, and agent_url
    """
    print(f"\n🚀 Deploying {mcp_file} to AgentCore Runtime...")
    
    # Get the directory where this script is located
    script_dir = Path(__file__).parent
    
    # Verify required files exist in the script directory
    required_files = [mcp_file, 'requirements.txt']
    for file in required_files:
        file_path = script_dir / file
        if not file_path.exists():
            raise FileNotFoundError(f"Required file {file} not found at {file_path}")
    print("   All required files found ✓")
    
    # Save current directory and change to script directory
    original_dir = os.getcwd()
    os.chdir(script_dir)
    print(f"   Working directory: {script_dir}")
    
    try:
        # Initialize Runtime
        agentcore_runtime = Runtime()
        
        # Configure auth
        auth_config = {
            "customJWTAuthorizer": {
                "allowedClients": [runtime_cognito_config["client_id"]],
                "discoveryUrl": runtime_cognito_config["discovery_url"]
            }
        }
        
        # Set environment variables if provided
        # if env_vars:
        #     print(f"   Setting environment variables: {list(env_vars.keys())}")
        #     for key, value in env_vars.items():
        #         os.environ[key] = value
        
        # Configure Runtime with custom execution role
        print("   Configuring AgentCore Runtime...")
        print(f"   Using Runtime execution role: {runtime_role_arn}")
        response = agentcore_runtime.configure(
            entrypoint=mcp_file,
            execution_role=runtime_role_arn,  # Use custom role instead of auto-create
            auto_create_ecr=True,
            requirements_file="requirements.txt",
            non_interactive=True,
            region=REGION,
            authorizer_configuration=auth_config,
            protocol="MCP",
            agent_name=agent_name,
            #environment_variables=env_vars or {}
        )
        print("   Configuration completed ✓")
        
        # Launch to Runtime
        print("   Launching MCP server to AgentCore Runtime...")
        print("   This may take several minutes...")
        launch_result = agentcore_runtime.launch(auto_update_on_conflict=True, env_vars=env_vars)
        
        agent_arn = launch_result.agent_arn
        agent_id = launch_result.agent_id
        
        # Construct agent URL
        encoded_arn = agent_arn.replace(':', '%3A').replace('/', '%2F')
        agent_url = f'https://bedrock-agentcore.{REGION}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT'
        
        print(f"✅ {mcp_file} deployed successfully")
        print(f"   Agent ARN: {agent_arn}")
        print(f"   Agent ID: {agent_id}")
        print(f"   Agent URL: {agent_url}")
        
        return {
            "agent_arn": agent_arn,
            "agent_id": agent_id,
            "agent_url": agent_url
        }
    finally:
        # Always restore the original directory
        os.chdir(original_dir)


def create_oauth_credential_provider(runtime_cognito_config):
    """Create AgentCore Identity OAuth credential provider for outbound auth."""
    print("\n🔐 Creating OAuth credential provider for Gateway outbound auth...")
    
    try:
        identity_client = boto3.client('bedrock-agentcore-control', region_name=REGION)
        
        cognito_provider = identity_client.create_oauth2_credential_provider(
            name="ac-gateway-mcp-server-identity",
            credentialProviderVendor="CustomOauth2",
            oauth2ProviderConfigInput={
                'customOauth2ProviderConfig': {
                    'oauthDiscovery': {
                        'discoveryUrl': runtime_cognito_config["discovery_url"],
                    },
                    'clientId': runtime_cognito_config["client_id"],
                    'clientSecret': runtime_cognito_config["client_secret"]
                }
            }
        )
        
        cognito_provider_arn = cognito_provider['credentialProviderArn']
        print(f"✅ OAuth credential provider created")
        print(f"   Provider ARN: {cognito_provider_arn}")
        
        return cognito_provider_arn
    except Exception as e:
        print(f"❌ Error creating OAuth credential provider: {e}")
        sys.exit(1)


def create_gateway_target(gateway_id, agent_url, credential_provider_arn, runtime_scope_string, target_name):
    """Create a Gateway target for an MCP server or get existing one."""
    print(f"\n🎯 Creating/Getting Gateway target: {target_name}...")
    
    try:
        gateway_client = boto3.client('bedrock-agentcore-control', region_name=REGION)
        
        # Try to list existing targets to see if one with this name exists
        try:
            list_response = gateway_client.list_gateway_targets(gatewayIdentifier=gateway_id)
            existing_targets = list_response.get('items', [])  # API returns 'items' not 'targets'
            
            for target in existing_targets:
                if target.get('name') == target_name:
                    target_id = target.get('targetId')
                    print(f"✅ Using existing Gateway target: {target_name}")
                    print(f"   Target ID: {target_id}")
                    return target_id
        except Exception as list_error:
            print(f"   Could not list targets: {list_error}")
        
        # Target doesn't exist, create it
        print(f"   Target '{target_name}' not found, creating new one...")
        
        create_gateway_target_response = gateway_client.create_gateway_target(
            name=target_name,
            gatewayIdentifier=gateway_id,
            targetConfiguration={
                'mcp': {
                    'mcpServer': {
                        'endpoint': agent_url
                    }
                }
            },
            credentialProviderConfigurations=[
                {
                    'credentialProviderType': 'OAUTH',
                    'credentialProvider': {
                        'oauthCredentialProvider': {
                            'providerArn': credential_provider_arn,
                            'scopes': [runtime_scope_string]
                        }
                    }
                },
            ]
        )
        
        target_id = create_gateway_target_response.get('targetId', 'N/A')
        print(f"✅ Gateway target created: {target_name}")
        print(f"   Target ID: {target_id}")
        
        return target_id
    except Exception as e:
        print(f"❌ Error with Gateway target: {e}")
        sys.exit(1)


def verify_gateway_targets(gateway_id):
    """Verify that Gateway targets exist and are READY."""
    print(f"\n✅ Verifying Gateway targets...")
    
    try:
        gateway_client = boto3.client('bedrock-agentcore-control', region_name=REGION)
        list_targets_response = gateway_client.list_gateway_targets(gatewayIdentifier=gateway_id)
        
        targets = list_targets_response.get('items', [])  # API returns 'items' not 'targets'
        print(f"   Found {len(targets)} target(s)")
        
        for target in targets:
            target_name = target.get('name', 'Unknown')
            target_status = target.get('status', 'Unknown')
            print(f"   - {target_name}: {target_status}")
        
        return targets
    except Exception as e:
        print(f"⚠️  Warning: Could not verify targets: {e}")
        return []


def display_architecture_diagram(non_interactive=False):
    """Display the architecture diagram of what we're building."""
    diagram = """
╔══════════════════════════════════════════════════════════════════════╗
║                    ARCHITECTURE OVERVIEW                             ║
╚══════════════════════════════════════════════════════════════════════╝

┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT APPLICATION (QuickSuite)             │
│                    (Workshop User / Frontend)                       │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             │ HTTPS + JWT Token
                             │ (Inbound Auth)
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      AGENTCORE GATEWAY                              │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  • Protocol: MCP                                             │   │
│  │  • Inbound Auth: Cognito JWT (Gateway Pool)                  │   │
│  │  • Outbound Auth: OAuth2 (Runtime Pool)                      │   │
│  │  • Role: ac-gw-mcp-role                                      │   │
│  └──────────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             │ OAuth2 Token
                             │ (Outbound Auth)
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     AGENTCORE RUNTIME                               │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  • Inbound Auth: Cognito JWT (Runtime Pool)                  │   │
│  │  • Role: agentcore-runtime-mcp-data-role                     │   │
│  │  • Permissions: Athena, S3, S3Vectors, Glue, Bedrock         │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌──────────────────────┐         ┌──────────────────────┐          │
│  │   ATHENA MCP SERVER  │         │ S3VECTORS MCP SERVER │          │
│  │  ┌────────────────┐  │         │  ┌────────────────┐  │          │
│  │  │ • Query Athena │  │         │  │ • Vector Search│  │          │
│  │  │ • List DBs     │  │         │  │ • Embeddings   │  │          │
│  │  │ • Get Tables   │  │         │  │ • S3 Storage   │  │          │
│  │  └────────────────┘  │         │  └────────────────┘  │          │
│  └──────────┬───────────┘         └──────────┬───────────┘          │
└─────────────┼──────────────────────────────────┼────────────────────┘
              │                                  │
              ▼                                  ▼
    ┌─────────────────┐              ┌─────────────────┐
    │  AWS ATHENA     │              │   AMAZON S3     │
    │  (Data Lake)    │              │  (Vectors)      │
    └─────────────────┘              └─────────────────┘

╔══════════════════════════════════════════════════════════════════════╗
║                      AUTHENTICATION FLOW                             ║
╚══════════════════════════════════════════════════════════════════════╝

1. CLIENT → GATEWAY (Inbound Auth)
   • Client authenticates with Gateway Cognito Pool
   • Receives JWT token with 'invoke' scope
   • Sends requests to Gateway with JWT token

2. GATEWAY → RUNTIME (Outbound Auth)
   • Gateway uses OAuth2 Credential Provider
   • Authenticates with Runtime Cognito Pool
   • Receives OAuth2 token with 'invoke' scope
   • Forwards requests to Runtime MCP servers

3. RUNTIME → AWS SERVICES
   • Runtime uses IAM role (agentcore-runtime-mcp-data-role)
   • Accesses Athena, S3, S3Vectors, Glue, Bedrock
   • Returns results through the chain

╔══════════════════════════════════════════════════════════════════════╗
║                      DEPLOYMENT STEPS                                ║
╚══════════════════════════════════════════════════════════════════════╝

Step 1:  Create Gateway IAM Role (ac-gw-mcp-role)
Step 2:  Create Runtime IAM Role (agentcore-runtime-mcp-data-role)
Step 3:  Create Gateway Cognito Pool (Inbound Auth)
Step 4:  Create Runtime Cognito Pool (Outbound Auth)
Step 5:  Create AgentCore Gateway
Step 6:  Deploy Athena MCP Server to Runtime
Step 7:  Deploy S3Vectors MCP Server to Runtime
Step 8:  Create OAuth2 Credential Provider
Step 9:  Create Gateway Targets (Athena + S3Vectors)
Step 10: Verify Deployment

"""
    print(diagram)
    if not non_interactive:
        input("Press Enter to start the deployment...")
    else:
        print("🚀 Starting automated deployment...\n")


def wait_for_user(step_name, non_interactive=False):
    """Pause and wait for user input before continuing."""
    if non_interactive:
        print(f"\n{'─' * 70}")
        print(f"▶️  Next step: {step_name}")
        print(f"{'─' * 70}\n")
        return
    
    print(f"\n{'─' * 70}")
    input(f"⏸️  Next step: {step_name}\n   Press Enter to continue to next step...")
    print(f"{'─' * 70}\n")


def main():
    """Main deployment function."""
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Deploy MCP Servers to AgentCore Gateway')
    parser.add_argument('--non-interactive', action='store_true', 
                       help='Run in non-interactive mode without pausing for user input')
    args = parser.parse_args()
    
    non_interactive = args.non_interactive
    
    print("=" * 70)
    print("🚀 MCP Servers to AgentCore Gateway - Deployment")
    if non_interactive:
        print("   Mode: Non-Interactive (Automated)")
    else:
        print("   Mode: Interactive (Step-by-Step)")
    print("=" * 70)
    
    # Display architecture diagram
    display_architecture_diagram(non_interactive)
    
    # Step 1: Load configuration
    config = load_config()
    print(f"\n{'─' * 70}")
    print('Step Completed: Configuration loaded')
    wait_for_user("Create Gateway IAM role", non_interactive)
    
    # Step 2: Create Gateway IAM role
    gateway_role_arn = create_gateway_iam_role()
    print(f"\n{'─' * 70}")
    print("Step Completed: Gateway IAM role created")
    wait_for_user("Create Runtime IAM role", non_interactive)
    
    # Step 3: Create Runtime IAM role (with Athena and S3Vectors permissions)
    runtime_role_arn = create_runtime_execution_role()
    print(f"\n{'─' * 70}")
    print("Step Completed: Runtime IAM role created")
    wait_for_user("Create Gateway Cognito pool", non_interactive)
    
    # Step 4: Create Cognito pools
    gw_cognito_config = create_cognito_pool_for_gateway()
    print(f"\n{'─' * 70}")
    print("Step Completed: Gateway Cognito pool created")
    wait_for_user("Create Runtime Cognito pool", non_interactive)
    
    runtime_cognito_config = create_cognito_pool_for_runtime()
    print(f"\n{'─' * 70}")
    print("Step Completed: Runtime Cognito pool created")
    wait_for_user("Create AgentCore Gateway", non_interactive)
    
    # Step 5: Create AgentCore Gateway
    gateway_info = create_agentcore_gateway(gateway_role_arn, gw_cognito_config)
    print(f"\n{'─' * 70}")
    print("Step Completed: AgentCore Gateway created")
    wait_for_user("Deploy Athena MCP Server to Runtime", non_interactive)
    
    # Step 6: Deploy Athena MCP Server to Runtime
    # Check environment variables first, then fall back to config file
    athena_env_vars = {
        "DEFAULT_S3_OUTPUT_LOCATION": os.environ.get("DEFAULT_S3_OUTPUT_LOCATION") or config.get("DEFAULT_S3_OUTPUT_LOCATION", ""),
        "WORKGROUP": os.environ.get("WORKGROUP") or config.get("WORKGROUP", "")
    }
    
    # Log which source was used for configuration
    if os.environ.get("DEFAULT_S3_OUTPUT_LOCATION"):
        print(f"   Using DEFAULT_S3_OUTPUT_LOCATION from environment: {athena_env_vars['DEFAULT_S3_OUTPUT_LOCATION']}")
    elif config.get("DEFAULT_S3_OUTPUT_LOCATION"):
        print(f"   Using DEFAULT_S3_OUTPUT_LOCATION from config file: {athena_env_vars['DEFAULT_S3_OUTPUT_LOCATION']}")
    
    if os.environ.get("WORKGROUP"):
        print(f"   Using WORKGROUP from environment: {athena_env_vars['WORKGROUP']}")
    elif config.get("WORKGROUP"):
        print(f"   Using WORKGROUP from config file: {athena_env_vars['WORKGROUP']}")
    athena_agent = deploy_mcp_server_to_runtime(
        mcp_file="athena_mcp.py",
        agent_name="athena_mcp_server",
        runtime_role_arn=runtime_role_arn,
        runtime_cognito_config=runtime_cognito_config,
        config=config,
        env_vars=athena_env_vars
    )
    print(f"\n{'─' * 70}")
    print("Step Completed: Athena MCP Server deployed to Runtime")
    wait_for_user("Deploy S3Vectors MCP Server to Runtime", non_interactive)
    
    # Step 7: Deploy S3Vectors MCP Server to Runtime
    s3vectors_agent = deploy_mcp_server_to_runtime(
        mcp_file="s3vectors_mcp.py",
        agent_name="s3vectors_mcp_server",
        runtime_role_arn=runtime_role_arn,
        runtime_cognito_config=runtime_cognito_config,
        config=config
    )
    print(f"\n{'─' * 70}")
    print("Step Completed: S3Vectors MCP Server deployed to Runtime")
    wait_for_user("Create OAuth credential provider", non_interactive)
    
    # Step 8: Create OAuth credential provider
    credential_provider_arn = create_oauth_credential_provider(runtime_cognito_config)
    print(f"\n{'─' * 70}")
    print("Step Completed: OAuth credential provider created")
    wait_for_user("Create Athena Gateway target", non_interactive)
    
    # Step 9: Create Gateway targets for both MCP servers
    athena_target_id = create_gateway_target(
        gateway_id=gateway_info["gateway_id"],
        agent_url=athena_agent["agent_url"],
        credential_provider_arn=credential_provider_arn,
        runtime_scope_string=runtime_cognito_config["scope_string"],
        target_name="athena-mcp-target"
    )
    print(f"\n{'─' * 70}")
    print("Step Completed: Athena Gateway target created")
    wait_for_user("Create S3Vectors Gateway target", non_interactive)
    
    s3vectors_target_id = create_gateway_target(
        gateway_id=gateway_info["gateway_id"],
        agent_url=s3vectors_agent["agent_url"],
        credential_provider_arn=credential_provider_arn,
        runtime_scope_string=runtime_cognito_config["scope_string"],
        target_name="s3vectors-mcp-target"
    )
    print(f"\n{'─' * 70}")
    print("Step Completed: S3Vectors Gateway target created")
    wait_for_user("Verify Gateway targets", non_interactive)
    
    # Step 10: Verify Gateway targets
    targets = verify_gateway_targets(gateway_info["gateway_id"])
    if not non_interactive:
        wait_for_user("Gateway targets verified", non_interactive)
    
    # Summary
    print("\n" + "=" * 70)
    print("✅ Deployment Complete!")
    print("=" * 70)
    print(f"\n📋 Essential Deployment Information:")
    
    # Calculate token URL from discovery URL
    token_url = gw_cognito_config['discovery_url'].replace('/.well-known/openid-configuration', '/oauth2/token')
    
    print(f"\nGateway ID: {gateway_info['gateway_id']}")
    print(f"Gateway URL: {gateway_info['gateway_url']}")
    print(f"Cognito Token URL: {token_url}")
    print(f"Client ID: {gw_cognito_config['client_id']}")
    print(f"Client Secret: {gw_cognito_config['client_secret']}")
    print("\n" + "=" * 70)
    
    # Save deployment info to file
    deployment_info = {
        "gateway": gateway_info,
        "gateway_role_arn": gateway_role_arn,
        "runtime_role_arn": runtime_role_arn,
        "gateway_auth": {
            "client_id": gw_cognito_config["client_id"],
            "client_secret": gw_cognito_config["client_secret"],
            "discovery_url": gw_cognito_config["discovery_url"]
        },
        "athena_mcp": athena_agent,
        "s3vectors_mcp": s3vectors_agent,
        "credential_provider_arn": credential_provider_arn,
        "targets": {
            "athena": athena_target_id,
            "s3vectors": s3vectors_target_id
        }
    }
    
    deployment_file = Path(__file__).parent / "deployment_info.json"
    with open(deployment_file, 'w') as f:
        json.dump(deployment_info, f, indent=2)
    
    print(f"\n💾 Deployment info saved to: {deployment_file}")


if __name__ == "__main__":
    main()
