from aws_cdk import (
    aws_s3 as s3,
    RemovalPolicy,
    Stack
)
from constructs import Construct

class S3Stack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        self.bucket = s3.Bucket(
            self, "serverless-log-bucket-cdk",
            bucket_name="serverless-log-bucket-cdk",  
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True
        ) 
