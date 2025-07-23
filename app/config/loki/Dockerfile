FROM grafana/loki:3.4.1

COPY app/config/loki/loki-config.yaml /etc/loki/loki-config.yaml
CMD ["-config.file=/etc/loki/loki-config.yaml"]
