from aws_cdk import (
    aws_route53 as route53,
    aws_route53_targets as targets,
    Stack
)
from constructs import Construct

class Route53Stack(Stack):
    def __init__(self, scope: Construct, id: str, vpc, internal_alb, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Private hosted zone
        self.internal_zone = route53.PrivateHostedZone(
            self, "InternalHostedZone",
            zone_name="internal.com",
            vpc=vpc
        )
        # A records for loki and grafana
        self.loki_record = route53.ARecord(
            self, "LokiInternalRecord",
            zone=self.internal_zone,
            record_name="loki.internal.com",
            target=route53.RecordTarget.from_alias(targets.LoadBalancerTarget(internal_alb))
        )
        self.grafana_record = route53.ARecord(
            self, "GrafanaInternalRecord",
            zone=self.internal_zone,
            record_name="grafana.internal.com",
            target=route53.RecordTarget.from_alias(targets.LoadBalancerTarget(internal_alb))
        ) 
