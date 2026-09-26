# Remote Backup & Restore Script

Automated backup and restore utility for remote servers over SSH. Backs up or restores configured directories and files on target servers, with support for compression, dry-run simulation, and automated test verification.

## Features

- **Multi-Server & Multi-Folder**: Batch execute backups and restores across multiple servers and directory paths.
- **Compression & Cleanup**: Optional `--cleanup-backup` compresses backups to `.tar.gz` and frees space.
- **Dry-Run Mode**: Validate actions without modifying files (`--dry-run`).
- **End-to-End Testing**: Built-in verification (`-test` and `create-test-folders-files`).
- **Web UI Dashboard**: Zero-dependency, lightweight web UI to trigger operations, monitor live terminal logs, and browse history.

---

## Web UI

Start the built-in web dashboard:

```bash
# Using the script flag
./remote-bkp-restore.sh --ui
# or specify a custom port
./remote-bkp-restore.sh --ui 9000

# Or launch directly with Python 3
python3 web_ui.py
```

Then open [http://localhost:8080](http://localhost:8080) in your web browser.

---

## CLI Usage

```bash
./remote-bkp-restore.sh [options] <server_list_file> <parent_folder_list_file> <operation>
```

### Operations
- `backup`: Backs up files/folders with timestamped suffixes.
- `restore`: Restores from the most recent backup.
- `create-test-folders-files`: Generates sample folders/files on remote servers for testing.
- `-test`: Runs an automated SSH backup & restore test sequence.

### Options
- `--ui`, `--web [port]`: Launch the local Web UI dashboard (default port 8080).
- `--dry-run`: Show what would happen without making any changes on the remote hosts.
- `--cleanup-backup`: Compress backup to `.tar.gz` and delete the uncompressed copy.
- `--help`: Display usage information.

### Examples

```bash
# Perform a dry run backup
./remote-bkp-restore.sh --dry-run servers.txt folders.txt backup

# Backup and compress
./remote-bkp-restore.sh --cleanup-backup servers.txt folders.txt backup

# Restore latest backup
./remote-bkp-restore.sh servers.txt folders.txt restore

# Run SSH verification test
./remote-bkp-restore.sh -test servers.txt
```
