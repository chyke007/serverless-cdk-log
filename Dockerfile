FROM python:3.11-slim

WORKDIR /app

COPY app/sample_logger.py .
COPY requirements.txt .

# Install all dependencies including OpenTelemetry
# RUN pip install --no-cache-dir -r requirements.txt
RUN pip install -r requirements.txt

EXPOSE 8080

CMD ["python", "sample_logger.py"] 
