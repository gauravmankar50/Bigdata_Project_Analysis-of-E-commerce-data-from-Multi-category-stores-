import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.dynamicframe import DynamicFrame
from pyspark.sql.functions import split
from pyspark.sql.functions import count
from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.functions import sum, isnan, col
from pyspark.sql.functions import split
from pyspark.sql.functions import col
from pyspark.sql.types import LongType, IntegerType, DateType, TimestampType, FloatType

spark = SparkSession.builder.appName("Load Data from S3").getOrCreate()
sc = SparkContext.getOrCreate()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)

df = spark.read.format("csv").option("header", "true").load("s3://gauravproject/kaggle/2019-Nov.csv")

df2 = df.filter((col("category_code").isNull()) & (col("brand").isNull()))

dfsuper = df.subtract(df2).dropna(how='all')

dfsuper = dfsuper.withColumn('category', split('category_code', '\.')[0]) \
                  .withColumn('subcategory', split('category_code', '\.')[1])

dfsuper = dfsuper.withColumn('event_date', split('event_time', ' ')[0]) \
                  .withColumn('event_time(UTC)', split('event_time', ' ')[1]) \
                  .withColumn('garbage', split('event_time', ' ')[2])


dfsuper = dfsuper.drop("event_time", "category_code", "garbage")

pivot_df = dfsuper.groupBy("event_type", "product_id", "category_id", "brand", "price", "user_id", "user_session", "category", "subcategory",  "event_date", "event_time(UTC)")\
    .pivot("event_type", ["cart", "view", "purchase"])\
    .agg(count("*"))\
    .fillna(0)

dffinal = pivot_df.filter(col("price") != 0)

dffinal = dffinal.na.drop(subset=["price"])

dffinal = dffinal.withColumn("product_id", col("product_id").cast(LongType())) \
    .withColumn("category_id", col("category_id").cast(LongType())) \
    .withColumn("user_id", col("user_id").cast(LongType())) \
    .withColumn("price", col("price").cast(FloatType())) \
    .withColumn("cart", col("cart").cast(IntegerType())) \
    .withColumn("view", col("view").cast(IntegerType())) \
    .withColumn("purchase", col("purchase").cast(IntegerType())) \
    .withColumn("event_date", col("event_date").cast(DateType())) \
    .withColumn("event_time(UTC)", col("event_time(UTC)").cast(TimestampType()))   

df_1 = dffinal.withColumn('date', split('event_time(UTC)', ' ')[0]) \
       .withColumn('time', split('event_time(UTC)', ' ')[1])

df_1 = df_1.drop("date")

df_1 = df_1.fillna('not specified')


df_2 = df_1.withColumn('time_int', unix_timestamp('time', 'HH:mm:ss').cast('integer'))

df_2 = df_2.withColumn('time_new', from_unixtime('time_int', 'HH:mm:ss'))

dynamic_frame = DynamicFrame.fromDF(df_2, glueContext, "dynamic_frame_name") 
output_dir = "s3://gauravbigout/"
glueContext.write_dynamic_frame.from_options(frame = dynamic_frame, connection_type = "s3", connection_options = {"path": output_dir}, format = "parquet")
job.commit()

