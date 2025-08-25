#!/usr/bin/env python3
"""
Kubernetes OpenTelemetry Test Application
=========================================
A simple Flask app to test the OpenTelemetry stack in Kubernetes.
"""

import time
import random
import sys
import os
import logging
from flask import Flask, jsonify, request

# Check dependencies
try:
    from opentelemetry import trace, metrics
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.instrumentation.flask import FlaskInstrumentor
    from opentelemetry.instrumentation.requests import RequestsInstrumentor
    from opentelemetry.instrumentation.logging import LoggingInstrumentor
    from opentelemetry._logs import set_logger_provider
    from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    print("✅ OpenTelemetry dependencies available")
except ImportError as e:
    print("❌ Missing dependencies. Install with:")
    print("pip install flask opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp \\")
    print("            opentelemetry-instrumentation-flask opentelemetry-instrumentation-requests")
    sys.exit(1)

# Setup OpenTelemetry
print("🔧 Setting up OpenTelemetry...")

# Enhanced resource attributes for Kubernetes APM
resource = Resource.create({
    "service.name": "instrumented-app",
    "service.version": "1.2.0",
    "service.instance.id": f"instrumented-app-k8s-{random.randint(1000,9999)}",
    "service.namespace": "apps",
    "deployment.environment.name": "kubernetes",
    "k8s.namespace.name": "apps",
    "k8s.pod.name": "instrumented-app-pod"
})

# Setup tracing
trace.set_tracer_provider(TracerProvider(resource=resource))
tracer = trace.get_tracer(__name__)

# Setup structured logging with trace correlation
logger_provider = LoggerProvider(resource=resource)
set_logger_provider(logger_provider)

log_exporter = OTLPLogExporter(
    endpoint=os.environ.get("OTEL_EXPORTER_OTLP_LOGS_ENDPOINT", "http://localhost:4318/v1/logs")
)
logger_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))

handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)

root_logger = logging.getLogger()
root_logger.addHandler(handler)
root_logger.setLevel(logging.INFO)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
root_logger.addHandler(console_handler)

LoggingInstrumentor().instrument(set_logging_format=True)

# Override Werkzeug/Flask logs to use OpenTelemetry
werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.handlers.clear()
werkzeug_logger.addHandler(handler)
werkzeug_logger.setLevel(logging.INFO)
werkzeug_logger.propagate = False

flask_logger = logging.getLogger('flask.app')
flask_logger.handlers.clear()
flask_logger.addHandler(handler)
flask_logger.setLevel(logging.INFO)
flask_logger.propagate = False

print("✅ Werkzeug/Flask logs redirected to OpenTelemetry")

# Custom HTTP request logging with trace context (will be configured after app creation)
class OpenTelemetryHTTPLogger:
    def __init__(self, app):
        self.app = app
        
    def log_request(self, response):
        from opentelemetry import trace
        current_span = trace.get_current_span()
        
        if current_span.is_recording():
            trace_id = format(current_span.get_span_context().trace_id, '032x')
            span_id = format(current_span.get_span_context().span_id, '016x')
            
            logging.info(
                f"HTTP Request: {request.method} {request.path} {response.status_code}",
                extra={
                    "http.method": request.method,
                    "http.path": request.path,
                    "http.status_code": response.status_code,
                    "http.user_agent": request.headers.get('User-Agent', ''),
                    "http.remote_addr": request.remote_addr,
                    "trace_id": trace_id,
                    "span_id": span_id
                }
            )
        return response

# Setup metrics  
metric_exporter = OTLPMetricExporter(
    endpoint=os.environ.get("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT", "http://localhost:4318/v1/metrics")
)
metric_reader = PeriodicExportingMetricReader(metric_exporter, export_interval_millis=30000)  # Export every 30 seconds
metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[metric_reader]))
meter = metrics.get_meter(__name__)

# Trace exporter
trace_exporter = OTLPSpanExporter(
    endpoint=os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://localhost:4318/v1/traces")
)

span_processor = BatchSpanProcessor(trace_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)

# APM Custom Metrics
request_counter = meter.create_counter(
    "http_requests_total",
    description="Total HTTP requests by method, endpoint and status"
)

request_duration = meter.create_histogram(
    "http_request_duration_seconds",
    description="HTTP request duration in seconds"
)

db_query_duration = meter.create_histogram(
    "db_query_duration_seconds",
    description="Database query duration in seconds"
)

print("✅ OpenTelemetry configured with APM metrics")

# Create Flask app with custom logging
app = Flask(__name__)

# Disable Flask's default logging to avoid duplicate logs
app.logger.disabled = True
app.logger.propagate = False

# Disable Werkzeug's default access logs 
import logging
log = logging.getLogger('werkzeug')
log.disabled = True

# APM Enhancement: Auto-instrument Flask for HTTP metrics
FlaskInstrumentor().instrument_app(app)
RequestsInstrumentor().instrument()

print("✅ Flask auto-instrumentation enabled with OpenTelemetry logging override")

# Install custom HTTP logger after app creation
http_logger = OpenTelemetryHTTPLogger(app)

@app.after_request
def log_request_with_trace_context(response):
    return http_logger.log_request(response)

@app.route("/")
def home():
    """Homepage with basic trace and APM metrics"""
    start_time = time.time()
    
    with tracer.start_as_current_span("home_request") as span:
        span.set_attribute("http.method", "GET")
        span.set_attribute("http.route", "/")
        span.set_attribute("http.endpoint", "home")
        
        logging.info("Homepage request started", extra={"endpoint": "/", "method": "GET"})
        
        processing_time = random.uniform(0.1, 0.3)
        time.sleep(processing_time)
        
        span.set_attribute("processing_time", processing_time)
        span.add_event("Request processed")
        
        duration = time.time() - start_time
        request_counter.add(1, {
            "method": "GET",
            "endpoint": "/",
            "status_code": "200"
        })
        request_duration.record(duration, {
            "method": "GET", 
            "endpoint": "/",
            "status_code": "200"
        })
        
        logging.info(
            "Homepage request completed successfully", 
            extra={
                "endpoint": "/", 
                "method": "GET", 
                "status_code": 200,
                "processing_time": processing_time,
                "total_duration": duration
            }
        )
        
        return jsonify({
            "message": "Hello from Kubernetes OpenTelemetry Test App! 🚀",
            "service": "instrumented-app",
            "version": "1.2.0",
            "environment": "kubernetes",
            "processing_time": processing_time,
            "timestamp": time.time()
        })

@app.route("/api/data")
def get_data():
    """API endpoint with nested spans and APM metrics"""
    start_time = time.time()
    
    with tracer.start_as_current_span("get_data") as span:
        span.set_attribute("http.method", "GET")
        span.set_attribute("http.route", "/api/data")
        span.set_attribute("http.endpoint", "get_data")
        
        # Simulate database query with enhanced instrumentation
        db_start = time.time()
        with tracer.start_as_current_span("database_query") as db_span:
            db_span.set_attribute("db.system", "postgresql")
            db_span.set_attribute("db.operation", "SELECT")
            db_span.set_attribute("db.table", "users")
            db_span.set_attribute("db.statement", "SELECT id, name FROM users LIMIT 10")
            
            db_time = random.uniform(0.05, 0.15)
            time.sleep(db_time)
            
            data = [
                {"id": 1, "name": "Alice", "status": "active"},
                {"id": 2, "name": "Bob", "status": "active"},
                {"id": 3, "name": "Charlie", "status": "inactive"}
            ]
            db_span.set_attribute("db.rows_affected", len(data))
            
            # Database query metric
            db_query_duration.record(db_time, {
                "db.system": "postgresql",
                "db.operation": "SELECT",
                "db.table": "users"
            })
        
        # Simulate processing
        processing_time = random.uniform(0.02, 0.08)
        time.sleep(processing_time)
        
        total_time = time.time() - start_time
        span.set_attribute("processing.duration", processing_time)
        span.set_attribute("request.total_duration", total_time)
        
        # APM Metrics
        request_counter.add(1, {
            "method": "GET",
            "endpoint": "/api/data", 
            "status_code": "200"
        })
        request_duration.record(total_time, {
            "method": "GET",
            "endpoint": "/api/data",
            "status_code": "200"
        })
        
        return jsonify({
            "data": data,
            "count": len(data),
            "db_query_time": db_time,
            "processing_time": processing_time,
            "total_time": total_time,
            "service": "test-app"
        })

@app.route("/api/checkout", methods=['POST'])
def checkout():
    """Checkout endpoint with random success/failure and APM metrics"""
    start_time = time.time()
    
    checkout_data = request.get_json() or {}
    user_id = checkout_data.get("userId", "anonymous")
    amount = checkout_data.get("amount", 0.0)
    currency = checkout_data.get("userCurrency", "USD")
    email = checkout_data.get("email", "unknown@example.com")
    
    with tracer.start_as_current_span("checkout_process") as span:
        span.set_attribute("http.method", "POST")
        span.set_attribute("http.route", "/api/checkout")
        span.set_attribute("http.endpoint", "checkout")
        span.set_attribute("user.id", user_id)
        span.set_attribute("user.email", email)
        span.set_attribute("checkout.amount", amount)
        span.set_attribute("checkout.currency", currency)
        
        payment_processing_time = random.uniform(0.1, 0.3)
        time.sleep(payment_processing_time)
        
        logging.info(
            "Checkout process started", 
            extra={
                "user_id": user_id,
                "amount": amount,
                "currency": currency,
                "email": email
            }
        )
        
        success_rate = 0.7
        is_success = random.random() < success_rate
        
        if is_success:
            order_id = f"ORD-{random.randint(10000, 99999)}"
            span.set_attribute("checkout.status", "success")
            span.set_attribute("checkout.order_id", order_id)
            span.set_attribute("payment.processed_amount", amount)
            span.add_event("Payment processed successfully")
            span.add_event("Order created", attributes={"order.id": order_id})
            
            logging.info(
                "Checkout completed successfully", 
                extra={
                    "user_id": user_id,
                    "order_id": order_id,
                    "amount": amount,
                    "currency": currency,
                    "payment_processing_time": payment_processing_time,
                    "status": "success"
                }
            )
            
            duration = time.time() - start_time
            request_counter.add(1, {
                "method": "POST",
                "endpoint": "/api/checkout",
                "status_code": "200",
                "currency": currency
            })
            request_duration.record(duration, {
                "method": "POST",
                "endpoint": "/api/checkout",
                "status_code": "200",
                "currency": currency
            })
            
            return jsonify({
                "status": "success",
                "message": "Checkout completed successfully",
                "order_id": order_id,
                "user_id": user_id,
                "amount": amount,
                "currency": currency,
                "payment_processing_time": payment_processing_time,
                "total_processing_time": duration,
                "service": "test-app"
            })
        else:
            error_types = [
                "payment_declined", 
                "insufficient_funds", 
                "card_expired", 
                "fraud_detected",
                "payment_timeout",
                "invalid_card_number"
            ]
            error_type = random.choice(error_types)
            error_msg = f"Checkout failed: {error_type} for user {user_id}"
            
            span.set_status(trace.Status(trace.StatusCode.ERROR, error_msg))
            span.set_attribute("error.type", error_type)
            span.set_attribute("error.message", error_msg)
            span.set_attribute("checkout.status", "failed")
            span.set_attribute("payment.failure_reason", error_type)
            span.set_attribute("payment.attempted_amount", amount)
            span.add_event("Payment failed", attributes={
                "failure.reason": error_type,
                "user.id": user_id,
                "amount": amount
            })
            span.record_exception(Exception(error_msg))
            
            logging.error(
                "Checkout failed with payment error",
                extra={
                    "user_id": user_id,
                    "amount": amount,
                    "currency": currency,
                    "error_type": error_type,
                    "error_message": error_msg,
                    "payment_processing_time": payment_processing_time,
                    "status": "failed"
                }
            )
            
            duration = time.time() - start_time
            request_counter.add(1, {
                "method": "POST",
                "endpoint": "/api/checkout",
                "status_code": "500",
                "currency": currency,
                "error_type": error_type
            })
            request_duration.record(duration, {
                "method": "POST",
                "endpoint": "/api/checkout",
                "status_code": "500",
                "currency": currency,
                "error_type": error_type
            })
            
            raise Exception(error_msg)

@app.route("/api/error")
def simulate_error():
    """Endpoint that simulates an error with APM metrics"""
    start_time = time.time()
    
    with tracer.start_as_current_span("error_simulation") as span:
        span.set_attribute("http.method", "GET")
        span.set_attribute("http.route", "/api/error")
        span.set_attribute("http.endpoint", "simulate_error")
        
        # Simulate some processing before error
        processing_time = random.uniform(0.05, 0.15)
        time.sleep(processing_time)
        
        # Always error for testing
        error_msg = "Simulated error for testing traces and error metrics"
        span.set_status(trace.Status(trace.StatusCode.ERROR, error_msg))
        span.record_exception(Exception(error_msg))
        span.set_attribute("error.type", "SimulatedError")
        span.set_attribute("error.message", error_msg)
        
        # APM Error Metrics
        duration = time.time() - start_time
        request_counter.add(1, {
            "method": "GET",
            "endpoint": "/api/error",
            "status_code": "500"
        })
        request_duration.record(duration, {
            "method": "GET",
            "endpoint": "/api/error", 
            "status_code": "500"
        })
        
        return jsonify({
            "error": error_msg,
            "error_type": "SimulatedError",
            "processing_time": processing_time,
            "service": "test-app"
        }), 500

@app.route("/health")
def health():
    """Health check endpoint with APM metrics"""
    start_time = time.time()
    
    with tracer.start_as_current_span("health_check") as span:
        span.set_attribute("http.method", "GET")
        span.set_attribute("http.route", "/health")
        span.set_attribute("http.endpoint", "health")
        
        # APM Metrics for health checks
        duration = time.time() - start_time
        request_counter.add(1, {
            "method": "GET",
            "endpoint": "/health",
            "status_code": "200"
        })
        request_duration.record(duration, {
            "method": "GET",
            "endpoint": "/health",
            "status_code": "200"
        })
        
        return jsonify({
            "status": "healthy",
            "service": "instrumented-app",
            "version": "1.2.0",
            "features": ["auto-instrumentation", "custom-metrics", "apm-ready"],
            "timestamp": time.time()
        })

if __name__ == "__main__":
    print("")
    print("🧪 Kubernetes OpenTelemetry APM Test App")
    print("=" * 45)
    print(f"📡 Sending traces to: {os.environ.get('OTEL_EXPORTER_OTLP_TRACES_ENDPOINT', 'http://localhost:4318/v1/traces')}")
    print(f"📊 Sending metrics to: {os.environ.get('OTEL_EXPORTER_OTLP_METRICS_ENDPOINT', 'http://localhost:4318/v1/metrics')}")
    print(f"📋 Sending logs to: {os.environ.get('OTEL_EXPORTER_OTLP_LOGS_ENDPOINT', 'http://localhost:4318/v1/logs')}")
    print("🌐 App running at: http://0.0.0.0:3333")
    print("")
    print("🎯 APM Features Enabled:")
    print("  ✅ Flask auto-instrumentation")
    print("  ✅ Custom HTTP metrics (requests_total, duration_seconds)")
    print("  ✅ Database query metrics")
    print("  ✅ Kubernetes resource attributes")
    print("  ✅ Error tracking and metrics")
    print("  ✅ Structured logging with trace correlation")
    print("  ✅ OpenTelemetry override for Flask/Werkzeug logs")
    print("  ✅ Custom HTTP request logging with trace context")
    print("")
    print("🔗 Test endpoints:")
    print("  • GET /          - Homepage with APM metrics")
    print("  • GET /api/data  - Data API with DB metrics")
    print("  • POST /api/checkout - Checkout process with random success/failure (70% success)")
    print("  • GET /api/error - Error simulation with error metrics")
    print("  • GET /health    - Health check with metrics")
    print("")
    print("🔍 Environment: kubernetes")
    print("=" * 45)
    print("Starting server...")
    print("")
    
    try:
        # Run Flask with custom logging - no default access logs
        app.run(host="0.0.0.0", port=3333, debug=False, use_reloader=False, threaded=True)
    except KeyboardInterrupt:
        print("\n👋 Kubernetes test app stopped!")
