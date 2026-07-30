#!/bin/bash
# PiNAS Archive Script
# Moves old data files from SSD to HDD based on file age and type

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONF_FILE="${SCRIPT_DIR}/archive.conf"

# Load config
if [ ! -f "$CONF_FILE" ]; then
    echo "[ERROR] Config not found: $CONF_FILE"
    exit 1
fi
source "$CONF_FILE"

# Validate directories
if [ ! -d "$SOURCE_DIR" ]; then
    echo "[ERROR] Source directory not found: $SOURCE_DIR"
    exit 1
fi

if [ ! -d "$ARCHIVE_DIR" ]; then
    echo "[ERROR] Archive directory not found: $ARCHIVE_DIR"
    echo "       Mount the HDD and create the directory first."
    exit 1
fi

# Log function
log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo "$msg"
    if [ -n "$LOG_FILE" ]; then
        echo "$msg" >> "$LOG_FILE" 2>/dev/null || true
    fi
}

# Main
log "=== PiNAS Archive Start ==="
log "Source: $SOURCE_DIR"
log "Archive: $ARCHIVE_DIR"
log "Age threshold: $AGE_DAYS days"
log "Dry run: $DRY_RUN"

# Count files
moved=0
skipped=0
errors=0
total_size=0

# Find and process files
# Using a temp file to handle filenames with spaces
TMPFILE=$(mktemp)
trap "rm -f $TMPFILE" EXIT

# Build the find command dynamically
FIND_CMD="find '$SOURCE_DIR' -type f -mtime +${AGE_DAYS}"

# Add exclusions
for dir in $EXCLUDE_DIRS; do
    FIND_CMD="${FIND_CMD} -not -path '${SOURCE_DIR}/${dir}/*'"
done

# Skip hidden files/directories
FIND_CMD="${FIND_CMD} -not -path '${SOURCE_DIR}/.*' -not -name '.*'"

# Execute find and filter by extension
eval $FIND_CMD > "$TMPFILE" 2>/dev/null || true

while IFS= read -r filepath; do
    [ -z "$filepath" ] && continue

    # Check extension
    filename=$(basename "$filepath")
    ext="${filename##*.}"
    ext_lower=$(echo "$ext" | tr '[:upper:]' '[:lower:]')

    match=0
    for allowed_ext in $ARCHIVE_EXTENSIONS; do
        if [ "$ext_lower" = "$allowed_ext" ]; then
            match=1
            break
        fi
    done

    if [ $match -eq 0 ]; then
        skipped=$((skipped + 1))
        continue
    fi

    # Get relative path
    relpath="${filepath#$SOURCE_DIR/}"
    dest="${ARCHIVE_DIR}/${relpath}"
    dest_dir=$(dirname "$dest")

    # Get file size
    fsize=$(stat -c%s "$filepath" 2>/dev/null || echo 0)
    fsize_mb=$(echo "scale=1; $fsize / 1048576" | bc 2>/dev/null || echo "?")

    if [ "$DRY_RUN" = "yes" ]; then
        log "[DRY RUN] Would move: $relpath (${fsize_mb}MB)"
    else
        # Create destination directory
        if ! mkdir -p "$dest_dir" 2>/dev/null; then
            log "[ERROR] Cannot create directory: $dest_dir"
            errors=$((errors + 1))
            continue
        fi

        # Move file
        if mv "$filepath" "$dest" 2>/dev/null; then
            log "[MOVED] $relpath (${fsize_mb}MB)"
            moved=$((moved + 1))
            total_size=$((total_size + fsize))
        else
            log "[ERROR] Failed to move: $relpath"
            errors=$((errors + 1))
        fi
    fi
done < "$TMPFILE"

# Summary
total_size_mb=$(echo "scale=1; $total_size / 1048576" | bc 2>/dev/null || echo "0")
log "=== Archive Complete ==="
log "Moved: $moved files (${total_size_mb}MB)"
log "Skipped (wrong type): $skipped"
log "Errors: $errors"

if [ "$DRY_RUN" = "yes" ]; then
    log "[NOTE] This was a dry run. Set DRY_RUN=\"no\" in archive.conf to actually move files."
fi
