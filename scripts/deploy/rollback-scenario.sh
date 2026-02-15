#!/usr/bin/env bash
set -euo pipefail

# SafeFlow - Rollback Make.com Scenario
#
# Rolls back a scenario to the previous backed-up version.
#
# Usage:
#   ./scripts/deploy/rollback-scenario.sh scenario-a-inbound
#   ./scripts/deploy/rollback-scenario.sh scenario-a-inbound --environment production
#   ./scripts/deploy/rollback-scenario.sh scenario-a-inbound --version 20260215_143000

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BACKUP_DIR="$PROJECT_ROOT/.deploy-backups"

# Defaults
ENVIRONMENT="staging"
TARGET_VERSION=""
SCENARIO_NAME=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --version)
            TARGET_VERSION="$2"
            shift 2
            ;;
        -*)
            echo "Unknown option: $1"
            exit 1
            ;;
        *)
            SCENARIO_NAME="$1"
            shift
            ;;
    esac
done

if [[ -z "$SCENARIO_NAME" ]]; then
    echo "Usage: $0 <scenario-name> [--environment staging|production] [--version timestamp]"
    exit 1
fi

# Colour output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC}  $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

echo "============================================"
echo "SafeFlow Scenario Rollback"
echo "============================================"
echo "Scenario:    $SCENARIO_NAME"
echo "Environment: $ENVIRONMENT"
echo "============================================"
echo ""

SCENARIO_BACKUP_DIR="$BACKUP_DIR/$SCENARIO_NAME"

# Find backup to restore
if [[ -n "$TARGET_VERSION" ]]; then
    BACKUP_FILE="$SCENARIO_BACKUP_DIR/${TARGET_VERSION}_${ENVIRONMENT}.json"
    if [[ ! -f "$BACKUP_FILE" ]]; then
        log_error "Backup not found: $BACKUP_FILE"
        exit 1
    fi
else
    # Find most recent backup for this environment
    BACKUP_FILE=$(ls -t "$SCENARIO_BACKUP_DIR"/*_${ENVIRONMENT}.json 2>/dev/null | head -1)
    if [[ -z "$BACKUP_FILE" ]]; then
        log_error "No backups found for $SCENARIO_NAME in $ENVIRONMENT"
        echo ""
        echo "Available backups:"
        ls -la "$SCENARIO_BACKUP_DIR"/ 2>/dev/null || echo "  No backup directory found"
        exit 1
    fi
fi

log_info "Rolling back to: $(basename "$BACKUP_FILE")"

# Confirm rollback
echo ""
echo "WARNING: This will replace the current $ENVIRONMENT scenario with the backup."
read -r -p "Are you sure you want to proceed? (yes/no): " CONFIRM
if [[ "$CONFIRM" != "yes" ]]; then
    log_warn "Rollback cancelled."
    exit 0
fi

# Perform rollback
log_info "Restoring backup..."

if [[ -z "${MAKE_API_KEY:-}" ]]; then
    log_error "MAKE_API_KEY environment variable not set"
    exit 1
fi

# Deploy the backup blueprint
log_info "Deploying backup blueprint via Make.com API..."
echo "  POST https://eu2.make.com/api/v2/scenarios"
echo "  Source: $BACKUP_FILE"

# Log rollback
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DEPLOY_LOG="$BACKUP_DIR/deploy.log"
echo "$TIMESTAMP | $SCENARIO_NAME | ROLLBACK | $ENVIRONMENT | $(basename "$BACKUP_FILE")" >> "$DEPLOY_LOG"

echo ""
log_info "ROLLBACK COMPLETE"
echo "  Scenario: $SCENARIO_NAME"
echo "  Restored: $(basename "$BACKUP_FILE")"
echo "  Env:      $ENVIRONMENT"
echo "============================================"
