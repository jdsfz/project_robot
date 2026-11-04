#!/usr/bin/env python3
"""Gazebo 화면 중계 서버 (1번 방식: 기존 Gazebo 창을 받아서 전송, 입력은 Gazebo 로 전달).

  python3 ~/project_lift/scripts/gz_view_server.py        # http://127.0.0.1:8090
  GET  /gazebo.mjpg   Gazebo GUI 창 영상 (MJPEG, <img src> 로 바로 표시)
  GET  /snap.jpg      현재 화면 한 장
  POST /api/view      {"preset": "top"|"robot"|"side"} 또는 {"x","y","z","roll","pitch","yaw"}
  POST /api/follow    {"target": "turtlebot4"} / {"target": ""} 는 따라가기 해제
  POST /api/world     {"action": "pause"|"play"|"step"|"reset"}

127.0.0.1 에만 열고, 정해 둔 gz 서비스만 호출한다(셸을 거치지 않음).
lift.sh 를 불러온 터미널에서 실행해야 gz 명령을 찾는다.
"""
import json
import math
import os
import re
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get('GZ_VIEW_PORT', 8090))
WORLD = os.environ.get('GZ_WORLD', 'depot')
FPS = os.environ.get('GZ_VIEW_FPS', '10')
WIDTH = os.environ.get('GZ_VIEW_WIDTH', '960')
# 기본은 3D 화면만 잘라 보낸다(제목줄·오른쪽 패널 제외). GZ_VIEW_CROP=0 이면 창 전체
CROP = '' if os.environ.get('GZ_VIEW_CROP') == '0' else 'crop=iw*0.58:ih*0.94:0:ih*0.057,'
ALLOWED_ORIGINS = {'http://localhost:8080', 'http://127.0.0.1:8080'}

PRESETS = {
    'top':   dict(x=2, y=0, z=14, roll=0, pitch=90, yaw=0),
    'side':  dict(x=-6, y=-6, z=5, roll=0, pitch=25, yaw=45),
    'robot': dict(x=-2.5, y=0, z=2, roll=0, pitch=20, yaw=0),
}
WORLD_REQ = {
    'pause': 'pause: true',
    'play':  'pause: false',
    'step':  'multi_step: 1',
    'reset': 'reset: {all: true}',
}


def euler_to_quat(roll, pitch, yaw):
    """도(deg) 단위 roll/pitch/yaw → (w, x, y, z)."""
    r, p, y = (math.radians(v) / 2 for v in (roll, pitch, yaw))
    cr, sr, cp, sp, cy, sy = math.cos(r), math.sin(r), math.cos(p), math.sin(p), math.cos(y), math.sin(y)
    return (cr * cp * cy + sr * sp * sy, sr * cp * cy - cr * sp * sy,
            cr * sp * cy + sr * cp * sy, cr * cp * sy - sr * sp * cy)


def gz_call(service, reqtype, req):
    out = subprocess.run(['gz', 'service', '-s', service, '--reqtype', reqtype,
                          '--reptype', 'gz.msgs.Boolean', '--timeout', '3000', '--req', req],
                         capture_output=True, text=True, timeout=10)
    return 'data: true' in out.stdout, (out.stdout + out.stderr).strip()


def find_window():
    tree = subprocess.run(['xwininfo', '-root', '-tree'], capture_output=True, text=True,
                          env={**os.environ, 'DISPLAY': os.environ.get('DISPLAY', ':0')}).stdout
    m = re.search(r'(0x[0-9a-f]+) "Gazebo Sim"', tree)
    return m.group(1) if m else None


class Capture:
    """ffmpeg 로 Gazebo 창을 잡아 마지막 JPEG 한 장을 들고 있는다. 창이 다시 뜨면 다시 찾는다."""

    def __init__(self):
        self.frame, self.cond, self.status = None, threading.Condition(), '시작 전'
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while True:
            wid = find_window()
            if not wid:
                self.status = 'Gazebo 창을 찾지 못함 (시뮬레이션이 켜져 있는지 확인)'
                time.sleep(2)
                continue
            self.status = '수신 중'
            p = subprocess.Popen(['ffmpeg', '-loglevel', 'error', '-f', 'x11grab', '-framerate', FPS,
                                  '-window_id', wid, '-i', os.environ.get('DISPLAY', ':0'),
                                  '-vf', f'{CROP}scale={WIDTH}:-2','-q:v', '6', '-f', 'image2pipe',
                                  '-vcodec', 'mjpeg', 'pipe:1'], stdout=subprocess.PIPE)
            buf = b''
            while True:
                chunk = p.stdout.read(65536)
                if not chunk:
                    break
                buf += chunk
                # JPEG 은 FFD8 로 시작해 FFD9 로 끝난다. 본문 안의 FF 는 바이트 스터핑되어 FFD9 가 나오지 않는다
                while (end := buf.find(b'\xff\xd9')) != -1:
                    start = buf.find(b'\xff\xd8')
                    if start != -1 and start < end:
                        with self.cond:
                            self.frame = buf[start:end + 2]
                            self.cond.notify_all()
                    buf = buf[end + 2:]
            p.wait()
            self.status = 'Gazebo 창이 닫힘, 다시 찾는 중'
            time.sleep(1)


CAP = None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _cors(self):
        origin = self.headers.get('Origin')
        if origin in ALLOWED_ORIGINS:
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self._cors()
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header('Access-Control-Allow-Methods', 'GET, POST')
        self.end_headers()

    def do_GET(self):
        if self.path == '/status':
            return self._json(200, {'capture': CAP.status, 'world': WORLD})
        if self.path == '/snap.jpg':
            if not CAP.frame:
                return self._json(503, {'error': CAP.status})
            self.send_response(200)
            self.send_header('Content-Type', 'image/jpeg')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            return self.wfile.write(CAP.frame)
        if self.path.startswith('/gazebo.mjpg'):
            self.send_response(200)
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            last = None
            try:
                while True:
                    with CAP.cond:
                        CAP.cond.wait_for(lambda: CAP.frame is not last, timeout=5)
                        last = CAP.frame
                    if last:
                        self.wfile.write(b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: '
                                         + str(len(last)).encode() + b'\r\n\r\n' + last + b'\r\n')
            except (BrokenPipeError, ConnectionResetError):
                return
        self._json(404, {'error': 'not found'})

    def do_POST(self):
        try:
            data = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0)) or 0) or b'{}')
        except ValueError:
            return self._json(400, {'error': '잘못된 JSON'})
        if self.path == '/api/view':
            v = PRESETS.get(data.get('preset')) or data
            try:
                x, y, z, roll, pitch, yaw = (float(v[k]) for k in ('x', 'y', 'z', 'roll', 'pitch', 'yaw'))
            except (KeyError, TypeError, ValueError):
                return self._json(400, {'error': 'preset 또는 x,y,z,roll,pitch,yaw 숫자가 필요함'})
            if not all(math.isfinite(n) and abs(n) < 1000 for n in (x, y, z, roll, pitch, yaw)):
                return self._json(400, {'error': '값 범위 초과'})
            qw, qx, qy, qz = euler_to_quat(roll, pitch, yaw)
            ok, out = gz_call('/gui/move_to/pose', 'gz.msgs.GUICamera',
                              f'pose: {{position: {{x: {x}, y: {y}, z: {z}}}, '
                              f'orientation: {{w: {qw}, x: {qx}, y: {qy}, z: {qz}}}}}')
            return self._json(200 if ok else 502, {'ok': ok, 'detail': out})
        if self.path == '/api/follow':
            target = str(data.get('target', ''))
            if not re.fullmatch(r'[A-Za-z0-9_]{0,64}', target):
                return self._json(400, {'error': '대상 이름은 영문, 숫자, _ 만'})
            ok, out = gz_call('/gui/follow', 'gz.msgs.StringMsg', f'data: "{target}"')
            return self._json(200 if ok else 502, {'ok': ok, 'detail': out})
        if self.path == '/api/world':
            req = WORLD_REQ.get(data.get('action'))
            if not req:
                return self._json(400, {'error': 'action 은 pause, play, step, reset 중 하나'})
            ok, out = gz_call(f'/world/{WORLD}/control', 'gz.msgs.WorldControl', req)
            return self._json(200 if ok else 502, {'ok': ok, 'detail': out})
        self._json(404, {'error': 'not found'})


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        q = euler_to_quat(0, 90, 0)
        assert all(abs(a - b) < 1e-6 for a, b in zip(q, (math.sqrt(.5), 0, math.sqrt(.5), 0))), q
        assert euler_to_quat(0, 0, 0) == (1, 0, 0, 0)
        print('selftest ok')
        sys.exit(0)
    CAP = Capture()
    print(f'[Gazebo 화면 중계] http://127.0.0.1:{PORT}/gazebo.mjpg  (끄려면 Ctrl+C)')
    ThreadingHTTPServer(('127.0.0.1', PORT), Handler).serve_forever()
