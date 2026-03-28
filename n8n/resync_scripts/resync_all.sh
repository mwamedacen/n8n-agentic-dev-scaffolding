#!/bin/bash
set -e

# =============================================================================
# Resync all workflows from n8n back to template files
#
# Auto-discovers all workflow keys from the environment YAML config and
# resyncs each one.
#
# Usage:
#   ./resync_all.sh <env>
#
# Example:
#   ./resync_all.sh dev
#   ./resync_all.sh prod
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
echo -e "${BLUE}Resyncing All Workflows for ${DISPLAY_NAME}${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# --- Get all workflow keys from YAML ---
WORKFLOW_KEYS=$(python3 -c "
import yaml
with open('$ENV_CONFIG', 'r') as f:
    config = yaml.safe_load(f)
workflows = config.get('workflows', {})
for key in sorted(workflows.keys()):
    print(key)
")

if [ -z "$WORKFLOW_KEYS" ]; then
    echo -e "${YELLOW}No workflows found in environment config.${NC}"
    exit 0
fi

# --- Resync each workflow ---
TOTAL_COUNT=0
SUCCESS_COUNT=0
FAILED_COUNT=0
FAILED_WORKFLOWS=""

while IFS= read -r workflow_key; do
    if [ -z "$workflow_key" ]; then
        continue
    fi

    TOTAL_COUNT=$((TOTAL_COUNT + 1))

    echo -e "${BLUE}[$TOTAL_COUNT] Resyncing: ${workflow_key}${NC}"

    # Use resync_workflow.sh for each workflow (disable set -e temporarily)
    set +e
    bash "$SCRIPT_DIR/resync_workflow.sh" "$ENV_ARG" "$workflow_key"
    RESYNC_EXIT=$?
    set -e

    if [ $RESYNC_EXIT -eq 0 ]; then
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
    else
        FAILED_COUNT=$((FAILED_COUNT + 1))
        FAILED_WORKFLOWS="${FAILED_WORKFLOWS}  - ${workflow_key}\n"
        echo -e "${RED}[$workflow_key] resync FAILED${NC}"
    fi
    echo ""

done <<< "$WORKFLOW_KEYS"

# --- Summary ---
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Resync Summary for ${DISPLAY_NAME}${NC}"
echo -e "${BLUE}========================================${NC}"
echo "  Total:   $TOTAL_COUNT"
echo -e "  ${GREEN}Success: $SUCCESS_COUNT${NC}"
echo -e "  ${RED}Failed:  $FAILED_COUNT${NC}"

if [ $FAILED_COUNT -gt 0 ]; then
    echo ""
    echo -e "${RED}Failed workflows:${NC}"
    echo -e "$FAILED_WORKFLOWS"
    exit 1
else
    echo ""
    echo -e "${GREEN}All workflows resynced successfully!${NC}"
fi
