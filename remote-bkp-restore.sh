#!/bin/bash

# remote-bkp-restore.sh: Backup/Restore Script for Remote Servers
# Usage: ./remote-bkp-restore.sh <server_list_file> <folder_list_file> <backup|restore>
# Example: ./remote-bkp-restore.sh servers.txt folders.txt backup
#
# This script (remote-bkp-restore.sh) backs up or restores configured folders on
# remote servers. It reads server and folder lists from input files, validates
# inputs, executes the required operation remotely, and logs the outcome.

set -Eeuo pipefail
umask 077

# ----------------------------------------------------------------------------
# GLOBAL CONFIGURATION
# ----------------------------------------------------------------------------
# IMPORTANT SECURITY NOTE:
# This script is intended to run from a dedicated control server, where a trusted
# administrative account (typically root) has password-less SSH access to target
# servers. This design is convenient for automation, but it is high-risk if used
# without strict controls. Follow industry best practices:
#   - Use a dedicated SSH keypair for automation, not personal/root keys.
#   - Restrict the public key to the minimum required servers and commands.
#   - Store the private key on the control server with strict permissions (700 on
#     the directory, 600 on the key file) and avoid sharing it.
#   - Prefer a non-root administrative account when possible; if root is required,
#     restrict its SSH access to this script and the affected hosts only.
#   - Audit logins, monitor the control server, and limit direct shell access.
#   - Validate inputs before running, and ensure the script is reviewed and kept
#     in a version-controlled, restricted-access location.
# The script name is used in usage output and log identification.
readonly SCRIPT_NAME="$(basename "$0")"
# Timestamp ensures each run produces unique backup names and log files.
readonly TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
# Backup suffix appended to original file/folder names during backup operations.
readonly BACKUP_DIR_SUFFIX="_backup_${TIMESTAMP}"
# Log file location stored in the current working directory for easy access.
readonly LOG_FILE="${PWD}/backup_restore_${TIMESTAMP}.log"
# Optional SSH key path for automation. Set SSH_KEY_PATH=/path/to/key before running.
readonly SSH_KEY_PATH="${SSH_KEY_PATH:-}"
SSH_OPTS=(
    -o BatchMode=yes
    -o ConnectTimeout=10
    -o StrictHostKeyChecking=yes
)
if [[ -n "$SSH_KEY_PATH" ]]; then
    if [[ ! -f "$SSH_KEY_PATH" ]]; then
        echo "Error: SSH key file '$SSH_KEY_PATH' not found" >&2
        exit 1
    fi
    if [[ ! -r "$SSH_KEY_PATH" ]]; then
        echo "Error: SSH key file '$SSH_KEY_PATH' is not readable" >&2
        exit 1
    fi
    SSH_OPTS+=( -i "$SSH_KEY_PATH" )
fi

# ----------------------------------------------------------------------------
# UTILITY FUNCTIONS
# ----------------------------------------------------------------------------
# Writes a timestamped message to the log and also prints it to stdout.
log_message() {
    local message="$1"
    touch "$LOG_FILE"
    chmod 600 "$LOG_FILE"
    printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$message" | tee -a "$LOG_FILE"
}

# Removes leading/trailing whitespace from a line read from a text list file.
trim() {
    local value="$1"
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"
    printf '%s' "$value"
}

read_list_entries() {
    local file_path="$1"
    local line

    while IFS= read -r line || [[ -n "$line" ]]; do
        line="$(trim "$line")"
        [[ -z "$line" || "$line" =~ ^# ]] && continue
        printf '%s\n' "$line"
    done < "$file_path"
}

print_usage() {
    cat <<EOF
Usage: $SCRIPT_NAME [--dry-run] <server_list_file> <parent_folder_list_file> <backup|restore>
    $SCRIPT_NAME [--dry-run] <server_list_file> <parent_folder_list_file> create-test-folders-files
    $SCRIPT_NAME -test <server_list_file>
       $SCRIPT_NAME --help
       $SCRIPT_NAME help

Options:
  --dry-run              Show what would happen without making changes
  --help, -h, help      Show this help message
  server_list_file       File containing remote server names/addresses (one per line)
  parent_folder_list_file File containing folder paths to back up or restore (one per line)
  backup|restore         Operation to perform
    -test                  Run full end-to-end test (ssh, create, backup, restore) on servers

Examples:
  $SCRIPT_NAME servers.txt folders.txt backup
  $SCRIPT_NAME servers.txt folders.txt restore
  $SCRIPT_NAME --dry-run servers.txt folders.txt backup
    $SCRIPT_NAME servers.txt folders.txt create-test-folders-files
    $SCRIPT_NAME --dry-run servers.txt folders.txt create-test-folders-files
    $SCRIPT_NAME -test servers.txt
EOF
}

remote_backup_folder() {
    local server="$1"
    local target_path="$2"

    if [[ "$DRY_RUN" == true ]]; then
        log_message "DRY RUN: Would backup '$target_path' on $server"
        return 0
    fi

    ssh "${SSH_OPTS[@]}" "$server" bash -s -- "$target_path" "$BACKUP_DIR_SUFFIX" <<'REMOTE'
set -Eeuo pipefail

target_path="$1"
backup_suffix="$2"

if [[ ! -e "$target_path" ]]; then
    echo "Error: Path '$target_path' does not exist on $(hostname)"
    exit 1
fi

parent_dir="$(dirname -- "$target_path")"
entry_name="$(basename -- "$target_path")"

if [[ -d "$target_path" ]]; then
    backup_path="${parent_dir}/${entry_name}${backup_suffix}"
    printf 'Creating backup: %s\n' "$backup_path"
    cp -a -- "$target_path" "$backup_path"
elif [[ -f "$target_path" ]]; then
    backup_path="${parent_dir}/${entry_name}${backup_suffix}"
    printf 'Creating backup: %s\n' "$backup_path"
    cp -a -- "$target_path" "$backup_path"
else
    echo "Error: Path '$target_path' is neither a file nor a directory on $(hostname)"
    exit 1
fi

printf 'Backup completed successfully on %s\n' "$(hostname)"
REMOTE
}

remote_restore_folder() {
    local server="$1"
    local target_path="$2"

    if [[ "$DRY_RUN" == true ]]; then
        log_message "DRY RUN: Would restore '$target_path' on $server"
        return 0
    fi

    ssh "${SSH_OPTS[@]}" "$server" bash -s -- "$target_path" <<'REMOTE'
set -Eeuo pipefail

target_path="$1"

if [[ -d "$target_path" ]]; then
    parent_dir="$(dirname -- "$target_path")"
    entry_name="$(basename -- "$target_path")"

    shopt -s nullglob
    mapfile -t backup_matches < <(find "$parent_dir" -mindepth 1 -maxdepth 1 -type d -name "${entry_name}_backup_*" -printf '%T@ %p\n' 2>/dev/null | sort -nr | cut -d' ' -f2-)

    if [[ ${#backup_matches[@]} -eq 0 ]]; then
        echo "Error: No backup found for $target_path on $(hostname)"
        exit 1
    fi

    backup_path="${backup_matches[0]}"

    if [[ -d "$target_path" ]]; then
        echo "Removing original folder: $target_path"
        rm -rf -- "$target_path"
    fi

    printf 'Restoring from: %s\n' "$backup_path"
    cp -a -- "$backup_path" "$target_path"
elif [[ -f "$target_path" ]]; then
    parent_dir="$(dirname -- "$target_path")"
    entry_name="$(basename -- "$target_path")"

    shopt -s nullglob
    mapfile -t backup_matches < <(find "$parent_dir" -mindepth 1 -maxdepth 1 -type f -name "${entry_name}_backup_*" -printf '%T@ %p\n' 2>/dev/null | sort -nr | cut -d' ' -f2-)

    if [[ ${#backup_matches[@]} -eq 0 ]]; then
        echo "Error: No backup found for $target_path on $(hostname)"
        exit 1
    fi

    backup_path="${backup_matches[0]}"

    if [[ -e "$target_path" ]]; then
        echo "Removing original file: $target_path"
        rm -f -- "$target_path"
    fi

    printf 'Restoring from: %s\n' "$backup_path"
    cp -a -- "$backup_path" "$target_path"
else
    echo "Error: Path '$target_path' is neither a file nor a directory on $(hostname)"
    exit 1
fi

printf 'Restore completed successfully on %s\n' "$(hostname)"
REMOTE
}

remote_create_test_folders_files() {
    local server="$1"
    local target_path="$2"

    if [[ "$DRY_RUN" == true ]]; then
        log_message "DRY RUN: Would create test folders/files at '$target_path' on $server"
        return 0
    fi

    ssh "${SSH_OPTS[@]}" "$server" bash -s -- "$target_path" <<'REMOTE'
set -Eeuo pipefail

target_path="$1"

if [[ -e "$target_path" ]]; then
    echo "Warning: Path '$target_path' already exists on $(hostname), skipping creation"
    exit 0
fi

parent_dir="$(dirname -- "$target_path")"
mkdir -p -- "$parent_dir"

if [[ "$target_path" == */ ]]; then
    # Create as directory
    mkdir -p -- "$target_path"
    printf 'Created test folder: %s\n' "$target_path"
    touch -- "$target_path/test_file_1.txt"
    echo "Test file 1" > "$target_path/test_file_1.txt"
    touch -- "$target_path/test_file_2.txt"
    echo "Test file 2" > "$target_path/test_file_2.txt"
    mkdir -p -- "$target_path/subfolder"
    echo "Nested test file" > "$target_path/subfolder/nested.txt"
else
    # Create as file
    printf 'Created test file: %s\n' "$target_path"
    echo "Test content for $target_path" > "$target_path"
fi

printf 'Test folders/files created successfully on %s\n' "$(hostname)"
REMOTE
}

remote_run_test_sequence() {
    local server="$1"
    local testbase="/tmp/remote_bkp_test_${TIMESTAMP}"
    ssh "${SSH_OPTS[@]}" "$server" bash -s -- "$testbase" <<'REMOTE'
set -Eeuo pipefail

testbase="$1"
mkdir -p -- "$testbase"
testdir="$testbase/testdir/"
testfile="$testdir/test.txt"

# create test files
mkdir -p -- "$testdir"
echo "hello" > "$testfile"

# perform backup
backup_suffix="_backup_test"
cp -a -- "$testdir" "${testdir%/}${backup_suffix}"

# remove original and restore from backup
rm -rf -- "$testdir"
cp -a -- "${testdir%/}${backup_suffix}" "$testdir"

# verify
if [[ -f "$testfile" ]]; then
    echo "TEST_OK"
    exit 0
else
    echo "TEST_FAIL"
    exit 2
fi
REMOTE
}

# ----------------------------------------------------------------------------
# INPUT VALIDATION
# ----------------------------------------------------------------------------
DRY_RUN=false
POSITIONAL_ARGS=()

while (($#)); do
    case "$1" in
        -h|--help)
            print_usage
            exit 0
            ;;
        help)
            if [[ $# -eq 1 ]]; then
                print_usage
                exit 0
            fi
            POSITIONAL_ARGS+=("$1")
            shift
            ;;
        -n|--dry-run)
            DRY_RUN=true
            shift
            ;;
        --)
            shift
            POSITIONAL_ARGS+=("$@")
            break
            ;;
        -*)
            echo "Error: Unknown option '$1'" >&2
            print_usage
            exit 1
            ;;
        *)
            POSITIONAL_ARGS+=("$1")
            shift
            ;;
    esac
done

if [[ ${#POSITIONAL_ARGS[@]} -ne 3 ]]; then
    print_usage
    exit 1
fi

server_list_file="${POSITIONAL_ARGS[0]}"
folder_list_file="${POSITIONAL_ARGS[1]}"
operation="${POSITIONAL_ARGS[2]}"

if [[ ! -f "$server_list_file" ]]; then
    echo "Error: Server list file '$server_list_file' not found" >&2
    exit 1
fi

if [[ ! -f "$folder_list_file" ]]; then
    echo "Error: Folder list file '$folder_list_file' not found" >&2
    exit 1
fi

if [[ "$operation" != "backup" && "$operation" != "restore" && "$operation" != "create-test-folders-files" ]]; then
    echo "Error: Operation must be 'backup', 'restore', or 'create-test-folders-files'" >&2
    print_usage
    exit 1
fi

# ----------------------------------------------------------------------------
# MAIN EXECUTION
# ----------------------------------------------------------------------------
log_message "Starting ${operation} operation"
log_message "Servers file: $server_list_file"
log_message "Folders file: $folder_list_file"
if [[ "$DRY_RUN" == true ]]; then
    log_message "Dry run enabled: no remote changes will be made"
fi

success_count=0
failure_count=0

mapfile -t servers < <(read_list_entries "$server_list_file")
mapfile -t folders < <(read_list_entries "$folder_list_file")

for server in "${servers[@]}"; do
    for folder in "${folders[@]}"; do
        if [[ "$operation" == "backup" ]]; then
            if remote_backup_folder "$server" "$folder" >> "$LOG_FILE" 2>&1; then
                ((success_count += 1))
                log_message "Backup successful for $server:$folder"
            else
                ((failure_count += 1))
                log_message "Backup failed for $server:$folder"
            fi
        else
            if remote_restore_folder "$server" "$folder" >> "$LOG_FILE" 2>&1; then
                ((success_count += 1))
                log_message "Restore successful for $server:$folder"
            else
                ((failure_count += 1))
                log_message "Restore failed for $server:$folder"
            fi
        fi
    done
done

log_message "========================================"
log_message "${operation^} operation completed"
log_message "Successful operations: $success_count"
log_message "Failed operations: $failure_count"
log_message "Log file: $LOG_FILE"







