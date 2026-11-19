#!/usr/bin/env python3
"""강의실 Gazebo 월드 생성기.

이 파일 위쪽 [설정] 부분의 숫자만 고치고 다시 실행하면 classroom.sdf 가 새로 만들어진다.
  1) 만들기:  python3 ~/classroom/make_classroom.py
  2) 보기:    gz sim ~/classroom/classroom.sdf

좌표 약속 (위에서 내려다본 그림 기준)
  x : 왼쪽(-) ↔ 오른쪽(+)
  y : 뒤쪽(-) ↔ 앞쪽(+)   앞쪽 = 강사님 자리, 스크린, 출입문이 있는 벽
  z : 바닥(0) → 위
  방 한가운데 바닥이 (0, 0, 0). 단위는 m(미터).
"""
import os

# ============================== [설정] ==============================

# 1. 방 크기
ROOM_W = 12.0      # 좌우 폭 (m)
ROOM_D = 10.0      # 앞뒤 길이 (m)
WALL_H = 2.6       # 벽 높이
WALL_T = 0.1       # 벽 두께

# 2. 학생 책상 배치: 앞줄부터 한 줄씩, [왼쪽 분단, 가운데 분단, 오른쪽 분단]
#    숫자 = 그 책상에 앉는 사람 수. 0 이면 그 자리에 책상 없음.
LAYOUT = [
    [3, 2, 3],
    [3, 2, 3],
    [3, 2, 3],
    [2, 2, 2],
]
COL_X = [-3.6, 0.0, 3.6]   # 분단 가운데 x 위치 (왼쪽, 가운데, 오른쪽)
FIRST_ROW_Y = 2.0          # 첫 줄 책상의 y 위치 (앞벽은 y = ROOM_D/2 = 5.0)
ROW_GAP = 1.6              # 줄과 줄 사이 간격 (책상 중심끼리)

# 3. 책상 / 의자 크기
SEAT_W = 0.6       # 한 사람당 책상 폭 → 3인 책상 = 1.8 m
DESK_D = 0.5       # 책상 깊이
DESK_H = 0.75      # 책상 높이
CHAIRS = True      # 의자도 놓을지 (False 면 책상만)

# 4. 앞쪽 (강사 책상, 스크린, 출입문)
TEACHER_DESK = dict(x=-4.0, y=3.8, w=1.6, d=0.7)    # 강사 책상 위치와 크기
SCREEN = dict(x=0.0, w=3.0, bottom=0.9, top=2.4)    # 빔 프로젝터 스크린 (앞벽에 붙음)
DOOR = dict(x=4.7, w=1.0, h=2.1, open=True)         # 출입문 (앞벽, 가운데 x 위치와 폭). open=False 면 닫힘

# 5. 색 (빨강, 초록, 파랑) 0~1
C_WALL = (0.85, 0.85, 0.80)
C_DESK = (0.72, 0.55, 0.35)
C_LEG = (0.30, 0.30, 0.30)
C_CHAIR = (0.20, 0.35, 0.60)
C_TEACHER = (0.45, 0.30, 0.20)
C_SCREEN = (0.97, 0.97, 0.97)
C_DOOR = (0.55, 0.35, 0.20)

# ============================ [설정 끝] ============================


def box(name, x, y, z, sx, sy, sz, color, yaw=0.0):
    """상자 모양 부품 하나 (보이는 모양 visual + 부딪히는 모양 collision)."""
    r, g, b = color
    return f"""
      <link name="{name}">
        <pose>{x:.3f} {y:.3f} {z:.3f} 0 0 {yaw:.3f}</pose>
        <collision name="c"><geometry><box><size>{sx:.3f} {sy:.3f} {sz:.3f}</size></box></geometry></collision>
        <visual name="v"><geometry><box><size>{sx:.3f} {sy:.3f} {sz:.3f}</size></box></geometry>
          <material><ambient>{r} {g} {b} 1</ambient><diffuse>{r} {g} {b} 1</diffuse></material></visual>
      </link>"""


def model(name, x, y, links):
    """움직이지 않는(static) 물체 하나. links 는 box() 들을 이어 붙인 글자."""
    return f"""
    <model name="{name}">
      <static>true</static>
      <pose>{x:.3f} {y:.3f} 0 0 0 0</pose>{links}
    </model>"""


def desk_links(w, d, h, color):
    """책상 = 상판 1개 + 다리 4개."""
    t, leg = 0.04, 0.04
    s = box("top", 0, 0, h - t / 2, w, d, t, color)
    for i, (sx, sy) in enumerate([(1, 1), (1, -1), (-1, 1), (-1, -1)]):
        s += box(f"leg{i}", sx * (w / 2 - leg), sy * (d / 2 - leg), (h - t) / 2,
                 leg, leg, h - t, C_LEG)
    return s


def chair_links(prefix, x, y, facing):
    """의자 = 앉는 판 + 기둥 + 등받이. facing=+1 이면 앞(+y)을 봄."""
    back_y = y - facing * 0.2
    return (box(f"{prefix}_seat", x, y, 0.45, 0.4, 0.4, 0.04, C_CHAIR)
            + box(f"{prefix}_post", x, y, 0.215, 0.05, 0.05, 0.43, C_LEG)
            + box(f"{prefix}_back", x, back_y, 0.68, 0.4, 0.04, 0.42, C_CHAIR))


def build():
    parts = []
    half_w, half_d = ROOM_W / 2, ROOM_D / 2
    zc = WALL_H / 2

    # ---- 벽: 뒤, 왼쪽, 오른쪽 + 앞벽(출입문 자리만 비움) ----
    walls = box("back", 0, -half_d, zc, ROOM_W, WALL_T, WALL_H, C_WALL)
    walls += box("left", -half_w, 0, zc, WALL_T, ROOM_D, WALL_H, C_WALL)
    walls += box("right", half_w, 0, zc, WALL_T, ROOM_D, WALL_H, C_WALL)
    door_l, door_r = DOOR["x"] - DOOR["w"] / 2, DOOR["x"] + DOOR["w"] / 2
    front_l = door_l - (-half_w)            # 왼쪽 끝 ~ 문 왼쪽
    walls += box("front_l", -half_w + front_l / 2, half_d, zc, front_l, WALL_T, WALL_H, C_WALL)
    front_r = half_w - door_r               # 문 오른쪽 ~ 오른쪽 끝
    if front_r > 0.01:
        walls += box("front_r", door_r + front_r / 2, half_d, zc, front_r, WALL_T, WALL_H, C_WALL)
    above = WALL_H - DOOR["h"]              # 문 위쪽 벽
    walls += box("front_top", DOOR["x"], half_d, DOOR["h"] + above / 2, DOOR["w"], WALL_T, above, C_WALL)
    parts.append(model("walls", 0, 0, walls))

    # ---- 출입문: 열림이면 방 안쪽으로 90도 열린 판, 닫힘이면 구멍을 막음 ----
    if DOOR["open"]:
        door = box("panel", door_r - 0.03, half_d - DOOR["w"] / 2, DOOR["h"] / 2,
                   0.04, DOOR["w"], DOOR["h"], C_DOOR)
    else:
        door = box("panel", DOOR["x"], half_d, DOOR["h"] / 2, DOOR["w"], 0.04, DOOR["h"], C_DOOR)
    parts.append(model("door", 0, 0, door))

    # ---- 빔 프로젝터 스크린 (앞벽에 붙은 흰 판) ----
    sh = SCREEN["top"] - SCREEN["bottom"]
    parts.append(model("projector_screen", SCREEN["x"], half_d - WALL_T / 2 - 0.02,
                       box("screen", 0, 0, SCREEN["bottom"] + sh / 2, SCREEN["w"], 0.02, sh, C_SCREEN)))

    # ---- 강사 책상 (학생 쪽을 보고, 의자는 앞벽 쪽) ----
    td = TEACHER_DESK
    links = desk_links(td["w"], td["d"], DESK_H, C_TEACHER)
    if CHAIRS:
        links += chair_links("chair", 0, td["d"] / 2 + 0.35, facing=-1)
    parts.append(model("teacher_desk", td["x"], td["y"], links))

    # ---- 학생 책상 ----
    desks = seats = 0
    for r, row in enumerate(LAYOUT):
        y = FIRST_ROW_Y - r * ROW_GAP
        for c, n in enumerate(row):
            if n <= 0:
                continue
            w = n * SEAT_W
            links = desk_links(w, DESK_D, DESK_H, C_DESK)
            if CHAIRS:
                for i in range(n):
                    cx = -w / 2 + SEAT_W * (i + 0.5)
                    links += chair_links(f"chair{i}", cx, -(DESK_D / 2 + 0.3), facing=+1)
            parts.append(model(f"desk_r{r + 1}_c{c + 1}", COL_X[c], y, links))
            desks += 1
            seats += n

    world = f"""<?xml version="1.0"?>
<!-- make_classroom.py 로 자동 생성된 파일. 직접 고치지 말고 make_classroom.py 를 고친 뒤 다시 실행하세요. -->
<sdf version="1.9">
  <world name="classroom">
    <physics name="1ms" type="ignored">
      <max_step_size>0.001</max_step_size>
      <real_time_factor>1.0</real_time_factor>
    </physics>
    <plugin filename="gz-sim-physics-system" name="gz::sim::systems::Physics"/>
    <plugin filename="gz-sim-user-commands-system" name="gz::sim::systems::UserCommands"/>
    <plugin filename="gz-sim-scene-broadcaster-system" name="gz::sim::systems::SceneBroadcaster"/>
    <plugin filename="gz-sim-sensors-system" name="gz::sim::systems::Sensors">
      <render_engine>ogre2</render_engine>
    </plugin>

    <scene>
      <ambient>0.6 0.6 0.6 1</ambient>
      <background>0.7 0.8 0.9 1</background>
    </scene>

    <light type="directional" name="sun">
      <cast_shadows>false</cast_shadows>
      <pose>0 0 10 0 0 0</pose>
      <diffuse>0.9 0.9 0.9 1</diffuse>
      <direction>-0.3 0.2 -1</direction>
    </light>

    <model name="ground_plane">
      <static>true</static>
      <link name="link">
        <collision name="c"><geometry><plane><normal>0 0 1</normal><size>50 50</size></plane></geometry></collision>
        <visual name="v"><geometry><plane><normal>0 0 1</normal><size>50 50</size></plane></geometry>
          <material><ambient>0.6 0.6 0.6 1</ambient><diffuse>0.6 0.6 0.6 1</diffuse></material></visual>
      </link>
    </model>
{''.join(parts)}
  </world>
</sdf>
"""
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "classroom.sdf")
    with open(out, "w", encoding="utf-8") as f:
        f.write(world)
    print(f"만들었어요: {out}")
    print(f"학생 책상 {desks}개, 좌석 {seats}개")
    print(f"보기: gz sim {out}")


if __name__ == "__main__":
    build()
