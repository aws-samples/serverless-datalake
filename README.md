
# Serverless Datalake with Amazon EventBridge

### Architecture
![architecture](/serverless-datalake.drawio.png?raw=true)

<br>
<br>

### Overview
This solution demonstrates how we could build a serverless ETL solution with Amazon Eventbridge, Kinesis Firehose, AWS Glue.

* Amazon Eventbridge is a high throughput serverless event router used for ingesting data, it provides out-of-the-box integration with multiple AWS services. We could generate custom events from multiple hetrogenous sources and route it to any of the AWS services without the need to write any integration logic. With content based routing , a single event bus can route events to different services based on the match/un-matched event content.

* Kinesis Firehose is used to buffer the events and store them as json files in S3.

* AWS Glue is a serverless data integration service. We've used Glue to transform the raw event data and also to generate a 
schema using AWS Glue crawler. AWS Glue Jobs run some basic transformations on the incoming raw data. It then compresses, partitions the data and stores it in parquet(columnar) storage. AWS Glue job is configured to run every hour. A successful AWS Glue job completion would trigger the AWS Glue Crawler that in turn would either create a schema on the S3 data or update the schema and other metadata such as newly added/deleted table partitions.

* Glue Workflow
![alt text](/glue-workflow.png?raw=true)

* Glue Crawler
![Crawler](/glue-crawler.png?raw=true)

* Datalake Table
![Table](/glue-table.png?raw=true)

* Once the table is created we could query it through Athena and visualize it using Quicksight. <br>
Athena Query
![Athena](/athena_query.png?raw=true)

* This solution also provides a test lambda that generates 500 random events to push to the bus. The lambda is part of the **test_stack.py** nested stack. The lambda should be invoked on demand.
Test lambda name: **serverless-event-simulator-dev**



This solution could be used to build a datalake for API usage tracking, State Change Notifications, Content based routing and much more.


### Setup to execute on AWS Cloudshell

1. Create an new IAM user with Admin access

2. Configure your aws cli environment with the access/secret keys of the new admin user using the below command on cloudshell
   ```
   $ aws configure
   ```

3. upgrade npm
    ```
    $  sudo npm install n stable -g
    ```

4. Install cdk toolkit if not already done so

    ```
    $   sudo npm install -g aws-cdk@2.55.1
    ```

5.  Note: You may need to do a cdk bootstrap if you haven't used cdk before. Link: https://docs.aws.amazon.com/cdk/v2/guide/bootstrapping.html

    ```
    $   e.g. cdk bootstrap aws://ACCOUNT-NUMBER-1/REGION-1 aws://ACCOUNT-NUMBER-2/REGION-2 ...

    $   e.g -> cdk bootstrap aws://642933501378/us-east-1
    ```
<br>

4. create a python virtualenv:
```
$  cd serverless-datalake
$  python3 -m venv .venv
```

5. After the init process completes and the virtualenv is created, you can use the following
step to activate your virtualenv.

```
$ source .venv/bin/activate
```

*  (Windows Platfrom)If you are a Windows platform, you would activate the virtualenv like this:

```
% .venv\Scripts\activate.bat
```

6. Once the virtualenv is activated, you can install the required dependencies.

```
$  pip install -r requirements.txt
```

7. At this point you can now synthesize the CloudFormation template for this code.

```
$  cdk synth -c environment_name=dev
```

8. You can deploy the generated CloudFormation template using the below command
```
$  cdk deploy -c environment_name=dev ServerlessDatalakeStack
```

9. Configurations for dev environment are defined in cdk.json. S3 bucket name is created on the fly based on account_id and region in which the cdk is deployed

10. After you've successfully deployed this stack on your account, you could test it out by executing the test lambda thats deployed as part of this stack.
Test lambda name: **serverless-event-simulator-dev** . This lambda will push 500 random events to the event-bus.
