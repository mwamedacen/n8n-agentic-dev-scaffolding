#!/bin/bash
set -e

# =============================================================================
# Deactivate all workflows for an n8n environment
#
# Reads all workflow IDs from the environment YAML and deactivates each one.
#
# Usage:
#   ./deactivate_all.sh <env>
#
# Example:
#   ./deactivate_all.sh dev
#   ./deactivate_all.sh prod
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_common.sh"

# --- Parse arguments ---
ENV_ARG="$1"

validate_env_arg "$ENV_ARG"

# --- Load environment ---
load_env "$ENV_ARG"
echo ""

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Deactivating All Workflows for ${DISPLAY_NAME}${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# --- Get all workflow IDs dynamically from YAML ---
WORKFLOW_DATA=$(python3 -c "
import yaml
with open('$ENV_CONFIG', 'r') as f:
    config = yaml.safe_load(f)
workflows = config.get('workflows', {})
for key, wf in workflows.items():
    wf_id = wf.get('id', '')
    wf_name = wf.get('name', key)
    if wf_id:
        print(f'{key}|{wf_id}|{wf_name}')
")

TOTAL_COUNT=0
SUCCESS_COUNT=0
FAILED_COUNT=0

while IFS='|' read -r wf_key wf_id wf_name; do
    if [ -z "$wf_key" ] || [ -z "$wf_id" ]; then
        continue
    fi

    TOTAL_COUNT=$((TOTAL_COUNT + 1))

    echo -e "  Deactivating: ${wf_name} (${wf_id})..."

    RESPONSE=$(curl -s -w "\n%{http_code}" \
        -X POST \
        -H "Content-Type: application/json" \
        -H "X-N8N-API-KEY: ${N8N_API_KEY}" \
        "${API_BASE}/api/v1/workflows/${wf_id}/deactivate")

    HTTP_CODE=$(echo "$RESPONSE" | tail -1)

    if [ "$HTTP_CODE" -eq 200 ]; then
        echo -e "  ${GREEN}Deactivated: ${wf_name}${NC}"
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
    else
        echo -e "  ${RED}Failed to deactivate: ${wf_name} (HTTP $HTTP_CODE)${NC}"
        FAILED_COUNT=$((FAILED_COUNT + 1))
    fi

done <<< "$WORKFLOW_DATA"

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Deactivation Summary for ${DISPLAY_NAME}${NC}"
echo -e "${BLUE}========================================${NC}"
echo "  Total:   $TOTAL_COUNT"
echo -e "  ${GREEN}Success: $SUCCESS_COUNT${NC}"
echo -e "  ${RED}Failed:  $FAILED_COUNT${NC}"

if [ $FAILED_COUNT -gt 0 ]; then
    exit 1
fi
