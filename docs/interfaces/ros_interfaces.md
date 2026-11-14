속도 명령
- 토픽: /cmd_vel
- 형식: geometry_msgs/msg/Twist
- linear.x: 전진·후진 속도 (m/s)
- angular.z: 회전 속도 (rad/s)

좌표계 이름
- map: 저장된 지도 기준
- odom: 바퀴 이동으로 계산한 기준
- base_link: 로봇 중심
## 메카넘 구동 검토

보유 장비 Raspbot V2는 제조사 자료상 메카넘 휠과 독립 구동 모터를 사용합니다. examples/manual/manual_jiy.py는 수동모드 시험용으로 Flask 요청을 Raspbot_Lib 모터 명령으로 바꾸며, ROS/Gazebo 연동은 하지 않습니다. 전진·후진·제자리 좌우회전·정지만 제공합니다. 현재 ROS 초안도 linear.x와 angular.z만 정의해 이 버튼 동작을 대응시킬 수 있지만 횡이동 명령은 정의하지 않았습니다.

Gazebo에서 기존 버튼 동작만 재현하는 첫 단계는 linear.x와 angular.z로 구성할 수 있습니다. 메카넘의 횡이동까지 지원할지는 별도 범위 결정이 필요합니다. 기존 Flask 명령을 Gazebo 출력으로 바꾸는 경로와 ROS 노드 경계도 함께 정해야 합니다. 공통 제어 인터페이스는 다음 중 선택해야 합니다.

- geometry_msgs/msg/Twist를 사용할 경우 linear.y를 횡이동으로 정의하고, 실물 드라이버와 Gazebo 플러그인의 축·부호·단위를 맞춥니다.
- 또는 실물 모터 드라이버에 맞춘 하위 인터페이스를 두고 공통 주행 명령으로 변환합니다.

[Yahboom 제품 안내](https://www.yahboom.store/collections/raspberry-pi-5-series/products/raspbot-v2)는 ROS 2 Humble 기준을 제시합니다. 팀 표준 Jazzy 환경에서 제조사 드라이버를 그대로 사용할 수 있는지는 확인되지 않았습니다. Pi에서 동작 중인 수동조작 방식과 패키지·ROS 의존성을 먼저 확인합니다. 이 내용은 검토 사항이며 인터페이스 확정이나 구현 완료를 뜻하지 않습니다.



