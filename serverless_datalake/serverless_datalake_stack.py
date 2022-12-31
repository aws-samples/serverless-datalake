from aws_cdk import (
    # Duration,
    Stack
    # aws_sqs as sqs,
)
import aws_cdk as _cdk
import os
from constructs import Construct
from .infrastructure.ingestion_stack import IngestionStack
from .infrastructure.etl_stack import EtlStack
from .infrastructure.test_stack import TestStack


class ServerlessDatalakeStack(Stack):

    def tag_my_stack(self, stack):
        tags = _cdk.Tags.of(stack)
        tags.add("project", "serverless-streaming-etl-sample")

    def __init__(self, scope: Construct, construct_id: str, bucket_name, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        env_name = self.node.try_get_context('environment_name')
        if env_name is None:
            print('Setting environment to dev as environment_name is not passed during synthesis')
            env_name = 'dev'
        account_id = os.getenv('CDK_DEFAULT_ACCOUNT')
        region = os.getenv('CDK_DEFAULT_REGION')
        env = _cdk.Environment(account=account_id, region=region)
        ingestion_bus_stack = IngestionStack(self, f'ingestion-bus-stack-{env_name}', bucket_name=bucket_name)
        etl_serverless_stack = EtlStack(self, f'etl-serverless-stack-{env}', bucket_name=bucket_name)
        test_stack = TestStack(self, f'test_serverless_datalake-{env}')
        self.tag_my_stack(ingestion_bus_stack)
        self.tag_my_stack(etl_serverless_stack)
        self.tag_my_stack(test_stack)
        etl_serverless_stack.add_dependency(ingestion_bus_stack)
        test_stack.add_dependency(etl_serverless_stack)
