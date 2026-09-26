#!/usr/bin/env python3
"""
Simple Web UI for remote-bkp-restore.sh
Provides a web interface to configure, execute, and monitor remote backup and restore operations.
Requires only standard library Python 3.
"""

import http.server
import json
import os
import re
import socketserver
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse

BASE_DIR = Path(__file__).resolve().parent
SCRIPT_PATH = BASE_DIR / "remote-bkp-restore.sh"

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Remote Backup & Restore UI</title>
  <style>
    :root {
      --bg: #0f172a;
      --card-bg: #1e293b;
      --card-border: #334155;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --primary: #3b82f6;
      --primary-hover: #2563eb;
      --success: #10b981;
      --warning: #f59e0b;
      --danger: #ef4444;
      --term-bg: #030712;
      --term-text: #22c55e;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background-color: var(--bg);
      color: var(--text);
      line-height: 1.5;
      padding: 24px;
    }

    .container {
      max-width: 1000px;
      margin: 0 auto;
    }

    header {
      margin-bottom: 24px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid var(--card-border);
      padding-bottom: 16px;
    }

    .title-group h1 {
      font-size: 1.6rem;
      font-weight: 700;
      color: #fff;
    }

    .title-group p {
      font-size: 0.9rem;
      color: var(--text-muted);
    }

    .badge {
      display: inline-block;
      font-size: 0.75rem;
      font-weight: 600;
      padding: 4px 8px;
      border-radius: 9999px;
      background: #334155;
      color: #93c5fd;
    }

    .grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 20px;
    }

    @media (max-width: 768px) {
      .grid { grid-template-columns: 1fr; }
    }

    .card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 8px;
      padding: 20px;
      margin-bottom: 20px;
    }

    .card-title {
      font-size: 1.1rem;
      font-weight: 600;
      margin-bottom: 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    .form-group {
      margin-bottom: 16px;
    }

    label {
      display: block;
      font-size: 0.85rem;
      font-weight: 600;
      margin-bottom: 6px;
      color: #e2e8f0;
    }

    .help-text {
      font-size: 0.75rem;
      color: var(--text-muted);
      margin-top: 4px;
    }

    select, input[type="text"], textarea {
      width: 100%;
      background: #0f172a;
      border: 1px solid var(--card-border);
      border-radius: 6px;
      color: var(--text);
      padding: 10px 12px;
      font-size: 0.9rem;
      outline: none;
      transition: border-color 0.15s ease;
    }

    select:focus, input[type="text"]:focus, textarea:focus {
      border-color: var(--primary);
    }

    textarea {
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      resize: vertical;
      min-height: 80px;
    }

    .checkbox-group {
      display: flex;
      gap: 16px;
      margin-top: 8px;
      flex-wrap: wrap;
    }

    .checkbox-item {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 0.85rem;
      cursor: pointer;
    }

    .checkbox-item input {
      accent-color: var(--primary);
      width: 16px;
      height: 16px;
      cursor: pointer;
    }

    .btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 10px 20px;
      font-size: 0.95rem;
      font-weight: 600;
      border-radius: 6px;
      border: none;
      cursor: pointer;
      transition: all 0.15s ease;
      width: 100%;
      gap: 8px;
    }

    .btn-primary {
      background: var(--primary);
      color: #fff;
    }
    .btn-primary:hover:not(:disabled) {
      background: var(--primary-hover);
    }
    .btn:disabled {
      opacity: 0.6;
      cursor: not-allowed;
    }

    .terminal-container {
      background: var(--term-bg);
      border: 1px solid var(--card-border);
      border-radius: 8px;
      overflow: hidden;
    }

    .terminal-header {
      background: #111827;
      padding: 8px 12px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid #1f2937;
      font-size: 0.75rem;
      color: var(--text-muted);
    }

    .terminal-dots {
      display: flex;
      gap: 6px;
    }

    .dot {
      width: 10px;
      height: 10px;
      border-radius: 50%;
    }
    .dot-red { background: #ef4444; }
    .dot-yellow { background: #f59e0b; }
    .dot-green { background: #10b981; }

    pre#terminalOutput {
      padding: 16px;
      color: var(--term-text);
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.85rem;
      max-height: 420px;
      overflow-y: auto;
      white-space: pre-wrap;
      word-break: break-all;
    }

    .status-tag {
      font-size: 0.75rem;
      padding: 2px 8px;
      border-radius: 4px;
      font-weight: 600;
    }
    .status-idle { background: #374151; color: #9ca3af; }
    .status-running { background: #1e3a8a; color: #93c5fd; }
    .status-success { background: #064e3b; color: #6ee7b7; }
    .status-error { background: #7f1d1d; color: #fca5a5; }

    .logs-list {
      list-style: none;
      max-height: 180px;
      overflow-y: auto;
      margin-top: 8px;
    }

    .log-item {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 6px 8px;
      font-size: 0.8rem;
      border-bottom: 1px solid #334155;
      font-family: ui-monospace, SFMono-Regular, monospace;
    }

    .log-item:hover {
      background: #334155;
      border-radius: 4px;
    }

    .log-item a {
      color: #93c5fd;
      text-decoration: none;
      cursor: pointer;
    }

    .log-item a:hover {
      text-decoration: underline;
    }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="title-group">
        <h1>Remote Backup & Restore UI</h1>
        <p>Interactive web control for remote-bkp-restore.sh</p>
      </div>
      <div>
        <span class="badge">Branch: ui-enhancement</span>
      </div>
    </header>

    <div class="grid">
      <!-- Left Column: Controls -->
      <div>
        <div class="card">
          <div class="card-title">
            <span>⚙️ Configuration</span>
          </div>

          <form id="actionForm">
            <div class="form-group">
              <label for="operation">Operation</label>
              <select id="operation" name="operation" onchange="toggleFolderInput()">
                <option value="backup">📦 Backup</option>
                <option value="restore">🔄 Restore</option>
                <option value="create-test-folders-files">🧪 Create Test Folders / Files</option>
                <option value="-test">⚡ SSH End-to-End Test (-test)</option>
              </select>
              <div class="help-text">Choose the backup/restore task to perform.</div>
            </div>

            <div class="form-group">
              <label>Options</label>
              <div class="checkbox-group">
                <label class="checkbox-item">
                  <input type="checkbox" id="dry_run" name="dry_run">
                  <span>Dry Run (--dry-run)</span>
                </label>
                <label class="checkbox-item" id="cleanupContainer">
                  <input type="checkbox" id="cleanup_backup" name="cleanup_backup">
                  <span>Compress & Cleanup (--cleanup-backup)</span>
                </label>
              </div>
            </div>

            <div class="form-group">
              <label for="servers">Server List (one host per line)</label>
              <textarea id="servers" name="servers" rows="3" placeholder="192.168.1.10&#10;web01.example.com"></textarea>
              <div class="help-text">Remote hostnames or IP addresses to connect via SSH.</div>
            </div>

            <div class="form-group" id="foldersGroup">
              <label for="folders">Target Folders / Files (one path per line)</label>
              <textarea id="folders" name="folders" rows="3" placeholder="/var/www/html/&#10;/etc/nginx/nginx.conf"></textarea>
              <div class="help-text">Directories ending with / will be backed up as folders.</div>
            </div>

            <div class="form-group">
              <label for="ssh_key">SSH Private Key Path (optional)</label>
              <input type="text" id="ssh_key" name="ssh_key" placeholder="e.g. /Users/username/.ssh/id_rsa">
              <div class="help-text">Leave blank to use default SSH agent or ~/.ssh/ configuration.</div>
            </div>

            <button type="submit" id="runBtn" class="btn btn-primary">
              <span id="btnIcon">▶</span>
              <span id="btnText">Execute Operation</span>
            </button>
          </form>
        </div>

        <div class="card">
          <div class="card-title">
            <span>📋 Recent Log Files</span>
            <button onclick="loadLogs()" style="background:none; border:none; color:var(--text-muted); cursor:pointer; font-size:0.8rem;">🔄 Refresh</button>
          </div>
          <ul id="logsList" class="logs-list">
            <li style="color:var(--text-muted); font-size:0.8rem;">Loading log files...</li>
          </ul>
        </div>
      </div>

      <!-- Right Column: Terminal Output -->
      <div>
        <div class="card" style="height: 100%; display: flex; flex-direction: column;">
          <div class="card-title">
            <span>🖥️ Execution Output</span>
            <span id="statusTag" class="status-tag status-idle">IDLE</span>
          </div>

          <div class="terminal-container" style="flex: 1; display: flex; flex-direction: column;">
            <div class="terminal-header">
              <div class="terminal-dots">
                <div class="dot dot-red"></div>
                <div class="dot dot-yellow"></div>
                <div class="dot dot-green"></div>
              </div>
              <span id="termHeaderInfo">Ready</span>
              <button onclick="copyTerminal()" style="background:none; border:none; color:var(--text-muted); cursor:pointer; font-size:0.75rem;">📋 Copy</button>
            </div>
            <pre id="terminalOutput" style="flex:1;">Welcome to Remote Backup & Restore Web UI.
Select options on the left and click "Execute Operation".
Output and progress logs will appear here in real time.</pre>
          </div>
        </div>
      </div>
    </div>
  </div>

  <script>
    function toggleFolderInput() {
      const op = document.getElementById('operation').value;
      const foldersGroup = document.getElementById('foldersGroup');
      const cleanupContainer = document.getElementById('cleanupContainer');
      
      if (op === '-test') {
        foldersGroup.style.display = 'none';
        cleanupContainer.style.display = 'none';
      } else {
        foldersGroup.style.display = 'block';
        cleanupContainer.style.display = (op === 'backup') ? 'flex' : 'none';
      }
    }

    function setStatus(status, text) {
      const tag = document.getElementById('statusTag');
      tag.className = 'status-tag status-' + status;
      tag.textContent = text || status.toUpperCase();
    }

    function copyTerminal() {
      const content = document.getElementById('terminalOutput').textContent;
      navigator.clipboard.writeText(content).then(() => {
        alert('Terminal output copied to clipboard');
      });
    }

    async function loadLogs() {
      try {
        const res = await fetch('/api/logs');
        const data = await res.json();
        const list = document.getElementById('logsList');
        list.innerHTML = '';
        if (!data.logs || data.logs.length === 0) {
          list.innerHTML = '<li style="color:var(--text-muted); font-size:0.8rem;">No log files found.</li>';
          return;
        }
        data.logs.forEach(log => {
          const li = document.createElement('li');
          li.className = 'log-item';
          li.innerHTML = `
            <a onclick="viewLog('${log.name}')">${log.name}</a>
            <span style="color:var(--text-muted)">${log.size}</span>
          `;
          list.appendChild(li);
        });
      } catch (err) {
        console.error('Failed to load logs', err);
      }
    }

    async function viewLog(filename) {
      try {
        setStatus('running', 'READING LOG');
        const res = await fetch('/api/log?file=' + encodeURIComponent(filename));
        const data = await res.json();
        document.getElementById('terminalOutput').textContent = data.content;
        document.getElementById('termHeaderInfo').textContent = filename;
        setStatus('idle', 'LOG VIEW');
      } catch (err) {
        alert('Failed to read log file: ' + err);
      }
    }

    document.getElementById('actionForm').addEventListener('submit', async (e) => {
      e.preventDefault();

      const servers = document.getElementById('servers').value.trim();
      const folders = document.getElementById('folders').value.trim();
      const operation = document.getElementById('operation').value;
      const dry_run = document.getElementById('dry_run').checked;
      const cleanup_backup = document.getElementById('cleanup_backup').checked;
      const ssh_key = document.getElementById('ssh_key').value.trim();

      if (!servers) {
        alert('Please specify at least one server.');
        return;
      }

      if (operation !== '-test' && !folders) {
        alert('Please specify at least one target folder or file path.');
        return;
      }

      const runBtn = document.getElementById('runBtn');
      const btnText = document.getElementById('btnText');
      const btnIcon = document.getElementById('btnIcon');
      const term = document.getElementById('terminalOutput');

      runBtn.disabled = true;
      btnIcon.textContent = '⏳';
      btnText.textContent = 'Running...';
      setStatus('running', 'RUNNING');
      document.getElementById('termHeaderInfo').textContent = 'Executing ' + operation + '...';

      term.textContent = `>>> Executing operation: ${operation}\\n`;
      term.textContent += `>>> Servers: ${servers.split('\\n').filter(Boolean).join(', ')}\\n`;
      if (operation !== '-test') {
        term.textContent += `>>> Target paths: ${folders.split('\\n').filter(Boolean).join(', ')}\\n`;
      }
      term.textContent += `>>> Dry run: ${dry_run} | Cleanup: ${cleanup_backup}\\n`;
      term.textContent += `--------------------------------------------------------\\n`;

      try {
        const res = await fetch('/api/run', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            operation,
            servers,
            folders,
            dry_run,
            cleanup_backup,
            ssh_key
          })
        });

        const result = await res.json();
        term.textContent += result.output || '(No output returned)';
        term.textContent += `\\n--------------------------------------------------------\\n`;
        term.textContent += `>>> Process exited with code ${result.exit_code}.\\n`;

        if (result.exit_code === 0) {
          setStatus('success', 'SUCCESS');
        } else {
          setStatus('error', 'FAILED (Code ' + result.exit_code + ')');
        }
        loadLogs();
      } catch (err) {
        term.textContent += `\\n[Client Error]: ${err.message}\\n`;
        setStatus('error', 'ERROR');
      } finally {
        runBtn.disabled = false;
        btnIcon.textContent = '▶';
        btnText.textContent = 'Execute Operation';
      }
    });

    // Initial setup
    toggleFolderInput();
    loadLogs();
  </script>
</body>
</html>
"""


class BackupUIHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress default noisy console logging, or format cleanly
        sys.stderr.write(f"[{self.log_date_time_string()}] {format % args}\n")

    def send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            body = HTML_TEMPLATE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/api/logs":
            logs = []
            for file in sorted(BASE_DIR.glob("backup_restore_*.log"), key=os.path.getmtime, reverse=True):
                size_kb = max(1, round(file.stat().st_size / 1024))
                logs.append({"name": file.name, "size": f"{size_kb} KB"})
            self.send_json({"logs": logs})
            return

        if path == "/api/log":
            params = parse_qs(parsed.query)
            filename = params.get("file", [""])[0]
            # Prevent directory traversal
            clean_name = os.path.basename(filename)
            target = BASE_DIR / clean_name
            if not target.exists() or not clean_name.startswith("backup_restore_"):
                self.send_json({"error": "Log file not found"}, status=404)
                return
            try:
                content = target.read_text(encoding="utf-8", errors="replace")
                self.send_json({"name": clean_name, "content": content})
            except Exception as e:
                self.send_json({"error": str(e)}, status=500)
            return

        self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/run":
            self.send_error(404, "Not Found")
            return

        try:
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            payload = json.loads(post_data.decode("utf-8"))

            operation = payload.get("operation", "backup")
            servers_text = payload.get("servers", "").strip()
            folders_text = payload.get("folders", "").strip()
            dry_run = bool(payload.get("dry_run", False))
            cleanup_backup = bool(payload.get("cleanup_backup", False))
            ssh_key = payload.get("ssh_key", "").strip()

            # Input validation
            if not servers_text:
                self.send_json({"exit_code": 1, "output": "Error: No servers specified"}, status=400)
                return

            if operation != "-test" and not folders_text:
                self.send_json({"exit_code": 1, "output": "Error: No target folders/files specified"}, status=400)
                return

            # Write temporary server and folder files
            with tempfile.NamedTemporaryFile("w+", delete=False, prefix="servers_", suffix=".txt") as sf:
                sf.write(servers_text + "\n")
                servers_file = sf.name

            folders_file = None
            if operation != "-test":
                with tempfile.NamedTemporaryFile("w+", delete=False, prefix="folders_", suffix=".txt") as ff:
                    ff.write(folders_text + "\n")
                    folders_file = ff.name

            # Build command arguments
            cmd = ["bash", str(SCRIPT_PATH)]
            if dry_run:
                cmd.append("--dry-run")
            if cleanup_backup and operation == "backup":
                cmd.append("--cleanup-backup")

            if operation == "-test":
                cmd.extend(["-test", servers_file])
            else:
                cmd.extend([servers_file, folders_file, operation])

            env = os.environ.copy()
            if ssh_key:
                env["SSH_KEY_PATH"] = os.path.expanduser(ssh_key)

            proc = subprocess.run(
                cmd,
                cwd=str(BASE_DIR),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )

            # Cleanup temporary files
            try:
                os.remove(servers_file)
                if folders_file and os.path.exists(folders_file):
                    os.remove(folders_file)
            except OSError:
                pass

            self.send_json({
                "exit_code": proc.returncode,
                "output": proc.stdout,
            })

        except Exception as e:
            self.send_json({"exit_code": -1, "output": f"Internal Server Error: {str(e)}"}, status=500)


def run_server(port=8080):
    server_address = ("127.0.0.1", port)
    # Allow port reuse
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(server_address, BackupUIHandler) as httpd:
        print(f"==================================================")
        print(f" Remote Backup & Restore Web UI running at:")
        print(f" http://localhost:{port}")
        print(f" Press Ctrl+C to stop.")
        print(f"==================================================")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server.")


if __name__ == "__main__":
    port = 8080
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"Usage: {sys.argv[0]} [port]")
            sys.exit(1)
    run_server(port)
