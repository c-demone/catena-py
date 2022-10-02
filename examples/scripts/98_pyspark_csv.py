#!/usr/bin/env python


import pyspark
import os

spark = pyspark.sql.SparkSession.builder.appName('pyspark_test').getOrCreate()

data = spark.read.csv(os.environ['data_dir'])

data.show()
