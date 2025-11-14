#!/bin/bash
# Check service health status and optionally wait for services to be healthy
# Usage:
#   check_service_health.sh [service1] [service2] ... [--wait] [--timeout SECONDS]

set +e  # Don't exit on errors - we handle exit codes manually

# Default timeout (seconds)
TIMEOUT=${TIMEOUT:-60}
WAIT_FOR_HEALTHY=false
SERVICES=()

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --wait)
            WAIT_FOR_HEALTHY=true
            shift
            ;;
        --timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        *)
            SERVICES+=("$1")
            shift
            ;;
    esac
done

# If no services specified, check common services
if [ ${#SERVICES[@]} -eq 0 ]; then
    SERVICES=("postgres" "qdrant" "llm-proxy" "agentic-api")
fi

# Function to check if a service is running
is_service_running() {
    local service=$1
    # Check if service is running - "Up" status indicates container is running
    if docker compose ps "$service" 2>/dev/null | grep -qE "(Up|Running)"; then
        return 0
    fi
    return 1
}

# Function to check if a service is healthy
is_service_healthy() {
    local service=$1
    # Check if service is healthy - look for "healthy" status
    if docker compose ps "$service" 2>/dev/null | grep -q "healthy"; then
        return 0
    fi
    return 1
}

# Function to wait for service to be healthy
wait_for_service_healthy() {
    local service=$1
    local timeout=$2
    local elapsed=0
    
    echo "⏳ Waiting for $service to be healthy (timeout: ${timeout}s)..."
    
    while [ $elapsed -lt $timeout ]; do
        if is_service_healthy "$service"; then
            echo "✅ $service is healthy"
            return 0
        fi
        sleep 2
        elapsed=$((elapsed + 2))
    done
    
    echo "❌ $service did not become healthy within ${timeout}s"
    return 1
}

# Check each service
ALL_HEALTHY=true
NEEDS_START=()

for service in "${SERVICES[@]}"; do
    if is_service_running "$service"; then
        if is_service_healthy "$service"; then
            echo "✅ $service is running and healthy"
        else
            echo "⚠️  $service is running but not healthy"
            if [ "$WAIT_FOR_HEALTHY" = true ]; then
                if ! wait_for_service_healthy "$service" "$TIMEOUT"; then
                    ALL_HEALTHY=false
                fi
            else
                ALL_HEALTHY=false
            fi
        fi
    else
        echo "⚠️  $service is not running"
        NEEDS_START+=("$service")
        ALL_HEALTHY=false
    fi
done

# Return exit code based on health status
if [ "$ALL_HEALTHY" = true ]; then
    exit 0
else
    # If we have services that need to start, return special exit code
    if [ ${#NEEDS_START[@]} -gt 0 ]; then
        exit 2  # Services need to be started
    else
        exit 1  # Services are running but not healthy
    fi
fi

