#!/usr/bin/env python3
import os

import aws_cdk as cdk

from serverless_datalake.serverless_datalake_stack import ServerlessDatalakeStack

account_id = os.getenv('CDK_DEFAULT_ACCOUNT')
region = os.getenv('CDK_DEFAULT_REGION')

app = cdk.App()
env=cdk.Environment(account=account_id, region=region)
# Set Context Bucket_name
env_name = app.node.try_get_context('environment_name')
bucket_name =  f"lake-store-{env_name}-{region}-{account_id}"
ServerlessDatalakeStack(app, "ServerlessDatalakeStack", bucket_name=bucket_name,
    # If you don't specify 'env', this stack will be environment-agnostic.
    # Account/Region-dependent features and context lookups will not work,
    # but a single synthesized template can be deployed anywhere.

    # Uncomment the next line to specialize this stack for the AWS Account
    # and Region that are implied by the current CLI configuration.
    env=env

    # Uncomment the next line if you know exactly what Account and Region you
    # want to deploy the stack to. */

    #env=cdk.Environment(account='123456789012', region='us-east-1'),

    # For more information, see https://docs.aws.amazon.com/cdk/latest/guide/environments.html
    )

app.synth()
