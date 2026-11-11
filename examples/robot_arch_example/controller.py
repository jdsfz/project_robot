"""Shared input/control logic. No Pi or ROS imports belong in this file."""
from drive import wheel_speeds


def run(output) -> None:
    print("W/S: 전후진, A/D: 회전 조합, X: 정지, Q: 종료")
    print("간단 예제라 키를 입력한 뒤 Enter를 누릅니다.")
    while True:
        keys = input("> ").strip().lower()
        if keys == "q":
            return
        if keys == "x":
            keys = ""
        if any(key not in "wasd" for key in keys):
            print("W/A/S/D, X 또는 Q를 입력하세요.")
            continue
        left, right = wheel_speeds(set(keys))
        output.set_wheels(left, right)
        print(f"left={left}, right={right}")
