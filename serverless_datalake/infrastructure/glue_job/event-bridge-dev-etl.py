import boto3
import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.dynamicframe import DynamicFrame
from datetime import datetime, timedelta
from pyspark.sql.functions import to_json, struct, substring, from_json, lit, col, when, concat, concat_ws
from pyspark.sql.types import StringType

args = getResolvedOptions(sys.argv, ['JOB_NAME', 's3_output_location', 's3_input_location'])
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)
logger = glueContext.get_logger()

logger.info('\n -- Glue ETL Job begins -- ')

s3_input_path = args["s3_input_location"]
s3_output_path = args["s3_output_location"]

now = datetime.utcnow()
current_date = now.date()
# Go back 5 days in the past. With Glue Bookmarking enabled only newer files are processed
from_date = current_date - timedelta(days=5)
delta = timedelta(days=1)
bucket_path = []
while from_date <= current_date:
    # S3 Paths to process.
    if len(bucket_path) >= 10:
        logger.info(f'\n Backtrack complete: Found all paths up to {from_date} ')
        break
    lastprocessedtimestamp = str(from_date)
    path = s3_input_path + 'year=' + str(from_date.year) + '/month=' + str(from_date.month).zfill(
        2) + '/day=' + str(from_date.day).zfill(2)
    logger.info(f'\n AWS Glue will check for newer unprocessed files in path : {path}')
    bucket_path.append(path)
    from_date += delta

if len(bucket_path) > 0:
    # Read S3 data as a Glue Dynamic Frame
    datasource0 = glueContext.create_dynamic_frame.from_options(connection_type="s3",
                                                                connection_options={'paths': bucket_path,
                                                                                    'groupFiles': 'inPartition'},
                                                                format="json", transformation_ctx="dtx")
    if datasource0 and datasource0.count() > 0:
        logger.info('\n -- Count Number of Rows --')
        print(datasource0.count())
        logger.info('\n -- Printing datasource schema --')
        logger.info(datasource0.printSchema())
        logger.info('\n -- Flatten dynamic frame --')
        # Unnests json data into a flat dataframe
        unnested_dyf = UnnestFrame.apply(frame=datasource0,  transformation_ctx='unnest')
        logger.info('\n -- Convert dynamic frame to Spark data frame --')
        sparkDF = unnested_dyf.toDF()
        logger.info('\n -- Add new Columns to Spark data frame --')
        sparkDF = sparkDF.withColumn('year', substring('time', 1, 4))
        sparkDF = sparkDF.withColumn('month', substring('time', 6, 2))
        sparkDF = sparkDF.withColumn('day', substring('time', 9, 2))
        sparkDF = sparkDF.withColumnRenamed("detail.amount.value", "amount")
        sparkDF = sparkDF.withColumnRenamed("detail.amount.currency", "currency")
        sparkDF = sparkDF.withColumnRenamed("detail.location.country", "country")
        sparkDF = sparkDF.withColumnRenamed("detail.location.state", "state")
        sparkDF = sparkDF.withColumn('name', concat_ws(' ', sparkDF["`detail.firstName`"], sparkDF["`detail.lastName`"]))

        dt_cols = sparkDF.columns
        for col_dt in dt_cols:
            if '.' in col_dt:
                logger.info(f'Dropping Column {col_dt}')
                sparkDF = sparkDF.drop(col_dt)
        
        transformed_dyf = DynamicFrame.fromDF(sparkDF, glueContext, "trnx")
        
        # drop null fields if present
        dropnullfields = DropNullFields.apply(frame=transformed_dyf, transformation_ctx="dropnullfields")
        dropnullfields = dropnullfields.repartition(2)

        logger.info('\n -- Printing schema after ETL --')
        logger.info(dropnullfields.printSchema())
        # Store in Compressed partitioned Parquet format on S3. Data partitioned by Year/Month/Day
        logger.info('\n -- Storing data in snappy compressed, partitioned, parquet format for optimal query performance --')
        datasink4 = glueContext.write_dynamic_frame.from_options(frame=dropnullfields, connection_type="s3",
                                                                 connection_options={"path": s3_output_path,
                                                                                     "partitionKeys": ['year', 'month',
                                                                                                       'day']},
                                                                 format="parquet", transformation_ctx="s3sink")
        

    logger.info('Sample Glue Job complete')
    # Necessary for Glue Job Bookmarking
    job.commit()
    