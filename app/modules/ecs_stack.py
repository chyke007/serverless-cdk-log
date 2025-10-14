# ECS Stack module
from aws_cdk import (
    aws_ecs as ecs,
    aws_ec2 as ec2,
    aws_efs as efs,
    aws_s3 as s3,
    aws_ecr as ecr,
    aws_elasticloadbalancingv2 as elbv2,
    # Logger Service with multiple target groups
    aws_ecs_patterns as ecs_patterns,
    aws_logs as logs,
    aws_iam as iam,
    aws_ssm as ssm,
    Stack
)
        
from constructs import Construct

class EcsStack(Stack):
    def __init__(self, scope: Construct, id: str, vpc, ecs_sg, efs, efs_grafana_ap, efs_loki_ap, s3_bucket, ecr_grafana, ecr_loki, ecr_logger, alb_stack, amp_workspace, sqs_stack, dynamodb_stack, **kwargs):
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

        # Add Add AMP permissions, CloudWatch permissions and  X-Ray metrics)
        task_role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("AmazonPrometheusFullAccess"))
        execution_role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("AmazonPrometheusFullAccess"))
        task_role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("CloudWatchFullAccess"))
        task_role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("AWSXRayDaemonWriteAccess"))
        task_role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("AWSXrayReadOnlyAccess"))

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
                efs_loki_ap.access_point_arn,
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
                efs_loki_ap.access_point_arn,
            ]
        ))

        # Add ADOT Collector execution role permissions
        execution_role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AmazonECSTaskExecutionRolePolicy"))
        execution_role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("CloudWatchLogsFullAccess"))

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

        # Grant SQS permissions to the task role (avoid cross-stack policy attachment)
        sqs_stack.message_queue.grant_send_messages(task_role)
        sqs_stack.message_queue.grant_consume_messages(task_role)

        # Grant DynamoDB permissions to the task role (avoid cross-stack policy attachment)
        dynamodb_stack.app_table.grant_read_write_data(task_role)

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
            environment={
                "GF_SECURITY_ADMIN_PASSWORD": "admin",
                "AMP_WORKSPACE_URL": amp_workspace.attr_prometheus_endpoint,
                "AWS_SDK_LOAD_CONFIG":"true",
                "GF_AUTH_SIGV4_AUTH_ENABLED":"true"
            }
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
            ),
            environment={
                "OTEL_SERVICE_NAME": "logger-app",
                "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4317",
                "OTEL_TRACES_SAMPLER": "parentbased_always_on",
                # "AWS_XRAY_DAEMON_ADDRESS": "aws-otel-collector:2000",
                "AWS_REGION": "us-east-1",
                "SQS_MESSAGE_QUEUE_URL": sqs_stack.message_queue.queue_url,
                "DYNAMODB_APP_TABLE": dynamodb_stack.app_table.table_name,
                
            }
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
        
        
        logger_service = ecs.FargateService(
            self, "LoggerService",
            service_name="logger-service",
            cluster=self.cluster,
            task_definition=logger_task_def,
            security_groups=[ecs_sg],
            desired_count=1,
            assign_public_ip=True,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
        )
    
        adot_collector_container = logger_task_def.add_container(
            "AdotCollector",
            image=ecs.ContainerImage.from_registry("public.ecr.aws/aws-observability/aws-otel-collector:latest"),
            essential=False,
            logging=ecs.LogDriver.aws_logs(stream_prefix="adot-collector"),
            environment={
                "AWS_REGION": "us-east-1",
                "AWS_XRAY_TRACING_NAME": "logger-app",
                "OTEL_RESOURCE_ATTRIBUTES": "service.name=logger-app,service.version=1.0.0",
                "AOT_CONFIG_CONTENT": f"""receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318
  awsecscontainermetrics:
    collection_interval: 10s
processors:
  batch:
    timeout: 1s
    send_batch_size: 1024
  filter:
    metrics:
      include:
        match_type: strict
        metric_names:
          - ecs.task.memory.utilized
          - ecs.task.memory.reserved
          - ecs.task.cpu.utilized
          - ecs.task.cpu.reserved
          - ecs.task.network.rate.rx
          - ecs.task.network.rate.tx
          - ecs.task.storage.read_bytes
          - ecs.task.storage.write_bytes
exporters:
  awsxray:
    region: us-east-1
  prometheusremotewrite:
    endpoint: {amp_workspace.attr_prometheus_endpoint}api/v1/remote_write
    auth:
      authenticator: sigv4auth
extensions:
  health_check:
  pprof:
    endpoint: :1888
  zpages:
    endpoint: :55679
  sigv4auth:
    region: us-east-1
    service: aps
service:
  extensions: [pprof, zpages, health_check, sigv4auth]
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [awsxray]
    metrics:
      receivers: [otlp]
      processors: [batch]
      exporters: [prometheusremotewrite]
    metrics/ecs:
      receivers: [awsecscontainermetrics]
      processors: [filter]
      exporters: [prometheusremotewrite]"""
            }
        )

        adot_collector_container.add_port_mappings(
            ecs.PortMapping(container_port=4317, protocol=ecs.Protocol.TCP)
        )
        adot_collector_container.add_port_mappings(
            ecs.PortMapping(container_port=4318, protocol=ecs.Protocol.TCP)
        )
        adot_collector_container.add_port_mappings(
            ecs.PortMapping(container_port=1888, protocol=ecs.Protocol.TCP)
        )
        adot_collector_container.add_port_mappings(
            ecs.PortMapping(container_port=55679, protocol=ecs.Protocol.TCP)
        )
        
        alb_stack.grafana_tg.add_target(grafana_service)
        alb_stack.loki_tg.add_target(loki_service) 
        alb_stack.logger_tg.add_target(logger_service)
