#!/usr/bin/env bash
# Downloads rf2o_laser_odometry (lidar odometry, MAPIRlab, GPL-3.0) into src/, pinned to a tested commit.
# Called by setup_pi.sh and setup_pc.sh. Not stored in this repository (third-party code, own licence).
set -e
cd "$(dirname "$0")"
REPO=https://github.com/MAPIRlab/rf2o_laser_odometry.git
COMMIT=b38c68e    # branch ros2, tested with ROS 2 Jazzy
DIR=src/rf2o_laser_odometry
if [ ! -d "$DIR/.git" ]; then
  echo ">> Downloading rf2o_laser_odometry"
  git clone -q -b ros2 "$REPO" "$DIR"
fi
git -C "$DIR" fetch -q origin ros2 || true
git -C "$DIR" checkout -q "$COMMIT"
echo ">> rf2o_laser_odometry at $(git -C "$DIR" rev-parse --short HEAD)"
