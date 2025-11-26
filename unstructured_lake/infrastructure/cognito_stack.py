"""
Cognito Authentication Stack for Document Insight Extraction System

This module defines the Cognito User Pool and User Pool Client for user authentication.
"""
from aws_cdk import (
    aws_cognito as cognito,
    aws_ssm as ssm,
    Duration,
)
from constructs import Construct
from infrastructure.base_stack import BaseDocumentInsightStack


class CognitoAuthStack(BaseDocumentInsightStack):
    """
    Stack for Cognito authentication resources.
    
    Creates:
    - Cognito User Pool with email sign-in
    - User Pool Client with auth flow configuration
    - Exports user pool ID and client ID
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        env_name: str,
        config: dict,
        **kwargs
    ) -> None:
        """
        Initialize the Cognito authentication stack.
        
        Args:
            scope: CDK app or parent construct
            construct_id: Unique identifier for this stack
            env_name: Environment name (dev, prod, etc.)
            config: Environment-specific configuration dictionary
            **kwargs: Additional stack properties
        """
        super().__init__(scope, construct_id, env_name, config, **kwargs)

        # Create Cognito User Pool
        self.user_pool = self._create_user_pool()
        
        # Create User Pool Client
        self.user_pool_client = self._create_user_pool_client()
        
        # Note: Cognito Authorizer is created in API Gateway stack
        
        # Export outputs
        self._create_outputs()

    def _create_user_pool(self) -> cognito.UserPool:
        """
        Create Cognito User Pool with email sign-in and password policy.
        
        Returns:
            Cognito UserPool construct
        """
        user_pool = cognito.UserPool(
            self,
            "DocumentInsightUserPool",
            user_pool_name=self.get_resource_name("user-pool"),
            # Email sign-in configuration
            sign_in_aliases=cognito.SignInAliases(
                email=True,
                username=False
            ),
            # Self sign-up configuration
            self_sign_up_enabled=True,
            # Email verification
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            # Password policy
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=True,
                temp_password_validity=Duration.days(7)
            ),
            # Account recovery
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            # Standard attributes
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(
                    required=True,
                    mutable=True
                )
            ),
            # MFA configuration (optional)
            mfa=cognito.Mfa.OPTIONAL,
            mfa_second_factor=cognito.MfaSecondFactor(
                sms=True,
                otp=True
            ),
            # Removal policy
            removal_policy=self.removal_policy
        )

        return user_pool

    def _create_user_pool_client(self) -> cognito.UserPoolClient:
        """
        Create User Pool Client with auth flow configuration.
        
        Returns:
            Cognito UserPoolClient construct
        """
        user_pool_client = cognito.UserPoolClient(
            self,
            "DocumentInsightUserPoolClient",
            user_pool=self.user_pool,
            user_pool_client_name=self.get_resource_name("user-pool-client"),
            # Auth flows
            auth_flows=cognito.AuthFlow(
                user_password=True,  # USER_PASSWORD_AUTH
                user_srp=True,       # USER_SRP_AUTH
                admin_user_password=True  # ADMIN_USER_PASSWORD_AUTH
            ),
            # Token validity
            access_token_validity=Duration.hours(24),
            id_token_validity=Duration.hours(24),
            refresh_token_validity=Duration.days(30),
            # OAuth configuration
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(
                    authorization_code_grant=True,
                    implicit_code_grant=True
                ),
                scopes=[
                    cognito.OAuthScope.EMAIL,
                    cognito.OAuthScope.OPENID,
                    cognito.OAuthScope.PROFILE
                ]
            ),
            # Prevent user existence errors
            prevent_user_existence_errors=True,
            # Enable token revocation
            enable_token_revocation=True
        )

        return user_pool_client



    def _create_outputs(self) -> None:
        """Create CloudFormation outputs and SSM parameters for user pool and client IDs."""
        # Store in SSM Parameter Store for cross-stack access
        ssm.StringParameter(
            self,
            "UserPoolIdParameter",
            parameter_name=f"/{self.project_name}/{self.env_name}/cognito/user-pool-id",
            string_value=self.user_pool.user_pool_id,
            description="Cognito User Pool ID"
        )
        
        ssm.StringParameter(
            self,
            "UserPoolClientIdParameter",
            parameter_name=f"/{self.project_name}/{self.env_name}/cognito/user-pool-client-id",
            string_value=self.user_pool_client.user_pool_client_id,
            description="Cognito User Pool Client ID"
        )
        
        # CloudFormation outputs
        self.add_stack_output(
            "UserPoolId",
            value=self.user_pool.user_pool_id,
            description="Cognito User Pool ID",
            export_name=f"{self.stack_name}-UserPoolId"
        )

        self.add_stack_output(
            "UserPoolClientId",
            value=self.user_pool_client.user_pool_client_id,
            description="Cognito User Pool Client ID",
            export_name=f"{self.stack_name}-UserPoolClientId"
        )

        self.add_stack_output(
            "UserPoolArn",
            value=self.user_pool.user_pool_arn,
            description="Cognito User Pool ARN",
            export_name=f"{self.stack_name}-UserPoolArn"
        )

