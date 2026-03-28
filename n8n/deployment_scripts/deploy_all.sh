#!/bin/bash
set -e

# =============================================================================
# Deploy all workflows to an n8n environment using deployment_order.yaml
#
# Reads tier-based deployment order and deploys workflows sequentially.
# For dev environments, deactivates all workflows after deployment
# unless --keep-active is specified.
#
# Usage:
#   ./deploy_all.sh <env> [--keep-active|-k]
#
# Example:
#   ./deploy_all.sh dev
#   ./deploy_all.sh dev --keep-active
#   ./deploy_all.sh prod
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_common.sh"

# --- Parse arguments ---
ENV_ARG=""
KEEP_ACTIVE=false

for arg in "$@"; do
    case "$arg" in
        --keep-active|-k)
            KEEP_ACTIVE=true
            ;;
        *)
            if [ -z "$ENV_ARG" ]; then
                ENV_ARG="$arg"
            fi
            ;;
    esac
done

validate_env_arg "$ENV_ARG"

# --- Load environment ---
load_env "$ENV_ARG"
echo ""

# --- Read deployment order ---
DEPLOYMENT_ORDER_FILE="$PROJECT_DIR/n8n/deployment_order.yaml"

if [ ! -f "$DEPLOYMENT_ORDER_FILE" ]; then
    echo -e "${RED}Error: deployment_order.yaml not found: $DEPLOYMENT_ORDER_FILE${NC}"
    exit 1
fi

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Deploying All Workflows for ${DISPLAY_NAME}${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Parse tiers and workflows from deployment_order.yaml
TIERS_JSON=$(python3 -c "
import yaml, json
with open('$DEPLOYMENT_ORDER_FILE', 'r') as f:
    data = yaml.safe_load(f)
tiers = data.get('tiers', data.get('deployment_order', []))
print(json.dumps(tiers))
")

# --- Deploy tier by tier ---
TOTAL_COUNT=0
SUCCESS_COUNT=0
FAILED_COUNT=0
FAILED_WORKFLOWS=""

# Iterate through tiers
TIER_COUNT=$(echo "$TIERS_JSON" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))")

for (( tier_idx=0; tier_idx<TIER_COUNT; tier_idx++ )); do
    TIER_NAME=$(echo "$TIERS_JSON" | python3 -c "
import json, sys
tiers = json.load(sys.stdin)
tier = tiers[$tier_idx]
print(tier.get('name', tier.get('tier', 'Tier $((tier_idx+1))')))
")

    TIER_WORKFLOWS=$(echo "$TIERS_JSON" | python3 -c "
import json, sys
tiers = json.load(sys.stdin)
tier = tiers[$tier_idx]
workflows = tier.get('workflows', [])
for w in workflows:
    print(w)
")

    if [ -z "$TIER_WORKFLOWS" ]; then
        continue
    fi

    echo -e "${YELLOW}--- ${TIER_NAME} ---${NC}"
    echo ""

    while IFS= read -r workflow_key; do
        if [ -z "$workflow_key" ]; then
            continue
        fi

        TOTAL_COUNT=$((TOTAL_COUNT + 1))

        echo -e "${BLUE}[$TOTAL_COUNT] Deploying: ${workflow_key}${NC}"

        # Use deploy_workflow.sh for each workflow (disable set -e temporarily)
        set +e
        bash "$SCRIPT_DIR/deploy_workflow.sh" "$ENV_ARG" "$workflow_key"
        DEPLOY_EXIT=$?
        set -e

        if [ $DEPLOY_EXIT -eq 0 ]; then
            SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
            echo -e "${GREEN}[$workflow_key] deployed successfully${NC}"
        else
            FAILED_COUNT=$((FAILED_COUNT + 1))
            FAILED_WORKFLOWS="${FAILED_WORKFLOWS}  - ${workflow_key}\n"
            echo -e "${RED}[$workflow_key] deployment FAILED${NC}"
        fi
        echo ""

    done <<< "$TIER_WORKFLOWS"
done

# --- Deactivate for dev environment unless --keep-active ---
if [ "$ENV_ARG" = "dev" ] && [ "$KEEP_ACTIVE" = false ]; then
    echo -e "${YELLOW}Dev environment: deactivating all workflows...${NC}"
    bash "$SCRIPT_DIR/deactivate_all.sh" "$ENV_ARG"
    echo ""
fi

# --- Summary ---
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Deployment Summary for ${DISPLAY_NAME}${NC}"
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
    echo -e "${GREEN}All workflows deployed successfully!${NC}"
fi
