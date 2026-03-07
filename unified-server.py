#!/usr/bin/env python3
"""
Unified server that serves static files and proxies API requests.
Runs on port 8317 as main entry point, proxies to cliproxy on port 8316.
"""

import http.server
import socketserver
import urllib.request
import urllib.error
import subprocess
import signal
import sys
import os
import time
import atexit
import re
import tempfile
import json

# Configuration
PUBLIC_PORT = 8317      # Main entry point
BACKEND_PORT = 8316     # cliproxy-server runs here

# Auto-detect paths
HOME = os.path.expanduser("~")
CLI_PROXY_DIR = os.path.join(HOME, ".cli-proxy-api")
STATIC_DIR = os.path.join(CLI_PROXY_DIR, "static")
BIN_DIR = os.path.join(HOME, "bin")
CLIPROXY_PATH = os.path.join(BIN_DIR, "cliproxyapi-plus")
CONFIG_PATH = os.path.join(CLI_PROXY_DIR, "config.yaml")

cliproxy_process = None
_temp_config = None

def _create_backend_config():
    """Create a temporary config with the backend port."""
    global _temp_config
    try:
        with open(CONFIG_PATH, 'r') as f:
            config_text = f.read()
        # Replace port value in YAML
        config_text = re.sub(r'^port:\s*\d+', f'port: {BACKEND_PORT}', config_text, count=1, flags=re.MULTILINE)
        _temp_config = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', prefix='cliproxy-backend-', delete=False)
        _temp_config.write(config_text)
        _temp_config.close()
        return _temp_config.name
    except Exception as e:
        print(f"   Failed to create backend config: {e}")
        return CONFIG_PATH

def start_cliproxy():
    """Start cliproxy-server on backend port"""
    global cliproxy_process

    backend_config = _create_backend_config()

    try:
        cliproxy_process = subprocess.Popen(
            [CLIPROXY_PATH, '-config', backend_config],
        )
        print(f"   Started cliproxyapi-plus on port {BACKEND_PORT} (PID: {cliproxy_process.pid})")
        time.sleep(2)  # Wait for startup
        return True
    except Exception as e:
        print(f"   Failed to start cliproxy: {e}")
        return False

def stop_cliproxy():
    """Stop cliproxy-server"""
    global cliproxy_process, _temp_config
    if cliproxy_process:
        print("\n   Stopping cliproxy-server...")
        cliproxy_process.terminate()
        try:
            cliproxy_process.wait(timeout=5)
        except:
            cliproxy_process.kill()
        cliproxy_process = None
    if _temp_config and os.path.exists(_temp_config.name):
        os.unlink(_temp_config.name)
        _temp_config = None

class UnifiedHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def log_message(self, format, *args):
        # Quieter logging
        if '/v0/' in str(args) or '/v1/' in str(args):
            return  # Skip API logging
        super().log_message(format, *args)

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, PUT, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Management-Key, Authorization')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        # Lightweight health check endpoint
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
            return
        # API requests -> proxy to backend
        if self.path.startswith('/v0/') or self.path.startswith('/v1/'):
            self.proxy_request('GET')
        # System Management
        elif self.path.startswith('/api/system/'):
            self.handle_system_api('GET')
        # Root -> redirect to dashboard
        elif self.path == '/':
            self.send_response(302)
            self.send_header('Location', '/dashboard.html')
            self.end_headers()
        else:
            # Static files
            super().do_GET()

    def do_POST(self):
        if self.path.startswith('/v0/') or self.path.startswith('/v1/'):
            self.proxy_request('POST')
        elif self.path.startswith('/api/system/'):
            self.handle_system_api('POST')
        else:
            self.send_error(404)

    def do_DELETE(self):
        if self.path.startswith('/v0/') or self.path.startswith('/v1/'):
            self.proxy_request('DELETE')
        else:
            self.send_error(404)

    def do_PUT(self):
        if self.path.startswith('/v0/') or self.path.startswith('/v1/'):
            self.proxy_request('PUT')
        else:
            self.send_error(404)

    def do_PATCH(self):
        if self.path.startswith('/v0/') or self.path.startswith('/v1/'):
            self.proxy_request('PATCH')
        else:
            self.send_error(404)

    def handle_system_api(self, method):
        # Extremely basic remote management endpoints for the UI
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        
        if self.path == '/api/system/restart' and method == 'POST':
            print("   [System API] Restarting cliproxy...")
            stop_cliproxy()
            time.sleep(1)
            start_cliproxy()
            self.wfile.write(b'{"status":"restarted"}')
        elif self.path == '/api/system/stop' and method == 'POST':
            print("   [System API] Stopping cliproxy...")
            stop_cliproxy()
            self.wfile.write(b'{"status":"stopped"}')
        elif self.path == '/api/system/info' and method == 'GET':
            status = "online" if cliproxy_process else "offline"
            pid = cliproxy_process.pid if cliproxy_process else None
            out = f'{{"status":"{status}", "pid":{pid or "null"}}}'
            self.wfile.write(out.encode('utf-8'))
        elif self.path == '/api/system/add-provider' and method == 'POST':
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                name = data.get('name', '').strip()
                base_url = data.get('base_url', '').strip()
                api_key = data.get('api_key', '').strip()
                
                if not name or not base_url or not api_key:
                    self.send_error(400, "Missing required fields")
                    return
                    
                config_path = os.path.expanduser('~/.cli-proxy-api/config.yaml')
                
                # Check if provider already exists
                with open(config_path, 'r') as f:
                    content = f.read()
                    if f'- name: "{name}"' in content or f"- name: {name}" in content:
                        self.send_error(409, "Provider name already exists")
                        return

                # Attempt to fetch models
                models_yaml = ""
                chosen_base_url = base_url
                try:
                    m_list = []
                    # Try direct /models
                    urls_to_try = [base_url.rstrip('/') + '/models']
                    if '/v1' not in base_url:
                        urls_to_try.append(base_url.rstrip('/') + '/v1/models')
                        
                    for models_url in urls_to_try:
                        try:
                            m_req = urllib.request.Request(models_url, headers={'Authorization': f'Bearer {api_key}'})
                            with urllib.request.urlopen(m_req, timeout=5) as m_resp:
                                m_data = json.loads(m_resp.read().decode('utf-8'))
                                m_list = m_data.get('data', [])
                                if m_list: 
                                    if '/v1/models' in models_url:
                                        chosen_base_url = base_url.rstrip('/') + '/v1'
                                    break
                        except: continue

                    if m_list:
                        models_yaml = "    models:\n"
                        for m in m_list:
                            m_id = m.get('id')
                            if m_id:
                                models_yaml += f'      - name: "{m_id}"\n        alias: "{m_id}"\n'
                except Exception as me:
                    print(f"   [System API] Could not fetch models for {name}: {me}")

                # Append to file
                append_str = f"""
  - name: "{name}"
    base-url: "{chosen_base_url}"
    api-key-entries:
      - api-key: "{api_key}"
{models_yaml}"""
                with open(config_path, 'a') as f:
                    if "openai-compatibility:" not in content:
                        f.write("\nopenai-compatibility:")
                    f.write(append_str)
                    
                self.wfile.write(b'{"status":"success"}')
            except Exception as e:
                self.send_error(500, str(e))
        elif self.path == '/api/system/raw-config' and method == 'GET':
            try:
                config_path = os.path.expanduser('~/.cli-proxy-api/config.yaml')
                if os.path.exists(config_path):
                    with open(config_path, 'r') as f:
                        content = f.read()
                    self.wfile.write(json.dumps({"yaml": content}).encode('utf-8'))
                else:
                    self.send_error(404, "Config not found")
            except Exception as e:
                self.send_error(500, str(e))
        elif self.path == '/api/system/raw-config' and method == 'POST':
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                yaml_content = data.get('yaml', '')
                if not yaml_content:
                    self.send_error(400, "YAML content is empty")
                    return
                    
                config_path = os.path.expanduser('~/.cli-proxy-api/config.yaml')
                with open(config_path, 'w') as f:
                    f.write(yaml_content)
                
                # Auto restart to apply changes
                stop_cliproxy()
                time.sleep(1)
                start_cliproxy()
                
                self.wfile.write(b'{"status":"saved_and_restarted"}')
            except Exception as e:
                self.send_error(500, str(e))
        else:
            self.send_error(404)

    def proxy_request(self, method):
        try:
            target_url = f'http://localhost:{BACKEND_PORT}{self.path}'
            print(f"   [Proxy] {method} {self.path} -> {target_url}")

            # Copy headers
            headers = {}
            # Standard headers
            for key in ['X-Management-Key', 'Authorization', 'Content-Type', 'Accept']:
                val = self.headers.get(key)
                if val:
                    headers[key] = val

            # Anthropic specific headers for Claude Code
            for key in ['x-api-key', 'anthropic-version', 'anthropic-beta']:
                val = self.headers.get(key)
                if val:
                    headers[key] = val
                    print(f"   [Header] {key}: {val[:5]}...")
            
            # Map x-api-key to Authorization (ALWAYS prioritize x-api-key for proxying)
            x_api_key = self.headers.get('x-api-key')
            if x_api_key:
                headers['Authorization'] = f"Bearer {x_api_key}"
                print(f"   [Mapping] x-api-key -> Authorization")

            # Get body for POST/PUT/DELETE
            data = None
            if method in ['POST', 'PUT', 'DELETE'] and self.headers.get('Content-Length'):
                content_length = int(self.headers.get('Content-Length'))
                data = self.rfile.read(content_length)
                print(f"   [Body] Size: {content_length}")

            req = urllib.request.Request(
                target_url,
                data=data,
                headers=headers,
                method=method
            )

            with urllib.request.urlopen(req, timeout=30) as response:
                content = response.read()
                self.send_response(response.status)

                for header, value in response.headers.items():
                    if header.lower() not in ['transfer-encoding', 'connection', 'access-control-allow-origin', 'content-length']:
                        self.send_header(header, value)
                
                # We handle content-length manually to match read()
                self.send_header('Content-Length', str(len(content)))
                self.end_headers()
                self.wfile.write(content)

        except urllib.error.HTTPError as e:
            print(f"   [Error] Backend returned {e.code}")
            self.send_response(e.code)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(e.read())

        except urllib.error.URLError as e:
            self.send_error(503, f"Backend unavailable: {str(e.reason)}")

        except Exception as e:
            self.send_error(502, f"Proxy error: {str(e)}")

def main():
    # Register cleanup
    atexit.register(stop_cliproxy)
    signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))
    signal.signal(signal.SIGINT, lambda s, f: sys.exit(0))

    print("""
╔══════════════════════════════════════════════════════════╗
║         Unified CLI Proxy Server                         ║
╚══════════════════════════════════════════════════════════╝
""")

    # Start backend
    print("Starting backend server...")
    if not start_cliproxy():
        print("Warning: Running without backend (API calls will fail)")

    # Start unified server
    print(f"\nStarting unified server on port {PUBLIC_PORT}...")

    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("", PUBLIC_PORT), UnifiedHandler) as httpd:
        print(f"""
Ready!

Dashboards:
  http://localhost:{PUBLIC_PORT}/              -> Dashboard (Enhanced v2)
  http://localhost:{PUBLIC_PORT}/dashboard.html

API Endpoints:
  http://localhost:{PUBLIC_PORT}/v1/...        -> Proxied to backend
  http://localhost:{PUBLIC_PORT}/v0/...        -> Proxied to backend

Press Ctrl+C to stop...
""")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass

    stop_cliproxy()
    print("\nServer stopped.")

if __name__ == '__main__':
    main()
