#!/bin/bash
set -e

# =============================================================================
# Deploy a single workflow to an n8n environment
#
# Usage:
#   ./deploy_workflow.sh <env> <workflow_key>
#
# Example:
#   ./deploy_workflow.sh dev periodic_excel_report
#   ./deploy_workflow.sh prod invoice_processor
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_common.sh"

# --- Parse arguments ---
ENV_ARG="$1"
WORKFLOW_KEY="$2"

validate_env_arg "$ENV_ARG"

if [ -z "$WORKFLOW_KEY" ]; then
    echo -e "${RED}Error: Workflow key is required${NC}"
    echo ""
    echo "Usage: $0 <env> <workflow_key>"
    echo ""
    echo "Example: $0 dev periodic_excel_report"
    exit 1
fi

# --- Load environment ---
load_env "$ENV_ARG"
echo ""

# --- Get workflow metadata ---
WORKFLOW_ID=$(get_workflow_id "$WORKFLOW_KEY")
WORKFLOW_NAME=$(get_workflow_name "$WORKFLOW_KEY")

echo -e "${BLUE}Workflow: ${WORKFLOW_NAME} (key: ${WORKFLOW_KEY}, id: ${WORKFLOW_ID})${NC}"
echo ""

# --- Auto-discover template file ---
TEMPLATE_FILE="$PROJECT_DIR/n8n/workflows/${WORKFLOW_KEY}.template.json"

if [ ! -f "$TEMPLATE_FILE" ]; then
    echo -e "${RED}Error: Template file not found: $TEMPLATE_FILE${NC}"
    echo "Expected convention: n8n/workflows/<workflow_key>.template.json"
    exit 1
fi

# --- Hydrate ---
run_generic_hydration "$WORKFLOW_KEY" "$TEMPLATE_FILE"
echo ""

# --- Deploy ---
GENERATED_FILE="$GENERATED_DIR/${WORKFLOW_KEY}.generated.json"

if [ ! -f "$GENERATED_FILE" ]; then
    echo -e "${RED}Error: Generated file not found: $GENERATED_FILE${NC}"
    echo "Hydration may have failed."
    exit 1
fi

deploy_and_activate_verbose "$WORKFLOW_ID" "$GENERATED_FILE" "$WORKFLOW_NAME"

echo -e "${GREEN}Successfully deployed: ${WORKFLOW_NAME}${NC}"
