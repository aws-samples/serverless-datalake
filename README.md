
# Serverless Datalake with Amazon EventBridge

### Architecture
![architecture](https://user-images.githubusercontent.com/25897220/210151716-5e670221-db78-4681-b711-1ef8d94ea102.png)

<br>
<br>

### Overview
This solution demonstrates how we could build a serverless ETL solution with Amazon Eventbridge, Kinesis Firehose, AWS Glue.

* Amazon Eventbridge is a high throughput serverless event router used for ingesting data, it provides out-of-the-box integration with multiple AWS services. We could generate custom events from multiple hetrogenous sources and route it to any of the AWS services without the need to write any integration logic. With content based routing , a single event bus can route events to different services based on the match/un-matched event content.

* Kinesis Firehose is used to buffer the events and store them as json files in S3.

* AWS Glue is a serverless data integration service. We've used Glue to transform the raw event data and also to generate a 
schema using AWS Glue crawler. AWS Glue Jobs run some basic transformations on the incoming raw data. It then compresses, partitions the data and stores it in parquet(columnar) storage. AWS Glue job is configured to run every hour. A successful AWS Glue job completion would trigger the AWS Glue Crawler that in turn would either create a schema on the S3 data or update the schema and other metadata such as newly added/deleted table partitions.

* Glue Workflow
<img width="1033" alt="glue-workflow" src="https://user-images.githubusercontent.com/25897220/210151743-399ad0cf-9cfd-47c4-b193-6bf899074a41.png">

* Glue Crawler
<img width="1099" alt="glue-crawler" src="https://user-images.githubusercontent.com/25897220/210151749-c84a909a-df2a-468c-a5c6-37532cb3ce6b.png">

* Datalake Table
<img width="1106" alt="glue-table" src="https://user-images.githubusercontent.com/25897220/210151755-048092c5-a53b-4e3f-a46b-2900ab3f8470.png">

* Once the table is created we could query it through Athena and visualize it using Quicksight. <br>
Athena Query
<img width="1364" alt="athena_query" src="https://user-images.githubusercontent.com/25897220/210151765-0c80f4dc-d909-4597-a5f3-4d4b4897ee97.png">

* This solution also provides a test lambda that generates 500 random events to push to the bus. The lambda is part of the **test_stack.py** nested stack. The lambda should be invoked on demand.
Test lambda name: **serverless-event-simulator-dev**



This solution could be used to build a datalake for API usage tracking, State Change Notifications, Content based routing and much more.


### Setup to execute on AWS Cloudshell

1. Create an new IAM user(username = LakeAdmin) with Administrator access

2. Once the user is created. Head to  Security Credentials Tab and generate access/secret key for the new IAM user.

2. Copy access/secret keys for the  newly created IAM User.

3. Search for AWS Cloudshell. Configure your aws cli environment with the access/secret keys of the new admin user using the below command on AWS Cloudshell
   ```
   aws configure
   ```

4. upgrade npm
    ```
    sudo npm install n stable -g
    ```

5. Install cdk toolkit if not already done so

    ```
    sudo npm install -g aws-cdk@2.55.1
    ```

6.  Note: You may need to do a cdk bootstrap if you haven't used cdk before. Link: https://docs.aws.amazon.com/cdk/v2/guide/bootstrapping.html

    ```
    Syntax ->  cdk bootstrap aws://ACCOUNT-NUMBER-1/REGION-1 aws://ACCOUNT-NUMBER-2/REGION-2 ...

    example -> cdk bootstrap aws://642933501378/us-east-1
    ```
<br>

7. Git Clone the serverless-datalake repository from aws-samples
   ```
     git clone https://github.com/aws-samples/serverless-datalake.git
   ```

8. create a python virtualenv:
```
cd serverless-datalake
python3 -m venv .venv
```

9. After the init process completes and the virtualenv is created, you can use the following
step to activate your virtualenv.

```
source .venv/bin/activate
```

*  (Windows Platfrom skip if your using CloudShell)If you are a Windows platform, you would activate the virtualenv like this:

```
% .venv\Scripts\activate.bat
```

10. Once the virtualenv is activated, you can install the required dependencies.

```
pip install -r requirements.txt
```

11. At this point you can now synthesize the CloudFormation template for this code.

```
cdk synth -c environment_name=dev
```

12. You can deploy the generated CloudFormation template using the below command
```
cdk deploy -c environment_name=dev ServerlessDatalakeStack
```

13. After you've successfully deployed this stack on your account, you could test it out by executing the test lambda thats deployed as part of this stack.
Test lambda name: **serverless-event-simulator-dev** . This lambda will push 1K random transaction events to the event-bus.

14. Verify if raw data is available in the s3 bucket under prefix 'raw-data/....'

15. Verify if the Glue job is running

16. Once the Glue job succeeds, it would trigger a glue crawler that creates a table in our datalake

17. Head to Athena after the table is created and query the table

18. Create 3 roles -> cloud-developer / Business-Analyst / Data-engineer

19. Head to Lake formation and assing privileges to these roles

20. Swtich roles and head to Athena and test Column level security

21. Configurations for dev environment are defined in cdk.json. S3 bucket name is created on the fly based on account_id and region in which the cdk is deployed