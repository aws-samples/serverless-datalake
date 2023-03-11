
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

1. Create an new IAM user(username = LakeAdmin) with Administrator access.Enable Console access too

2. Once the user is created. Head to  Security Credentials Tab and generate access/secret key for the new IAM user.

2. Copy access/secret keys for the  newly created IAM User on your local machine.

3. Search for AWS Cloudshell. Configure your aws cli environment with the access/secret keys of the new admin user using the below command on AWS Cloudshell
   ```
   aws configure
   ```

4. Git Clone the serverless-datalake repository from aws-samples
   ```
     git clone https://github.com/aws-samples/serverless-datalake.git
   ```

8. cd serverless-datalake
```
cd serverless-datalake

```

9. Fire the bash script that automates the lake creation process.
```
sh create_lake.sh
```

10. After you've successfully deployed this stack on your account, you could test it out by executing the test lambda thats deployed as part of this stack.
Test lambda name: **serverless-event-simulator-dev** . This lambda will push 1K random transaction events to the event-bus.

11. Verify if raw data is available in the s3 bucket under prefix 'raw-data/....'

12. Verify if the Glue job is running

13. Once the Glue job succeeds, it would trigger a glue crawler that creates a table in our datalake

14. Head to Athena after the table is created and query the table

15. Create 3 roles in IAM with Administrator access -> cloud-developer / cloud-analyst / cloud-data-engineer 

16. Add inline Permissions to IAM user(LakeAdmin) so that we can switch roles
```
 {
  "Version": "2012-10-17",
  "Statement": {
    "Effect": "Allow",
    "Action": "sts:AssumeRole",
    "Resource": "arn:aws:iam::account-id:role/cloud-*"
  }
}
```

16. Head to Amazon Lake formation and under Tables, select our table -> Actions -> Grant privileges to cloud-developer role

17. Add column level security

17. In an incognito window, login as LakeAdmin user.

18. Switch roles and head to Athena and test Column level security.

19. Now in Amazon Lake Formation (Back to our main window), create a Data Filter and add the below 
          a. Under Row Filter expression add ->  country='IN'
             a.1 https://docs.aws.amazon.com/lake-formation/latest/dg/data-filters-about.html
          b. Include columns you wish to view for that role.
       
       <img width="495" alt="Screenshot 2023-03-12 at 3 30 51 AM" src="https://user-images.githubusercontent.com/25897220/224513414-a123c821-39cf-49a1-9428-5f09460a10c9.png">
  
    
    
20. Head back to the incognito window and fire the select command. Confirm if RLS and CLS are correctly working for that role.
21. Configurations for dev environment are defined in cdk.json. S3 bucket name is created on the fly based on account_id and region in which the cdk is deployed
