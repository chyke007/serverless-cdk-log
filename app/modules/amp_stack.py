# AMP (Amazon Managed Prometheus) Stack module
from aws_cdk import (
    aws_aps as amp,
    aws_iam as iam,
    Stack
)
from constructs import Construct

class AmpStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Create AMP Workspace
        self.workspace = amp.CfnWorkspace(
            self, "PrometheusWorkspace",
            alias="logger-app-prometheus"
        )
