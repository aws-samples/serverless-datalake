"""
Deploy MCP Servers (Redshift and S3Vectors) to AgentCore Gateway as targets.
Deploys a fresh gateway for the Redshift Lakehouse use case (separate from the Athena gateway).
Based on: deploy_agent.py pattern with ac_utils and two-pool Cognito auth.
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

# ============================================================================
# GLOBAL CONFIGURATION - Redshift Lakehouse Gateway
# ============================================================================

# IAM Role Names
RUNTIME_ROLE_NAME = "agentcore-runtime-redshift-lakehouse-role"
GATEWAY_ROLE_NAME = "ac-gw-redshift-lakehouse-role"

# Gateway
GATEWAY_NAME = "ac-gateway-redshift-lakehouse"
GATEWAY_DESCRIPTION = "AgentCore Gateway with Redshift MCP + S3Vectors MCP (Lakehouse Analytics)"

# Cognito - Gateway (Inbound Auth)
GW_USER_POOL_NAME = "redshift-lakehouse-gateway-pool"
GW_RESOURCE_SERVER_ID = "redshift-lakehouse-gateway-id"
GW_RESOURCE_SERVER_NAME = "redshift-lakehouse-gateway-name"
GW_CLIENT_NAME = "redshift-lakehouse-gateway-client"

# Cognito - Runtime (Outbound Auth)
RT_USER_POOL_NAME = "redshift-lakehouse-runtime-pool"
RT_RESOURCE_SERVER_ID = "redshift-lakehouse-runtime-id"
RT_RESOURCE_SERVER_NAME = "redshift-lakehouse-runtime-name"
RT_CLIENT_NAME = "redshift-lakehouse-runtime-client"

# MCP Server Deployments
REDSHIFT_MCP_FILE = "redshift_mcp.py"
REDSHIFT_AGENT_NAME = "redshift_mcp_server"
S3VECTORS_MCP_FILE = "s3vectors_mcp.py"
S3VECTORS_AGENT_NAME = "s3vectors_mcp_server_lakehouse"

# Gateway Targets
REDSHIFT_TARGET_NAME = "redshift-mcp-target"
S3VECTORS_TARGET_NAME = "s3vectors-mcp-target-lakehouse"

# OAuth Credential Provider
OAUTH_CREDENTIAL_PROVIDER_NAME = "ac-gateway-redshift-lakehouse-identity"

# ============================================================================


def load_config():
    """Load configuration from redshift_config.json file."""
    print("Loading configuration from redshift_config.json...")

    config_path = Path(__file__).parent / "redshift_config.json"

    if not config_path.exists():
        print(f"Configuration file not found: {config_path}")
        sys.exit(1)

    try:
        with open(config_path, 'r') as f:
            config = json.load(f)

        print(f"Configuration loaded successfully")
        return config
    except Exception as e:
        print(f"Error loading configuration: {e}")
        sys.exit(1)


def create_runtime_execution_role():
    """Create or update IAM role for AgentCore Runtime with Redshift and S3Vectors permissions."""
    print("\nCreating/Updating IAM role for AgentCore Runtime...")

    iam_client = boto3.client('iam')

    try:
        try:
            response = iam_client.get_role(RoleName=RUNTIME_ROLE_NAME)
            role_arn = response['Role']['Arn']
            print(f"  Role '{RUNTIME_ROLE_NAME}' already exists - updating policies...")

            # Delete all existing inline policies
            try:
                policies = iam_client.list_role_policies(RoleName=RUNTIME_ROLE_NAME, MaxItems=100)
                for policy_name in policies.get('PolicyNames', []):
                    iam_client.delete_role_policy(RoleName=RUNTIME_ROLE_NAME, PolicyName=policy_name)
                    print(f"   Deleted old policy: {policy_name}")
            except Exception as e:
                print(f"   Warning: Could not delete old policies: {e}")

            agentcore_runtime_iam_role = utils.create_agentcore_runtime_role_with_data_permissions("redshift-lakehouse")
            role_arn = agentcore_runtime_iam_role['Role']['Arn']
            print(f"  Runtime IAM role updated: {role_arn}")
            return role_arn

        except iam_client.exceptions.NoSuchEntityException:
            print(f"   Role '{RUNTIME_ROLE_NAME}' not found, creating new one...")
            agentcore_runtime_iam_role = utils.create_agentcore_runtime_role_with_data_permissions("redshift-lakehouse")
            role_arn = agentcore_runtime_iam_role['Role']['Arn']
            print(f"  Runtime IAM role created: {role_arn}")
            return role_arn
    except Exception as e:
        print(f"Error with Runtime IAM role: {e}")
        sys.exit(1)


def create_gateway_iam_role():
    """Create or update IAM role for the Gateway to assume."""
    print("\nCreating/Updating IAM role for AgentCore Gateway...")

    iam_client = boto3.client('iam')

    try:
        try:
            response = iam_client.get_role(RoleName=GATEWAY_ROLE_NAME)
            role_arn = response['Role']['Arn']
            print(f"  Role '{GATEWAY_ROLE_NAME}' already exists - updating policies...")

            try:
                policies = iam_client.list_role_policies(RoleName=GATEWAY_ROLE_NAME, MaxItems=100)
                for policy_name in policies.get('PolicyNames', []):
                    iam_client.delete_role_policy(RoleName=GATEWAY_ROLE_NAME, PolicyName=policy_name)
                    print(f"   Deleted old policy: {policy_name}")
            except Exception as e:
                print(f"   Warning: Could not delete old policies: {e}")

            agentcore_gateway_iam_role = utils.create_agentcore_gateway_role(GATEWAY_ROLE_NAME)
            role_arn = agentcore_gateway_iam_role['Role']['Arn']
            print(f"  Gateway IAM role updated: {role_arn}")
            return role_arn

        except iam_client.exceptions.NoSuchEntityException:
            print(f"   Role '{GATEWAY_ROLE_NAME}' not found, creating new one...")
            agentcore_gateway_iam_role = utils.create_agentcore_gateway_role(GATEWAY_ROLE_NAME)
            role_arn = agentcore_gateway_iam_role['Role']['Arn']
            print(f"  Gateway IAM role created: {role_arn}")
            return role_arn
    except Exception as e:
        print(f"Error with Gateway IAM role: {e}")
        sys.exit(1)


def create_cognito_pool_for_gateway():
    """Create or get existing Amazon Cognito Pool for inbound authorization to Gateway."""
    print("\nCreating/Getting Cognito Pool for Gateway (Inbound Auth)...")

    SCOPES = [
        {
            "ScopeName": "invoke",
            "ScopeDescription": "Scope for invoking the agentcore gateway"
        },
    ]

    scope_names = [f"{GW_RESOURCE_SERVER_ID}/{scope['ScopeName']}" for scope in SCOPES]
    scope_string = " ".join(scope_names)

    cognito = boto3.client("cognito-idp", region_name=REGION)

    try:
        gw_user_pool_id = utils.get_or_create_user_pool(cognito, GW_USER_POOL_NAME)
        print(f"   User Pool ID: {gw_user_pool_id}")

        utils.get_or_create_resource_server(
            cognito, gw_user_pool_id, GW_RESOURCE_SERVER_ID, GW_RESOURCE_SERVER_NAME, SCOPES
        )
        print("   Resource server ensured")

        gw_client_id, gw_client_secret = utils.get_or_create_m2m_client(
            cognito, gw_user_pool_id, GW_CLIENT_NAME, GW_RESOURCE_SERVER_ID, scope_names,
            oauth_flow="code"
        )

        gw_cognito_discovery_url = f'https://cognito-idp.{REGION}.amazonaws.com/{gw_user_pool_id}/.well-known/openid-configuration'

        print(f"  Gateway Cognito Pool ready")
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
        print(f"Error with Cognito Pool: {e}")
        raise


def create_cognito_pool_for_runtime():
    """Create or get existing Amazon Cognito Pool for outbound authorization (Gateway -> Runtime)."""
    print("\nCreating/Getting Cognito Pool for Runtime (Outbound Auth for Gateway)...")

    SCOPES = [
        {
            "ScopeName": "invoke",
            "ScopeDescription": "Scope for invoking the agentcore runtime"
        },
    ]

    scope_names = [f"{RT_RESOURCE_SERVER_ID}/{scope['ScopeName']}" for scope in SCOPES]
    scope_string = " ".join(scope_names)

    cognito = boto3.client("cognito-idp", region_name=REGION)

    try:
        runtime_user_pool_id = utils.get_or_create_user_pool(cognito, RT_USER_POOL_NAME)
        print(f"   User Pool ID: {runtime_user_pool_id}")

        utils.get_or_create_resource_server(
            cognito, runtime_user_pool_id, RT_RESOURCE_SERVER_ID, RT_RESOURCE_SERVER_NAME, SCOPES
        )
        print("   Resource server ensured")

        runtime_client_id, runtime_client_secret = utils.get_or_create_m2m_client(
            cognito, runtime_user_pool_id, RT_CLIENT_NAME, RT_RESOURCE_SERVER_ID, scope_names
        )

        runtime_cognito_discovery_url = f'https://cognito-idp.{REGION}.amazonaws.com/{runtime_user_pool_id}/.well-known/openid-configuration'

        print(f"  Runtime Cognito Pool ready")
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
        print(f"Error with Runtime Cognito Pool: {e}")
        raise


def create_agentcore_gateway(gateway_role_arn, gw_cognito_config):
    """Create the AgentCore Gateway or get existing one."""
    print("\nCreating/Getting AgentCore Gateway...")

    try:
        gateway_client = boto3.client('bedrock-agentcore-control', region_name=REGION)

        try:
            list_response = gateway_client.list_gateways()
            existing_gateways = list_response.get('items', [])

            for gateway in existing_gateways:
                if gateway.get('name') == GATEWAY_NAME:
                    gateway_id = gateway.get('gatewayId')
                    gateway_details = gateway_client.get_gateway(gatewayIdentifier=gateway_id)
                    gateway_url = gateway_details.get('gatewayUrl')
                    print(f"  Using existing Gateway")
                    print(f"   Gateway ID: {gateway_id}")
                    print(f"   Gateway URL: {gateway_url}")
                    return {
                        "gateway_id": gateway_id,
                        "gateway_url": gateway_url
                    }
        except Exception as list_error:
            print(f"   Could not list gateways: {list_error}")

        print(f"   Gateway '{GATEWAY_NAME}' not found, creating new one...")

        auth_config = {
            "customJWTAuthorizer": {
                "allowedClients": [gw_cognito_config["client_id"]],
                "discoveryUrl": gw_cognito_config["discovery_url"]
            }
        }

        create_response = gateway_client.create_gateway(
            name=GATEWAY_NAME,
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
            description=GATEWAY_DESCRIPTION
        )

        gateway_id = create_response["gatewayId"]
        gateway_url = create_response["gatewayUrl"]

        print(f"  Gateway created successfully")
        print(f"   Gateway ID: {gateway_id}")
        print(f"   Gateway URL: {gateway_url}")

        return {
            "gateway_id": gateway_id,
            "gateway_url": gateway_url
        }
    except Exception as e:
        print(f"Error with Gateway: {e}")
        sys.exit(1)



def deploy_mcp_server_to_runtime(mcp_file, agent_name, runtime_role_arn, runtime_cognito_config, config, env_vars=None):
    """
    Deploy an MCP server to AgentCore Runtime (from source file).

    Args:
        mcp_file: Name of the MCP server file (e.g., 's3vectors_mcp.py')
        agent_name: Name for the agent
        runtime_role_arn: ARN of the IAM role for Runtime execution
        runtime_cognito_config: Runtime Cognito configuration
        config: Application configuration
        env_vars: Optional environment variables to set

    Returns:
        Dictionary with agent_arn, agent_id, and agent_url
    """
    print(f"\nDeploying {mcp_file} to AgentCore Runtime...")

    script_dir = Path(__file__).parent

    required_files = [mcp_file, 'requirements.txt']
    for file in required_files:
        file_path = script_dir / file
        if not file_path.exists():
            raise FileNotFoundError(f"Required file {file} not found at {file_path}")
    print("   All required files found")

    original_dir = os.getcwd()
    os.chdir(script_dir)
    print(f"   Working directory: {script_dir}")

    try:
        agentcore_runtime = Runtime()

        auth_config = {
            "customJWTAuthorizer": {
                "allowedClients": [runtime_cognito_config["client_id"]],
                "discoveryUrl": runtime_cognito_config["discovery_url"]
            }
        }

        print("   Configuring AgentCore Runtime...")
        print(f"   Using Runtime execution role: {runtime_role_arn}")
        response = agentcore_runtime.configure(
            entrypoint=mcp_file,
            execution_role=runtime_role_arn,
            auto_create_ecr=True,
            requirements_file="requirements.txt",
            non_interactive=True,
            region=REGION,
            authorizer_configuration=auth_config,
            protocol="MCP",
            agent_name=agent_name,
        )
        print("   Configuration completed")

        print("   Launching MCP server to AgentCore Runtime...")
        print("   This may take several minutes...")
        launch_result = agentcore_runtime.launch(auto_update_on_conflict=True, env_vars=env_vars)

        agent_arn = launch_result.agent_arn
        agent_id = launch_result.agent_id

        encoded_arn = agent_arn.replace(':', '%3A').replace('/', '%2F')
        agent_url = f'https://bedrock-agentcore.{REGION}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT'

        print(f"  {mcp_file} deployed successfully")
        print(f"   Agent ARN: {agent_arn}")
        print(f"   Agent ID: {agent_id}")
        print(f"   Agent URL: {agent_url}")

        return {
            "agent_arn": agent_arn,
            "agent_id": agent_id,
            "agent_url": agent_url
        }
    finally:
        dockerfile_path = script_dir / "Dockerfile"
        if dockerfile_path.exists():
            dockerfile_path.unlink()
        os.chdir(original_dir)


def create_oauth_credential_provider(runtime_cognito_config):
    """Create or get existing AgentCore Identity OAuth credential provider for outbound auth."""
    print("\nCreating/Getting OAuth credential provider for Gateway outbound auth...")

    try:
        identity_client = boto3.client('bedrock-agentcore-control', region_name=REGION)

        # Check if credential provider already exists
        try:
            list_response = identity_client.list_oauth2_credential_providers()
            providers = list_response.get('credentialProviders', [])

            for provider in providers:
                if provider.get('name') == OAUTH_CREDENTIAL_PROVIDER_NAME:
                    cognito_provider_arn = provider.get('credentialProviderArn')
                    print(f"  Using existing OAuth credential provider")
                    print(f"   Provider ARN: {cognito_provider_arn}")
                    return cognito_provider_arn
        except Exception as list_error:
            print(f"   Could not list credential providers: {list_error}")

        # Create new credential provider
        cognito_provider = identity_client.create_oauth2_credential_provider(
            name=OAUTH_CREDENTIAL_PROVIDER_NAME,
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
        print(f"  OAuth credential provider created")
        print(f"   Provider ARN: {cognito_provider_arn}")

        return cognito_provider_arn
    except Exception as e:
        print(f"Error creating OAuth credential provider: {e}")
        sys.exit(1)


def create_gateway_target(gateway_id, agent_url, credential_provider_arn, runtime_scope_string, target_name):
    """Create a Gateway target for an MCP server or get existing one."""
    print(f"\nCreating/Getting Gateway target: {target_name}...")

    try:
        gateway_client = boto3.client('bedrock-agentcore-control', region_name=REGION)

        try:
            list_response = gateway_client.list_gateway_targets(gatewayIdentifier=gateway_id)
            existing_targets = list_response.get('items', [])

            for target in existing_targets:
                if target.get('name') == target_name:
                    target_id = target.get('targetId')
                    print(f"  Using existing Gateway target: {target_name}")
                    print(f"   Target ID: {target_id}")
                    return target_id
        except Exception as list_error:
            print(f"   Could not list targets: {list_error}")

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
        print(f"  Gateway target created: {target_name}")
        print(f"   Target ID: {target_id}")

        return target_id
    except Exception as e:
        print(f"Error with Gateway target: {e}")
        sys.exit(1)


def verify_gateway_targets(gateway_id):
    """Verify that Gateway targets exist and are READY."""
    print(f"\nVerifying Gateway targets...")

    try:
        gateway_client = boto3.client('bedrock-agentcore-control', region_name=REGION)
        list_targets_response = gateway_client.list_gateway_targets(gatewayIdentifier=gateway_id)

        targets = list_targets_response.get('items', [])
        print(f"   Found {len(targets)} target(s)")

        for target in targets:
            target_name = target.get('name', 'Unknown')
            target_status = target.get('status', 'Unknown')
            print(f"   - {target_name}: {target_status}")

        return targets
    except Exception as e:
        print(f"Warning: Could not verify targets: {e}")
        return []


def display_architecture_diagram(non_interactive=False):
    """Display the architecture diagram of what we're building."""
    diagram = """
===========================================================================
                    REDSHIFT LAKEHOUSE GATEWAY - ARCHITECTURE
===========================================================================

+---------------------------------------------------------------------------+
|                         CLIENT APPLICATION (QuickSuite)                    |
|                    (Workshop User / Frontend)                              |
+------------------------------------+--------------------------------------+
                                     |
                                     | HTTPS + JWT Token
                                     | (Inbound Auth)
                                     v
+---------------------------------------------------------------------------+
|                      AGENTCORE GATEWAY                                     |
|  +---------------------------------------------------------------------+  |
|  |  Name: ac-gateway-redshift-lakehouse                                |  |
|  |  Protocol: MCP                                                      |  |
|  |  Inbound Auth: Cognito JWT (Gateway Pool)                           |  |
|  |  Outbound Auth: OAuth2 (Runtime Pool)                               |  |
|  |  Role: ac-gw-redshift-lakehouse-role                                |  |
|  +---------------------------------------------------------------------+  |
+------------------------------------+--------------------------------------+
                                     |
                                     | OAuth2 Token
                                     | (Outbound Auth)
                                     v
+---------------------------------------------------------------------------+
|                     AGENTCORE RUNTIME                                      |
|  +---------------------------------------------------------------------+  |
|  |  Inbound Auth: Cognito JWT (Runtime Pool)                           |  |
|  |  Role: agentcore-runtime-redshift-lakehouse-role                    |  |
|  |  Permissions: Redshift Data API, S3, S3Vectors, Glue, Bedrock       |  |
|  +---------------------------------------------------------------------+  |
|                                                                           |
|  +------------------------+         +------------------------+            |
|  | REDSHIFT MCP SERVER    |         | S3VECTORS MCP SERVER   |            |
|  | +--------------------+ |         | +--------------------+ |            |
|  | | list_schemas       | |         | | Vector Search      | |            |
|  | | list_tables        | |         | | Embeddings         | |            |
|  | | list_columns       | |         | | S3 Storage         | |            |
|  | | execute_query (RO) | |         | +--------------------+ |            |
|  | +--------------------+ |         +----------+-------------+            |
|  +----------+-------------+                    |                          |
+---------------------------------------------------------------------------+
              |                                  |
              v                                  v
    +-------------------+              +-------------------+
    | Redshift          |              |   Amazon S3       |
    | Serverless        |              |  (Vectors)        |
    | + Spectrum        |              +-------------------+
    |   -> Parquet Lake |
    |   -> Iceberg Lake |
    | + Local Tables    |
    |   -> CTAS / MVs   |
    +-------------------+

===========================================================================
                      DEPLOYMENT STEPS
===========================================================================

Step 1:  Create Gateway IAM Role (ac-gw-redshift-lakehouse-role)
Step 2:  Create Runtime IAM Role (agentcore-runtime-redshift-lakehouse-role)
Step 3:  Create Gateway Cognito Pool (Inbound Auth)
Step 4:  Create Runtime Cognito Pool (Outbound Auth)
Step 5:  Create AgentCore Gateway
Step 6:  Deploy Redshift MCP Server to Runtime
Step 7:  Deploy S3Vectors MCP Server to Runtime
Step 8:  Create OAuth2 Credential Provider
Step 9:  Create Gateway Targets (Redshift + S3Vectors)
Step 10: Verify Deployment

"""
    print(diagram)
    if not non_interactive:
        input("Press Enter to start the deployment...")
    else:
        print("Starting automated deployment...\n")


def wait_for_user(step_name, non_interactive=False):
    """Pause and wait for user input before continuing."""
    if non_interactive:
        print(f"\n{'=' * 70}")
        print(f"  Next step: {step_name}")
        print(f"{'=' * 70}\n")
        return

    print(f"\n{'=' * 70}")
    input(f"  Next step: {step_name}\n   Press Enter to continue...")
    print(f"{'=' * 70}\n")


def main():
    """Main deployment function."""
    import argparse

    parser = argparse.ArgumentParser(description='Deploy Redshift Lakehouse MCP Servers to AgentCore Gateway')
    parser.add_argument('--non-interactive', action='store_true',
                       help='Run in non-interactive mode without pausing for user input')
    args = parser.parse_args()

    non_interactive = args.non_interactive

    print("=" * 70)
    print("Redshift Lakehouse MCP - AgentCore Gateway Deployment")
    if non_interactive:
        print("   Mode: Non-Interactive (Automated)")
    else:
        print("   Mode: Interactive (Step-by-Step)")
    print("=" * 70)

    # Clean up any leftover Dockerfile from previous deploy_agent.py runs
    leftover_dockerfile = Path(__file__).parent / "Dockerfile"
    if leftover_dockerfile.exists():
        leftover_dockerfile.unlink()
        print("   Cleaned up leftover Dockerfile from previous deployment")

    # Display architecture diagram
    display_architecture_diagram(non_interactive)

    # Step 1: Load configuration
    config = load_config()
    print(f"\n{'=' * 70}")
    print('Step Completed: Configuration loaded')
    wait_for_user("Create Gateway IAM role", non_interactive)

    # Step 2: Create Gateway IAM role
    gateway_role_arn = create_gateway_iam_role()
    print(f"\n{'=' * 70}")
    print("Step Completed: Gateway IAM role created")
    wait_for_user("Create Runtime IAM role", non_interactive)

    # Step 3: Create Runtime IAM role (with Redshift and S3Vectors permissions)
    runtime_role_arn = create_runtime_execution_role()
    print(f"\n{'=' * 70}")
    print("Step Completed: Runtime IAM role created")
    wait_for_user("Create Gateway Cognito pool", non_interactive)

    # Step 4: Create Cognito pools
    gw_cognito_config = create_cognito_pool_for_gateway()
    print(f"\n{'=' * 70}")
    print("Step Completed: Gateway Cognito pool created")
    wait_for_user("Create Runtime Cognito pool", non_interactive)

    runtime_cognito_config = create_cognito_pool_for_runtime()
    print(f"\n{'=' * 70}")
    print("Step Completed: Runtime Cognito pool created")
    wait_for_user("Create AgentCore Gateway", non_interactive)

    # Step 5: Create AgentCore Gateway
    gateway_info = create_agentcore_gateway(gateway_role_arn, gw_cognito_config)
    print(f"\n{'=' * 70}")
    print("Step Completed: AgentCore Gateway created")
    wait_for_user("Deploy Redshift MCP Server to Runtime", non_interactive)

    # Step 6: Deploy Redshift MCP Server to Runtime (custom source, uses Redshift Data API)
    redshift_env_vars = {
        "REDSHIFT_WORKGROUP": os.environ.get("REDSHIFT_WORKGROUP") or config.get("REDSHIFT_WORKGROUP", "workshop-redshift-wg"),
        "REDSHIFT_DATABASE": os.environ.get("REDSHIFT_DATABASE") or config.get("REDSHIFT_DATABASE", "analytics_db"),
    }

    print(f"   Using REDSHIFT_WORKGROUP: {redshift_env_vars['REDSHIFT_WORKGROUP']}")
    print(f"   Using REDSHIFT_DATABASE: {redshift_env_vars['REDSHIFT_DATABASE']}")

    redshift_agent = deploy_mcp_server_to_runtime(
        mcp_file=REDSHIFT_MCP_FILE,
        agent_name=REDSHIFT_AGENT_NAME,
        runtime_role_arn=runtime_role_arn,
        runtime_cognito_config=runtime_cognito_config,
        config=config,
        env_vars=redshift_env_vars
    )
    print(f"\n{'=' * 70}")
    print("Step Completed: Redshift MCP Server deployed to Runtime")
    wait_for_user("Deploy S3Vectors MCP Server to Runtime", non_interactive)

    # Step 7: Deploy S3Vectors MCP Server to Runtime
    s3vectors_agent = deploy_mcp_server_to_runtime(
        mcp_file=S3VECTORS_MCP_FILE,
        agent_name=S3VECTORS_AGENT_NAME,
        runtime_role_arn=runtime_role_arn,
        runtime_cognito_config=runtime_cognito_config,
        config=config
    )
    print(f"\n{'=' * 70}")
    print("Step Completed: S3Vectors MCP Server deployed to Runtime")
    wait_for_user("Create OAuth credential provider", non_interactive)

    # Step 8: Create OAuth credential provider
    credential_provider_arn = create_oauth_credential_provider(runtime_cognito_config)
    print(f"\n{'=' * 70}")
    print("Step Completed: OAuth credential provider created")
    wait_for_user("Create Redshift Gateway target", non_interactive)

    # Step 9: Create Gateway targets for both MCP servers
    redshift_target_id = create_gateway_target(
        gateway_id=gateway_info["gateway_id"],
        agent_url=redshift_agent["agent_url"],
        credential_provider_arn=credential_provider_arn,
        runtime_scope_string=runtime_cognito_config["scope_string"],
        target_name=REDSHIFT_TARGET_NAME
    )
    print(f"\n{'=' * 70}")
    print("Step Completed: Redshift Gateway target created")
    wait_for_user("Create S3Vectors Gateway target", non_interactive)

    s3vectors_target_id = create_gateway_target(
        gateway_id=gateway_info["gateway_id"],
        agent_url=s3vectors_agent["agent_url"],
        credential_provider_arn=credential_provider_arn,
        runtime_scope_string=runtime_cognito_config["scope_string"],
        target_name=S3VECTORS_TARGET_NAME
    )
    print(f"\n{'=' * 70}")
    print("Step Completed: S3Vectors Gateway target created")
    wait_for_user("Verify Gateway targets", non_interactive)

    # Step 10: Verify Gateway targets
    targets = verify_gateway_targets(gateway_info["gateway_id"])
    if not non_interactive:
        wait_for_user("Gateway targets verified", non_interactive)

    # Summary
    print("\n" + "=" * 70)
    print("Deployment Complete!")
    print("=" * 70)
    print(f"\nEssential Deployment Information:")

    user_pool_id = gw_cognito_config['user_pool_id']
    user_pool_id_lowercase = user_pool_id.lower().replace('_', '')
    token_url = f"https://{user_pool_id_lowercase}.auth.{REGION}.amazoncognito.com/oauth2/token"
    authorize_url = f"https://{user_pool_id_lowercase}.auth.{REGION}.amazoncognito.com/oauth2/authorize"

    print(f"\nGateway ID: {gateway_info['gateway_id']}")
    print(f"Gateway URL: {gateway_info['gateway_url']}")
    print(f"Cognito Token URL: {token_url}")
    print(f"Cognito Authorize URL: {authorize_url}")
    print(f"Client ID: {gw_cognito_config['client_id']}")
    print(f"Client Secret: {gw_cognito_config['client_secret']}")
    print("\n" + "=" * 70)

    # Save deployment info to file
    deployment_info = {
        "gateway": gateway_info,
        "gateway_role_arn": gateway_role_arn,
        "runtime_role_arn": runtime_role_arn,
        "token_url": token_url,
        "authorize_url": authorize_url,
        "gateway_auth": {
            "client_id": gw_cognito_config["client_id"],
            "client_secret": gw_cognito_config["client_secret"],
            "discovery_url": gw_cognito_config["discovery_url"],
            "token_url": token_url
        },
        "redshift_mcp": redshift_agent,
        "s3vectors_mcp": s3vectors_agent,
        "credential_provider_arn": credential_provider_arn,
        "targets": {
            "redshift": redshift_target_id,
            "s3vectors": s3vectors_target_id
        }
    }

    deployment_file = Path(__file__).parent / "redshift_deployment_info.json"
    with open(deployment_file, 'w') as f:
        json.dump(deployment_info, f, indent=2)

    print(f"\nDeployment info saved to: {deployment_file}")


if __name__ == "__main__":
    main()
