#!/bin/bash
set -e

# =============================================================================
# Shared functions for n8n deployment scripts
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
GENERATED_DIR=""
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

    # Load secrets: root .env first (defaults), then .env.<env> overlay.
    # Env-specific values WIN for shared keys (matches admin._load_env).
    local ROOT_ENV="$PROJECT_DIR/.env"
    if [ -f "$ROOT_ENV" ]; then
        set -a
        # shellcheck disable=SC1090
        source "$ROOT_ENV"
        set +a
    fi
    if [ -f "$ENV_FILE" ]; then
        set -a
        # shellcheck disable=SC1090
        source "$ENV_FILE"
        set +a
    fi

    # Check N8N_API_KEY is set
    if [ -z "$N8N_API_KEY" ]; then
        echo -e "${RED}Error: N8N_API_KEY is not set.${NC}"
        echo "Define it in $ROOT_ENV or $ENV_FILE, or export it before running."
        exit 1
    fi

    # Set generated directory
    GENERATED_DIR="$PROJECT_DIR/n8n/workflows/generated/${ENV_NAME}"
    mkdir -p "$GENERATED_DIR"

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
# deploy_and_activate - Uploads workflow JSON via PUT, then activates via POST
# =============================================================================
deploy_and_activate() {
    local workflow_id="$1"
    local workflow_file="$2"

    # Upload workflow via PUT
    local upload_response
    upload_response=$(curl -s -w "\n%{http_code}" \
        -X PUT \
        -H "Content-Type: application/json" \
        -H "X-N8N-API-KEY: ${N8N_API_KEY}" \
        -d @"$workflow_file" \
        "${API_BASE}/api/v1/workflows/${workflow_id}")

    local upload_http_code
    upload_http_code=$(echo "$upload_response" | tail -1)
    local upload_body
    upload_body=$(echo "$upload_response" | sed '$d')

    if [ "$upload_http_code" -ne 200 ]; then
        echo -e "${RED}Upload failed (HTTP $upload_http_code)${NC}"
        echo "$upload_body"
        return 1
    fi

    # Activate workflow via POST
    local activate_response
    activate_response=$(curl -s -w "\n%{http_code}" \
        -X POST \
        -H "Content-Type: application/json" \
        -H "X-N8N-API-KEY: ${N8N_API_KEY}" \
        "${API_BASE}/api/v1/workflows/${workflow_id}/activate")

    local activate_http_code
    activate_http_code=$(echo "$activate_response" | tail -1)

    if [ "$activate_http_code" -ne 200 ]; then
        echo -e "${YELLOW}Warning: Activation failed (HTTP $activate_http_code)${NC}"
        return 1
    fi

    return 0
}

# =============================================================================
# deploy_and_activate_verbose - Same as deploy_and_activate with detailed output
# =============================================================================
deploy_and_activate_verbose() {
    local workflow_id="$1"
    local workflow_file="$2"
    local workflow_name="${3:-}"

    echo -e "${BLUE}Deploying workflow: ${workflow_name:-$workflow_id}${NC}"
    echo "  Workflow ID: $workflow_id"
    echo "  Source file: $workflow_file"
    echo ""

    # Upload workflow via PUT
    echo -e "  ${YELLOW}Uploading workflow...${NC}"
    local upload_response
    upload_response=$(curl -s -w "\n%{http_code}" \
        -X PUT \
        -H "Content-Type: application/json" \
        -H "X-N8N-API-KEY: ${N8N_API_KEY}" \
        -d @"$workflow_file" \
        "${API_BASE}/api/v1/workflows/${workflow_id}")

    local upload_http_code
    upload_http_code=$(echo "$upload_response" | tail -1)
    local upload_body
    upload_body=$(echo "$upload_response" | sed '$d')

    if [ "$upload_http_code" -ne 200 ]; then
        echo -e "  ${RED}Upload FAILED (HTTP $upload_http_code)${NC}"
        echo "  Response: $upload_body"
        return 1
    fi
    echo -e "  ${GREEN}Upload successful (HTTP $upload_http_code)${NC}"

    # Activate workflow via POST
    echo -e "  ${YELLOW}Activating workflow...${NC}"
    local activate_response
    activate_response=$(curl -s -w "\n%{http_code}" \
        -X POST \
        -H "Content-Type: application/json" \
        -H "X-N8N-API-KEY: ${N8N_API_KEY}" \
        "${API_BASE}/api/v1/workflows/${workflow_id}/activate")

    local activate_http_code
    activate_http_code=$(echo "$activate_response" | tail -1)

    if [ "$activate_http_code" -ne 200 ]; then
        echo -e "  ${YELLOW}Warning: Activation returned HTTP $activate_http_code${NC}"
        return 1
    fi
    echo -e "  ${GREEN}Activation successful${NC}"
    echo ""

    return 0
}

# =============================================================================
# run_generic_hydration - Calls hydrate_workflow.py with standard args
# =============================================================================
run_generic_hydration() {
    local workflow_key="$1"
    local template_file="$2"

    echo -e "${YELLOW}Hydrating workflow: ${workflow_key}${NC}"
    echo "  Template: $template_file"
    echo "  Environment: $ENV_NAME"
    echo ""

    python3 "$PROJECT_DIR/n8n/build_scripts/hydrate_workflow.py" \
        -e "$ENV_NAME" \
        -t "$template_file" \
        -k "$workflow_key"
}
