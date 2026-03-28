#!/bin/bash
set -e

# =============================================================================
# Resync a single workflow from n8n back to a template file
#
# Fetches the workflow from the n8n API, dehydrates it (reverses hydration),
# and saves the result as a template file.
#
# Usage:
#   ./resync_workflow.sh <env> <workflow_key> [remove_triggers]
#
# Example:
#   ./resync_workflow.sh dev periodic_excel_report
#   ./resync_workflow.sh prod invoice_processor true
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_common.sh"

# --- Parse arguments ---
ENV_ARG="$1"
WORKFLOW_KEY="$2"
REMOVE_TRIGGERS="${3:-false}"

validate_env_arg "$ENV_ARG"

if [ -z "$WORKFLOW_KEY" ]; then
    echo -e "${RED}Error: Workflow key is required${NC}"
    echo ""
    echo "Usage: $0 <env> <workflow_key> [remove_triggers]"
    echo ""
    echo "Example: $0 dev periodic_excel_report"
    echo "         $0 prod invoice_processor true"
    exit 1
fi

# --- Load environment ---
load_env "$ENV_ARG"
echo ""

# --- Auto-discover template path ---
TEMPLATE_PATH="n8n/workflows/${WORKFLOW_KEY}.template.json"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Resyncing Workflow: ${WORKFLOW_KEY}${NC}"
echo -e "${BLUE}========================================${NC}"
echo "  Template path: $TEMPLATE_PATH"
echo "  Remove triggers: $REMOVE_TRIGGERS"
echo ""

# --- Resync ---
resync_workflow "$WORKFLOW_KEY" "$TEMPLATE_PATH" "$REMOVE_TRIGGERS"

echo -e "${GREEN}Resync complete for: ${WORKFLOW_KEY}${NC}"
