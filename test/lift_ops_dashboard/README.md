# LIFT 운행 대시보드

Gazebo 시뮬레이션(TurtleBot4 + Nav2)을 브라우저에서 보고 조작하는 대시보드입니다.
기존 Gazebo 창을 그대로 받아서 보여 주고, 대시보드의 버튼 입력은 기존 Gazebo와 ROS 2로 전달합니다.

기준 커밋: `6768f43` (project_lift, 브랜치 `dashboard-ops`)

## 들어 있는 파일

| 파일 | 언어 | 역할 |
|---|---|---|
| `dashboard/ops.html` | HTML, CSS, JavaScript | 새 운행 대시보드 (Gazebo 화면, 시작 순서, 장소 이동과 취소, 직접 운전) |
| `dashboard/index.html` | HTML, CSS, JavaScript | 3일차 실습용 대시보드 (센서, 주행 버튼, 체크리스트) |
| `scripts/dashboard.sh` | Bash | rosbridge(9090)와 웹 서버(8080)를 함께 실행 |
| `scripts/gz_view_server.py` | Python 3 (표준 라이브러리만) | Gazebo 창 화면 중계(8090)와 Gazebo 조작 요청 처리 |

## 필요한 환경

- Windows 11 + WSL2 Ubuntu 24.04 (WSLg 화면 사용)
- ROS 2 Jazzy, Gazebo Harmonic, Nav2 (`nav2_bringup`, TurtleBot4 시뮬레이션)
- 추가 패키지:

```bash
sudo apt install -y ros-jazzy-rosbridge-suite ffmpeg x11-utils
```

- 브라우저가 인터넷에 연결되어 있어야 합니다. `roslib.js`와 글꼴을 CDN에서 불러옵니다.

## 설치

압축을 풀고 두 폴더를 `~/project_lift` 아래에 복사합니다. 다른 위치에 두어도 되지만, `dashboard`와 `scripts` 두 폴더는 같은 상위 폴더 안에 있어야 합니다.

```bash
mkdir -p ~/project_lift
cp -r dashboard scripts ~/project_lift/
chmod +x ~/project_lift/scripts/*.sh ~/project_lift/scripts/*.py
```

`scripts/dashboard.sh`는 첫 줄에서 `~/lift.sh`(LIFT 과정의 공통 환경 파일)를 불러옵니다. 이 파일이 없으면 그 줄을 `source /opt/ros/jazzy/setup.bash`로 바꾸세요.

## 실행 (터미널 3개)

모든 터미널은 ROS 환경을 불러온 상태여야 하고, `ROS_DOMAIN_ID`가 서로 같아야 합니다.

1. 시뮬레이션

```bash
ros2 launch nav2_bringup tb4_simulation_launch.py headless:=False
```

2. 대시보드 (rosbridge + 웹 서버)

```bash
bash ~/project_lift/scripts/dashboard.sh
```

3. Gazebo 화면 중계

```bash
python3 ~/project_lift/scripts/gz_view_server.py
```

4. Windows 브라우저에서 `http://localhost:8080/ops.html`을 엽니다.

## 사용 순서

1. 맨 위 상태 표시가 모두 초록색이 되는지 봅니다 (ROS 연결, Gazebo 화면, 내비게이션).
2. **시작 순서**에서 [출발점으로 지정]을 누릅니다. 로봇이 출발점에 있을 때만 누르세요.
3. 몇 초 뒤 "내비게이션 준비"가 초록색이 되면 [충전소] 또는 [선반 A]를 누릅니다.
4. 이동 중에는 직접 운전 버튼이 잠깁니다. 멈추려면 [이동 취소]를 누릅니다.

화면 시점 버튼과 시뮬레이션 버튼(일시정지, 다시 진행, 한 단계만, 처음 상태로)은 실제 Gazebo에 명령을 보냅니다. [처음 상태로]를 누르면 로봇 위치가 초기화되므로 [출발점으로 지정]을 다시 눌러야 합니다.

## 선택 사항

- **Mission Manager**: `ros2 run amr_agent mission_manager`가 실행 중이면 장소 좌표를 `/resolve_location`에서 받아오고, [Mission Manager 상태 조회] 버튼이 동작합니다. 실행 중이 아니면 대시보드 안의 기본 좌표(dock 0,0 / shelf_a 2,1)를 씁니다.
- **화면 중계 설정** (`gz_view_server.py` 실행 전에 지정):

| 변수 | 기본값 | 설명 |
|---|---|---|
| `GZ_VIEW_PORT` | 8090 | 중계 서버 포트 |
| `GZ_WORLD` | depot | Gazebo 월드 이름 |
| `GZ_VIEW_FPS` | 10 | 초당 장수 |
| `GZ_VIEW_WIDTH` | 960 | 영상 폭 |
| `GZ_VIEW_CROP` | (켜짐) | `0`이면 3D 화면만 자르지 않고 Gazebo 창 전체를 보냄 |

## 안전과 한계

- 모든 서버는 `127.0.0.1`에만 열립니다. 같은 PC의 브라우저에서만 접속할 수 있습니다.
- `gz_view_server.py`는 정해 둔 Gazebo 서비스(시점 이동, 따라가기, 일시정지, 진행, 한 단계, 초기화)만 호출하고, 셸 명령은 실행하지 않습니다.
- 대시보드 영상은 보기 전용입니다. Gazebo 창처럼 마우스로 시점을 돌릴 수는 없습니다.
- Gazebo 창이 세로로 길면 영상 양옆에 여백이 생깁니다. Gazebo 창을 가로로 넓히세요.
- Gazebo 창을 최소화하거나 다른 창이 가렸을 때 캡처가 되는지는 확인하지 않았습니다.
- 이동 진행률은 위치를 기준으로 계산한 대략값입니다.
