import math, os, pty, sys, threading, time, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from x2 import X2Parser, encode_packet

def fake_turns(n_turns, rfun):
    out = b''
    for t in range(n_turns):
        for p in range(24):                       # 24 packets x 15 points = 360
            pts = [(p * 15 + k, rfun(p * 15 + k) * 1000) for k in range(15)]
            out += encode_packet(pts, first_of_turn=(p == 0))
    return out

stream = fake_turns(4, lambda d: 2.0 + 0.5 * math.sin(math.radians(d)))
p = X2Parser(); scans = []
for i in range(0, len(stream), 37):               # arbitrary chunking
    scans += p.feed(b'\x00\x13' + stream[i:i + 37] if i == 0 else stream[i:i + 37])
assert len(scans) == 3, len(scans)               # the 4th turn is still open
s = scans[1]; assert len(s) == 360, len(s)
for a, r in s:
    assert abs(r - (2.0 + 0.5 * math.sin(a))) < 0.01, (a, r)
print('parser ok: 3 turns, 360 points each, ranges within 1 cm')

# live mode through a virtual serial port
m, sl = pty.openpty(); port = os.ttyname(sl)
done = threading.Event()
def writer():
    # stream until the viewer exits: a fixed burst could end before a slow runner has started viewer.py
    while not done.is_set():
        os.write(m, fake_turns(1, lambda d: 3.0)); time.sleep(0.05)
threading.Thread(target=writer, daemon=True).start()
out = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), 'viewer.py'), 'live', port,
                      '--save', '/tmp/live.png', '--seconds', '2', '--csv', '/tmp/live.csv'],
                     capture_output=True, text=True, timeout=60)
done.set()
print(out.stdout.strip(), out.stderr[-300:])
assert 'saved' in out.stdout and os.path.getsize('/tmp/live.csv') > 1000
print('live mode ok (csv written)')
