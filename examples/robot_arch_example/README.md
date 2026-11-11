# 간단한 Pi/Gazebo 코드 구조 예제

- `controller.py`: 키 입력과 공통 제어 흐름
- `drive.py`: 키를 좌우 바퀴 속도(-100~100)로 변환
- `pi_output.py`: 공통 바퀴 속도를 Raspbot 모터 명령으로 전달
- `gazebo_output.py`: 같은 값을 ROS 2 `/cmd_vel`로 전달
- `main.py`: 실행할 출력부 선택

`main.py`의 `MODE`를 `"pi"` 또는 `"gazebo"`로 설정하세요. 입력은 W/S 전후진, A/D 회전 조합, X 정지, Q 종료이며 Enter를 눌러 명령을 전송합니다.

Gazebo에서는 ROS 2 Jazzy 환경을 source한 뒤 실행하고, 로봇 모델이 `/cmd_vel`을 구독하도록 구성해야 합니다. Raspberry Pi 모드에서는 `Raspbot_Lib`가 설치되어 있어야 합니다. Gazebo 변환 상수는 모델에 맞춘 실측 조정이 필요한 예시값입니다.
