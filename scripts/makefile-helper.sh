#!/bin/bash
# Makefile helper functions
# This script contains reusable functions for complex Makefile operations

# Only set strict mode when script is executed directly, not when sourced
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    set -euo pipefail
fi

# Get API key from various sources
# Usage: get_api_key [API_KEY]
# Returns: API key value via stdout
get_api_key() {
    local api_key="${1:-}"
    
    if [ -n "$api_key" ]; then
        echo "$api_key"
        return 0
    fi
    
    # Try secrets/admin_api_key.txt first
    if [ -f "secrets/admin_api_key.txt" ]; then
        cat secrets/admin_api_key.txt | tr -d '\n'
        return 0
    fi
    
    # Fall back to secrets/openai_api_key.txt
    if [ -f "secrets/openai_api_key.txt" ]; then
        cat secrets/openai_api_key.txt | tr -d '\n'
        return 0
    fi
    
    echo "❌ Please provide API_KEY=\"your-token\" or ensure secrets/admin_api_key.txt or secrets/openai_api_key.txt exists" >&2
    return 1
}

# Check if database and vector store already have data
# Usage: check_data_exists
# Exit codes:
#   0 = Data exists and is fresh
#   1 = Data doesn't exist or is stale
#   2 = Error checking data
check_data_exists() {
    local plan_count
    local vector_count
    local collection_name="${COLLECTION_NAME:-noteplan_files_collection}"
    
    # Check if plans table exists and has data
    plan_count=$(docker compose exec -T postgres psql -U knowledge -d knowledge_workflow -t -c "SELECT COUNT(*) FROM plans;" 2>/dev/null | tr -d ' \n')
    
    if [ -z "$plan_count" ] || [ "$plan_count" = "0" ]; then
        echo "⚠️  No plans found in database" >&2
        return 1
    fi
    
    # Check if vector store collection exists and has points
    vector_count=$(docker compose exec -T qdrant curl -s "http://localhost:6333/collections/$collection_name" 2>/dev/null | grep -o '"points_count":[0-9]*' | grep -o '[0-9]*' | head -1)
    
    if [ -z "$vector_count" ] || [ "$vector_count" = "0" ]; then
        echo "⚠️  No vectors found in collection $collection_name" >&2
        return 1
    fi
    
    echo "✅ Data exists: $plan_count plans, $vector_count vectors"
    return 0
}

# Check service health status and optionally wait for services to be healthy
# Usage: check_service_health [service1] [service2] ... [--wait] [--timeout SECONDS]
# Exit codes:
#   0 = All services are healthy
#   1 = Services are running but not healthy
#   2 = Services need to be started
check_service_health() {
    local timeout="${TIMEOUT:-60}"
    local wait_for_healthy=false
    local services=()
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --wait)
                wait_for_healthy=true
                shift
                ;;
            --timeout)
                timeout="$2"
                shift 2
                ;;
            *)
                services+=("$1")
                shift
                ;;
        esac
    done
    
    # If no services specified, check common services
    if [ ${#services[@]} -eq 0 ]; then
        services=("postgres" "qdrant" "llm-proxy" "agentic-api")
    fi
    
    # Function to check if a service is running
    is_service_running() {
        local service=$1
        if docker compose ps "$service" 2>/dev/null | grep -qE "(Up|Running)"; then
            return 0
        fi
        return 1
    }
    
    # Function to check if a service is healthy
    is_service_healthy() {
        local service=$1
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
        
        echo "⏳ Waiting for $service to be healthy (timeout: ${timeout}s)..." >&2
        
        while [ $elapsed -lt $timeout ]; do
            if is_service_healthy "$service"; then
                echo "✅ $service is healthy" >&2
                return 0
            fi
            sleep 2
            elapsed=$((elapsed + 2))
        done
        
        echo "❌ $service did not become healthy within ${timeout}s" >&2
        return 1
    }
    
    # Check each service
    local all_healthy=true
    local needs_start=()
    
    for service in "${services[@]}"; do
        if is_service_running "$service"; then
            if is_service_healthy "$service"; then
                echo "✅ $service is running and healthy" >&2
            else
                echo "⚠️  $service is running but not healthy" >&2
                if [ "$wait_for_healthy" = true ]; then
                    if ! wait_for_service_healthy "$service" "$timeout"; then
                        all_healthy=false
                    fi
                else
                    all_healthy=false
                fi
            fi
        else
            echo "⚠️  $service is not running" >&2
            needs_start+=("$service")
            all_healthy=false
        fi
    done
    
    # Return exit code based on health status
    if [ "$all_healthy" = true ]; then
        return 0
    else
        # If we have services that need to start, return special exit code
        if [ ${#needs_start[@]} -gt 0 ]; then
            return 2  # Services need to be started
        else
            return 1  # Services are running but not healthy
        fi
    fi
}

# Format API response with headers and body separated
# Usage: format_api_response
# Reads curl output with -i flag from stdin and formats it nicely
format_api_response() {
    local in_headers=true
    local body_lines=()
    local stats_lines=()
    
    echo "📋 Response Headers:"
    
    while IFS= read -r line; do
        if [[ "$line" =~ ^HTTP/ ]]; then
            echo "  $line"
        elif [[ -n "$line" && "$line" =~ : && "$in_headers" == true ]]; then
            echo "  $line"
        elif [[ -z "$line" && "$in_headers" == true ]]; then
            in_headers=false
            echo ""
            echo "📄 Response Body:"
        elif [[ "$in_headers" == false ]]; then
            if [[ "$line" =~ ^Response\ Time: ]] || [[ "$line" =~ ^HTTP\ Status: ]]; then
                stats_lines+=("$line")
            elif [[ -n "$line" ]]; then
                body_lines+=("$line")
            fi
        fi
    done
    
    # Format and print body
    if [[ ${#body_lines[@]} -gt 0 ]]; then
        local body_text
        body_text=$(IFS=$'\n'; echo "${body_lines[*]}")
        
        # Try to format as JSON if it looks like JSON
        if command -v jq >/dev/null 2>&1 && echo "$body_text" | jq . >/dev/null 2>&1; then
            echo "$body_text" | jq .
        else
            echo "$body_text"
        fi
    else
        echo "(empty body)"
    fi
    
    # Print stats
    if [[ ${#stats_lines[@]} -gt 0 ]]; then
        echo ""
        printf '%s\n' "${stats_lines[@]}"
    fi
}

# Test the note query API
# Usage: test_note_query_api QUERY API_KEY_VALUE
# Uses the mounted script at /app/scripts/containers/test/test_note_query_api.sh
test_note_query_api() {
    local query="${1:-}"
    local api_key_value="${2:-}"
    
    if [ -z "$query" ]; then
        echo "❌ Please provide QUERY=\"your question about notes\"" >&2
        return 1
    fi
    
    if [ -z "$api_key_value" ]; then
        echo "❌ API key is required" >&2
        return 1
    fi
    
    echo "🧪 Testing note query API with query: $query"
    
    # Build the JSON payload with proper escaping
    local json_payload
    json_payload=$(printf '{"query": "%s"}' "$(echo "$query" | sed 's/"/\\"/g')")
    
    # Run the mounted script in docker container with environment variables
    API_KEY_VALUE="$api_key_value" \
    JSON_PAYLOAD="$json_payload" \
    docker compose run --rm -e API_KEY_VALUE -e JSON_PAYLOAD test \
        /app/scripts/containers/test/test_note_query_api.sh
}

# Main dispatcher - call functions by name
# Usage: makefile_helper FUNCTION_NAME [args...]
main() {
    local function_name="${1:-}"
    shift || true
    
    case "$function_name" in
        get_api_key)
            get_api_key "$@"
            ;;
        check_data_exists)
            check_data_exists "$@"
            ;;
        check_service_health)
            check_service_health "$@"
            ;;
        format_api_response)
            format_api_response "$@"
            ;;
        test_note_query_api)
            test_note_query_api "$@"
            ;;
        *)
            echo "Unknown function: $function_name" >&2
            echo "Available functions: get_api_key, check_data_exists, check_service_health, format_api_response, test_note_query_api" >&2
            return 1
            ;;
    esac
}

# If script is executed directly (not sourced), run main
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    main "$@"
fi
