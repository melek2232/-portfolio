# pc/: control the robot from your PC

Everything runs in a ROS 2 **Jazzy** Docker container (the Pi runs Jazzy). Needs Docker and the same `robot.env` as the Pi.

| Script | What it does |
|---|---|
| `panel.sh` | web panel at http://localhost:8080: live map + lidar, drive, modes, e-stop, click-to-go, map download |
| `rviz.sh` | RViz (needs X11: `xhost +local:docker`) |
| `teleop_keyboard.sh` | drive with the terminal keyboard (hold a key) |
| `mode.sh stop\|manual\|explore\|nav` | change the robot mode |
| `estop.sh [release]` | software emergency stop |

The panel listens on localhost only; commands need a random token that only the served page has (a web site you
visit cannot drive the robot through your browser). `web_panel/test_panel.py` tests it in a real browser.
