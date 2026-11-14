"""
라즈봇 V2 웹 제어 서버 (카메라 영상 + 바퀴 제어 + 카메라 방향 제어)

실행:  python3 manual_jiy.py
접속:  브라우저에서 http://로봇IP:5000

처음 실행 전에 아래 "설정" 부분의 숫자들을 우리 로봇에 맞게 확인하세요.
"""

import atexit
import threading
import time

import cv2
from flask import Flask, Response, jsonify, request

# =====================================================
# 0. 라즈봇 보드 연결
#    (노트북처럼 Raspbot_Lib가 없는 곳에서는 "테스트 모드"로 실행되어
#     바퀴/서보 대신 터미널에 글자만 출력합니다)
# =====================================================
try:
    from Raspbot_Lib import Raspbot
    car = Raspbot()
except Exception as e:
    print(f"[경고] Raspbot_Lib를 불러오지 못했습니다 ({e}) → 테스트 모드", flush=True)
    car = None

# 바퀴와 서보가 같은 보드(I2C)를 쓰므로, 동시에 명령이 섞이지 않게 잠금
bus_lock = threading.Lock()


# =====================================================
# 1. 설정 (우리 로봇에 맞게 바꾸는 곳)
# =====================================================

# --- 바퀴 보정표: wheel_test.py 결과대로 수정 ---
MOTOR_ID = {"FL": 0, "RL": 1, "FR": 2, "RR": 3}   # 위치 → 실제 모터 번호
DIRECTION = {"FL": 1, "RL": 1, "FR": 1, "RR": 1}  # 거꾸로 돌면 -1

SPEED = 80          # 전진/후진 속도 (0~255)
TURN_SPEED = 60     # 회전 속도
WATCHDOG_SEC = 0.5  # 이 시간 동안 명령이 없으면 자동 정지 (와이파이 끊김 대비)

# 바퀴 순서: (앞왼쪽 FL, 뒤왼쪽 RL, 앞오른쪽 FR, 뒤오른쪽 RR)
#   1 = 앞으로, -1 = 뒤로, 0 = 멈춤
MOVES = {
    "FORWARD":  (1, 1, 1, 1),
    "BACKWARD": (-1, -1, -1, -1),
    "LEFT":     (-1, -1, 1, 1),   # 제자리 왼쪽 회전
    "RIGHT":    (1, 1, -1, -1),   # 제자리 오른쪽 회전
    "STOP":     (0, 0, 0, 0),
}

# --- 카메라 서보 ---
PAN_ID = 1               # 좌우 서보 번호
TILT_ID = 2              # 상하 서보 번호
PAN_RANGE = (0, 180)     # 좌우 허용 각도
TILT_RANGE = (0, 110)    # 상하 허용 각도 (설명서의 안전 범위로 맞추기!)
PAN_CENTER = 90
TILT_CENTER = 90
SERVO_STEP = 10          # 버튼 한 번에 움직일 각도

# --- 카메라 화질 ---
CAM_INDEX = 0
CAM_WIDTH = 640
CAM_HEIGHT = 480
CAM_FPS = 30
JPEG_QUALITY = 80


# =====================================================
# 2. 바퀴 제어
# =====================================================
WHEEL_ORDER = ["FL", "RL", "FR", "RR"]

drive_state = {"moving": False, "last_cmd_time": 0.0}


def set_wheels(pattern, speed):
    for name, sign in zip(WHEEL_ORDER, pattern):
        value = int(sign * speed * DIRECTION[name])
        if car is None:
            continue
        with bus_lock:
            car.Ctrl_Muto(MOTOR_ID[name], value)


def drive(command):
    pattern = MOVES[command]
    speed = TURN_SPEED if command in ("LEFT", "RIGHT") else SPEED
    set_wheels(pattern, speed)

    drive_state["moving"] = command != "STOP"
    drive_state["last_cmd_time"] = time.time()

    if car is None:
        print(f"[테스트] 바퀴 명령: {command}", flush=True)


def watchdog_loop():
    """버튼을 떼거나 연결이 끊겨서 명령이 안 오면 자동으로 멈춤"""
    while True:
        time.sleep(0.1)
        if drive_state["moving"] and time.time() - drive_state["last_cmd_time"] > WATCHDOG_SEC:
            drive("STOP")
            print("[안전] 명령이 끊겨서 자동 정지", flush=True)


# =====================================================
# 3. 카메라 방향(서보) 제어
# =====================================================
servo_state = {"pan": PAN_CENTER, "tilt": TILT_CENTER}


def clamp(value, low, high):
    return max(low, min(high, value))


def apply_servos():
    if car is None:
        print(f"[테스트] 카메라 각도: 좌우 {servo_state['pan']}°, 상하 {servo_state['tilt']}°", flush=True)
        return
    with bus_lock:
        car.Ctrl_Servo(PAN_ID, servo_state["pan"])
        car.Ctrl_Servo(TILT_ID, servo_state["tilt"])


def move_camera(direction):
    # 버튼 방향과 실제 회전 방향이 반대라면 + 와 - 를 바꾸세요
    if direction == "LEFT":
        servo_state["pan"] = clamp(servo_state["pan"] + SERVO_STEP, *PAN_RANGE)
    elif direction == "RIGHT":
        servo_state["pan"] = clamp(servo_state["pan"] - SERVO_STEP, *PAN_RANGE)
    elif direction == "UP":
        servo_state["tilt"] = clamp(servo_state["tilt"] - SERVO_STEP, *TILT_RANGE)
    elif direction == "DOWN":
        servo_state["tilt"] = clamp(servo_state["tilt"] + SERVO_STEP, *TILT_RANGE)
    elif direction == "CENTER":
        servo_state["pan"] = PAN_CENTER
        servo_state["tilt"] = TILT_CENTER
    apply_servos()


# =====================================================
# 4. 카메라 영상
#    카메라는 스레드 하나만 읽고 "최신 사진"을 저장해 둠
#    → 여러 명이 접속해도 영상이 나뉘지 않음
# =====================================================
camera = cv2.VideoCapture(CAM_INDEX, cv2.CAP_V4L2)
camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
camera.set(cv2.CAP_PROP_FRAME_WIDTH, CAM_WIDTH)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_HEIGHT)
camera.set(cv2.CAP_PROP_FPS, CAM_FPS)

frame_lock = threading.Lock()
latest_jpeg = None


def camera_loop():
    global latest_jpeg
    while True:
        ok, frame = camera.read()
        if not ok:
            time.sleep(0.05)   # 실패 시 잠깐 쉬기 (CPU 100% 방지)
            continue
        ok, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
        if ok:
            with frame_lock:
                latest_jpeg = buffer.tobytes()


def generate_frames():
    last_sent = None
    while True:
        with frame_lock:
            jpg = latest_jpeg
        if jpg is None or jpg is last_sent:
            time.sleep(0.01)
            continue
        last_sent = jpg
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + jpg + b"\r\n"
        )


# =====================================================
# 5. 웹페이지
# =====================================================
app = Flask(__name__)

PAGE = """
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Raspbot Control</title>
<style>
  body { font-family: Arial, sans-serif; text-align: center; margin: 0;
         padding: 16px; background: #f1f5f9; }
  .camera { width: 100%; max-width: 640px; border-radius: 10px; background: #222; }
  .panels { display: flex; flex-wrap: wrap; justify-content: center; gap: 24px; }
  .pad { display: grid; grid-template-columns: repeat(3, 80px); gap: 10px; }
  button { height: 70px; font-size: 18px; font-weight: bold; border: 0;
           border-radius: 14px; background: #2563eb; color: white;
           touch-action: none; user-select: none; -webkit-user-select: none; }
  button:active { background: #1d4ed8; }
  .stop { background: #dc2626; }
  .cam button { background: #059669; }
  .cam button:active { background: #047857; }
  .empty { visibility: hidden; }
  #status { margin: 14px; color: #334155; }
</style>
</head>
<body>
  <h2>라즈봇 실시간 카메라</h2>
  <img class="camera" src="/video" alt="카메라 영상">
  <p id="status">제어 대기 중</p>

  <div class="panels">
    <div>
      <h3>바퀴 (누르는 동안만 이동)</h3>
      <div class="pad">
        <button class="empty"></button>
        <button data-move="FORWARD">▲<br>전진</button>
        <button class="empty"></button>
        <button data-move="LEFT">⟲<br>좌회전</button>
        <button class="stop" id="stopBtn">■<br>정지</button>
        <button data-move="RIGHT">⟳<br>우회전</button>
        <button class="empty"></button>
        <button data-move="BACKWARD">▼<br>후진</button>
        <button class="empty"></button>
      </div>
    </div>

    <div class="cam">
      <h3>카메라 방향</h3>
      <div class="pad">
        <button class="empty"></button>
        <button data-cam="UP">↑</button>
        <button class="empty"></button>
        <button data-cam="LEFT">←</button>
        <button data-cam="CENTER">●<br>정면</button>
        <button data-cam="RIGHT">→</button>
        <button class="empty"></button>
        <button data-cam="DOWN">↓</button>
        <button class="empty"></button>
      </div>
    </div>
  </div>

<script>
  const statusEl = document.getElementById("status");
  let repeatTimer = null;

  async function post(url, direction) {
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ direction: direction })
      });
      const data = await res.json();
      statusEl.textContent = data.message;
    } catch (e) {
      statusEl.textContent = "서버 통신 오류";
    }
  }

  // 바퀴: 누르고 있는 동안 0.2초마다 명령을 다시 보냄
  // (서버는 0.5초 동안 명령이 없으면 스스로 멈춤)
  function startMove(cmd) {
    stopRepeat();
    post("/move", cmd);
    repeatTimer = setInterval(() => post("/move", cmd), 200);
  }
  function stopRepeat() {
    if (repeatTimer) { clearInterval(repeatTimer); repeatTimer = null; }
  }
  function endMove() {
    if (repeatTimer) { stopRepeat(); post("/move", "STOP"); }
  }

  document.querySelectorAll("[data-move]").forEach(btn => {
    btn.addEventListener("pointerdown", e => { e.preventDefault(); startMove(btn.dataset.move); });
    ["pointerup", "pointerleave", "pointercancel"].forEach(ev => btn.addEventListener(ev, endMove));
  });
  document.getElementById("stopBtn").addEventListener("click", () => { stopRepeat(); post("/move", "STOP"); });
  window.addEventListener("blur", endMove);   // 다른 앱으로 전환하면 정지

  // 카메라: 누를 때마다 한 칸씩
  document.querySelectorAll("[data-cam]").forEach(btn => {
    btn.addEventListener("click", () => post("/camera", btn.dataset.cam));
  });
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return PAGE


@app.route("/video")
def video():
    return Response(generate_frames(),
                    mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/move", methods=["POST"])
def move():
    data = request.get_json(silent=True) or {}
    command = data.get("direction", "")
    if command not in MOVES:
        return jsonify({"success": False, "message": "잘못된 바퀴 명령"}), 400
    drive(command)
    return jsonify({"success": True, "message": f"바퀴: {command}"})


@app.route("/camera", methods=["POST"])
def camera_move():
    data = request.get_json(silent=True) or {}
    direction = data.get("direction", "")
    if direction not in {"UP", "DOWN", "LEFT", "RIGHT", "CENTER"}:
        return jsonify({"success": False, "message": "잘못된 카메라 명령"}), 400
    move_camera(direction)
    return jsonify({
        "success": True,
        "message": f"카메라: 좌우 {servo_state['pan']}°, 상하 {servo_state['tilt']}°"
    })


# =====================================================
# 6. 종료 시 정리 (바퀴 정지 + 카메라 닫기)
# =====================================================
def cleanup():
    try:
        set_wheels(MOVES["STOP"], 0)
    finally:
        camera.release()
    print("종료: 바퀴 정지, 카메라 닫음", flush=True)


atexit.register(cleanup)


# =====================================================
# 7. 실행
# =====================================================
if __name__ == "__main__":
    if not camera.isOpened():
        raise RuntimeError("카메라를 열 수 없습니다. USB 연결과 번호(CAM_INDEX)를 확인하세요.")

    drive("STOP")
    apply_servos()   # 시작할 때 카메라를 정면으로

    threading.Thread(target=camera_loop, daemon=True).start()
    threading.Thread(target=watchdog_loop, daemon=True).start()

    print("서버 실행: http://로봇IP:5000", flush=True)
    app.run(host="0.0.0.0", port=5000, threaded=True)
