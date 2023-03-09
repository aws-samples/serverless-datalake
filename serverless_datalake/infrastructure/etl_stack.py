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


class EtlStack(NestedStack):

   def __init__(self, scope: Construct, construct_id: str, bucket_name, **kwargs) -> None:
      super().__init__(scope, construct_id, **kwargs)
      env = self.node.try_get_context('environment_name')
      if env is None:
          print('Setting environment as Dev')
          print('Fetching Dev Properties')
          env = 'dev'
      # fetching details from cdk.json
      config_details = self.node.try_get_context(env)
      # Create a Glue Role
      glue_role = _cdk.aws_iam.Role(self, f'etl-role-{env}', assumed_by=_cdk.aws_iam.ServicePrincipal(service='glue.amazonaws.com'),
                                    role_name=f'etlrole{env}', managed_policies=[
          _cdk.aws_iam.ManagedPolicy.from_managed_policy_arn(self, 's3-full-access-etl',
                                                             managed_policy_arn='arn:aws:iam::aws:policy/AmazonS3FullAccess'),
          _cdk.aws_iam.ManagedPolicy.from_aws_managed_policy_name(
              "service-role/AWSGlueServiceRole")
      ]
      )

      s3_bucket = _cdk.aws_s3.Bucket.from_bucket_name(
          self, f's3_lake_{env}', bucket_name=bucket_name)

      # Upload Glue Script on S3
      _cdk.aws_s3_deployment.BucketDeployment(self, f"glue_scripts_deploy_{env}",
                                              sources=[_cdk.aws_s3_deployment.Source
                                                       .asset(os.path.join(os.getcwd(), 'serverless_datalake/infrastructure/glue_job/'))],
                                              destination_bucket=s3_bucket, 
                                              destination_key_prefix=config_details[
                                                  "glue-script-location"]
                                              )
      workflow = _cdk.aws_glue.CfnWorkflow(self, f'workflow-{env}', name=f'serverless-etl-{env}',
       description='sample etl with eventbridge ingestion', max_concurrent_runs=1)
      
      # Create a Glue job and run on schedule
      glue_job = _cdk.aws_glue.CfnJob(
          self, f'serverless-etl-{env}',
          name=config_details['glue-job-name'],
          number_of_workers=config_details['workers'],
          worker_type=config_details['worker-type'],
          command=_cdk.aws_glue.CfnJob.JobCommandProperty(name='glueetl',
                                                          script_location=f"s3://{bucket_name}{config_details['glue-script-uri']}",
                                                          ),
          role=glue_role.role_arn,
          glue_version='3.0',
          execution_property=_cdk.aws_glue.CfnJob.ExecutionPropertyProperty(
              max_concurrent_runs=1),
          description='Serverless etl processing raw data from event-bus',
          default_arguments={
              "--enable-metrics": "",
              "--enable-job-insights": "true",
              '--TempDir': f"s3://{bucket_name}{config_details['temp-location']}",
              '--job-bookmark-option': 'job-bookmark-enable',
              '--s3_input_location': f's3://{bucket_name}/raw-data/',
              '--s3_output_location': f"s3://{bucket_name}{config_details['glue-output']}"
              }
      )


      # Create a Glue Database
      glue_database = _cdk.aws_glue.CfnDatabase(self, f'glue-database-{env}',
                                                catalog_id=self.account, database_input=_cdk.aws_glue.CfnDatabase
                                                .DatabaseInputProperty(
                                                  location_uri=f"s3://{bucket_name}{config_details['glue-database-location']}",
                                                  description='store processed data', name=config_details['glue-database-name']))

      # Create a Glue Crawler
      glue_crawler = _cdk.aws_glue.CfnCrawler(self, f'glue-crawler-{env}',
                                              role=glue_role.role_arn, name=config_details['glue-crawler'],
                                              database_name=config_details['glue-database-name'],
                                              targets=_cdk.aws_glue.CfnCrawler.TargetsProperty(s3_targets=[
                                                  _cdk.aws_glue.CfnCrawler.S3TargetProperty(
                                                      path=f"s3://{bucket_name}{config_details['glue-output']}")
                                              ]), table_prefix=config_details['glue-table-name'],
                                              description='Crawl over processed parquet data. This optimizes query cost'
                                              )

      # Create a Glue cron Trigger ̰
      job_trigger = _cdk.aws_glue.CfnTrigger(self, f'glue-job-trigger-{env}',
                                name=config_details['glue-job-trigger-name'],
                                actions=[_cdk.aws_glue.CfnTrigger.ActionProperty(job_name=glue_job.name)],
                                workflow_name=workflow.name,
                                type='SCHEDULED',
                                start_on_creation=True,
                                schedule=config_details['glue-job-cron'])
      
      job_trigger.add_depends_on(glue_job)
      job_trigger.add_depends_on(glue_crawler)
      job_trigger.add_depends_on(glue_crawler)
      job_trigger.add_depends_on(glue_database)

      # Create a Glue conditional trigger that triggers the crawler on successful job completion
      crawler_trigger = _cdk.aws_glue.CfnTrigger(self, f'glue-crawler-trigger-{env}',
                                name=config_details['glue-crawler-trigger-name'],
                                actions=[_cdk.aws_glue.CfnTrigger.ActionProperty(
                                crawler_name=glue_crawler.name)],
                                workflow_name=workflow.name,
                                type='CONDITIONAL',
                                predicate=_cdk.aws_glue.CfnTrigger.PredicateProperty(
                conditions=[_cdk.aws_glue.CfnTrigger.ConditionProperty(
                job_name=glue_job.name,
                logical_operator='EQUALS',
                state="SUCCEEDED"
            )]
        ),
        start_on_creation=True
    )

      #TODO: Create an Athena Workgroup

      