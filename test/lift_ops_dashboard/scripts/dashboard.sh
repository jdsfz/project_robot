#!/usr/bin/env bash
# 초보자용 웹 대시보드:  bash ~/project_lift/scripts/dashboard.sh
#   rosbridge(ws://localhost:9090) 와 웹 서버(http://localhost:8080) 를 함께 켠다.
#   Windows 브라우저에서 http://localhost:8080 을 연다. Ctrl+C 로 둘 다 끈다.
source ~/lift.sh >/dev/null
DIR=$(cd "$(dirname "$0")/../dashboard" && pwd)

ros2 launch rosbridge_server rosbridge_websocket_launch.xml use_sim_time:=true &
BRIDGE=$!
python3 -m http.server 8080 --bind 127.0.0.1 --directory "$DIR" >/dev/null 2>&1 &
WEB=$!
trap 'kill $BRIDGE $WEB 2>/dev/null; wait 2>/dev/null; echo "[대시보드] 종료"' INT TERM EXIT

echo "[대시보드] 브라우저에서 http://localhost:8080 을 여세요 (끄려면 Ctrl+C)"
wait
