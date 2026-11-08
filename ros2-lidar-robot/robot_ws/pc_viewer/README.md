# pc_viewer: see the lidar data and the generated map on your PC (no ROS, no Gazebo)

Works on Windows, Linux and macOS with Python 3.9+.

    pip install numpy matplotlib pyserial pillow

## 1. Simulation (no hardware)
    python viewer.py sim
A virtual robot explores the room. Left: the live lidar scan, with rate, points and nearest obstacle.
Right: the occupancy map being built (black = wall, white = free, grey = unknown), plus the robot path.

## 2. Your real YDLIDAR X2 plugged into the PC
    python viewer.py live COM5            (Windows: Device Manager > Ports)
    python viewer.py live /dev/ttyUSB0    (Linux: sudo usermod -aG dialout $USER first)
    python viewer.py live COM5 --csv scan.csv     (also records every point)
Same two panels. The map is built around the lidar's fixed position, with no motion estimate: keep the
lidar still, or move it slowly and press `r` to restart the map. A map while the robot drives needs the ROS
version (SLAM).

Keys: `r` reset map, `s` save map to `~/maps/map_*.pgm` + `.yaml` (usable by Nav2), `q` quit.
Options: `--max-range 8`, `--baud 115200`. Other lidars (X4, G4) use another protocol and are not supported here.
Test without any window: `python viewer.py sim --save out.png --seconds 60`, `python test_x2.py`.
