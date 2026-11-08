# Sourced by the pc/*.sh scripts. The Pi runs ROS 2 Jazzy: on the PC everything ROS runs in a Jazzy
# container (a native Lyrical install cannot reliably exchange data with a Jazzy robot).
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
set -a; [ -f "$ROOT/robot.env" ] && . "$ROOT/robot.env"; set +a
IMAGE="${ROS_IMAGE:-osrf/ros:jazzy-desktop}"
if docker info >/dev/null 2>&1; then DOCKER="docker"; else DOCKER="sudo docker"; fi
ENVARGS=(-e "ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-42}")
[ -n "$ROS_STATIC_PEERS" ] && ENVARGS+=(-e "ROS_STATIC_PEERS=$ROS_STATIC_PEERS")
[ -n "$ROS_AUTOMATIC_DISCOVERY_RANGE" ] && ENVARGS+=(-e "ROS_AUTOMATIC_DISCOVERY_RANGE=$ROS_AUTOMATIC_DISCOVERY_RANGE")
ros_run() {   # ros_run "shell command"  (non-interactive, host network)
  $DOCKER run --rm --net=host "${ENVARGS[@]}" "$IMAGE" bash -c "source /opt/ros/jazzy/setup.bash && $1"
}
