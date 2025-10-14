from aws_cdk import (
    aws_ec2 as ec2,
    Stack
)
from constructs import Construct

class SgStack(Stack):
    def __init__(self, scope: Construct, id: str, vpc, **kwargs):
        super().__init__(scope, id, **kwargs)

        # ✅ Security Group for VPN Endpoint
        self.client_vpn_sg = ec2.SecurityGroup(
            self, "ClientVPNSG",
            vpc=vpc,
            description="Allow VPN traffic to VPC resources",
            allow_all_outbound=True
        )
        self.client_vpn_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.all_traffic(), "Allow VPN client traffic")

        # ALB Security Group
        self.alb_sg = ec2.SecurityGroup(
            self, "AlbSG",
            vpc=vpc,
            description="Allow HTTP access to ALB",
            allow_all_outbound=True
        )
        self.alb_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(80), "Allow HTTP from anywhere")

        # ECS Security Group
        self.ecs_sg = ec2.SecurityGroup(
            self, "EcsSG",
            vpc=vpc,
            description="Allow traffic from ALB and EFS",
            allow_all_outbound=True
        )
      
        # EFS Security Group
        self.efs_sg = ec2.SecurityGroup(
            self, "EfsSG",
            vpc=vpc,
            description="Allow NFS from ECS",
            allow_all_outbound=True
        )
        self.efs_sg.add_ingress_rule(self.ecs_sg, ec2.Port.tcp(2049), "Allow NFS from ECS tasks")

        # Internal ALB Security Group (for private ALB)
        self.internal_alb_sg = ec2.SecurityGroup(
            self, "InternalAlbSG",
            vpc=vpc,
            description="Allow HTTP access to internal ALB from VPC",
            allow_all_outbound=True
        )
        self.internal_alb_sg.add_ingress_rule(
            ec2.Peer.ipv4(vpc.vpc_cidr_block),
            ec2.Port.tcp(80),
            "Allow HTTP from within VPC"
        ) 


        self.ecs_sg.add_ingress_rule(self.alb_sg, ec2.Port.tcp(8080), "Allow Logger app from ALB")
        self.ecs_sg.add_ingress_rule(self.internal_alb_sg, ec2.Port.tcp(3000), "Allow Grafana from ALB")
        self.ecs_sg.add_ingress_rule(self.internal_alb_sg, ec2.Port.tcp(3100), "Allow Loki from ALB")
        self.ecs_sg.add_ingress_rule(self.internal_alb_sg, ec2.Port.tcp(9090), "Allow Prometheus from ALB")
