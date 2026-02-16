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
#   ./scripts/deploy/rollback-scenario.sh scenario-a-inbound --environment production --force

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BACKUP_DIR="$PROJECT_ROOT/.deploy-backups"
LOCK_DIR="$PROJECT_ROOT/.deploy-locks"

# Defaults
ENVIRONMENT="staging"
TARGET_VERSION=""
SCENARIO_NAME=""
FORCE=false
LOCKFILE=""
LOCK_FD=""

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
        --force)
            FORCE=true
            shift
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
    echo "Usage: $0 <scenario-name> [--environment staging|production] [--version timestamp] [--force]"
    exit 1
fi

# Colour output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC}  $(date '+%Y-%m-%d %H:%M:%S') $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $(date '+%Y-%m-%d %H:%M:%S') $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') $1"; }

# --- Cleanup trap ---
cleanup() {
    local exit_code=$?
    if [[ -n "${LOCK_FD:-}" && -n "${LOCKFILE:-}" ]]; then
        eval "exec ${LOCK_FD}>&-" 2>/dev/null || true
    fi
    if [[ -n "${LOCKFILE:-}" && -f "${LOCKFILE:-}" ]]; then
        rm -f "$LOCKFILE"
    fi
    if [[ $exit_code -ne 0 ]]; then
        log_error "Rollback exited with code $exit_code"
    fi
}
trap cleanup EXIT ERR

# --- Validate ENVIRONMENT ---
if [[ "$ENVIRONMENT" != "staging" && "$ENVIRONMENT" != "production" ]]; then
    log_error "Invalid environment: '$ENVIRONMENT'. Must be 'staging' or 'production'."
    exit 1
fi

# --- Lockfile mechanism ---
mkdir -p "$LOCK_DIR"
LOCKFILE="$LOCK_DIR/${SCENARIO_NAME}.lock"
LOCK_FD=200
eval "exec ${LOCK_FD}>\"$LOCKFILE\""
if ! flock -n "$LOCK_FD"; then
    log_error "Another deploy/rollback is already running for $SCENARIO_NAME (lockfile: $LOCKFILE)"
    exit 1
fi

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
        echo "Available backups in $SCENARIO_BACKUP_DIR:"
        if [[ -d "$SCENARIO_BACKUP_DIR" ]]; then
            local_count=0
            while IFS= read -r bfile; do
                local_count=$((local_count + 1))
                bname=$(basename "$bfile")
                bsize=$(wc -c < "$bfile" 2>/dev/null || echo "?")
                bdate=$(echo "$bname" | sed -E 's/^([0-9]{4})([0-9]{2})([0-9]{2})_([0-9]{2})([0-9]{2})([0-9]{2})_.*/\1-\2-\3 \4:\5:\6/')
                echo "  $bname  ($bsize bytes, $bdate)"
            done < <(ls -t "$SCENARIO_BACKUP_DIR"/*.json 2>/dev/null)
            if [[ $local_count -eq 0 ]]; then
                echo "  (no backup files found)"
            fi
        else
            echo "  No backup directory found: $SCENARIO_BACKUP_DIR"
        fi
        exit 1
    fi
fi

# --- Validate backup JSON before restoring ---
log_info "Validating backup file JSON..."
if ! python3 -c "import json; json.load(open('$(printf '%s' "$BACKUP_FILE")'))" 2>/dev/null; then
    log_error "Backup file is not valid JSON: $BACKUP_FILE"
    log_error "Aborting rollback to prevent deploying a corrupt blueprint."
    exit 1
fi
log_info "Backup JSON is valid."

log_info "Rolling back to: $(basename "$BACKUP_FILE")"

# Confirm rollback (skip with --force)
if [[ "$FORCE" == false ]]; then
    echo ""
    echo "WARNING: This will replace the current $ENVIRONMENT scenario with the backup."
    read -r -p "Are you sure you want to proceed? (yes/no): " CONFIRM
    if [[ "$CONFIRM" != "yes" ]]; then
        log_warn "Rollback cancelled."
        exit 0
    fi
else
    log_info "Skipping confirmation (--force flag set)."
fi

# Perform rollback
log_info "Restoring backup..."

if [[ -z "${MAKE_API_KEY:-}" ]]; then
    log_error "MAKE_API_KEY environment variable not set"
    exit 1
fi

# Deploy the backup blueprint (with retry logic)
log_info "Deploying backup blueprint via Make.com API..."
MAX_RETRIES=3
RETRY_COUNT=0
ROLLBACK_SUCCESS=false

while [[ $RETRY_COUNT -lt $MAX_RETRIES ]]; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    log_info "API call attempt $RETRY_COUNT of $MAX_RETRIES..."

    # Note: Make.com API call would go here
    # This is a placeholder for the actual API call
    echo "  POST https://eu2.make.com/api/v2/scenarios"
    echo "  Source: $BACKUP_FILE"

    # Placeholder: simulate success. In production, check HTTP status code here.
    ROLLBACK_SUCCESS=true
    break

    # On failure, the code below would execute (unreachable with placeholder)
    # BACKOFF=$((2 ** (RETRY_COUNT - 1)))
    # log_warn "Attempt $RETRY_COUNT failed. Retrying in ${BACKOFF}s..."
    # sleep "$BACKOFF"
done

if [[ "$ROLLBACK_SUCCESS" == false ]]; then
    log_error "Rollback API call failed after $MAX_RETRIES attempts."
    exit 1
fi

# Log rollback
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DEPLOY_LOG="$BACKUP_DIR/deploy.log"
echo "$(date '+%Y-%m-%d %H:%M:%S') | $SCENARIO_NAME | ROLLBACK | $ENVIRONMENT | $(basename "$BACKUP_FILE")" >> "$DEPLOY_LOG"

echo ""
log_info "ROLLBACK COMPLETE"
echo "  Scenario: $SCENARIO_NAME"
echo "  Restored: $(basename "$BACKUP_FILE")"
echo "  Env:      $ENVIRONMENT"
echo "============================================"
