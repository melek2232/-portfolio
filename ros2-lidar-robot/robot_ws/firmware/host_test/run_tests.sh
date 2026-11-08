#!/usr/bin/env bash
# Compiles the sketch with PC stubs and runs its tests (needs g++). Not needed on the robot.
set -e
cd "$(dirname "$0")"
g++ -std=c++11 -Wall -Wextra -DHOST_FAKE_TIME -I. unit_test.cpp host_stubs.cpp -o /tmp/mega_unit_test
/tmp/mega_unit_test
