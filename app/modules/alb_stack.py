from aws_cdk import (
    aws_ec2 as ec2,
    aws_elasticloadbalancingv2 as elbv2,
    Stack
)
from constructs import Construct

class AlbStack(Stack):
    def __init__(self, scope: Construct, id: str, vpc, alb_sg, internal_alb_sg, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Single private ALB for Loki and Grafana
        self.internal_alb = elbv2.ApplicationLoadBalancer(
            self, "InternalAlb",
            vpc=vpc,
            internet_facing=False,
            security_group=internal_alb_sg,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)
        )
        # Target groups
        self.loki_tg = elbv2.ApplicationTargetGroup(
            self, "LokiTargetGroup",
            vpc=vpc,
            port=3100,
            protocol=elbv2.ApplicationProtocol.HTTP,
            target_type=elbv2.TargetType.IP,
            health_check=elbv2.HealthCheck(path="/ready", port="3100")
        )
        self.grafana_tg = elbv2.ApplicationTargetGroup(
            self, "GrafanaTargetGroup",
            vpc=vpc,
            port=3000,
            protocol=elbv2.ApplicationProtocol.HTTP,
            target_type=elbv2.TargetType.IP,
            health_check=elbv2.HealthCheck(path="/login", port="3000")
        )
        # Listener with host-based routing
        self.internal_listener = self.internal_alb.add_listener(
            "InternalListener",
            port=80,
            protocol=elbv2.ApplicationProtocol.HTTP,
            default_action=elbv2.ListenerAction.forward([self.grafana_tg])
        )
        self.internal_listener.add_action(
            "LokiHostRule",
            priority=1,
            conditions=[elbv2.ListenerCondition.host_headers(["loki.internal.com"])],
            action=elbv2.ListenerAction.forward([self.loki_tg])
        )
        self.internal_listener.add_action(
            "GrafanaHostRule",
            priority=2,
            conditions=[elbv2.ListenerCondition.host_headers(["grafana.internal.com"])],
            action=elbv2.ListenerAction.forward([self.grafana_tg])
        )
        # Public ALB for Logger App
        self.logger_alb = elbv2.ApplicationLoadBalancer(
            self, "LoggerAlb",
            vpc=vpc,
            internet_facing=True,
            security_group=alb_sg,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC)
        )
        # Target group for Logger App (public ALB)
        self.logger_tg = elbv2.ApplicationTargetGroup(
            self, "LoggerTargetGroup",
            vpc=vpc,
            port=8080,
            protocol=elbv2.ApplicationProtocol.HTTP,
            target_type=elbv2.TargetType.IP,
            health_check=elbv2.HealthCheck(path="/", port="8080")
        )
        self.logger_listener = self.logger_alb.add_listener(
            "LoggerListener",
            port=80,
            protocol=elbv2.ApplicationProtocol.HTTP,
            default_action=elbv2.ListenerAction.forward([self.logger_tg])
        ) 
