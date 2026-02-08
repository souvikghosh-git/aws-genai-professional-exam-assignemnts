from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_iam as iam,
    aws_sagemaker as sagemaker,
    RemovalPolicy
)
from constructs import Construct

class MLOpsStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # 1. S3 Bucket for Training Data & Models
        data_bucket = s3.Bucket(self, "FineTuningDataBucket",
            versioned=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True
        )

        # 2. IAM Role for SageMaker Fine-tuning
        sagemaker_role = iam.Role(self, "SageMakerExecutionRole",
            assumed_by=iam.ServicePrincipal("sagemaker.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSageMakerFullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonS3FullAccess") # Scope down in prod
            ]
        )

        # 3. (Optional) SageMaker Model Registry Group
        # CDK higher-level constructs for SageMaker aren't as rich, using Cfn
        model_package_group = sagemaker.CfnModelPackageGroup(self, "ModelPackageGroup",
            model_package_group_name="FinancialAppModelGroup",
            model_package_group_description="Versions of financial domain adapted models"
        )
        
        # Outputs
        self.bucket_name = data_bucket.bucket_name
        self.role_arn = sagemaker_role.role_arn
        self.model_package_group_name = model_package_group.model_package_group_name
