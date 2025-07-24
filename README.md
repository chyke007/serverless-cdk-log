# Serverless Logging and Visualization powered by AWS CDK!

## Architecture Diagram
<br>
  <img src="https://github.com/chyke007/serverless-cdk-log/blob/main/architecture/architecture_diagram.png" alt="Architecture" width="700"/>
<br>


## Setup
To manually create a virtualenv on MacOS and Linux:

```
$ python3 -m venv .venv
```

After the init process completes and the virtualenv is created, you can use the following
step to activate your virtualenv.

```
$ source .venv/bin/activate
```

If you are a Windows platform, you would activate the virtualenv like this:

```
% .venv\Scripts\activate.bat
```

Once the virtualenv is activated, you can install the required dependencies.

```
$ pip install -r requirements.txt
```

At this point you can now synthesize the CloudFormation template for this code.

```
$ cdk synth
```

To add additional dependencies, for example other CDK libraries, just add
them to your `requirements.txt` file and rerun the `pip install -r requirements.txt`
command.

## Useful commands

 * `cdk ls`          list all stacks in the app
 * `cdk synth`       emits the synthesized CloudFormation template
 * `cdk deploy`      deploy this stack to your default AWS account/region
 * `cdk diff`        compare deployed stack with current state
 * `cdk docs`        open CDK documentation

## Sample Python Logger Web App

A sample logger web app is provided in `app/sample_logger.py` that generates random logs and exposes a web endpoint. Each visit to `/` logs a timestamped message. The app is built with **FastAPI**.

### How to run locally

```bash
pip install -r requirements.txt
python app/sample_logger.py
```

Or run directly with uvicorn:

```bash
uvicorn app.sample_logger:app --host 0.0.0.0 --port 8080
```

Visit [http://localhost:8080](http://localhost:8080) in your browser.

### How to run in Docker

```bash
docker build -t logger-app .
docker run -p 8080:8080 logger-app
```

## Architecture

This project deploys a modern AWS logging and monitoring stack using ECS Fargate, ALB, EFS, S3, and FireLens. The architecture is as follows:

- **Logger App**: Runs as an ECS Fargate service, exposed via a public Application Load Balancer (ALB) on port 8080. Anyone can access it from the internet.
- **Grafana & Loki**: Both run as ECS Fargate services in private subnets, each behind a private/internal ALB (Grafana on 3000, Loki on 3100). They are not accessible from the public internet.
- **EFS**: Used by Grafana for persistent storage of dashboards and settings.
- **S3**: Used for log storage and backup.
- **FireLens**: Sidecar containers forward logs from ECS tasks to Loki and/or S3.
- **Security Groups**: Restrict access so only the ALB can reach the ECS services, and only ECS can reach EFS.
- **Flow**:
  - Users access the logger app via the public ALB.
  - Logger app generates logs and exposes a web endpoint.
  - Logs are sent to Loki and S3.
  - Grafana reads logs from Loki for visualization.
  - Only the logger app is public; Grafana and Loki are private.
  - To access Grafana, connection to Client VPN is required

## Architecture Diagram(in mermaid)

See the mermaid architecture below:

```mermaid
graph TD
  subgraph VPC["VPC (10.0.0.0/16)"]
    
    subgraph PublicSubnet["Public Subnet"]
      ALBLogger["Public ALB (Listener: 8080)<br>Security Group: Allows Internet -> Logger"]
      LoggerService["ECS Fargate Service: Logger App<br>Task Definition: logger-task"]
      ECRLogger["Amazon ECR: Logger Image<br>(ecrstack-logger-repo)"]
      ALBLogger -->|Target Group| LoggerService
    end

    subgraph PrivateSubnet["Private Subnet"]
      ALBGrafana["Private ALB (Listener: 3000)<br>Security Group: Internal Access"]
      ALBLoki["Private ALB (Listener: 3100)<br>Security Group: Internal Access"]
      GrafanaService["ECS Fargate Service: Grafana<br>Task Definition: grafana-task"]
      LokiService["ECS Fargate Service: Loki<br>Task Definition: loki-task"]
      ECRGrafana["Amazon ECR: Grafana Image<br>(ecrstack-grafana-repo)"]
      ECRLoki["Amazon ECR: Loki Image<br>(ecrstack-loki-repo)"]
      EFS["Amazon EFS (Persistent Storage)<br>Access Points for Grafana & Loki"]
      S3["Amazon S3 (Log Archive Bucket)<br>serverless-log-bucket-cdk"]
      
      ALBGrafana -->|Target Group| GrafanaService
      ALBLoki -->|Target Group| LokiService
      GrafanaService -- Mount --> EFS
      LokiService -- Mount --> EFS
      LokiService -- Push WAL & Chunks --> S3
    end

    subgraph Route53["Route 53 Private Hosted Zone<br>(internal.com)"]
      DNSGrafana["grafana.internal.com -> Private ALB"]
      DNSLoki["loki.internal.com -> Private ALB"]
      DNSGrafana --> ALBGrafana
      DNSLoki --> ALBLoki
    end

    subgraph ClientVPN["AWS Client VPN"]
      VPNEndpoint["Client VPN Endpoint<br>(Mutual TLS Auth)<br>Security Group: Allows DNS & ALB Access"]
      VPNEndpoint --> DNSGrafana
      VPNEndpoint --> DNSLoki
    end

    LoggerService -- Logs via FireLens --> LokiService
    GrafanaService -- Queries Metrics --> LokiService
    LoggerService -- Container Images --> ECRLogger
    GrafanaService -- Container Images --> ECRGrafana
    LokiService -- Container Images --> ECRLoki
  end

  note1["Note: Logger Service is public via ALB.<br>Grafana & Loki are private and accessed via Client VPN."]
```

## Deploying with GitHub Actions

 GitHub Actions workflow is provided to build, push, and deploy the logger app to ECS. Set the following secrets in your GitHub repository:
- `SERVER_CERT_ARN`
- `CLIENT_CERT_ARN`
- `ASSUME_ROLE_ARN`

The workflow will:
- Build and push the Docker image for the logger app, grafana and loki
- Deploy the CDK stack (including ECS, ALBs, EFS, S3, etc.)
- Redeploy the ECS services(logger app, grafana and loki) using new task definitions with latest build image

