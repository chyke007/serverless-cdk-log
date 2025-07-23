FROM python:3.11-slim

WORKDIR /app

COPY app/sample_logger.py .
RUN pip install --no-cache-dir FastAPI uvicorn

EXPOSE 8080

CMD ["python", "sample_logger.py"] 
