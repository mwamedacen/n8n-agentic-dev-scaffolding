#!/bin/bash
set -e

# =============================================================================
# Shared functions for n8n resync scripts
# =============================================================================

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# --- Directory computation ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# --- Global variables (set by load_env) ---
ENV_NAME=""
ENV_CONFIG=""
ENV_FILE=""
API_BASE=""
N8N_API_KEY=""
DISPLAY_NAME=""
WORKFLOW_NAME_POSTFIX=""

# =============================================================================
# validate_env_arg - Validates that an environment argument was provided
# =============================================================================
validate_env_arg() {
    if [ -z "$1" ]; then
        echo -e "${RED}Error: Environment name is required${NC}"
        echo ""
        echo "Usage: $0 <env> [additional_args...]"
        echo ""
        echo "Available environments:"
        local env_dir="$PROJECT_DIR/n8n/environments"
        if [ -d "$env_dir" ]; then
            for f in "$env_dir"/*.yaml; do
                if [ -f "$f" ]; then
                    local name
                    name="$(basename "$f" .yaml)"
                    echo "  - $name"
                fi
            done
        else
            echo "  (no environments directory found)"
        fi
        exit 1
    fi
}

# =============================================================================
# load_env - Loads YAML config + .env secrets for an environment
# =============================================================================
load_env() {
    ENV_NAME="$1"
    ENV_CONFIG="$PROJECT_DIR/n8n/environments/${ENV_NAME}.yaml"
    ENV_FILE="$PROJECT_DIR/.env.${ENV_NAME}"

    # Validate environment YAML exists
    if [ ! -f "$ENV_CONFIG" ]; then
        echo -e "${RED}Error: Environment config not found: $ENV_CONFIG${NC}"
        exit 1
    fi

    # Load display name
    DISPLAY_NAME=$(python3 -c "
import yaml
with open('$ENV_CONFIG', 'r') as f:
    config = yaml.safe_load(f)
print(config.get('displayName', '$ENV_NAME'))
")

    # Load workflow name postfix
    WORKFLOW_NAME_POSTFIX=$(python3 -c "
import yaml
with open('$ENV_CONFIG', 'r') as f:
    config = yaml.safe_load(f)
print(config.get('workflowNamePostfix', ''))
")

    # Determine API base URL from n8n.instanceName
    API_BASE=$(python3 -c "
import yaml
with open('$ENV_CONFIG', 'r') as f:
    config = yaml.safe_load(f)
instance = config.get('n8n', {}).get('instanceName', '')
if instance.startswith('http://') or instance.startswith('https://'):
    print(instance.rstrip('/'))
elif 'localhost' in instance or '127.0.0.1' in instance:
    print('http://' + instance.rstrip('/'))
else:
    print('https://' + instance.rstrip('/'))
")

    # Load .env secrets if available
    if [ -f "$ENV_FILE" ]; then
        set -a
        source "$ENV_FILE"
        set +a
    fi

    # Check N8N_API_KEY is set
    if [ -z "$N8N_API_KEY" ]; then
        echo -e "${RED}Error: N8N_API_KEY is not set.${NC}"
        echo "Make sure it's defined in $ENV_FILE or exported in your environment."
        exit 1
    fi

    echo -e "${BLUE}Environment: ${DISPLAY_NAME} (${ENV_NAME})${NC}"
    echo -e "${BLUE}API Base: ${API_BASE}${NC}"
}

# =============================================================================
# get_workflow_id - Gets workflow ID from YAML config
# =============================================================================
get_workflow_id() {
    local workflow_key="$1"
    python3 -c "
import yaml
with open('$ENV_CONFIG', 'r') as f:
    config = yaml.safe_load(f)
workflows = config.get('workflows', {})
wf = workflows.get('$workflow_key', {})
wf_id = wf.get('id', '')
if not wf_id:
    raise SystemExit('Workflow key \"$workflow_key\" not found or has no id in $ENV_CONFIG')
print(wf_id)
"
}

# =============================================================================
# get_workflow_name - Gets workflow name + postfix from YAML config
# =============================================================================
get_workflow_name() {
    local workflow_key="$1"
    python3 -c "
import yaml
with open('$ENV_CONFIG', 'r') as f:
    config = yaml.safe_load(f)
workflows = config.get('workflows', {})
wf = workflows.get('$workflow_key', {})
name = wf.get('name', '')
if not name:
    raise SystemExit('Workflow key \"$workflow_key\" not found or has no name in $ENV_CONFIG')
postfix = config.get('workflowNamePostfix', '')
print(f'{name}{postfix}')
"
}

# =============================================================================
# resync_workflow - Fetches workflow from n8n, dehydrates, saves to template
#
# Args:
#   $1 - workflow_key
#   $2 - template_path (relative to project dir or absolute)
#   $3 - remove_triggers (optional, "true" to remove trigger nodes)
# =============================================================================
resync_workflow() {
    local workflow_key="$1"
    local template_path="$2"
    local remove_triggers="${3:-false}"

    # Get workflow metadata
    local workflow_id
    workflow_id=$(get_workflow_id "$workflow_key")
    local workflow_name
    workflow_name=$(get_workflow_name "$workflow_key")

    echo -e "${BLUE}Resyncing: ${workflow_name} (key: ${workflow_key}, id: ${workflow_id})${NC}"

    # Fetch workflow from n8n API
    echo -e "  ${YELLOW}Fetching workflow from n8n...${NC}"
    local fetch_response
    fetch_response=$(curl -s -w "\n%{http_code}" \
        -X GET \
        -H "Content-Type: application/json" \
        -H "X-N8N-API-KEY: ${N8N_API_KEY}" \
        "${API_BASE}/api/v1/workflows/${workflow_id}")

    local http_code
    http_code=$(echo "$fetch_response" | tail -1)
    local body
    body=$(echo "$fetch_response" | sed '$d')

    if [ "$http_code" -ne 200 ]; then
        echo -e "  ${RED}Fetch FAILED (HTTP $http_code)${NC}"
        echo "  Response: $body"
        return 1
    fi
    echo -e "  ${GREEN}Fetched successfully${NC}"

    # Save fetched workflow to temp file
    local temp_file
    temp_file=$(mktemp /tmp/n8n_resync_XXXXXX.json)
    echo "$body" > "$temp_file"

    # Resolve template path
    local abs_template_path
    if [[ "$template_path" = /* ]]; then
        abs_template_path="$template_path"
    else
        abs_template_path="$PROJECT_DIR/$template_path"
    fi

    # Build dehydrate args
    local dehydrate_args=()
    dehydrate_args+=(--workflow-file "$temp_file")
    dehydrate_args+=(--output "$abs_template_path")
    dehydrate_args+=(--base-dir "$PROJECT_DIR")
    dehydrate_args+=(--env "$ENV_NAME")

    if [ "$remove_triggers" = "true" ]; then
        dehydrate_args+=(--remove-triggers)
    fi

    # Run dehydration
    echo -e "  ${YELLOW}Dehydrating workflow...${NC}"
    python3 "$PROJECT_DIR/n8n/resync_scripts/dehydrate_workflow.py" "${dehydrate_args[@]}"

    # Clean up temp file
    rm -f "$temp_file"

    echo -e "  ${GREEN}Template saved: ${abs_template_path}${NC}"
    echo ""
}
