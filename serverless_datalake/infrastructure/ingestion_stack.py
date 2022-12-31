from aws_cdk import (
    # Duration,
    Stack,
    NestedStack,
    aws_glue_alpha as _glue_alpha
    # aws_sqs as sqs,
)
import aws_cdk as _cdk
from constructs import Construct
import os
from .etl_stack import EtlStack


class IngestionStack(NestedStack):

   def __init__(self, scope: Construct, construct_id: str, bucket_name, **kwargs) -> None:
      super().__init__(scope, construct_id, **kwargs)
      env = self.node.try_get_context('environment_name')
      if env is None:
          print('Setting environment as Dev')
          print('Fetching Dev Properties')
          env = 'dev'
      # fetching details from cdk.json
      config_details = self.node.try_get_context(env)
    # Create an EventBus
      evt_bus = _cdk.aws_events.EventBus(
          self, f'bus-{env}', event_bus_name=config_details['bus-name'])

    # Create a rule that triggers on a Custom Bus event and sends data to Firehose
      # Define a rule that captures only card-events as an example
      custom_rule = _cdk.aws_events.Rule(self, f'bus-rule-{env}', rule_name=config_details['rule-name'],
                                         description="Match a custom-event type", event_bus=evt_bus,
                                         event_pattern=_cdk.aws_events.EventPattern(source=['transactions'], detail_type=['card-event']))

    # Create Kinesis Firehose as an Event Target
      # Step 1: Create a Firehose role
      firehose_to_s3_role = _cdk.aws_iam.Role(self, f'firehose_s3_role_{env}', assumed_by=_cdk.aws_iam.ServicePrincipal(
          'firehose.amazonaws.com'), role_name=config_details['firehose-s3-rolename'])

      # Step 2: Create an S3 bucket as a Firehose target
      s3_bucket = _cdk.aws_s3.Bucket(
          self, f'evtbus_s3_{env}', bucket_name=bucket_name)
      s3_bucket.grant_read_write(firehose_to_s3_role)

      # Step 3: Create a Firehose Delivery Stream
      firehose_stream = _cdk.aws_kinesisfirehose.CfnDeliveryStream(self, f'firehose_stream_{env}',
                                                                   delivery_stream_name=config_details['firehose-name'],
                                                                   delivery_stream_type='DirectPut',
                                                                   s3_destination_configuration=_cdk.aws_kinesisfirehose
                                                                   .CfnDeliveryStream.S3DestinationConfigurationProperty(
                                                                      bucket_arn=s3_bucket.bucket_arn,
                                                                      compression_format='GZIP',
                                                                      role_arn=firehose_to_s3_role.role_arn,
                                                                      buffering_hints=_cdk.aws_kinesisfirehose.CfnDeliveryStream.BufferingHintsProperty(
                                                                        interval_in_seconds=config_details['buffering-interval-in-seconds'],
                                                                        size_in_m_bs=config_details['buffering-size-in-mb']
                                                                      ),
                                                                      prefix='raw-data/year=!{timestamp:YYYY}/month=!{timestamp:MM}/day=!{timestamp:dd}/',
                                                                      error_output_prefix='error/!{firehose:random-string}/!{firehose:error-output-type}/year=!{timestamp:YYYY}/month=!{timestamp:MM}/day=!{timestamp:dd}/'
                                                                    )
                                                                  )

    # Create an IAM role that allows EventBus to communicate with Kinesis Firehose
      evt_firehose_role = _cdk.aws_iam.Role(self, f'evt_bus_to_firehose_{env}',
                                            assumed_by=_cdk.aws_iam.ServicePrincipal('events.amazonaws.com'),
                                            role_name=config_details['eventbus-firehose-rolename'])

      evt_firehose_role.add_to_policy(_cdk.aws_iam.PolicyStatement(
          resources=[firehose_stream.attr_arn],
          actions=['firehose:PutRecord', 'firehose:PutRecordBatch']
      ))

    # Link EventBus/ EventRule/ Firehose Target
      custom_rule.add_target(_cdk.aws_events_targets.KinesisFirehoseStream(firehose_stream))
