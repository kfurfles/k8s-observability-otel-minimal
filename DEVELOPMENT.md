# 🎓 Development & Learning Guide

**Purpose:** Educational guide for learning OpenTelemetry concepts and developing with the minimal stack.

---

## 🎯 **When to Use This Guide**

✅ **Perfect for:**
- Learning OpenTelemetry concepts
- Understanding distributed tracing
- Developing new features locally
- Debugging telemetry issues
- Quick iteration and experimentation

❌ **Not for:**
- Production deployment testing
- Auto-scaling validation
- Performance benchmarking
- Load testing capabilities

> **For production testing**, use the main [README.md](README.md) Kubernetes workflow.

---

## 🚀 **Quick Educational Setup**

### **Step 1: Deploy Observability Stack**
```bash
# Deploy the complete observability infrastructure
./scripts/up.sh
```

**What this creates:**
- 📊 **Grafana** → http://localhost:3000 (admin/admin)
- 🔍 **Tempo** → Distributed tracing backend
- 📈 **Prometheus** → Metrics storage
- 📡 **OTel Collector** → localhost:4317 (gRPC), localhost:4318 (HTTP)

### **Step 2: Install Dependencies Locally**
```bash
# Install Python dependencies for the example app
pip install -r examples/instrumented-app/requirements.txt
```

### **Step 3: Run Example App Locally**
```bash
# Run the instrumented Flask application
python3 examples/instrumented-app/src/app.py
```

**App will be available at:** http://localhost:3333

---

## 🧪 **Learning Experiments**

### **Experiment 1: Basic Tracing**
```bash
# Generate a simple trace
curl http://localhost:3333/

# View in Grafana:
# 1. Go to http://localhost:3000
# 2. Navigate to Explore → Tempo
# 3. Click "Run Query" to see your trace
```

**What to observe:**
- Trace ID and Span ID generation
- HTTP method, route, and status code attributes
- Processing time measurements

### **Experiment 2: Nested Spans & Database Simulation**
```bash
# Generate a trace with nested spans
curl http://localhost:3333/api/data

# This creates:
# ├── get_data (parent span)
# └── database_query (child span)
```

**What to observe:**
- Parent-child span relationships
- Database operation attributes (db.system, db.operation, db.table)
- Query duration measurements

### **Experiment 3: Error Tracing**
```bash
# Generate an error trace
curl http://localhost:3333/api/error

# This creates a span with:
# - Error status and message
# - Exception recording
# - Error attributes
```

**What to observe:**
- Error status codes in spans
- Exception stack traces
- Error attributes and events

### **Experiment 4: Complex Business Logic**
```bash
# Simulate a checkout process (random success/failure)
curl -X POST http://localhost:3333/api/checkout \
  -H "Content-Type: application/json" \
  -d '{"userId":"dev-user-123","amount":99.99,"userCurrency":"USD","email":"dev@example.com"}'

# Run multiple times to see both success and failure traces
```

**What to observe:**
- Business logic attributes (user.id, checkout.amount, checkout.currency)
- Success vs failure trace patterns
- Payment processing simulation

---

## 📊 **Understanding Metrics & APM**

### **Custom Metrics Generated**
The example app generates these metrics automatically:

```python
# HTTP Request Metrics
http_requests_total              # Counter by method, endpoint, status
http_request_duration_seconds    # Histogram of request durations

# Database Metrics  
db_query_duration_seconds        # Histogram of database query times
```

### **View Metrics in Grafana**
```bash
# 1. Go to http://localhost:3000
# 2. Navigate to Explore → Prometheus
# 3. Try these queries:

# Total requests by endpoint
sum by (endpoint) (http_requests_total)

# Request rate per minute
sum by (endpoint) (rate(http_requests_total[5m]) * 60)

# 95th percentile latency
histogram_quantile(0.95, sum by (endpoint, le) (rate(http_request_duration_seconds_bucket[5m])))
```

### **APM Dashboard**
- **URL:** http://localhost:3000/d/apm-routes-status
- **Purpose:** See routes, status codes, latencies in one view
- **Educational Value:** Learn how APM correlates metrics and traces

---

## 🔬 **Code Exploration**

### **Understanding the Instrumentation**

**File:** `examples/instrumented-app/src/app.py`

```python
# 1. Resource Configuration (lines 43-51)
resource = Resource.create({
    "service.name": "instrumented-app",
    "service.version": "1.2.0",
    "service.instance.id": f"instrumented-app-k8s-{random.randint(1000,9999)}",
    "deployment.environment.name": "kubernetes",
    # ... more attributes
})
```

**Learning Point:** Resources provide context about what is generating telemetry.

```python
# 2. Auto-instrumentation (lines 169-170)
FlaskInstrumentor().instrument_app(app)
RequestsInstrumentor().instrument()
```

**Learning Point:** Auto-instrumentation adds tracing to frameworks automatically.

```python
# 3. Manual Spans (lines 186-196)
with tracer.start_as_current_span("home_request") as span:
    span.set_attribute("http.method", "GET")
    span.set_attribute("http.route", "/")
    span.add_event("Request processed")
```

**Learning Point:** Manual spans give you full control over what to trace.

```python
# 4. Custom Metrics (lines 139-153)
request_counter.add(1, {
    "method": "GET",
    "endpoint": "/",
    "status_code": "200"
})
```

**Learning Point:** Custom metrics complement tracing with aggregatable data.

### **OpenTelemetry Collector Configuration**

**File:** `platform/manifests/all-in-one.yaml` (lines 26-128)

```yaml
# Receivers - How telemetry enters the collector
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317    # For SDKs using gRPC
      http:
        endpoint: 0.0.0.0:4318    # For SDKs using HTTP

# Processors - How telemetry is enriched/modified
processors:
  resource:                       # Adds environment info
  attributes:                     # Modifies span attributes
  batch:                         # Batches for efficiency

# Exporters - Where telemetry goes
exporters:
  otlp/tempo:                    # Traces → Tempo
  prometheusremotewrite:         # Metrics → Prometheus
```

**Learning Point:** Collector is a pipeline that receives, processes, and exports telemetry.

---

## 🧠 **Educational Scenarios**

### **Scenario 1: Debugging Slow Requests**
```bash
# 1. Generate some requests
for i in {1..10}; do curl http://localhost:3333/api/data; done

# 2. Go to Grafana → Explore → Tempo
# 3. Search for spans with duration > 200ms
# 4. Click on slow spans to see what caused the delay
```

### **Scenario 2: Understanding Service Dependencies**
```bash
# 1. Generate mixed traffic
curl http://localhost:3333/              # Simple request
curl http://localhost:3333/api/data      # Request with DB call
curl http://localhost:3333/api/checkout  # Business logic request

# 2. In Grafana → Tempo → Service Map
# 3. Observe how services interact
```

### **Scenario 3: Correlating Metrics and Traces**
```bash
# 1. Generate some errors
for i in {1..5}; do curl http://localhost:3333/api/error; done

# 2. In Prometheus: query error rate
sum(rate(http_requests_total{status_code="500"}[5m]))

# 3. Click on "Exemplar" data points
# 4. Follow links to related traces in Tempo
```

---

## 🔧 **Development Tips**

### **Modify and Experiment**
```bash
# 1. Edit examples/instrumented-app/src/app.py
# 2. Add new endpoints, spans, or metrics
# 3. Restart the app: Ctrl+C and run again
python3 examples/instrumented-app/src/app.py

# 4. Test your changes immediately
curl http://localhost:3333/your-new-endpoint
```

### **Common Development Patterns**

**Add Custom Span:**
```python
@app.route("/my-endpoint")
def my_function():
    with tracer.start_as_current_span("custom_operation") as span:
        span.set_attribute("custom.attribute", "value")
        # Your business logic here
        span.add_event("Custom event happened")
        return {"result": "success"}
```

**Add Custom Metric:**
```python
custom_counter = meter.create_counter(
    "custom_operations_total",
    description="Total custom operations"
)

# In your function:
custom_counter.add(1, {"operation_type": "important"})
```

### **Troubleshooting**
```bash
# Check if telemetry is being received
kubectl logs -n observability -l app=otel-collector --tail=50

# Check Tempo ingestion
kubectl logs -n observability -l app=tempo --tail=50

# Check Prometheus metrics
curl "http://localhost:9090/api/v1/query?query=up"
```

---

## 📚 **Next Steps**

### **Learn More About:**
1. **OpenTelemetry Concepts:** https://opentelemetry.io/docs/concepts/
2. **Span Attributes:** https://opentelemetry.io/docs/reference/specification/trace/semantic_conventions/
3. **Metrics Types:** https://opentelemetry.io/docs/reference/specification/metrics/
4. **Sampling:** How to reduce data volume in production

### **Experiment Ideas:**
- Add tracing to external API calls
- Implement custom samplers
- Create business-specific dashboards
- Add log correlation with traces
- Experiment with different attribute strategies

---

## 🎯 **Key Learning Outcomes**

After following this guide, you should understand:

✅ **How OpenTelemetry SDKs generate telemetry**  
✅ **The role of the OpenTelemetry Collector**  
✅ **How traces provide request-level visibility**  
✅ **How metrics provide aggregated insights**  
✅ **How to correlate metrics and traces for debugging**  
✅ **The basics of creating production-ready observability**

---

**Ready for production testing?** Check out the [README.md](README.md) for the full Kubernetes deployment workflow.
