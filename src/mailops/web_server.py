import http.server
import socketserver
import json
import logging
import os
from pathlib import Path
from typing import Any

from .config import load_config, save_config, AppConfig, PrintRule, MatchCriteria

logger = logging.getLogger(__name__)

PORT = 8000
WEB_ROOT = Path(__file__).parent / "web"

# Embedded HTML to avoid file management for now, or we can write it to a file.
# Let's write a simple HTML file.

class MailOpsRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(self.get_html().encode("utf-8"))
            return

        if self.path == "/api/config":
            cfg = load_config()
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(cfg.to_dict()).encode("utf-8"))
            return
            
        self.send_error(404)

    def do_POST(self):
        if self.path == "/api/config":
            length = int(self.headers.get("content-length", 0))
            data = self.rfile.read(length)
            try:
                payload = json.loads(data)
                # Validation happens in from_dict
                cfg = AppConfig.from_dict(payload)
                save_config(cfg)
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status": "ok"}')
            except Exception as e:
                self.send_error(400, f"Invalid config: {e}")
            return
            
        if self.path == "/api/preview":
            length = int(self.headers.get("content-length", 0))
            data = self.rfile.read(length)
            try:
                payload = json.loads(data)
                # payload is a PrintRule dict
                rule = PrintRule.from_dict(payload)
                
                from .manager import Manager
                mgr = Manager()
                matches = mgr.preview_rule(rule)
                
                # return simplified list
                res_data = [
                    {
                        "message_id": m.message_id, 
                        "subject": m.subject, 
                        "from": m.from_email,
                        "date": m.date
                    } 
                    for m in matches
                ]
                
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(res_data).encode("utf-8"))
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.send_error(400, f"Error: {e}")
            return

        if self.path == "/api/printers":
            try:
                from .actions.print_action import get_available_printers
                printers = get_available_printers()
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(printers).encode("utf-8"))
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.send_response(500)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return
            
        self.send_error(404)
        
    def get_html(self) -> str:
        return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MailOps Dashboard</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; padding: 20px; max-width: 800px; margin: 0 auto; }
        h1 { border-bottom: 2px solid #eee; padding-bottom: 10px; }
        .rule { border: 1px solid #ddd; padding: 15px; margin-bottom: 15px; border-radius: 5px; background: #fafafa; }
        .rule h3 { margin-top: 0; }
        label { display: block; margin-top: 10px; font-weight: bold; }
        input[type="text"], select { width: 100%; padding: 8px; margin-top: 5px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }
        .btn { background: #007bff; color: white; padding: 10px 15px; border: none; border-radius: 4px; cursor: pointer; }
        .btn:hover { background: #0056b3; }
        .btn-test { background: #6c757d; margin-right: 5px; }
        .actions { margin-top: 20px; text-align: right; }
        .modal { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); display: flex; justify-content: center; align-items: center; }
        .modal-content { background: white; padding: 20px; border-radius: 5px; width: 80%; max-height: 80%; overflow-y: auto; }
        .close { float: right; cursor: pointer; font-size: 20px; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
    </style>
</head>
<body>
    <h1>MailOps Configuration</h1>
    <div id="app">
        <div v-if="loading">Loading...</div>
        <div v-else>
            <div class="form-group">
                <label>Printer Name</label>
                <div style="display:flex; gap:10px;">
                    <select v-model="config.printer_name" v-if="printers.length > 0">
                        <option value="">(Select Printer)</option>
                        <option v-for="p in printers" :value="p">{{ p }}</option>
                    </select>
                    <input type="text" v-model="config.printer_name" v-else placeholder="Printer system name (e.g. HP_OfficeJet)">
                    
                    <button class="btn btn-test" @click="fetchPrinters" title="Refresh Printers">&#x21bb;</button>
                </div>
            </div>
            
            <h2>Rules</h2>
            <div v-for="(rule, idx) in config.print_rules" :key="idx" class="rule">
                <div style="display:flex; justify-content:space-between">
                    <h3>Rule {{ idx + 1 }}</h3>
                    <div>
                        <button class="btn btn-test" @click="testRule(rule)">Test</button>
                        <button @click="removeRule(idx)" style="color:red; background:none; border:none; cursor:pointer;">Remove</button>
                    </div>
                </div>
                
                <label>Name</label>
                <input type="text" v-model="rule.name">
                
                <label>Action</label>
                <select v-model="rule.action">
                    <option value="print">Print</option>
                    <option value="archive">Archive</option>
                    <option value="delete">Delete</option>
                    <option value="clickup">ClickUp</option>
                </select>
                
                <label>From Exact</label>
                <input type="text" v-model="rule.match.from_exact" placeholder="user@example.com">
                
                <label>From Domain</label>
                <input type="text" v-model="rule.match.from_domain" placeholder="example.com">
                
                <label>Subject Contains</label>
                <input type="text" v-model="rule.match.subject_contains" placeholder="Invoice">
                
                <label>Subject Excludes</label>
                <input type="text" v-model="rule.match.subject_excludes" placeholder="Sale">
            </div>
            
            <button class="btn" @click="addRule">+ Add Rule</button>
            
            <div class="actions">
                <button class="btn" @click="saveConfig">Save Changes</button>
            </div>
            <p v-if="msg" :style="{color: msgColor}">{{ msg }}</p>
        
            <!-- Test Modal -->
            <div v-if="showModal" class="modal">
                <div class="modal-content">
                    <span class="close" @click="showModal = false">&times;</span>
                    <h2>Preview Results</h2>
                    <p>Found {{ testResults.length }} matching emails from the last 7 days.</p>
                    <table v-if="testResults.length > 0">
                        <thead><tr><th>Date</th><th>From</th><th>Subject</th></tr></thead>
                        <tbody>
                            <tr v-for="r in testResults" :key="r.message_id">
                                <td>{{ r.date }}</td>
                                <td>{{ r.from }}</td>
                                <td>{{ r.subject }}</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>

    <script src="https://unpkg.com/vue@3/dist/vue.global.js"></script>
    <script>
        const { createApp } = Vue

        createApp({
            data() {
                return {
                    config: { printer_name: "", print_rules: [] },
                    printers: [],
                    loading: true,
                    msg: "",
                    msgColor: "green",
                    showModal: false,
                    testResults: []
                }
            },
            mounted() {
                this.fetchPrinters();
                fetch('/api/config')
                    .then(res => res.json())
                    .then(data => {
                        this.config = data;
                        this.loading = false;
                    })
                    .catch(err => console.error(err));
            },
            methods: {
                fetchPrinters() {
                    const btn = document.querySelector('.btn-test[title="Refresh Printers"]');
                    if(btn) btn.textContent = "...";
                    
                    fetch('/api/printers')
                        .then(res => res.json())
                        .then(data => {
                            this.printers = data;
                            if (data.length === 0) {
                                alert("No printers found on the system (via lpstat).");
                            }
                        })
                        .catch(err => {
                            console.error(err);
                            alert("Error fetching printers: " + err);
                        })
                        .finally(() => {
                           if(btn) btn.innerHTML = "&#x21bb;";
                        });
                },
                addRule() {
                    this.config.print_rules.push({
                        name: "New Rule",
                        action: "archive",
                        match: {}
                    });
                },
                removeRule(idx) {
                    this.config.print_rules.splice(idx, 1);
                },
                saveConfig() {
                    this.msg = "Saving...";
                    fetch('/api/config', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify(this.config)
                    })
                    .then(res => {
                        if (res.ok) {
                            this.msg = "Saved successfully!";
                            this.msgColor = "green";
                        } else {
                            this.msg = "Error saving config";
                            this.msgColor = "red";
                        }
                    })
                    .catch(err => {
                        this.msg = "Network error";
                        this.msgColor = "red";
                    });
                },
                testRule(rule) {
                    this.msg = "Testing rule...";
                    this.msgColor = "blue";
                    
                    fetch('/api/preview', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify(rule)
                    })
                    .then(res => res.json())
                    .then(data => {
                        this.testResults = data;
                        this.showModal = true;
                        this.msg = "";
                    })
                    .catch(err => {
                        console.error(err);
                        this.msg = "Error testing rule";
                        this.msgColor = "red";
                    });
                }
            }
        }).mount('#app')
    </script>
</body>
</html>
        """

def run_server(port: int = PORT):
    print(f"Starting MailOps Dashboard at http://localhost:{port}")
    try:
        with socketserver.TCPServer(("", port), MailOpsRequestHandler) as httpd:
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                pass
    except OSError as e:
        print(f"Error starting server on port {port}: {e}")
