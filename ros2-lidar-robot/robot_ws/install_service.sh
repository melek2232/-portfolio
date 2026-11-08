#!/usr/bin/env bash
# On the Pi, once: the robot software starts at boot (in mode 'stop': the robot will NOT move by itself).
#   ./install_service.sh          install + enable        ./install_service.sh remove   uninstall
# Then: sudo systemctl status robot     journalctl -u robot -f     sudo systemctl restart robot
set -e
cd "$(dirname "$0")"
if [ "$1" = "remove" ]; then
  sudo systemctl disable --now robot 2>/dev/null || true
  sudo rm -f /etc/systemd/system/robot.service
  sudo systemctl daemon-reload
  echo "service removed"; exit 0
fi
sed -e "s#__USER__#$USER#g" -e "s#__DIR__#$PWD#g" src/robot_base/service/robot.service \
  | sudo tee /etc/systemd/system/robot.service >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable --now robot
echo "installed. Status: sudo systemctl status robot"
