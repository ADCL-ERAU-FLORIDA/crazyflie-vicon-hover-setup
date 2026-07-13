# Architecture and Runtime Dependency Graph

Upstream, `sala4_crazyflie/` is a ROS 2 workspace package holding three loosely-coupled things:

| Area | What it is | Relationship to the flight scripts |
|---|---|---|
| `cflib_python/` | Standalone host-side Python flight scripts (talk to the drone over Crazyradio via `cflib`) | **This repo's payload** |
| `sala4/` + `sala4_bringup/` | The ROS 2 packages proper (nodes, launch files, Crazyswarm2 config) | Separate — the ROS way of flying; not used by these scripts |
| `Crazyflie-simulator-main/`, `model/` | Offline simulator + SDF drone models | Independent; sim/testing only |

`pid_pwm_position_viconpos.py` is **not** a ROS node — it is a plain `python3` program that opens the radio itself. One wrinkle: it imports `motorRaw.py`, which imports `rclpy`/`actuator_msgs`, so a sourced ROS 2 environment must still be present even though the script runs directly.

## Runtime dependency graph of `pid_pwm_position_viconpos.py`

```
pid_pwm_position_viconpos.py          ← YOU RUN THIS (control loop + trajectory)
│
├── controller/                       ← cascaded-PID "brain" (pure Python, no ROS)
│   ├── controller_pid.py             ← top-level: ControllerPID.controller_pid()
│   │   ├── position_controller.py    ← outer loop: pos/vel error → desired attitude + thrust
│   │   ├── attitude_controller.py    ← inner loop: attitude/rate error → roll/pitch/yaw torques
│   │   │      ├── pid.py             ← generic PID primitive (used by both loops)
│   │   │      └── pid_constants.py   ← ALL gains live here — the single tuning file
│   │   └── controller_types.py       ← dataclasses: State, Setpoint, Control, Attitude…
│
├── motorRaw.py                       ← MotorRaw: packs 4 PWM values into a raw-motor CRTP packet
│   └── cflib.crtp.crtpstack          ← (external) low-level radio protocol
│
├── vicon_bridge.py                   ← ViconStateSource: UDP listener on 127.0.0.1:51001
│                                        (receives Vicon pose from live_tracking_bridge,
│                                         feeds the loop + the onboard EKF via send_extpos)
│
└── cflib.*                           ← (external pip package) Crazyflie, SyncCrazyflie, LogConfig…
```

### What each piece does in the loop

- **`pid_pwm_position_viconpos.py`** — owns the trajectory list, the timing loop (`--loop-hz`, run at 100 Hz to stay under the 200 Hz Vicon rate), keyboard kill/trim keys, JSON logging to `waypoint_data.json`, and the power-distribution/cap math turning controller output into 4 motor PWMs.
- **`controller/`** — the reusable ROS-free control library. The script feeds it `State`/`Setpoint`, gets back a `Control` (thrust + roll/pitch/yaw). `pid_constants.py` holds every gain.
- **`motorRaw.py`** — the only ROS-touching dependency; serializes motor commands onto the raw CRTP port, bypassing the firmware controller.
- **`vicon_bridge.py`** — decoupled position source. It does not talk to Vicon directly; it listens on UDP `127.0.0.1:51001` for pose packets published by `vicon_bridge_cpp/live_tracking_bridge` (or `vicon_bridge_test.py`).
- **`vicon_bridge_cpp/live_tracking_bridge.cpp`** — ~120-line C++ helper linking against the Vicon DataStream SDK; connects to the Vicon PC, extracts the subject's pose, and forwards `x y z qx qy qz qw` (metres) to the UDP port. Built locally (binary not committed):

```bash
g++ -std=c++17 live_tracking_bridge.cpp -o live_tracking_bridge \
    -I"$SDK_LIB" -L"$SDK_LIB" -lViconDataStreamSDK_CPP -Wl,-rpath,"$SDK_LIB"
```

## Controller variants (maintained by copy, not configuration)

The base script has several whole-file siblings differing in a few constants — hover height, trajectory, Vicon feedback mode (`extpos` vs `extpose` vs yaw-rotated), and logging:

- `pid_pwm_position_viconpos.py` — base, preferred
- `pid_pwm_position_viconpose.py` — full-pose feedback variant
- `pid_pwm_position.py` — pre-Vicon variant
- `augmented_pid_pwm_position.py`, `mellinger_pwm_position.py` — alternative control laws (Mellinger uses `controller/controller_mellinger.py` + `mellinger_constants.py`)

The shared, stable core is `controller/` — variants re-implement only the outer script, not the control library.

## Outputs / data flow

Each run overwrites `cflib_python/waypoint_data.json` (position + setpoint log). Terminal output is what the results repo's analysis scripts parse.
