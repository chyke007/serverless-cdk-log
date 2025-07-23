from aws_cdk import (
    aws_efs as efs,
    CfnOutput,
    Stack
)
from constructs import Construct

class EfsAccessPointsStack(Stack):
    def __init__(self, scope: Construct, id: str, file_system: efs.IFileSystem, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Grafana Access Point
        self.grafana_ap = file_system.add_access_point(
            "GrafanaAccessPoint",
            path="/grafana-data",
            create_acl=efs.Acl(owner_uid="472", owner_gid="472", permissions="750"),
            posix_user=efs.PosixUser(uid="472", gid="472"),
        )

        # Loki Access Point
        self.loki_ap = file_system.add_access_point(
            "LokiAccessPoint",
            path="/loki-data",
            create_acl=efs.Acl(owner_uid="10001", owner_gid="10001", permissions="750"),
            posix_user=efs.PosixUser(uid="10001", gid="10001"),
        )

        # Output ARNs
        CfnOutput(self, "GrafanaAccessPointArn", value=self.grafana_ap.access_point_arn)
        CfnOutput(self, "LokiAccessPointArn", value=self.loki_ap.access_point_arn)
