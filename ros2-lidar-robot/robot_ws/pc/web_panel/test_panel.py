#!/usr/bin/env python3
"""Offline test of the web panel: real HTTP server + real browser (Chromium), fake robot behind it.
Checks: page renders the map/robot/scan, buttons and keys reach the backend, security (token, Host)."""
import json, math, os, sys, threading, time, urllib.request, urllib.error
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', '..', 'src', 'robot_description', 'tools'))
from panel_core import PanelState, make_server
import offline_check as oc

class Backend:
    def __init__(self): self.calls = []
    def send_cmd(self, v, w): self.calls.append(('cmd', round(v, 3), round(w, 3)))
    def set_mode(self, m): self.calls.append(('mode', m))
    def set_estop(self, b): self.calls.append(('estop', b))
    def send_goal(self, x, y, yaw): self.calls.append(('goal', round(x, 2), round(y, 2), round(yaw, 2)))

occ, inside = oc.build_world()
grid = np.full(occ.shape, 255, dtype=np.uint8)
grid[inside] = 0
grid[occ] = 100
state, backend = PanelState(), Backend()
state.set_map(oc.N, oc.N, oc.RES, -oc.HALF, -oc.HALF, grid.tobytes())
pose = (-1.0, 0.5, 0.6)
state.set_pose(*pose)
lx, ly = pose[0] + math.cos(pose[2]) * oc.LIDAR_X, pose[1] + math.sin(pose[2]) * oc.LIDAR_X
rng, ang = oc.scan(occ, lx, ly, pose[2])
state.set_scan([[round(lx + r * math.cos(a), 3), round(ly + r * math.sin(a), 3)] for r, a in zip(rng, ang) if np.isfinite(r)][::2])
state.set_state(dict(mode='manual', estop=False, reason='ok', front=0.8, rear=None, v=0.0, w=0.0))
state.set_health(dict(level='ok', problems=[], scan_hz=9.8, base=dict(connected=True, odometry='open_loop'),
                      pi=dict(temp_c=52.0, mem_free_mb=1800.0)))
def keep_fresh():            # the real node refreshes the pose at 10 Hz
    while True:
        state.set_pose(*pose); state.t_state = state.t_state if state.t_state < time.time() - 5 else time.time(); time.sleep(0.2)
threading.Thread(target=keep_fresh, daemon=True).start()
port = 18080
srv = make_server(state, backend, port)
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = f'http://localhost:{port}'
fails = 0
def check(name, cond, info=''):
    global fails
    print(('PASS ' if cond else 'FAIL ') + name + (f'  [{info}]' if (info and not cond) else ''))
    fails += 0 if cond else 1

# ---- security
def req(path, data=None, headers=None):
    r = urllib.request.Request(base + path, data=data, headers=headers or {}, method='POST' if data is not None else 'GET')
    try:
        with urllib.request.urlopen(r, timeout=5) as resp: return resp.status
    except urllib.error.HTTPError as e: return e.code
check('POST without token refused', req('/api/cmd', b'{"v":0.1,"w":0}', {'Content-Type': 'application/json'}) == 403)
check('POST with wrong token refused', req('/api/cmd', b'{"v":0.1,"w":0}', {'X-Panel-Token': 'nope'}) == 403)
check('wrong Host header refused (DNS rebinding)', req('/', None, {'Host': 'evil.example.com'}) == 403)
check('nothing reached the backend', backend.calls == [], backend.calls)
check('GET state works', req('/api/state?v=0') == 200)
check('mode validated', req('/api/mode', b'{"mode":"turbo"}', {'X-Panel-Token': srv.token}) == 400)
check('bad json refused', req('/api/cmd', b'{"v":"x"}', {'X-Panel-Token': srv.token}) == 400)
backend.calls.clear()

# ---- browser
from playwright.sync_api import sync_playwright
out = os.environ.get('PANEL_SHOT', '/tmp/panel.png')
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/opt/pw-browsers/chromium' if os.path.exists('/opt/pw-browsers/chromium') else None,
                          args=['--no-sandbox'])
    pg = b.new_page(viewport={'width': 1280, 'height': 760})
    errors = []
    pg.on('pageerror', lambda e: errors.append(str(e)))
    pg.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
    pg.goto(base)
    pg.wait_for_function("document.getElementById('sMode').textContent === 'manual'", timeout=8000)
    check('page loads and shows the robot state', pg.inner_text('#sMode') == 'manual')
    check('lidar rate and Mega shown', '9.8 Hz' in pg.inner_text('#sScan') and 'connected' in pg.inner_text('#sMega'))
    check('pi stats shown', '52' in pg.inner_text('#sPi'))
    pg.wait_for_timeout(600)
    # canvas really has map pixels (dark wall pixels and light free pixels)
    stats = pg.evaluate("""() => { const c = document.getElementById('cv'); const x = c.getContext('2d');
        const d = x.getImageData(0, 0, c.width, c.height).data; let dark = 0, light = 0, red = 0;
        for (let i = 0; i < d.length; i += 4) { const r = d[i], g = d[i+1], b = d[i+2];
          if (r > 200 && g < 110 && b < 110) red++; else if (r < 60 && g < 60 && b < 60) dark++; else if (r > 240 && g > 240 && b > 240) light++; }
        return {dark, light, red}; }""")
    check('map walls, free space and lidar points are drawn', stats['dark'] > 500 and stats['light'] > 5000 and stats['red'] > 50, stats)
    pg.screenshot(path=out)
    # modes
    pg.click('#modes button[data-mode="explore"]')
    pg.click('#btnEstop')
    pg.wait_for_timeout(300)
    check('mode button reaches the backend', ('mode', 'explore') in backend.calls, backend.calls)
    check('e-stop button reaches the backend', ('estop', True) in backend.calls, backend.calls)
    # keyboard drive: hold W, then release
    backend.calls.clear()
    pg.keyboard.down('w'); pg.wait_for_timeout(450); pg.keyboard.up('w'); pg.wait_for_timeout(300)
    cmds = [c for c in backend.calls if c[0] == 'cmd']
    moving = [c for c in cmds if c[1] > 0]
    check('holding W sends repeated forward commands', len(moving) >= 3 and abs(moving[0][1] - 0.10) < 1e-6, cmds)
    check('releasing W sends a final zero', cmds and cmds[-1][1:] == (0.0, 0.0), cmds)
    n_after = len(backend.calls); pg.wait_for_timeout(500)
    check('nothing is sent once released (dead-man)', len(backend.calls) == n_after)
    # arrow keys: forward-left arc
    backend.calls.clear()
    pg.keyboard.down('ArrowUp'); pg.keyboard.down('ArrowLeft'); pg.wait_for_timeout(300)
    pg.keyboard.up('ArrowUp'); pg.keyboard.up('ArrowLeft'); pg.wait_for_timeout(250)
    arcs = [c for c in backend.calls if c[0] == 'cmd' and c[1] > 0 and c[2] > 0]
    check('up+left = forward arc to the left', len(arcs) >= 2, backend.calls)
    # Escape = e-stop; space = stop
    backend.calls.clear()
    pg.keyboard.press('Escape'); pg.wait_for_timeout(250)
    check('Escape sends the e-stop', ('estop', True) in backend.calls, backend.calls)
    # goal by click and drag
    backend.calls.clear()
    box = pg.locator('#cv').bounding_box()
    pg.click('#btnGoal')
    cx, cy = box['x'] + box['width'] / 2, box['y'] + box['height'] / 2
    pg.mouse.move(cx + 60, cy - 40); pg.mouse.down(); pg.mouse.move(cx + 120, cy - 40); pg.mouse.up()
    pg.wait_for_timeout(250)
    goals = [c for c in backend.calls if c[0] == 'goal']
    check('click-drag on the map sends a goal with heading', len(goals) == 1 and abs(goals[0][3]) < 0.2, backend.calls)
    # goal is where we clicked: robot (-1,0.5) is at the centre (follow), +60 px right, 40 px up at 60 px/m
    check('goal position matches the click', goals and abs(goals[0][1] - (-1.0 + 1.0)) < 0.15 and abs(goals[0][2] - (0.5 + 40 / 60)) < 0.15, goals)
    # robot silent banner
    state.t_state = time.time() - 10
    pg.wait_for_timeout(500)
    check('"no link" banner when the robot is silent', pg.is_visible('#banner'))
    check('no JavaScript errors', not errors, errors)
    b.close()
srv.shutdown()
print('ALL PASSED' if not fails else f'{fails} FAILED')
sys.exit(1 if fails else 0)
