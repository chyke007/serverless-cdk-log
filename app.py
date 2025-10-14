#!/usr/bin/env python3
import aws_cdk as cdk
from aws_cdk import CfnOutput
from app.modules.vpc_stack import VpcStack
from app.modules.sg_stack import SgStack
from app.modules.efs_stack import EfsStack
from app.modules.efs_access_points_stack import EfsAccessPointsStack
from app.modules.s3_stack import S3Stack
from app.modules.ecr_stack import EcrStack
from app.modules.alb_stack import AlbStack
from app.modules.ecs_stack import EcsStack
from app.modules.route53_stack import Route53Stack
from app.modules.client_vpn_stack import ClientVpnStack
from app.modules.amp_stack import AmpStack
from app.modules.sqs_stack import SqsStack
from app.modules.dynamodb_stack import DynamoDbStack

app = cdk.App()

vpc_stack = VpcStack(app, "VpcStack")
sg_stack = SgStack(app, "SgStack", vpc=vpc_stack.vpc)
client_vpn_stack = ClientVpnStack(app, "ClientVpnStack", vpc=vpc_stack.vpc, client_vpn_sg=sg_stack.client_vpn_sg)
s3_stack = S3Stack(app, "S3Stack")
ecr_stack = EcrStack(app, "EcrStack")
alb_stack = AlbStack(app, "AlbStack", vpc=vpc_stack.vpc, alb_sg=sg_stack.alb_sg, internal_alb_sg=sg_stack.internal_alb_sg)

efs_stack = EfsStack(app, "EfsStack", vpc=vpc_stack.vpc, sg=sg_stack.efs_sg)
# EFS Access Points Stack (depends on EFS)
efs_ap_stack = EfsAccessPointsStack(app, "EfsAccessPointsStack", file_system=efs_stack.efs)
efs_ap_stack.add_dependency(efs_stack)

# AMP Stack
amp_stack = AmpStack(app, "AmpStack")
sqs_stack = SqsStack(app, "SqsStack")
dynamodb_stack = DynamoDbStack(app, "DynamoDbStack")

ecs_stack = EcsStack(
    app, "EcsStack",
    vpc=vpc_stack.vpc,
    ecs_sg=sg_stack.ecs_sg,
    efs=efs_stack.efs,
    efs_grafana_ap=efs_ap_stack.grafana_ap,
    efs_loki_ap=efs_ap_stack.loki_ap,
    s3_bucket=s3_stack.bucket,
    ecr_grafana=ecr_stack.grafana_repo,
    ecr_loki=ecr_stack.loki_repo,
    ecr_logger=ecr_stack.logger_repo,
    alb_stack=alb_stack,
    amp_workspace=amp_stack.workspace,
    sqs_stack=sqs_stack,
    dynamodb_stack=dynamodb_stack
)

route54_stack = Route53Stack(app, "Route53Stack", vpc=vpc_stack.vpc, internal_alb=alb_stack.internal_alb)

app.synth()
