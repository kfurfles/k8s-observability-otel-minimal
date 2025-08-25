#!/bin/bash

# =============================================================================
# LOAD TESTING SCRIPT - CONTEXT-AWARE
# Usage: ./scripts/test-load.sh
# 
# AUTOMATIC CONTEXT DETECTION:
# - If instrumented-app running locally → tests local app
# - If not found locally → auto-starts for development testing
# - For Kubernetes testing → ensure port-forward is active first
# =============================================================================

echo "🚀 Generating realistic traffic for instrumented-app..."
echo "Endpoints with different weights to simulate real usage:"
echo "  • /          - 35% (most accessed homepage)"
echo "  • /api/data  - 25% (main API)" 
echo "  • /api/checkout - 20% (checkout process - POST)"
echo "  • /health    - 15% (health checks)"
echo "  • /api/error - 5% (less frequent errors)"
echo ""

# Context Detection and Setup
echo "🧪 Context Detection:"
echo "  Checking for app at http://localhost:3333..."

if ! curl -s http://localhost:3333/health >/dev/null 2>&1; then
    echo "  ❌ No app found at localhost:3333"
    echo "  🚀 Auto-starting local instrumented-app for development testing"
    echo "  💡 For Kubernetes testing: kubectl port-forward -n apps svc/instrumented-app 3333:3333"
    echo ""
    
    python3 examples/instrumented-app/src/app.py &
    TEST_APP_PID=$!
    
    echo "  ⏳ Waiting for app to start..."
    sleep 5
    
    # Verify app started successfully
    if curl -s http://localhost:3333/health >/dev/null 2>&1; then
        echo "  ✅ Local app started successfully"
    else
        echo "  ❌ Failed to start local app"
        exit 1
    fi
else
    # Detect if it's K8s or local by checking response
    if curl -s http://localhost:3333/health 2>/dev/null | grep -q "instrumented-app" 2>/dev/null; then
        echo "  ✅ App detected (running via Kubernetes port-forward)"
        echo "  🎯 Testing Kubernetes deployment"
    else
        echo "  ✅ Local development app detected"
        echo "  🧪 Testing local instrumented-app"
    fi
fi

echo ""

# Function to generate random request
generate_request() {
    local rand=$((RANDOM % 100))
    
    if [ $rand -lt 35 ]; then
        # 35% - Homepage (most popular)
        curl -s http://localhost:3333/ >/dev/null
        echo -n "/"
    elif [ $rand -lt 60 ]; then
        # 25% - API Data (second most popular)
        curl -s http://localhost:3333/api/data >/dev/null
        echo -n "D"
    elif [ $rand -lt 80 ]; then
        # 20% - Checkout (payment process - POST)
        curl -s -X POST http://localhost:3333/api/checkout \
            -H "Content-Type: application/json" \
            -d '{"userId":"load-test-'"$RANDOM"'","amount":'"$((RANDOM % 1000 + 1))"'.99,"userCurrency":"USD","email":"loadtest@example.com"}' >/dev/null
        echo -n "C"
    elif [ $rand -lt 95 ]; then
        # 15% - Health checks (monitoring)
        curl -s http://localhost:3333/health >/dev/null
        echo -n "H"
    else
        # 5% - Errors (less frequent)
        curl -s http://localhost:3333/api/error >/dev/null
        echo -n "E"
    fi
}

# Generate traffic for 2 minutes
echo "Generating traffic for 2 minutes..."
echo "Legend: / = Homepage, D = Data API, C = Checkout, H = Health, E = Error"
echo ""

end_time=$(($(date +%s) + 120))
count=0

while [ $(date +%s) -lt $end_time ]; do
    # Generate 3-5 requests in parallel at each interval
    num_requests=$((RANDOM % 3 + 3))
    
    for i in $(seq 1 $num_requests); do
        generate_request &
    done
    
    wait
    count=$((count + num_requests))
    
    # Show progress every 10 requests
    if [ $((count % 10)) -eq 0 ]; then
        echo " [$count requests]"
    fi
    
    # Random interval between 0.5-2 seconds
    sleep_time=$(echo "scale=1; $(($RANDOM % 15 + 5)) / 10" | bc 2>/dev/null || echo "1")
    sleep $sleep_time
done

echo ""
echo "✅ Traffic generated: $count requests in 2 minutes"
echo "📊 Expected distribution:"
echo "  • Homepage (~35%): ~$((count * 35 / 100)) requests"
echo "  • API Data (~25%): ~$((count * 25 / 100)) requests" 
echo "  • Checkout (~20%): ~$((count * 20 / 100)) requests"
echo "  • Health (~15%): ~$((count * 15 / 100)) requests"
echo "  • Errors (~5%): ~$((count * 5 / 100)) requests"
echo ""
echo "🔗 Check the dashboard: http://localhost:3000/d/apm-routes-status"
echo "⏳ Wait ~30 seconds for metrics to appear in Prometheus"

