# ECS Stack module
from aws_cdk import (
    aws_ecs as ecs,
    aws_ec2 as ec2,
    aws_efs as efs,
    aws_s3 as s3,
    aws_ecr as ecr,
    aws_elasticloadbalancingv2 as elbv2,
    aws_logs as logs,
    aws_iam as iam,
    Stack
)
from constructs import Construct

class EcsStack(Stack):
    def __init__(self, scope: Construct, id: str, vpc, ecs_sg, efs, efs_grafana_ap, efs_loki_ap, s3_bucket, ecr_grafana, ecr_loki, ecr_logger, alb_stack, **kwargs):
        super().__init__(scope, id, **kwargs)

        # ECS Cluster
        self.cluster = ecs.Cluster(self, "AppCluster", vpc=vpc,  cluster_name="ecsstack-cluster")

        # Task Role and Execution Role
        task_role = iam.Role(self, "TaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            role_name="TaskRole"
        )
        execution_role = iam.Role(self, "ExecutionRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            role_name="ExecutionRole"
        )

        # Grant EFS access (file system and access points)
        task_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "elasticfilesystem:ClientMount",
                "elasticfilesystem:ClientWrite",
                "elasticfilesystem:ClientRootAccess",
                "elasticfilesystem:DescribeMountTargets"
            ],
            resources=[
                efs.file_system_arn,
                efs_grafana_ap.access_point_arn,
                efs_loki_ap.access_point_arn
            ]
        ))
       
        execution_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "elasticfilesystem:ClientMount",
                "elasticfilesystem:ClientWrite",
                "elasticfilesystem:ClientRootAccess",
                "elasticfilesystem:DescribeMountTargets"
            ],
            resources=[
                efs.file_system_arn,
                efs_grafana_ap.access_point_arn,
                efs_loki_ap.access_point_arn
            ]
        ))
       
        # Grant S3 access for Loki
        task_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "s3:PutObject",
                "s3:GetObject",
                "s3:ListBucket",
                "s3:DeleteObject"
            ],
            resources=[
                s3_bucket.bucket_arn,
                f"{s3_bucket.bucket_arn}/*"
            ]
        ))

        execution_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "s3:PutObject",
                "s3:GetObject",
                "s3:ListBucket",
                "s3:DeleteObject"
            ],
            resources=[
                s3_bucket.bucket_arn,
                f"{s3_bucket.bucket_arn}/*"
            ]
        ))

        # Grafana Task Definition
        grafana_task_def = ecs.FargateTaskDefinition(
            self, "GrafanaTaskDef",
            memory_limit_mib=2048,
            cpu=1024,
            task_role=task_role,
            execution_role=execution_role
        )
        # EFS volume for Grafana
        grafana_task_def.add_volume(
            name="grafana-efs",
            efs_volume_configuration=ecs.EfsVolumeConfiguration(
                file_system_id=efs.file_system_id,
                authorization_config=ecs.AuthorizationConfig(
                    access_point_id=efs_grafana_ap.access_point_id,
                    iam="ENABLED"
                ),
                transit_encryption="ENABLED"
            )
        )
        grafana_container = grafana_task_def.add_container(
            "GrafanaContainer",
            image=ecs.ContainerImage.from_ecr_repository(ecr_grafana),
            logging=ecs.LogDriver.aws_logs(stream_prefix="grafana"),
            environment={"GF_SECURITY_ADMIN_PASSWORD": "admin"}
        )
        grafana_container.add_port_mappings(
            ecs.PortMapping(container_port=3000, protocol=ecs.Protocol.TCP)
        )
        grafana_container.add_mount_points(
            ecs.MountPoint(
                container_path="/var/lib/grafana",
                source_volume="grafana-efs",
                read_only=False
            )
        )

        # Loki Task Definition
        loki_task_def = ecs.FargateTaskDefinition(
            self, "LokiTaskDef",
            memory_limit_mib=2048,
            cpu=1024,
            task_role=task_role,
            execution_role=execution_role
        )
        # EFS volume for Loki
        loki_task_def.add_volume(
            name="loki-efs",
            efs_volume_configuration=ecs.EfsVolumeConfiguration(
                file_system_id=efs.file_system_id,
                authorization_config=ecs.AuthorizationConfig(
                    access_point_id=efs_loki_ap.access_point_id,
                    iam="ENABLED"
                ),
                transit_encryption="ENABLED"
            )
        )
        loki_container = loki_task_def.add_container(
            "LokiContainer",
            image=ecs.ContainerImage.from_ecr_repository(ecr_loki),
            logging=ecs.LogDriver.aws_logs(stream_prefix="loki")
        )
        loki_container.add_port_mappings(
            ecs.PortMapping(container_port=3100, protocol=ecs.Protocol.TCP)
        )
        loki_container.add_mount_points(
            ecs.MountPoint(
                container_path="/var/loki",
                source_volume="loki-efs",
                read_only=False
            )
        )

        # Grafana Service
        grafana_service = ecs.FargateService(
            self, "GrafanaService",
            service_name="grafana-service",
            cluster=self.cluster,
            task_definition=grafana_task_def,
            security_groups=[ecs_sg],
            desired_count=1,
            assign_public_ip=True,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC)
        )
        # Loki Service
        loki_service = ecs.FargateService(
            self, "LokiService",
            service_name="loki-service",
            cluster=self.cluster,
            task_definition=loki_task_def,
            security_groups=[ecs_sg],
            desired_count=1,
            assign_public_ip=False,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)
        )

        # Logger App Task Definition with FireLens Sidecar
        logger_task_def = ecs.FargateTaskDefinition(
            self, "LoggerTaskDef",
            memory_limit_mib=1024,
            cpu=512,
            task_role=task_role,
            execution_role=execution_role
        )
       
       
        # Logger app container
        logger_container=logger_task_def.add_container(
            "LoggerAppContainer",
            image=ecs.ContainerImage.from_ecr_repository(ecr_logger),
            essential=True,
            logging=ecs.LogDrivers.firelens(
                options={
                    "Name": "grafana-loki",
                    "Url": "http://loki.internal.com/loki/api/v1/push",
                    # "Labels": "job=firelens-logs,environment=production",
                    "LabelKeys": "container_name,ecs_task_definition,source,ecs_cluster",
                    "LineFormat": "key_value",
                    "RemoveKeys": "container_id,ecs_task_arn"
                }
            )
        )
    
        logger_container.add_port_mappings(
            ecs.PortMapping(container_port=8080, protocol=ecs.Protocol.TCP)
        )

        # FireLens log router (sidecar)
        logger_task_def.add_firelens_log_router(
            "LogRouter",
            image=ecs.ContainerImage.from_registry("grafana/fluent-bit-plugin-loki:latest"),
            essential=True,
            firelens_config=ecs.FirelensConfig(
                type=ecs.FirelensLogRouterType.FLUENTBIT, 
                ),
            logging=ecs.LogDrivers.aws_logs(stream_prefix="firelens")
        )

        # Logger Service
        logger_service = ecs.FargateService(
            self, "LoggerService",
            service_name="logger-service",
            cluster=self.cluster,
            task_definition=logger_task_def,
            security_groups=[ecs_sg],
            desired_count=1,
            assign_public_ip=True,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC)
        )
        # Register ECS services as targets in their respective target groups
        alb_stack.logger_tg.add_target(logger_service)
        alb_stack.grafana_tg.add_target(grafana_service)
        alb_stack.loki_tg.add_target(loki_service) 
