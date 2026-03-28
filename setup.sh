#!/bin/bash
# =============================================================================
# n8n Agentic Dev Scaffolding - First-Time Setup Wizard
#
# Interactive setup that configures your local environment for n8n
# workflow development. Safe to run multiple times (non-destructive).
#
# Usage:
#   bash setup.sh
# =============================================================================

set -e

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo -e "${BOLD}========================================${NC}"
echo -e "${BOLD}  n8n Agentic Dev Scaffolding Setup${NC}"
echo -e "${BOLD}========================================${NC}"
echo ""

# =============================================================================
# Step 1: Check prerequisites
# =============================================================================
echo -e "${BLUE}Step 1: Checking prerequisites...${NC}"
echo ""

# Check Python 3
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1)
    echo -e "  ${GREEN}Python 3 found: ${PYTHON_VERSION}${NC}"
else
    echo -e "  ${RED}Python 3 is not installed.${NC}"
    echo "  Please install Python 3.8+ and try again."
    echo "  macOS: brew install python3"
    echo "  Ubuntu: sudo apt install python3"
    exit 1
fi

# Check PyYAML
if python3 -c "import yaml" 2>/dev/null; then
    echo -e "  ${GREEN}PyYAML is installed${NC}"
else
    echo -e "  ${YELLOW}PyYAML is not installed.${NC}"
    echo ""
    read -p "  Install PyYAML now? (y/n): " INSTALL_YAML
    if [ "$INSTALL_YAML" = "y" ] || [ "$INSTALL_YAML" = "Y" ]; then
        pip3 install pyyaml
        echo -e "  ${GREEN}PyYAML installed successfully${NC}"
    else
        echo -e "  ${RED}PyYAML is required. Install it with: pip3 install pyyaml${NC}"
        exit 1
    fi
fi

echo ""

# =============================================================================
# Step 2: Configure dev environment
# =============================================================================
echo -e "${BLUE}Step 2: Configure development environment${NC}"
echo ""

# Prompt for n8n instance URL
echo "  Enter your n8n instance URL."
echo "  Examples: your-instance.app.n8n.cloud, localhost:5678"
echo ""
read -p "  n8n instance URL: " N8N_INSTANCE_URL

if [ -z "$N8N_INSTANCE_URL" ]; then
    echo -e "  ${YELLOW}Skipping - you can configure this later in n8n/environments/dev.yaml${NC}"
    N8N_INSTANCE_URL="your-instance.app.n8n.cloud"
fi

# Prompt for n8n API key
echo ""
echo "  Enter your n8n API key."
echo "  You can find this in n8n under Settings > API."
echo ""
read -s -p "  n8n API key: " N8N_API_KEY
echo ""

if [ -z "$N8N_API_KEY" ]; then
    echo -e "  ${YELLOW}Skipping - you can configure this later in .env.dev${NC}"
    N8N_API_KEY="your_dev_n8n_api_key_here"
fi

# Create .env.dev
ENV_DEV_FILE="$PROJECT_DIR/.env.dev"
if [ -f "$ENV_DEV_FILE" ]; then
    echo ""
    echo -e "  ${YELLOW}.env.dev already exists.${NC}"
    read -p "  Overwrite it? (y/n): " OVERWRITE_ENV
    if [ "$OVERWRITE_ENV" != "y" ] && [ "$OVERWRITE_ENV" != "Y" ]; then
        echo "  Keeping existing .env.dev"
    else
        echo "N8N_API_KEY=${N8N_API_KEY}" > "$ENV_DEV_FILE"
        echo -e "  ${GREEN}Updated .env.dev${NC}"
    fi
else
    echo "N8N_API_KEY=${N8N_API_KEY}" > "$ENV_DEV_FILE"
    echo -e "  ${GREEN}Created .env.dev${NC}"
fi

# Update dev.yaml with instance URL
DEV_YAML="$PROJECT_DIR/n8n/environments/dev.yaml"
if [ -f "$DEV_YAML" ]; then
    sed -i.bak "s|instanceName:.*|instanceName: \"${N8N_INSTANCE_URL}\"|" "$DEV_YAML"
    rm -f "${DEV_YAML}.bak"
    echo -e "  ${GREEN}Updated n8n/environments/dev.yaml with instance URL${NC}"
else
    echo -e "  ${YELLOW}dev.yaml not found - skipping instance URL update${NC}"
fi

echo ""

# =============================================================================
# Step 3: Optional prod environment
# =============================================================================
echo -e "${BLUE}Step 3: Production environment (optional)${NC}"
echo ""
read -p "  Do you want to set up a prod environment too? (y/n): " SETUP_PROD

if [ "$SETUP_PROD" = "y" ] || [ "$SETUP_PROD" = "Y" ]; then
    echo ""
    read -p "  Prod n8n instance URL: " PROD_INSTANCE_URL
    read -s -p "  Prod n8n API key: " PROD_API_KEY
    echo ""

    if [ -n "$PROD_INSTANCE_URL" ]; then
        PROD_YAML="$PROJECT_DIR/n8n/environments/prod.yaml"
        if [ -f "$PROD_YAML" ]; then
            sed -i.bak "s|instanceName:.*|instanceName: \"${PROD_INSTANCE_URL}\"|" "$PROD_YAML"
            rm -f "${PROD_YAML}.bak"
            echo -e "  ${GREEN}Updated n8n/environments/prod.yaml${NC}"
        fi
    fi

    if [ -n "$PROD_API_KEY" ]; then
        ENV_PROD_FILE="$PROJECT_DIR/.env.prod"
        if [ -f "$ENV_PROD_FILE" ]; then
            echo -e "  ${YELLOW}.env.prod already exists. Skipping.${NC}"
        else
            echo "N8N_API_KEY=${PROD_API_KEY}" > "$ENV_PROD_FILE"
            echo -e "  ${GREEN}Created .env.prod${NC}"
        fi
    fi
else
    echo "  Skipping prod setup."
fi

echo ""

# =============================================================================
# Step 4: Bootstrap workflows
# =============================================================================
echo -e "${BLUE}Step 4: Bootstrap placeholder workflows (optional)${NC}"
echo ""
echo "  Bootstrapping creates placeholder workflows in your n8n instance"
echo "  and records their IDs in the environment YAML config."
echo ""
read -p "  Run bootstrap for dev environment now? (y/n): " RUN_BOOTSTRAP

if [ "$RUN_BOOTSTRAP" = "y" ] || [ "$RUN_BOOTSTRAP" = "Y" ]; then
    echo ""
    echo -e "  ${YELLOW}Running bootstrap...${NC}"
    python3 "$PROJECT_DIR/n8n/deployment_scripts/bootstrap_workflows.py" dev
    echo ""
    echo -e "  ${GREEN}Bootstrap complete!${NC}"
else
    echo "  Skipping bootstrap. You can run it later with:"
    echo "    python3 n8n/deployment_scripts/bootstrap_workflows.py dev"
fi

echo ""

# =============================================================================
# Done
# =============================================================================
echo -e "${BOLD}========================================${NC}"
echo -e "${GREEN}  Setup complete!${NC}"
echo -e "${BOLD}========================================${NC}"
echo ""
echo -e "${BOLD}Next steps:${NC}"
echo ""
echo "  1. Review your configuration:"
echo "     - n8n/environments/dev.yaml  (instance URL, credentials, workflow names)"
echo "     - .env.dev                   (API keys and secrets)"
echo ""
echo "  2. If you haven't bootstrapped yet, create placeholder workflows:"
echo "     python3 n8n/deployment_scripts/bootstrap_workflows.py dev"
echo ""
echo "  3. Hydrate templates for your environment:"
echo "     cd n8n/build_scripts && python3 hydrate_all.py -e dev"
echo ""
echo "  4. Deploy all workflows:"
echo "     cd n8n/deployment_scripts && ./deploy_all.sh dev"
echo ""
echo "  5. Start developing! Edit templates in n8n/workflows/ and"
echo "     prompts in common/prompts/, then hydrate and deploy."
echo ""
echo "  For full documentation, see README.md"
echo ""
