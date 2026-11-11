#!/usr/bin/env python3
"""Gazebo simulation backend for the existing controller.html keyboard UI.

Run this beside controller.html, after sourcing ROS 2 and starting the
ros_gz_sim_demos diff-drive example. The real-hardware manual.py is unchanged.
"""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node


# Match the demo robot launched by:
#   ros2 launch ros_gz_sim_demos diff_drive.launch.py
CMD_VEL_TOPIC = "/model/vehicle_blue/cmd_vel"
HTTP_HOST = "127.0.0.1"  # Local browser only; avoids exposing robot control on the LAN.
HTTP_PORT = 8000

# Gazebo Twist units are metres/second and radians/second, unlike the
# 0-100 motor power values used by the real Raspbot driver.
BASE_LINEAR_SPEED = 0.20
BASE_ANGULAR_SPEED = 0.60
SPEED_MULTIPLIERS = {1: 1.0, 2: 1.5, 3: 2.0}

HTML_PATH = Path(__file__).with_name("controller.html")


class SimController(Node):
    def __init__(self):
        super().__init__("manual_sim_controller")
        self.publisher = self.create_publisher(Twist, CMD_VEL_TOPIC, 10)
        self.get_logger().info(f"Publishing Gazebo velocity commands on {CMD_VEL_TOPIC}")

    def publish_keys(self, keys, speed_level):
        msg = Twist()
        forward = "w" in keys
        backward = "s" in keys

        # Pressing W and S together, or neither, means stop.
        if forward != backward:
            direction = 1.0 if forward else -1.0
            multiplier = SPEED_MULTIPLIERS[speed_level]
            msg.linear.x = direction * BASE_LINEAR_SPEED * multiplier

            # A/D steer while moving. Positive angular.z turns left in ROS.
            if "a" in keys and "d" not in keys:
                msg.angular.z = BASE_ANGULAR_SPEED * multiplier
            elif "d" in keys and "a" not in keys:
                msg.angular.z = -BASE_ANGULAR_SPEED * multiplier

        self.publisher.publish(msg)


class ControllerHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def send_text(self, code, message):
        body = message.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if parsed.path in ("/", "/controller.html"):
            try:
                body = HTML_PATH.read_bytes()
            except FileNotFoundError:
                self.send_text(500, "manual_sim.py와 controller.html을 같은 폴더에 두세요.")
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/control":
            keys = params.get("keys", [""])[0].lower()
            if any(key not in "wasd" for key in keys) or len(set(keys)) != len(keys):
                self.send_text(400, "잘못된 키 입력")
                return

            try:
                speed_level = int(params.get("speed", ["1"])[0])
            except ValueError:
                speed_level = 1
            if speed_level not in SPEED_MULTIPLIERS:
                speed_level = 1

            sim_node.publish_keys(set(keys), speed_level)
            action = "정지"
            if "w" in keys and "s" not in keys:
                action = "전진"
            elif "s" in keys and "w" not in keys:
                action = "후진"
            if "a" in keys and "d" not in keys and action != "정지":
                action += "·좌회전"
            elif "d" in keys and "a" not in keys and action != "정지":
                action += "·우회전"
            self.send_text(200, f"Gazebo 명령: {action}, 속도 단계={speed_level}")
            return

        if parsed.path == "/servo":
            self.send_text(200, "시뮬레이션 모드에서는 서보를 사용하지 않습니다.")
            return

        if parsed.path == "/video":
            self.send_text(503, "시뮬레이션 모드에서는 카메라 영상을 제공하지 않습니다.")
            return

        self.send_text(404, "요청한 경로가 없습니다.")

    def log_message(self, format, *args):
        pass


def main():
    global sim_node
    rclpy.init()
    sim_node = SimController()
    server = ThreadingHTTPServer((HTTP_HOST, HTTP_PORT), ControllerHandler)
    print(f"시뮬레이션 제어 페이지: http://{HTTP_HOST}:{HTTP_PORT}", flush=True)
    print(f"Gazebo 토픽: {CMD_VEL_TOPIC}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        sim_node.publish_keys(set(), 1)  # Stop the simulated robot on exit.
        server.server_close()
        sim_node.destroy_node()
        rclpy.shutdown()
        print("시뮬레이션 제어 서버 종료", flush=True)


if __name__ == "__main__":
    main()
