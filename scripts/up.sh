#!/bin/bash

# =============================================================================
# MINIMAL OPENTELEMETRY STACK - STARTUP SCRIPT
# Usage: ./scripts/up.sh
# =============================================================================

set -e

echo "🚀 Starting Minimal OpenTelemetry Stack..."
echo "=========================================="

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl not found. Please install kubectl first."
    exit 1
fi

# Check if cluster is accessible
if ! kubectl cluster-info &> /dev/null; then
    echo "❌ Cannot connect to Kubernetes cluster."
    echo "   Please check your kubectl configuration."
    exit 1
fi

echo "✅ Connected to Kubernetes cluster"

# Apply all manifests
echo ""
echo "📦 Deploying all components..."
kubectl apply -f platform/manifests/all-in-one.yaml

# Wait for running pods to be ready (exclude completed jobs)
echo ""
echo "⏳ Waiting for pods to be ready..."
kubectl wait --for=condition=ready pod \
    -l 'app in (grafana,tempo,otel-collector,prometheus,minio)' \
    -n observability --timeout=300s

# Wait for StatefulSet to be ready
echo ""
echo "⏳ Waiting for StatefulSet to be ready..."
kubectl wait --for=jsonpath='{.status.readyReplicas}'=1 statefulset/prometheus \
    -n observability --timeout=300s

# Check HPA status
echo ""
echo "📊 Checking HPA status..."
kubectl get hpa -n observability

if [ $? -eq 0 ]; then
    echo "✅ All running pods are ready!"
else
    echo "⚠️  Some pods are not ready. Checking status..."
    kubectl get pods -n observability
    echo ""
    echo "💡 You can check logs with: kubectl logs -n observability <pod-name>"
fi

# Clean up any existing port-forwards first
echo ""
echo "🧹 Cleaning up existing port-forwards..."
pkill -f "kubectl port-forward" 2>/dev/null || true
sleep 1

# Function to check if port is available
check_port_available() {
    local port=$1
    ! lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1
}

# Function to start port-forward with validation
start_port_forward() {
    local service=$1
    local port=$2
    local name=$3
    local url_desc=$4
    
    if check_port_available $port; then
        echo "  Starting $name port-forward..."
        kubectl port-forward -n observability svc/$service $port:$port >/dev/null 2>&1 &
        local pid=$!
        
        # Wait up to 5 seconds for port-forward to establish
        local count=0
        while [ $count -lt 5 ] && check_port_available $port; do
            sleep 1
            count=$((count + 1))
        done
        
        # Verify it's working
        if ! check_port_available $port; then
            echo "  ✅ $name: $url_desc"
            return 0
        else
            echo "  ⚠️  $name: Failed to start (trying manual access)"
            kill $pid 2>/dev/null || true
            return 1
        fi
    else
        echo "  ✅ $name: $url_desc (already running)"
        return 0
    fi
}

# Setup port-forwards with improved reliability
echo ""
echo "🌐 Setting up port-forwards..."

# Track success for summary
PF_SUCCESS=0
PF_TOTAL=4

# Grafana
if start_port_forward "grafana" "3000" "Grafana" "http://localhost:3000 (admin/admin)"; then
    ((PF_SUCCESS++))
fi

# Tempo (via Grafana)
echo "  ✅ Tempo: Access via Grafana → Explore → Tempo"

# OpenTelemetry HTTP
if start_port_forward "otel-collector" "4318" "OTel HTTP" "localhost:4318"; then
    ((PF_SUCCESS++))
fi

# OpenTelemetry gRPC
if start_port_forward "otel-collector" "4317" "OTel gRPC" "localhost:4317"; then
    ((PF_SUCCESS++))
fi

# Prometheus
if start_port_forward "prometheus" "9090" "Prometheus" "http://localhost:9090"; then
    ((PF_SUCCESS++))
fi

# Report port-forward status
echo ""
if [ $PF_SUCCESS -eq $PF_TOTAL ]; then
    echo "✅ All port-forwards active ($PF_SUCCESS/$PF_TOTAL)"
elif [ $PF_SUCCESS -gt 0 ]; then
    echo "⚠️  Partial port-forwards active ($PF_SUCCESS/$PF_TOTAL)"
    echo "   💡 You can manually access services or retry with:"
    echo "      kubectl port-forward -n observability svc/<service> <port>:<port>"
else
    echo "❌ No port-forwards active"
    echo "   💡 Access services manually with kubectl port-forward commands"
fi

echo ""
echo "🎉 Stack is ready!"
echo "=================="
echo ""
echo "🌐 Access URLs:"
echo "   • Grafana:    http://localhost:3000 (admin/admin)"
echo "   • Prometheus: http://localhost:9090"
echo "   • Tempo:      Access via Grafana → Explore → Tempo"
echo ""
echo "📡 Send telemetry to:"
echo "   • HTTP: localhost:4318"
echo "   • gRPC: localhost:4317"
echo ""
echo "🧪 Test with: ./scripts/deploy-examples.sh OR ./scripts/test-load.sh"
echo ""
echo "🛑 Stop options:"
echo "   • Full cleanup: ./scripts/down.sh"
echo "   • Stop port-forwards only: pkill -f 'kubectl port-forward'"
echo ""
echo "💡 If port-forwards fail, try manual access:"
echo "   kubectl port-forward -n observability svc/grafana 3000:3000"
echo "   kubectl port-forward -n observability svc/otel-collector 4318:4318"
