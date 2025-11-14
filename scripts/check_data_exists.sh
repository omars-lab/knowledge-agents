#!/bin/bash
# Check if database and vector store already have data
# Exit codes:
#   0 = Data exists and is fresh
#   1 = Data doesn't exist or is stale
#   2 = Error checking data

set +e

# Check if plans table exists and has data
PLAN_COUNT=$(docker compose exec -T postgres psql -U knowledge -d knowledge_workflow -t -c "SELECT COUNT(*) FROM plans;" 2>/dev/null | tr -d ' \n')

if [ -z "$PLAN_COUNT" ] || [ "$PLAN_COUNT" = "0" ]; then
    echo "⚠️  No plans found in database"
    exit 1
fi

# Check if vector store collection exists and has points
COLLECTION_NAME="${COLLECTION_NAME:-noteplan_files_collection}"
VECTOR_COUNT=$(docker compose exec -T qdrant curl -s http://localhost:6333/collections/$COLLECTION_NAME 2>/dev/null | grep -o '"points_count":[0-9]*' | grep -o '[0-9]*' | head -1)

if [ -z "$VECTOR_COUNT" ] || [ "$VECTOR_COUNT" = "0" ]; then
    echo "⚠️  No vectors found in collection $COLLECTION_NAME"
    exit 1
fi

echo "✅ Data exists: $PLAN_COUNT plans, $VECTOR_COUNT vectors"
exit 0

