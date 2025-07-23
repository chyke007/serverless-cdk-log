from aws_cdk import (
    aws_efs as efs,
    RemovalPolicy,
    Stack,
    CfnOutput,
    aws_ec2 as ec2
)
from constructs import Construct

class EfsStack(Stack):
    def __init__(self, scope: Construct, id: str, vpc, sg, **kwargs):
        super().__init__(scope, id, **kwargs)

        self.efs = efs.FileSystem(
            self, "GrafanaLokiEfs",
            vpc=vpc,
            security_group=sg,
            removal_policy=RemovalPolicy.DESTROY,
            lifecycle_policy=efs.LifecyclePolicy.AFTER_7_DAYS,
            performance_mode=efs.PerformanceMode.GENERAL_PURPOSE,
            throughput_mode=efs.ThroughputMode.BURSTING,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)
        )

        # Output file_system_id
        CfnOutput(self, "FileSystemId", value=self.efs.file_system_id)
