from aws_cdk import (
    # Duration,
    Stack,
    NestedStack
    # aws_sqs as sqs,
)
import aws_cdk as _cdk
from constructs import Construct
import os


class TestStack(NestedStack):
    
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        env = self.node.try_get_context('environment_name')
        
        # Define an On-demand Lambda function to randomly push data to the event bus
        function = _cdk.aws_lambda.Function(self, f'test_function_{env}', function_name=f'serverless-event-simulator-{env}',
         runtime=_cdk.aws_lambda.Runtime.PYTHON_3_9, memory_size=512, handler='event_simulator.handler',
         timeout= _cdk.Duration.minutes(10),
         code= _cdk.aws_lambda.Code.from_asset(os.path.join(os.getcwd(), 'serverless_datalake/infrastructure/lambda_tester/') ))
        
        lambda_policy = _cdk.aws_iam.PolicyStatement(actions=[
            "events:*",
        ], resources=["*"])

        function.add_to_role_policy(lambda_policy)

