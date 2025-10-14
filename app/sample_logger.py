import logging
import random
import time
import os
import json
import uuid
from datetime import datetime, timezone
from fastapi import FastAPI, Request, HTTPException
import threading
import uvicorn
import requests
import boto3
from botocore.exceptions import ClientError

# Configure standard logger first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S%z'
)
logger = logging.getLogger("sample_logger")

# Optional OpenTelemetry imports (with graceful fallback)
try:
    logger.info("Attempting to import OpenTelemetry packages...")
    from opentelemetry import trace
    logger.info("✓ opentelemetry.trace imported")
    from opentelemetry import metrics
    logger.info("✓ opentelemetry.metrics imported")
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    logger.info("✓ opentelemetry.instrumentation.fastapi imported")
    from opentelemetry.instrumentation.requests import RequestsInstrumentor
    logger.info("✓ opentelemetry.instrumentation.requests imported")
    from opentelemetry.instrumentation.boto3sqs import Boto3SQSInstrumentor
    logger.info("✓ opentelemetry.instrumentation.boto3sqs imported")
    from opentelemetry.instrumentation.botocore import BotocoreInstrumentor
    logger.info("✓ opentelemetry.instrumentation.botocore imported")
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    logger.info("✓ opentelemetry.exporter.otlp.proto.grpc.trace_exporter imported")
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
    logger.info("✓ opentelemetry.exporter.otlp.proto.grpc.metric_exporter imported")
    from opentelemetry.sdk.trace import TracerProvider
    logger.info("✓ opentelemetry.sdk.trace imported")
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    logger.info("✓ opentelemetry.sdk.trace.export imported")
    from opentelemetry.sdk.metrics import MeterProvider
    logger.info("✓ opentelemetry.sdk.metrics imported")
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    logger.info("✓ opentelemetry.sdk.metrics.export imported")
    from opentelemetry.sdk.resources import Resource
    logger.info("✓ opentelemetry.sdk.resources imported")
    OPENTELEMETRY_AVAILABLE = True
    logger.info("✅ All OpenTelemetry imports successful!")
except ImportError as e:
    logger.error(f"❌ OpenTelemetry import failed: {e}")
    import traceback
    logger.error(f"Import traceback: {traceback.format_exc()}")
    OPENTELEMETRY_AVAILABLE = False

LOG_LEVELS = [logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL]
LOG_LEVEL_NAMES = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
SAMPLE_MESSAGES = [
    "User login succeeded",
    "User login failed",
    "File uploaded successfully",
    "File upload failed",
    "Database connection established",
    "Database connection lost",
    "Cache miss",
    "Cache hit",
    "API request received",
    "API request failed",
    "Background job started",
    "Background job completed",
    "Unexpected exception occurred"
]

# Simple OpenTelemetry setup (only if enabled via environment)
def setup_opentelemetry():
    if not OPENTELEMETRY_AVAILABLE:
        logger.info("OpenTelemetry not available, skipping setup")
        return None
    
    # Only setup if OTLP endpoint is configured
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    logger.info(f"OTEL_EXPORTER_OTLP_ENDPOINT: {otlp_endpoint}")
    if not otlp_endpoint:
        # Use default endpoint for testing
        otlp_endpoint = "http://localhost:4317"
        logger.info(f"Using default OTLP endpoint: {otlp_endpoint}")
    
    try:
        logger.info(f"Setting up OpenTelemetry with endpoint: {otlp_endpoint}")
        
        # Create resource
        logger.info("Creating OpenTelemetry resource...")
        resource = Resource.create({
            "service.name": os.getenv("OTEL_SERVICE_NAME", "logger-app"),
            "service.version": "1.0.0",
            "deployment.environment": "production"
        })
        logger.info("Resource created successfully")
        
        # Setup tracing
        logger.info("Setting up tracing...")
        trace.set_tracer_provider(TracerProvider(resource=resource))
        tracer = trace.get_tracer(__name__)
        logger.info("Tracer created successfully")
        
        # Setup OTLP trace exporter with retry configuration
        logger.info("Setting up OTLP trace exporter...")
        otlp_trace_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
        span_processor = BatchSpanProcessor(
            otlp_trace_exporter,
            max_export_batch_size=512,
            export_timeout_millis=30000,
            schedule_delay_millis=5000
        )
        trace.get_tracer_provider().add_span_processor(span_processor)
        logger.info("Trace exporter setup completed")
        
        # Setup metrics with retry configuration
        logger.info("Setting up metrics...")
        otlp_metric_exporter = OTLPMetricExporter(endpoint=otlp_endpoint)
        metric_reader = PeriodicExportingMetricReader(
            otlp_metric_exporter, 
            export_interval_millis=15000,  # Increased interval to reduce load
            export_timeout_millis=30000
        )
        meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
        metrics.set_meter_provider(meter_provider)
        meter = metrics.get_meter(__name__)
        logger.info("Meter created successfully")
        
        logger.info("OpenTelemetry setup completed successfully")
        return tracer, meter
        
    except Exception as e:
        logger.error(f"Failed to setup OpenTelemetry: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None

# Initialize OpenTelemetry (optional)
# Add a small delay to let ADOT collector start first
import time
time.sleep(5)  # Give ADOT collector time to start

telemetry_result = setup_opentelemetry()
if telemetry_result:
    tracer, meter = telemetry_result
    logger.info("OpenTelemetry initialized successfully")
else:
    tracer, meter = None, None
    logger.info("OpenTelemetry not available - running without telemetry")

app = FastAPI()

# Create metrics (if available)
request_counter = None
response_time_histogram = None

if meter:
    try:
        request_counter = meter.create_counter(
            name="http_requests_total",
            description="Total number of HTTP requests",
            unit="1"
        )
        response_time_histogram = meter.create_histogram(
            name="http_request_duration_seconds",
            description="HTTP request duration in seconds",
            unit="s"
        )
        # Add custom business metrics
        user_actions_counter = meter.create_counter(
            name="user_actions_total",
            description="Total number of user actions",
            unit="1"
        )
        error_counter = meter.create_counter(
            name="errors_total",
            description="Total number of errors",
            unit="1"
        )
        sqs_messages_sent = meter.create_counter(
            name="sqs_messages_sent_total",
            description="Total number of SQS messages sent",
            unit="1"
        )
        sqs_messages_received = meter.create_counter(
            name="sqs_messages_received_total",
            description="Total number of SQS messages received",
            unit="1"
        )
        dynamodb_operations = meter.create_counter(
            name="dynamodb_operations_total",
            description="Total number of DynamoDB operations",
            unit="1"
        )
        aws_service_latency = meter.create_histogram(
            name="aws_service_duration_seconds",
            description="Duration of AWS service calls",
            unit="s"
        )
        logger.info("Metrics created successfully")
    except Exception as e:
        logger.error(f"Failed to create metrics: {e}")
        request_counter = None
        response_time_histogram = None
        user_actions_counter = None
        error_counter = None
        sqs_messages_sent = None
        sqs_messages_received = None
        dynamodb_operations = None
        aws_service_latency = None
else:
    user_actions_counter = None
    error_counter = None
    sqs_messages_sent = None
    sqs_messages_received = None
    dynamodb_operations = None
    aws_service_latency = None

# Initialize AWS services
try:
    aws_region = os.getenv("AWS_REGION", "us-east-1")
    sqs_client = boto3.client('sqs', region_name=aws_region)
    dynamodb = boto3.resource('dynamodb', region_name=aws_region)
    
    # Get queue URLs and table names from environment
    message_queue_url = os.getenv("SQS_MESSAGE_QUEUE_URL")
    app_table_name = os.getenv("DYNAMODB_APP_TABLE")
    
    if app_table_name:
        app_table = dynamodb.Table(app_table_name)
    else:
        app_table = None
            
    logger.info(f"AWS services initialized - Region: {aws_region}")
    logger.info(f"SQS Queue - Message: {message_queue_url}")
    logger.info(f"DynamoDB Tables - App: {app_table_name}")
    
except Exception as e:
    logger.error(f"Failed to initialize AWS services: {e}")
    sqs_client = None
    app_table = None

def random_log():
    while True:
        level = random.choice(LOG_LEVELS)
        level_name = LOG_LEVEL_NAMES[LOG_LEVELS.index(level)]
        msg = random.choice(SAMPLE_MESSAGES)
        logger.log(level, f"[{level_name}] {msg}")
        time.sleep(30)

@app.get("/")
async def index(request: Request):
    start_time = time.time()
    
    # Use tracing if available
    if tracer:
        with tracer.start_as_current_span("index_endpoint") as span:
            span.set_attribute("http.method", "GET")
            span.set_attribute("http.url", str(request.url))
            span.set_attribute("client.host", request.client.host)
            
            now = datetime.utcnow().isoformat()
            client_host = request.client.host
            logger.info(f"[INFO] Web endpoint visited at {now} from {client_host}. Deployed with Github workflow")
            
            # Record metrics if available
            if request_counter:
                request_counter.add(1, {"method": "GET", "endpoint": "/"})
            
            # Simulate some work
            time.sleep(random.uniform(0.1, 0.5))
            
            response_time = time.time() - start_time
            if response_time_histogram:
                response_time_histogram.record(response_time, {"method": "GET", "endpoint": "/"})
            
            return {"message": f"Logger app running. Visit time: {now}. Deployed with Github workflow"}
    else:
        # No tracing, just log normally
        now = datetime.utcnow().isoformat()
        client_host = request.client.host
        logger.info(f"[INFO] Web endpoint visited at {now} from {client_host}. Deployed with Github workflow. f")
        
        # Record metrics if available
        if request_counter:
            request_counter.add(1, {"method": "GET", "endpoint": "/"})
        
        # Simulate some work
        time.sleep(random.uniform(0.1, 0.5))
        
        response_time = time.time() - start_time
        if response_time_histogram:
            response_time_histogram.record(response_time, {"method": "GET", "endpoint": "/"})
        
        return {"message": f"Logger app running. Visit time: {now}. Deployed with Github workflow. f"}

@app.get("/test-telemetry")
async def test_telemetry():
    """Test endpoint to generate custom metrics and traces"""
    start_time = time.time()
    
    if tracer:
        with tracer.start_as_current_span("test_telemetry_endpoint") as span:
            span.set_attribute("test.type", "telemetry")
            span.set_attribute("test.timestamp", datetime.utcnow().isoformat())
            
            # Simulate some work
            time.sleep(random.uniform(0.1, 0.3))
            
            # Generate custom metrics
            if user_actions_counter:
                user_actions_counter.add(1, {"action": "test_telemetry", "endpoint": "/test-telemetry"})
            
            if error_counter and random.random() < 0.1:  # 10% chance of error
                error_counter.add(1, {"error_type": "simulated", "endpoint": "/test-telemetry"})
                span.set_attribute("test.error", "simulated_error")
            
            response_time = time.time() - start_time
            if response_time_histogram:
                response_time_histogram.record(response_time, {"endpoint": "/test-telemetry"})
            
            return {
                "message": "Telemetry test completed",
                "timestamp": datetime.utcnow().isoformat(),
                "response_time": response_time,
                "telemetry_enabled": True
            }
    else:
        return {
            "message": "Telemetry test completed (no tracing)",
            "timestamp": datetime.utcnow().isoformat(),
            "telemetry_enabled": False
        }

@app.get("/health")
async def health():
    if tracer:
        with tracer.start_as_current_span("health_check") as span:
            span.set_attribute("health.status", "healthy")
            return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
    else:
        return {"status": "healthy. No tracing", "timestamp": datetime.utcnow().isoformat()}

@app.post("/send-message")
async def send_message(request: Request):
    """Send a message to SQS queue"""
    start_time = time.time()
    
    if not sqs_client or not message_queue_url:
        raise HTTPException(status_code=500, detail="SQS not configured")
    
    if tracer:
        with tracer.start_as_current_span("send_sqs_message") as span:
            try:
                # Generate message data
                message_id = str(uuid.uuid4())
                message_data = {
                    "id": message_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "source": "logger-app",
                    "content": f"Test message {message_id}",
                    "client_ip": request.client.host
                }
                
                span.set_attribute("sqs.queue_url", message_queue_url)
                span.set_attribute("sqs.message_id", message_id)
                
                # Send message to SQS
                response = sqs_client.send_message(
                    QueueUrl=message_queue_url,
                    MessageBody=json.dumps(message_data),
                    MessageAttributes={
                        'MessageType': {
                            'StringValue': 'test-message',
                            'DataType': 'String'
                        },
                        'Source': {
                            'StringValue': 'logger-app',
                            'DataType': 'String'
                        }
                    }
                )
                
                # Record metrics
                if sqs_messages_sent:
                    sqs_messages_sent.add(1, {"queue": "message-queue", "status": "success"})
                
                if aws_service_latency:
                    aws_service_latency.record(time.time() - start_time, {"service": "sqs", "operation": "send_message"})
                
                span.set_attribute("sqs.message_id_response", response['MessageId'])
                
                logger.info(f"Message sent to SQS: {response['MessageId']}")
                
                return {
                    "message": "Message sent successfully",
                    "message_id": response['MessageId'],
                    "sqs_message_id": message_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
            except ClientError as e:
                span.set_attribute("error", True)
                span.set_attribute("error.message", str(e))
                
                if error_counter:
                    error_counter.add(1, {"service": "sqs", "operation": "send_message"})
                
                logger.error(f"Failed to send SQS message: {e}")
                raise HTTPException(status_code=500, detail=f"SQS error: {str(e)}")
    else:
        # No tracing fallback
        try:
            message_id = str(uuid.uuid4())
            message_data = {
                "id": message_id,
                "timestamp": datetime.utcnow().isoformat(),
                "source": "logger-app",
                "content": f"Test message {message_id}",
                "client_ip": request.client.host
            }
            
            response = sqs_client.send_message(
                QueueUrl=message_queue_url,
                MessageBody=json.dumps(message_data)
            )
            
            if sqs_messages_sent:
                sqs_messages_sent.add(1, {"queue": "message-queue", "status": "success"})
            
            logger.info(f"Message sent to SQS: {response['MessageId']}")
            
            return {
                "message": "Message sent successfully",
                "message_id": response['MessageId'],
                "sqs_message_id": message_id,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except ClientError as e:
            if error_counter:
                error_counter.add(1, {"service": "sqs", "operation": "send_message"})
            logger.error(f"Failed to send SQS message: {e}")
            raise HTTPException(status_code=500, detail=f"SQS error: {str(e)}")

@app.get("/receive-messages")
async def receive_messages():
    """Receive messages from SQS queue"""
    start_time = time.time()
    
    if not sqs_client or not message_queue_url:
        raise HTTPException(status_code=500, detail="SQS not configured")
    
    if tracer:
        with tracer.start_as_current_span("receive_sqs_messages") as span:
            try:
                span.set_attribute("sqs.queue_url", message_queue_url)
                
                # Receive messages from SQS
                response = sqs_client.receive_message(
                    QueueUrl=message_queue_url,
                    MaxNumberOfMessages=10,
                    WaitTimeSeconds=5
                )
                
                messages = response.get('Messages', [])
                
                # Record metrics
                if sqs_messages_received:
                    sqs_messages_received.add(len(messages), {"queue": "message-queue", "status": "success"})
                
                if aws_service_latency:
                    aws_service_latency.record(time.time() - start_time, {"service": "sqs", "operation": "receive_message"})
                
                span.set_attribute("sqs.messages_received", len(messages))
                
                # Delete messages after processing
                for message in messages:
                    sqs_client.delete_message(
                        QueueUrl=message_queue_url,
                        ReceiptHandle=message['ReceiptHandle']
                    )
                
                logger.info(f"Received {len(messages)} messages from SQS")
                
                return {
                    "message": f"Received {len(messages)} messages",
                    "messages": [json.loads(msg['Body']) for msg in messages],
                    "timestamp": datetime.utcnow().isoformat()
                }
                
            except ClientError as e:
                span.set_attribute("error", True)
                span.set_attribute("error.message", str(e))
                
                if error_counter:
                    error_counter.add(1, {"service": "sqs", "operation": "receive_message"})
                
                logger.error(f"Failed to receive SQS messages: {e}")
                raise HTTPException(status_code=500, detail=f"SQS error: {str(e)}")
    else:
        # No tracing fallback
        try:
            response = sqs_client.receive_message(
                QueueUrl=message_queue_url,
                MaxNumberOfMessages=10,
                WaitTimeSeconds=5
            )
            
            messages = response.get('Messages', [])
            
            if sqs_messages_received:
                sqs_messages_received.add(len(messages), {"queue": "message-queue", "status": "success"})
            
            # Delete messages after processing
            for message in messages:
                sqs_client.delete_message(
                    QueueUrl=message_queue_url,
                    ReceiptHandle=message['ReceiptHandle']
                )
            
            logger.info(f"Received {len(messages)} messages from SQS")
            
            return {
                "message": f"Received {len(messages)} messages",
                "messages": [json.loads(msg['Body']) for msg in messages],
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except ClientError as e:
            if error_counter:
                error_counter.add(1, {"service": "sqs", "operation": "receive_message"})
            logger.error(f"Failed to receive SQS messages: {e}")
            raise HTTPException(status_code=500, detail=f"SQS error: {str(e)}")

@app.post("/save-data")
async def save_data(request: Request):
    """Save data to DynamoDB"""
    start_time = time.time()
    
    if not app_table:
        raise HTTPException(status_code=500, detail="DynamoDB not configured")
    
    if tracer:
        with tracer.start_as_current_span("save_dynamodb_data") as span:
            try:
                # Generate data
                data_id = str(uuid.uuid4())
                timestamp = datetime.utcnow().isoformat()
                
                item = {
                    "id": data_id,
                    "timestamp": timestamp,
                    "user_id": f"user-{random.randint(1000, 9999)}",
                    "created_at": timestamp,
                    "data": {
                        "message": f"Sample data {data_id}",
                        "value": random.randint(1, 100),
                        "client_ip": request.client.host
                    },
                    "ttl": int((datetime.now(timezone.utc).timestamp() + 86400))  # 24 hours
                }
                
                span.set_attribute("dynamodb.table_name", app_table.table_name)
                span.set_attribute("dynamodb.item_id", data_id)
                
                # Save to DynamoDB
                app_table.put_item(Item=item)
                
                # Record metrics
                if dynamodb_operations:
                    dynamodb_operations.add(1, {"table": "app-table", "operation": "put_item", "status": "success"})
                
                if aws_service_latency:
                    aws_service_latency.record(time.time() - start_time, {"service": "dynamodb", "operation": "put_item"})
                
                logger.info(f"Data saved to DynamoDB: {data_id}")
                
                return {
                    "message": "Data saved successfully",
                    "id": data_id,
                    "timestamp": timestamp
                }
                
            except ClientError as e:
                span.set_attribute("error", True)
                span.set_attribute("error.message", str(e))
                
                if error_counter:
                    error_counter.add(1, {"service": "dynamodb", "operation": "put_item"})
                
                logger.error(f"Failed to save DynamoDB data: {e}")
                raise HTTPException(status_code=500, detail=f"DynamoDB error: {str(e)}")
    else:
        # No tracing fallback
        try:
            data_id = str(uuid.uuid4())
            timestamp = datetime.utcnow().isoformat()
            
            item = {
                "id": data_id,
                "timestamp": timestamp,
                "user_id": f"user-{random.randint(1000, 9999)}",
                "created_at": timestamp,
                "data": {
                    "message": f"Sample data {data_id}",
                    "value": random.randint(1, 100),
                    "client_ip": request.client.host
                },
                "ttl": int((datetime.now(timezone.utc).timestamp() + 86400))
            }
            
            app_table.put_item(Item=item)
            
            if dynamodb_operations:
                dynamodb_operations.add(1, {"table": "app-table", "operation": "put_item", "status": "success"})
            
            logger.info(f"Data saved to DynamoDB: {data_id}")
            
            return {
                "message": "Data saved successfully",
                "id": data_id,
                "timestamp": timestamp
            }
            
        except ClientError as e:
            if error_counter:
                error_counter.add(1, {"service": "dynamodb", "operation": "put_item"})
            logger.error(f"Failed to save DynamoDB data: {e}")
            raise HTTPException(status_code=500, detail=f"DynamoDB error: {str(e)}")

@app.get("/get-data/{data_id}")
async def get_data(data_id: str):
    """Get data from DynamoDB"""
    start_time = time.time()
    
    if not app_table:
        raise HTTPException(status_code=500, detail="DynamoDB not configured")
    
    if tracer:
        with tracer.start_as_current_span("get_dynamodb_data") as span:
            try:
                span.set_attribute("dynamodb.table_name", app_table.table_name)
                span.set_attribute("dynamodb.item_id", data_id)
                
                # Get item from DynamoDB
                response = app_table.get_item(
                    Key={
                        "id": data_id,
                        "timestamp": "latest"
                    }
                )
                
                item = response.get('Item')
                
                # Record metrics
                if dynamodb_operations:
                    dynamodb_operations.add(1, {"table": "app-table", "operation": "get_item", "status": "success" if item else "not_found"})
                
                if aws_service_latency:
                    aws_service_latency.record(time.time() - start_time, {"service": "dynamodb", "operation": "get_item"})
                
                if item:
                    logger.info(f"Data retrieved from DynamoDB: {data_id}")
                    return {
                        "message": "Data retrieved successfully",
                        "data": item,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                else:
                    logger.info(f"Data not found in DynamoDB: {data_id}")
                    raise HTTPException(status_code=404, detail="Data not found")
                    
            except ClientError as e:
                span.set_attribute("error", True)
                span.set_attribute("error.message", str(e))
                
                if error_counter:
                    error_counter.add(1, {"service": "dynamodb", "operation": "get_item"})
                
                logger.error(f"Failed to get DynamoDB data: {e}")
                raise HTTPException(status_code=500, detail=f"DynamoDB error: {str(e)}")
    else:
        # No tracing fallback
        try:
            response = app_table.get_item(
                Key={
                    "id": data_id,
                    "timestamp": "latest"
                }
            )
            
            item = response.get('Item')
            
            if dynamodb_operations:
                dynamodb_operations.add(1, {"table": "app-table", "operation": "get_item", "status": "success" if item else "not_found"})
            
            if item:
                logger.info(f"Data retrieved from DynamoDB: {data_id}")
                return {
                    "message": "Data retrieved successfully",
                    "data": item,
                    "timestamp": datetime.utcnow().isoformat()
                }
            else:
                logger.info(f"Data not found in DynamoDB: {data_id}")
                raise HTTPException(status_code=404, detail="Data not found")
                
        except ClientError as e:
            if error_counter:
                error_counter.add(1, {"service": "dynamodb", "operation": "get_item"})
            logger.error(f"Failed to get DynamoDB data: {e}")
            raise HTTPException(status_code=500, detail=f"DynamoDB error: {str(e)}")

@app.get("/workflow")
async def workflow(request: Request):
    """Complete workflow: send SQS message, save to DynamoDB, and process"""
    start_time = time.time()
    
    if tracer:
        with tracer.start_as_current_span("complete_workflow") as span:
            span.set_attribute("workflow.type", "full_workflow")
            
            try:
                # Step 1: Save data to DynamoDB
                data_id = str(uuid.uuid4())
                timestamp = datetime.utcnow().isoformat()
                
                if app_table:
                    item = {
                        "id": data_id,
                        "timestamp": timestamp,
                        "user_id": f"user-{random.randint(1000, 9999)}",
                        "created_at": timestamp,
                        "data": {
                            "message": f"Workflow data {data_id}",
                            "value": random.randint(1, 100),
                            "client_ip": request.client.host
                        },
                        "ttl": int((datetime.now(timezone.utc).timestamp() + 86400))
                    }
                    app_table.put_item(Item=item)
                    span.set_attribute("workflow.dynamodb_saved", True)
                
                # Step 2: Send message to SQS
                if sqs_client and message_queue_url:
                    message_data = {
                        "id": data_id,
                        "timestamp": timestamp,
                        "source": "workflow",
                        "content": f"Workflow message for data {data_id}",
                        "client_ip": request.client.host
                    }
                    
                    sqs_response = sqs_client.send_message(
                        QueueUrl=message_queue_url,
                        MessageBody=json.dumps(message_data),
                        MessageAttributes={
                            'MessageType': {
                                'StringValue': 'workflow-message',
                                'DataType': 'String'
                            }
                        }
                    )
                    span.set_attribute("workflow.sqs_sent", True)
                    span.set_attribute("workflow.sqs_message_id", sqs_response['MessageId'])
                
                # Record metrics
                if user_actions_counter:
                    user_actions_counter.add(1, {"action": "complete_workflow", "endpoint": "/workflow"})
                
                if dynamodb_operations:
                    dynamodb_operations.add(1, {"table": "app-table", "operation": "put_item", "status": "success"})
                
                if sqs_messages_sent:
                    sqs_messages_sent.add(1, {"queue": "message-queue", "status": "success"})
                
                workflow_time = time.time() - start_time
                if aws_service_latency:
                    aws_service_latency.record(workflow_time, {"service": "workflow", "operation": "complete"})
                
                logger.info(f"Workflow completed: {data_id}")
                
                return {
                    "message": "Workflow completed successfully",
                    "data_id": data_id,
                    "workflow_time": workflow_time,
                    "timestamp": timestamp,
                    "steps_completed": ["dynamodb_save", "sqs_send"]
                }
                
            except Exception as e:
                span.set_attribute("error", True)
                span.set_attribute("error.message", str(e))
                
                if error_counter:
                    error_counter.add(1, {"service": "workflow", "operation": "complete"})
                
                logger.error(f"Workflow failed: {e}")
                raise HTTPException(status_code=500, detail=f"Workflow error: {str(e)}")
    else:
        # No tracing fallback
        try:
            data_id = str(uuid.uuid4())
            timestamp = datetime.utcnow().isoformat()
            
            # Save to DynamoDB
            if app_table:
                item = {
                    "id": data_id,
                    "timestamp": timestamp,
                    "user_id": f"user-{random.randint(1000, 9999)}",
                    "created_at": timestamp,
                    "data": {
                        "message": f"Workflow data {data_id}",
                        "value": random.randint(1, 100),
                        "client_ip": request.client.host
                    },
                    "ttl": int((datetime.now(timezone.utc).timestamp() + 86400))
                }
                app_table.put_item(Item=item)
            
            # Send to SQS
            if sqs_client and message_queue_url:
                message_data = {
                    "id": data_id,
                    "timestamp": timestamp,
                    "source": "workflow",
                    "content": f"Workflow message for data {data_id}",
                    "client_ip": request.client.host
                }
                
                sqs_response = sqs_client.send_message(
                    QueueUrl=message_queue_url,
                    MessageBody=json.dumps(message_data)
                )
            
            if user_actions_counter:
                user_actions_counter.add(1, {"action": "complete_workflow", "endpoint": "/workflow"})
            
            workflow_time = time.time() - start_time
            
            logger.info(f"Workflow completed: {data_id}")
            
            return {
                "message": "Workflow completed successfully",
                "data_id": data_id,
                "workflow_time": workflow_time,
                "timestamp": timestamp,
                "steps_completed": ["dynamodb_save", "sqs_send"]
            }
            
        except Exception as e:
            if error_counter:
                error_counter.add(1, {"service": "workflow", "operation": "complete"})
            logger.error(f"Workflow failed: {e}")
            raise HTTPException(status_code=500, detail=f"Workflow error: {str(e)}")

if __name__ == "__main__":
    # Instrument FastAPI if OpenTelemetry is available
    if OPENTELEMETRY_AVAILABLE and tracer:
        try:
            FastAPIInstrumentor.instrument_app(app)
            RequestsInstrumentor().instrument()
            Boto3SQSInstrumentor().instrument()
            BotocoreInstrumentor().instrument()
            logger.info("FastAPI and AWS SDK instrumentation enabled")
        except Exception as e:
            logger.error(f"Failed to instrument FastAPI/AWS SDK: {e}")
    
    t = threading.Thread(target=random_log, daemon=True)
    t.start()
    uvicorn.run(app, host="0.0.0.0", port=8080) 
