#!/bin/bash

# =============================================================================
# MINIMAL OPENTELEMETRY STACK - SHUTDOWN SCRIPT
# Usage: ./scripts/down.sh
# =============================================================================

set -e

echo "🛑 Stopping Minimal OpenTelemetry Stack..."
echo "=========================================="

# Stop all kubectl port-forward processes
echo "📴 Stopping port-forwards..."
pkill -f "kubectl port-forward" 2>/dev/null || true
echo "✅ Port-forwards stopped"

# Delete the namespace (removes all resources)
echo ""
echo "🗑️  Removing all resources..."
kubectl delete namespace observability --ignore-not-found=true

# Wait for namespace deletion
echo "⏳ Waiting for namespace deletion..."
kubectl wait --for=delete namespace/observability --timeout=60s 2>/dev/null || true

echo ""
echo "✅ OpenTelemetry Stack stopped successfully!"
echo ""
echo "💡 To start again: ./scripts/up.sh"
