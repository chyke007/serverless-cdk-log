from aws_cdk import (
    aws_ecr as ecr,
    CfnOutput,
    Stack
)

from constructs import Construct

class EcrStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        self.grafana_repo = ecr.Repository(self, "GrafanaRepo", repository_name="ecrstack-grafana-repo",
            image_scan_on_push=True
        )
        self.loki_repo = ecr.Repository(self, "LokiRepo", repository_name="ecrstack-loki-repo",
            image_scan_on_push=True
        )
        self.logger_repo = ecr.Repository(self, "LoggerRepo", repository_name="ecrstack-logger-repo",
            image_scan_on_push=True
        )
        CfnOutput(self, "LoggerEcrRepoUri", value=self.logger_repo.repository_uri, description="ECR URI for the logger app. Use this for ECR_LOGGER_REPO in GitHub Actions.") 
