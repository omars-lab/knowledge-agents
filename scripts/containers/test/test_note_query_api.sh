#!/bin/bash
# Test note query API script for use in docker container
# This script is mounted into the test container and called with environment variables

set -euo pipefail

# Source the format_api_response function if available, otherwise define it inline
if [ -f /app/scripts/makefile-helper.sh ]; then
    source /app/scripts/makefile-helper.sh
else
    # Define format_api_response function inline
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
        
        if [[ ${#body_lines[@]} -gt 0 ]]; then
            local body_text
            body_text=$(IFS=$'\n'; echo "${body_lines[*]}")
            
            if command -v jq >/dev/null 2>&1 && echo "$body_text" | jq . >/dev/null 2>&1; then
                echo "$body_text" | jq .
            else
                echo "$body_text"
            fi
        else
            echo "(empty body)"
        fi
        
        if [[ ${#stats_lines[@]} -gt 0 ]]; then
            echo ""
            printf "%s\n" "${stats_lines[@]}"
        fi
    }
fi

# Make API call and format response
curl -s -X POST "http://agentic-api:8000/api/v1/notes/query" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $API_KEY_VALUE" \
    -d "$JSON_PAYLOAD" \
    -i \
    -w "\n\nResponse Time: %{time_total}s\nHTTP Status: %{http_code}\n" \
| format_api_response

