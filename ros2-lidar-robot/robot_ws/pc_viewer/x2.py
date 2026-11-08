"""YDLIDAR X2 packet parser (no ROS). Packet: AA 55 CT LSN FSA(2) LSA(2) CS(2) + LSN*2 bytes.
distance_mm = sample / 4, angle in 1/64 deg units after >>1. Returns scans (360-ish points per turn)."""
import math


def encode_packet(points, first_of_turn=False):
    """points: list of (angle_deg, dist_mm). Used by the tests to build a fake X2 stream."""
    n = len(points)
    fsa = (int(points[0][0] * 64) << 1) | 1
    lsa = (int(points[-1][0] * 64) << 1) | 1
    body = b''.join(int(d * 4).to_bytes(2, 'little') for _, d in points)
    head = bytes([0xAA, 0x55, 1 if first_of_turn else 0, n]) + fsa.to_bytes(2, 'little') \
        + lsa.to_bytes(2, 'little') + b'\x00\x00'
    return head + body


class X2Parser:
    def __init__(self):
        self.buf = bytearray()
        self.cur = []          # (angle_rad, dist_m) of the turn being built
        self.packets = 0
        self.bad = 0

    def feed(self, data):
        """Add bytes, return list of completed scans [(angle_rad, dist_m), ...]."""
        self.buf += data
        done = []
        b = self.buf
        while True:
            i = b.find(b'\xaa\x55')
            if i < 0:
                del b[:max(0, len(b) - 1)]
                break
            if i:
                del b[:i]
            if len(b) < 10:
                break
            ct, lsn = b[2], b[3]
            need = 10 + 2 * lsn
            if lsn == 0 or lsn > 80:
                del b[:2]
                self.bad += 1
                continue
            if len(b) < need:
                break
            fsa = (b[4] | b[5] << 8) >> 1
            lsa = (b[6] | b[7] << 8) >> 1
            a1, a2 = fsa / 64.0, lsa / 64.0
            if a2 < a1:
                a2 += 360.0
            if ct & 1 and self.cur:
                done.append(self.cur)
                self.cur = []
            for k in range(lsn):
                s = b[10 + 2 * k] | b[11 + 2 * k] << 8
                if s == 0:
                    continue
                ang = a1 + (a2 - a1) * (k / (lsn - 1) if lsn > 1 else 0)
                self.cur.append((math.radians(ang % 360.0), s / 4000.0))
            self.packets += 1
            del b[:need]
        return done
