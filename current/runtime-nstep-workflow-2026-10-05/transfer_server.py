"""Private LAN transfer of exactly two task ZIPs; no directory or repository service."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import time
import uuid

root = Path(__file__).resolve().parents[2] / 'runtime_trace/regular_nstep/artifacts/laptop-transfer'
token = uuid.uuid4().hex
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        names = {f'/{token}/{name}': root / name for name in ('package10-final2.zip', 'package100-final.zip')}
        path = names.get(self.path)
        if self.client_address[0] != '192.168.0.4' or path is None or not path.is_file():
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Length', str(path.stat().st_size))
        self.end_headers()
        with path.open('rb') as stream:
            while data := stream.read(1048576):
                self.wfile.write(data)
    def log_message(self, *args):
        pass
server = HTTPServer(('192.168.0.2', 43451), Handler)
server.timeout = 1
print(json.dumps({'url_prefix': f'http://192.168.0.2:43451/{token}/', 'expires_seconds': 900}), flush=True)
began = time.monotonic()
while time.monotonic() - began < 900:
    server.handle_request()
server.server_close()
