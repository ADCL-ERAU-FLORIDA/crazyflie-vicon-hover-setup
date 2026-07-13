# Crazyflie 2.1 + Vicon Hover Test Setup

Replication guide and lab code for hover / trajectory testing of a Crazyflie 2.1 using Vicon motion capture in place of GPS, with off-board raw-PWM control. Developed and used at the Advanced Dynamics and Control Lab (ADCL), Embry-Riddle Aeronautical University, building on the USC-CATT Crazyflie stack.

The controller runs on a laptop and sends raw PWM motor commands directly to the four Crazyflie motors. This requires the USC-CATT firmware fork — stock Bitcraze firmware does not expose the raw motor-command path.

## System architecture

```
Vicon Cameras
    ↓
Vicon PC (Tracker / Nexus / Shogun)          192.168.10.1
    ↓  Ethernet
Laptop: vicon_bridge_cpp/live_tracking_bridge
    ↓  UDP 127.0.0.1:51001  (x y z qx qy qz qw, metres, ~200 fps)
Python controller (pid_pwm_position_viconpos.py)
    ↓  Crazyradio USB dongle (CRTP raw-motor port)
Crazyflie 2.1 running USC-CATT firmware
    ↓
Raw PWM to motors 1–4
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full runtime dependency graph of the controller scripts.

## External dependencies (cloned/installed separately — NOT included here)

| Dependency | How to get it |
|---|---|
| USC-CATT Crazyflie firmware | `git clone https://github.com/USC-CATT/crazyflie-firmware` then **`git submodule update --init --recursive`** (mandatory — empty `vendor/CMSIS` breaks the build with a missing `arm_math.h`) |
| USC-CATT controller stack | `git clone https://github.com/USC-CATT/sala4_crazyflie` (this repo's `cflib_python/` is the lab's working snapshot of its `cflib_python` folder) |
| Bitcraze cflib + cfclient | `pip3 install cflib cfclient` |
| Crazyradio USB permissions | [Bitcraze udev rules guide](https://www.bitcraze.io/documentation/repository/crazyflie-lib-python/master/installation/usb_permissions/) |
| Vicon DataStream SDK 1.12 | [Download from Vicon](https://www.vicon.com/downloads/utilities-and-sdk/datastream-sdk) — proprietary, cannot be redistributed here. Extract to `~/vicon-datastream-sdk-1.12` and add `Release/Linux64` to `LD_LIBRARY_PATH` |

Full step-by-step from a bare Ubuntu 22.04 machine: [docs/SETUP_GUIDE.md](docs/SETUP_GUIDE.md).

## Quick start (after one-time setup)

**Pre-flight — every time:**

1. Vicon cameras calibrated, Crazyflie subject created and visible (subject name is case-sensitive, e.g. `Crazy_Test`).
2. Verify the drone's radio URI in `cfclient` (Connect → Scan). Channel/address vary per drone — `radio://0/100/2M/E7E7E7E701` is this lab's example, **yours may differ. Never assume another drone's URI.**
3. Propellers off for any bench/motor test; clear flight area, props on, for flight.

**Terminal 1 — Vicon bridge:**

```bash
cd ~/ros2_ws/src/sala4_crazyflie/cflib_python/vicon_bridge_cpp
./live_tracking_bridge 192.168.10.1 Crazy_Test 51001
#                      ^Vicon PC IP  ^subject   ^local UDP port
```

Healthy output looks like `[Vicon] ~200 fps | ... | errors 0`. Do not fly on zero packets or unstable fps.

**Terminal 2 — hover/trajectory controller:**

```bash
cd ~/ros2_ws/src/sala4_crazyflie/cflib_python
python3 pid_pwm_position_viconpos.py --uri radio://0/100/2M/E7E7E7E701 --loop-hz 100
```

`--loop-hz 100` keeps the control loop below the 200 Hz Vicon frame rate so every control step uses a fresh pose. (Lab data from 2026-07-09 showed clearly degraded tracking at 50 Hz — see the [results repo](https://github.com/ADCL-ERAU-FLORIDA/Summer-2026-K12-Intern-Crazyflie-Vicon-Test-Results).)

**Keep the controller terminal focused. SPACEBAR = kill all motors.** Full rules: [docs/SAFETY.md](docs/SAFETY.md).

## What is in this repo

```
cflib_python/            Lab working snapshot of the flight scripts
├── pid_pwm_position_viconpos.py    ← preferred controller (Vicon position via
│                                     send_extpos; onboard EKF handles attitude)
├── pid_pwm_position_viconpose.py   ← full-pose variant (orientation-flip sensitive)
├── motorRawTest.py                 ← raw-motor sanity test (props OFF)
├── vicon_bridge.py                 ← UDP listener the controllers import
├── vicon_bridge_cpp/
│   └── live_tracking_bridge.cpp    ← Vicon SDK → UDP forwarder (build locally)
├── controller/                     ← reusable cascaded-PID library
│   └── pid_constants.py            ← ALL gains live here (the tuning knob)
└── ... further variants and utilities (see docs/ARCHITECTURE.md)
docs/                    Setup guide, safety, troubleshooting, architecture, original PDFs
```

The compiled `live_tracking_bridge` binary is intentionally not committed. Build it against your SDK install:

```bash
cd cflib_python/vicon_bridge_cpp
g++ -std=c++17 live_tracking_bridge.cpp -o live_tracking_bridge \
    -I"$SDK_LIB" -L"$SDK_LIB" -lViconDataStreamSDK_CPP -Wl,-rpath,"$SDK_LIB"
# SDK_LIB = .../vicon-datastream-sdk-1.12/<build-hash>/Release/Linux64
```

## Related repositories

- Test results and analysis: [Summer-2026-K12-Intern-Crazyflie-Vicon-Test-Results](https://github.com/ADCL-ERAU-FLORIDA/Summer-2026-K12-Intern-Crazyflie-Vicon-Test-Results)
- Upstream: [USC-CATT/crazyflie-firmware](https://github.com/USC-CATT/crazyflie-firmware), [USC-CATT/sala4_crazyflie](https://github.com/USC-CATT/sala4_crazyflie)
- Reference work: [OmAcharya-avtr/crazyflie-missions](https://github.com/OmAcharya-avtr/crazyflie-missions), [OmAcharya-avtr/crazyflie-usc-workspace](https://github.com/OmAcharya-avtr/crazyflie-usc-workspace)
