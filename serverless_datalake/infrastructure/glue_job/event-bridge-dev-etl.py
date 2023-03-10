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
import hashlib, uuid


def get_masked_entities():
    """
    return a list of entities to be masked.
    If unstructured, use comprehend to determine entities to be masked
    """
    return ["name", "credit_card", "account", "city"]

def get_encrypted_entities():
    """
    return a list of entities to be masked.
    """
    return ["name", "credit_card"]
 

def get_region_name():
    global my_region
    my_session = boto3.session.Session()
    return my_session.region_name
    

def detect_sensitive_info(r):
    """
    return a tuple after masking is complete.
    If unstructured, use comprehend to determine entities to be masked
    """ 
    
    metadata = r['trnx_msg']
    try:
        for entity in get_masked_entities():
            entity_masked = entity + "_masked"
            r[entity_masked] = "#######################"
    except:
        print ("DEBUG:",sys.exc_info())

    client_pii = boto3.client('comprehend', region_name=get_region_name())
    
    try:
        response = client_pii.detect_pii_entities(
            Text = metadata,
            LanguageCode = 'en'
        )
        clean_text = metadata
        # reversed to not modify the offsets of other entities when substituting
        for NER in reversed(response['Entities']):
            clean_text = clean_text[:NER['BeginOffset']] + NER['Type'] + clean_text[NER['EndOffset']:]
        print(clean_text)
        r['trnx_msg_masked'] = clean_text
    except:
        print ("DEBUG:",sys.exc_info())

    return r


def encrypt_rows(r):
    """
    return tuple with encrypted string
    Hardcoding salted string. PLease feel free to use SSM and KMS.
    """
    salted_string = 'glue_crypt'
    encrypted_entities = get_encrypted_entities()
    print ("encrypt_rows", salted_string, encrypted_entities)
    try:
        for entity in encrypted_entities:
            salted_entity = r[entity] + salted_string
            hashkey = hashlib.sha3_256(salted_entity.encode()).hexdigest()
            r[entity + '_encrypted'] = hashkey
    except:
        print ("DEBUG:",sys.exc_info())
    return r


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
        
        logger.info('\n -- Printing datasource schema --')
        logger.info(datasource0.printSchema())
        
        # Unnests json data into a flat dataframe.
        # This glue transform converts a nested json into a flattened Glue DynamicFrame
        logger.info('\n -- Unnest dynamic frame --')
        unnested_dyf = UnnestFrame.apply(frame=datasource0,  transformation_ctx='unnest')
        
        # Convert to a Spark DataFrame
        sparkDF = unnested_dyf.toDF()
        
        logger.info('\n -- Add new Columns to Spark data frame --')
        # Generate Year/Month/day columns from the time field
        sparkDF = sparkDF.withColumn('year', substring('time', 1, 4))
        sparkDF = sparkDF.withColumn('month', substring('time', 6, 2))
        sparkDF = sparkDF.withColumn('day', substring('time', 9, 2))
        
        # Rename fields
        sparkDF = sparkDF.withColumnRenamed("detail.amount.value", "amount")
        sparkDF = sparkDF.withColumnRenamed("detail.amount.currency", "currency")
        sparkDF = sparkDF.withColumnRenamed("detail.location.country", "country")
        sparkDF = sparkDF.withColumnRenamed("detail.location.state", "state")
        sparkDF = sparkDF.withColumnRenamed("detail.location.city", "city")
        sparkDF = sparkDF.withColumnRenamed("detail.credit_card", "credit_card_number")
        sparkDF = sparkDF.withColumnRenamed("detail.transaction_message", "trnx_msg")
        
        # Concat firstName and LastName columns
        sparkDF = sparkDF.withColumn('name', concat_ws(' ', sparkDF["`detail.firstName`"], sparkDF["`detail.lastName`"]))

        dt_cols = sparkDF.columns
        # Drop detail.* columns
        for col_dt in dt_cols:
            if '.' in col_dt:
                logger.info(f'Dropping Column {col_dt}')
                sparkDF = sparkDF.drop(col_dt)
        

        transformed_dyf = DynamicFrame.fromDF(sparkDF, glueContext, "trnx")

        # Secure the lake through masking and encryption
        # Approach 1: Mask PII data
        masked_dyf = Map.apply(frame = transformed_dyf, f = detect_sensitive_info)
        masked_dyf.show()

        # Approach 2: Encrypting PII data
        # Apply encryption to the identified fields
        encrypted_dyf = Map.apply(frame = masked_dyf, f = encrypt_rows)

        
        # This Glue Transform drops null fields/columns if present in the dataset
        dropnullfields = DropNullFields.apply(frame=encrypted_dyf, transformation_ctx="dropnullfields")
        # This function repartitions the dataset into exactly two files however Coalesce is preferred
        # dropnullfields = dropnullfields.repartition(2)

        # logger.info('\n -- Printing schema after ETL --')
        # logger.info(dropnullfields.printSchema())
        
        logger.info('\n -- Storing data in snappy compressed, partitioned, parquet format for optimal query performance --')
        # Partition the DynamicFrame by Year/Month/Day. Compression type is snappy. Format is Parquet 
        datasink4 = glueContext.write_dynamic_frame.from_options(frame=dropnullfields, connection_type="s3",
                                                                 connection_options={"path": s3_output_path,
                                                                                     "partitionKeys": ['year', 'month',
                                                                                                       'day']},
                                                                 format="parquet", transformation_ctx="s3sink")
        

    logger.info('Sample Glue Job complete')
    # Necessary for Glue Job Bookmarking
    job.commit()
    