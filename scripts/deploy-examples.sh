#!/bin/bash

# =============================================================================
# DEPLOY EXAMPLE APPLICATIONS
# Usage: ./scripts/deploy-examples.sh
# =============================================================================

set -e

echo "🚀 Deploying Example Applications to Kubernetes (Clean Build)..."
echo "================================================================="

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl not found. Please install kubectl first."
    exit 1
fi

# Check if cluster is accessible
if ! kubectl cluster-info &> /dev/null; then
    echo "❌ Cannot connect to Kubernetes cluster."
    exit 1
fi

echo "✅ Connected to Kubernetes cluster"

# Force clean build - remove old images and pods
echo "🧹 Forcing clean build..."

# Set Docker environment to minikube
eval $(minikube docker-env)

# Remove old Docker images to force clean rebuild
echo "  Removing old Docker images..."
docker rmi load-generator:latest 2>/dev/null || echo "    load-generator:latest not found (OK)"
docker rmi instrumented-app:latest 2>/dev/null || echo "    instrumented-app:latest not found (OK)"

# Remove old pods if namespace exists
if kubectl get namespace apps >/dev/null 2>&1; then
    echo "  Removing old applications..."
    kubectl delete namespace apps --wait=false 2>/dev/null || true
    echo "  Waiting for namespace cleanup..."
    while kubectl get namespace apps >/dev/null 2>&1; do
        sleep 1
    done
fi

# Build Docker images in minikube context
echo "📦 Building Docker images from scratch..."

# Build instrumented-app image
echo "  Building instrumented-app image (clean build)..."
cd examples/instrumented-app
docker build -t instrumented-app:latest . --no-cache
cd ../..

# Build load-generator image
echo "  Building load-generator image (clean build)..."
cd examples/load-generator
docker build -t load-generator:latest . --no-cache
cd ../..

echo "✅ Clean Docker images built successfully in minikube context"

# Deploy applications
echo ""
echo "📦 Deploying applications..."
kubectl apply -f examples/instrumented-app/manifests/deployment.yaml
kubectl apply -f examples/load-generator/manifests/deployment.yaml

# Wait for pods to be ready
echo ""
echo "⏳ Waiting for pods to be ready..."
kubectl wait --for=condition=ready pod -l 'app in (instrumented-app,load-generator)' -n apps --timeout=300s

echo ""
echo "🎉 Applications deployed successfully!"

# Clean up any existing port-forwards first
echo ""
echo "🧹 Cleaning up existing port-forwards..."
pkill -f "kubectl port-forward.*apps" 2>/dev/null || true
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
    local namespace=$4
    
    if check_port_available $port; then
        echo "  Starting $name port-forward..."
        kubectl port-forward -n $namespace svc/$service $port:$port >/dev/null 2>&1 &
        local pid=$!
        
        # Wait up to 5 seconds for port-forward to establish
        local count=0
        while [ $count -lt 5 ] && check_port_available $port; do
            sleep 1
            count=$((count + 1))
        done
        
        # Verify it's working
        if ! check_port_available $port; then
            echo "  ✅ $name: http://localhost:$port"
            return 0
        else
            echo "  ⚠️  $name: Failed to start port-forward"
            kill $pid 2>/dev/null || true
            return 1
        fi
    else
        echo "  ✅ $name: http://localhost:$port (already running)"
        return 0
    fi
}

# Setup port-forwards
echo "🌐 Setting up port-forwards..."

PF_SUCCESS=0
PF_TOTAL=2

# Instrumented App
if start_port_forward "instrumented-app" "3333" "Instrumented App" "apps"; then
    ((PF_SUCCESS++))
fi

# Load Generator
if start_port_forward "load-generator" "8888" "Load Generator" "apps"; then
    ((PF_SUCCESS++))
fi

# Report port-forward status
echo ""
if [ $PF_SUCCESS -eq $PF_TOTAL ]; then
    echo "✅ All port-forwards active ($PF_SUCCESS/$PF_TOTAL)"
elif [ $PF_SUCCESS -gt 0 ]; then
    echo "⚠️  Partial port-forwards active ($PF_SUCCESS/$PF_TOTAL)"
else
    echo "❌ No port-forwards active"
fi

echo ""
echo "🧪 Quick Test:"
echo "   curl http://localhost:3333/health"
echo "   curl http://localhost:3333/"
echo ""
echo "🌐 Access Applications:"
echo "   • Instrumented App: http://localhost:3333"
echo "   • Load Generator:   http://localhost:8888"
echo ""
echo "🛑 Stop applications:"
echo "   kubectl delete namespace apps"
