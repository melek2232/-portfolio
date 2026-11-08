#!/usr/bin/env bash
# On your PC: RViz (alternative to the web panel).  Needs X11:  xhost +local:docker
. "$(dirname "$0")/_common.sh"
xhost +local:docker >/dev/null 2>&1
exec $DOCKER run --rm -it --net=host --ipc=host "${ENVARGS[@]}" \
  -e DISPLAY="$DISPLAY" -e LIBGL_ALWAYS_SOFTWARE=1 -v /tmp/.X11-unix:/tmp/.X11-unix \
  -v "$ROOT/src/robot_base/rviz:/rviz:ro" "$IMAGE" \
  bash -c "source /opt/ros/jazzy/setup.bash && rviz2 -d /rviz/mapping.rviz"
