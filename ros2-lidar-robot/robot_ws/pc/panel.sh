#!/usr/bin/env bash
# On your PC: the robot control panel in your web browser (live map, drive, modes, e-stop, click-to-go).
#   ./pc/panel.sh          then open  http://localhost:8080
. "$(dirname "$0")/_common.sh"
URL="http://localhost:${PANEL_PORT:-8080}"
echo "Starting the panel... open $URL  (Ctrl+C to quit)"
( sleep 4; command -v xdg-open >/dev/null && xdg-open "$URL" >/dev/null 2>&1 ) &
exec $DOCKER run --rm -it --net=host --ipc=host "${ENVARGS[@]}" \
  -v "$ROOT/pc/web_panel:/panel:ro" "$IMAGE" \
  bash -c "source /opt/ros/jazzy/setup.bash && python3 /panel/panel.py --port ${PANEL_PORT:-8080}"
