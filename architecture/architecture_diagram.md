graph TD
  subgraph PublicSubnet
    ALBLogger["Public ALB (8080)"]
    LoggerService["ECS Fargate: Logger App"]
    ALBLogger -->|Target Group| LoggerService
  end

  subgraph PrivateSubnet
    ALBGrafana["Private ALB (3000)\n(Grafana)"]
    ALBLoki["Private ALB (3100)\n(Loki)"]
    GrafanaService["ECS Fargate: Grafana"]
    LokiService["ECS Fargate: Loki"]
    EFS["EFS (Grafana data)"]
    S3["S3 (Logs)"]
    ALBGrafana -->|Target Group| GrafanaService
    ALBLoki -->|Target Group| LokiService
    GrafanaService -- EFS Mount --> EFS
    LokiService -- Log Export --> S3
  end

  VPC["VPC"]
  VPC --> PublicSubnet
  VPC --> PrivateSubnet
  LoggerService -- Logs --> S3
  LoggerService -- Logs --> LokiService
  GrafanaService -- Reads Logs --> LokiService
  note1["Note: Only Logger App is public. Grafana/Loki are private."]
