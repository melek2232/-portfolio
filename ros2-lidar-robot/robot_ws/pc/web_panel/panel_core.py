"""Web panel core (no ROS here, so it is testable): thread-safe state + small HTTP server.

Security: the server listens on 127.0.0.1 only; every POST needs the random token embedded in the
page we serve, and the Host header must be localhost (blocks other web sites and DNS rebinding from
sending commands to the robot through your browser)."""
import base64
import json
import os
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
MODES = ('stop', 'manual', 'explore', 'nav')


class PanelState:
    def __init__(self):
        self.lock = threading.Lock()
        self.map = None            # dict(w,h,res,ox,oy,data_b64)
        self.map_version = 0
        self.pose = None           # dict(x,y,yaw)
        self.scan = []             # [[x, y], ...] in the map frame
        self.state = {}
        self.health = {}
        self.t_state = 0.0
        self.t_pose = 0.0
        self.last_goal = None

    def set_map(self, w, h, res, ox, oy, raw_bytes):
        with self.lock:
            self.map = dict(w=w, h=h, res=res, ox=ox, oy=oy,
                            data=base64.b64encode(raw_bytes).decode('ascii'))
            self.map_version += 1

    def set_pose(self, x, y, yaw):
        with self.lock:
            self.pose = dict(x=x, y=y, yaw=yaw)
            self.t_pose = time.time()

    def set_scan(self, pts):
        with self.lock:
            self.scan = pts

    def set_state(self, d):
        with self.lock:
            self.state = d
            self.t_state = time.time()

    def set_health(self, d):
        with self.lock:
            self.health = d

    def snapshot(self, have_version):
        with self.lock:
            now = time.time()
            return dict(
                map=self.map if self.map_version > have_version else None,
                map_version=self.map_version,
                pose=self.pose if now - self.t_pose < 2.0 else None,
                scan=self.scan, state=self.state, health=self.health,
                state_age=(now - self.t_state) if self.t_state else None,
                goal=self.last_goal)


def make_server(state, backend, port=8080, host='127.0.0.1'):
    """backend: object with send_cmd(v, w), set_mode(str), set_estop(bool), send_goal(x, y, yaw)."""
    token = secrets.token_urlsafe(16)
    with open(os.path.join(HERE, 'index.html'), encoding='utf-8') as f:
        page = f.read().replace('__TOKEN__', token)
    allowed_hosts = {f'localhost:{port}', f'127.0.0.1:{port}', f'[::1]:{port}'}

    class Handler(BaseHTTPRequestHandler):
        server_version = 'RobotPanel/1'

        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype='application/json'):
            data = body if isinstance(body, bytes) else body.encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(data)

        def _host_ok(self):
            return host != '127.0.0.1' or self.headers.get('Host', '') in allowed_hosts

        def do_GET(self):
            if not self._host_ok():
                return self._send(403, '{"error":"bad host"}')
            u = urlparse(self.path)
            if u.path == '/':
                return self._send(200, page, 'text/html; charset=utf-8')
            if u.path == '/api/state':
                q = parse_qs(u.query)
                have = int(q.get('v', ['0'])[0])
                return self._send(200, json.dumps(state.snapshot(have)))
            self._send(404, '{"error":"not found"}')

        def do_POST(self):
            if not self._host_ok() or self.headers.get('X-Panel-Token') != token:
                return self._send(403, '{"error":"forbidden"}')
            try:
                n = int(self.headers.get('Content-Length', '0'))
                body = json.loads(self.rfile.read(min(n, 4096)) or b'{}')
                path = urlparse(self.path).path
                if path == '/api/cmd':
                    backend.send_cmd(float(body['v']), float(body['w']))
                elif path == '/api/mode':
                    if body['mode'] not in MODES:
                        return self._send(400, '{"error":"bad mode"}')
                    backend.set_mode(body['mode'])
                elif path == '/api/estop':
                    backend.set_estop(bool(body['on']))
                elif path == '/api/goal':
                    x, y, yaw = float(body['x']), float(body['y']), float(body['yaw'])
                    backend.send_goal(x, y, yaw)
                    with state.lock:
                        state.last_goal = dict(x=x, y=y, yaw=yaw)
                else:
                    return self._send(404, '{"error":"not found"}')
            except (KeyError, ValueError, TypeError) as exc:
                return self._send(400, json.dumps({'error': str(exc)}))
            self._send(200, '{"ok":true}')

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    server.token = token
    return server
