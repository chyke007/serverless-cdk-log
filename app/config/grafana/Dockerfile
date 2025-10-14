FROM grafana/grafana-oss:latest

# Install the AWS X-Ray datasource plugin
RUN grafana-cli plugins install grafana-x-ray-datasource

# Copy configuration files
COPY app/config/grafana/grafana-config.yaml /etc/grafana/provisioning/datasources/datasources.yaml
