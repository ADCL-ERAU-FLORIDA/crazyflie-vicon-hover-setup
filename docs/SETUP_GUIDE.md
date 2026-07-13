# Crazyflie 2.1 + Vicon Hover Replication Guide

**USC-CATT Firmware + `cflib_python` Off-Board Raw-PWM Control**

This guide explains how to set up a Crazyflie 2.1 for hover testing using Vicon motion capture, the USC-CATT Crazyflie firmware fork, and the USC-CATT `sala4_crazyflie/cflib_python` controller stack. It starts from a bare Ubuntu 22.04 machine and an unflashed Crazyflie, and ends with a working Vicon-based hover test.

The controller runs on the laptop and sends raw PWM motor commands directly to the four Crazyflie motors. Because of this, the USC-CATT firmware fork is required — stock Bitcraze firmware does not expose the required raw motor-command path.

*(This is the markdown transcription of the original "Crazyflie 2.1 Vicon Test (Descriptive)" PDF, archived in `docs/pdf/`.)*

## 0. System Overview

### 0.1 What this setup does

```
Vicon Cameras
    ↓
Vicon PC / Vicon Tracker / Nexus / Shogun
    ↓
Ethernet Network
    ↓
Laptop running Vicon bridge
    ↓
UDP pose stream on localhost
    ↓
Python controller in cflib_python
    ↓
Crazyradio USB dongle
    ↓
Crazyflie 2.1 running USC-CATT firmware
    ↓
Raw PWM commands to motors
```

### 0.2 Main software components

| Component | Purpose |
|---|---|
| USC-CATT `crazyflie-firmware` | Firmware flashed to the Crazyflie. Adds raw motor command support. |
| USC-CATT `sala4_crazyflie` | Contains Python controllers, Vicon bridge code, tests, and mission scripts. |
| Bitcraze `cflib` | Python library for communicating with the Crazyflie through Crazyradio. |
| Bitcraze `cfclient` | GUI used for flashing and basic Crazyflie testing. |
| Vicon DataStream SDK 1.12 | Allows the laptop to receive live Vicon tracking data. |
| `live_tracking_bridge` | Reads Vicon pose data and forwards it to Python through UDP. |
| `pid_pwm_position_viconpos.py` | Preferred hover controller using Vicon position and onboard EKF attitude. |

## 1. Target Folder Layout

After setup, the home folder should look like this:

```
~/crazyflie-firmware/
~/ros2_ws/
└── src/
    └── sala4_crazyflie/
        └── cflib_python/
            ├── motorRawTest.py
            ├── pid_pwm_position_viconpos.py
            ├── pid_pwm_position_viconpose.py
            ├── vicon_bridge.py
            └── vicon_bridge_cpp/
~/vicon-datastream-sdk-1.12/
```

All commands in this guide use `~`, so they work regardless of Linux username.

## 2. Hardware Required

| Item | Purpose |
|---|---|
| Crazyflie 2.1 | Drone being controlled. |
| Crazyradio PA / Crazyradio 2.0 | Radio link between laptop and Crazyflie. |
| Vicon camera system | Provides external motion capture position data. |
| Vicon PC | Runs Nexus, Tracker, or Shogun. |
| Ubuntu 22.04 laptop/desktop | Runs firmware tools, Vicon bridge, and Python controller. |
| Ethernet connection to Vicon network | Required for live Vicon streaming. |
| Battery for Crazyflie | Flight power. |
| Clear flight area / net / safety setup | Required for testing. |

## 3. Safety Rules

This setup sends raw PWM directly to the motors. **There is no high-level onboard safety controller protecting the vehicle from bad commands.**

Before every test:

1. Remove propellers for installation, flashing, and raw motor tests.
2. Secure the drone during the first motor test.
3. Keep the controller terminal focused during flight.
4. Press `SPACEBAR` to kill the motors immediately.
5. Keep one hand near the keyboard during every flight test.
6. Use a low hover height for first tests.
7. Do not run the controller in a background or headless terminal.
8. Do not fly if Vicon tracking is unstable or the subject is not visible.
9. Do not fly if the Vicon bridge shows zero packets.
10. Do not assume another drone's URI. Always scan for your own.

Emergency controls:

| Key | Action |
|---|---|
| `SPACEBAR` | Kill all motors immediately. |
| `1`–`4` | Trim motor 1–4 to 0.65×. |

## 4. Install Bitcraze cflib, cfclient, and USB Permissions

```bash
sudo apt update
sudo apt install -y git python3-pip
pip3 install cflib
pip3 install cfclient
```

The Crazyradio must be usable without `sudo`. Follow the official [Bitcraze USB permissions guide](https://www.bitcraze.io/documentation/repository/crazyflie-lib-python/master/installation/usb_permissions/). After installing the udev rules, log out and back in (or reboot), then verify:

```bash
groups | grep plugdev
lsusb | grep -i bitcraze
```

Your user must be in `plugdev` and the Bitcraze dongle detected. If not detected, unplug and reconnect the Crazyradio.

## 5. Clone and Build the USC-CATT Firmware

```bash
cd ~
git clone https://github.com/USC-CATT/crazyflie-firmware.git
cd ~/crazyflie-firmware
git submodule update --init --recursive     # REQUIRED
ls ~/crazyflie-firmware/vendor/CMSIS        # must not be empty
```

If `vendor/CMSIS` is empty the build fails with a missing `arm_math.h` — rerun the submodule command.

```bash
sudo apt install -y swig make gcc-arm-none-eabi build-essential
cd ~/crazyflie-firmware
make cf2_defconfig
make -j$(nproc)
ls -lh ~/crazyflie-firmware/build/cf2.bin   # expected output file
```

Optional Python bindings (only if scripting directly against firmware bindings): `make bindings_python`.

## 6. Flash the Crazyflie

### 6.1 GUI method (preferred)

1. Hold the Crazyflie power button ~3 s until the blue LEDs blink (bootloader mode).
2. Plug in the Crazyradio.
3. Run `cfclient`.
4. Connect → Bootloader tab → Initiate bootloader cold boot → browse to `~/crazyflie-firmware/build/cf2.bin` → Program.
5. Wait until all pages are written; restart the Crazyflie normally.

### 6.2 CLI method

```bash
cd ~/crazyflie-firmware
make cload
```

Drone must be in bootloader mode with the Crazyradio plugged in.

## 7. Clone the USC-CATT Controller Stack

```bash
mkdir -p ~/ros2_ws/src
cd ~/ros2_ws/src
git clone https://github.com/USC-CATT/sala4_crazyflie.git
cd ~/ros2_ws/src/sala4_crazyflie/cflib_python
ls   # expect motorRawTest.py, pid_pwm_position_viconpos.py, pid_pwm_position_viconpose.py, vicon_bridge.py, vicon_bridge_cpp/
```

*(This repo's `cflib_python/` folder is the ADCL working snapshot of that directory, including local modifications — you can substitute it in.)*

## 8. Find the Crazyflie Radio URI

Every Crazyflie has its own radio URI. **Do not reuse another lab drone's URI.**

```bash
python3 -c "import cflib.crtp; cflib.crtp.init_drivers(); print(cflib.crtp.scan_interfaces())"
```

Example output: `[('radio://0/100/2M/E7E7E7E701', 'Crazyflie')]` → URI `radio://0/100/2M/E7E7E7E701`. Yours may differ (channel and address are per-drone; you can also verify in the `cfclient` GUI via Scan). Use your scanned URI in every controller script.

## 9. Run Raw Motor Sanity Test

Confirms the Crazyradio works, the firmware accepts raw motor commands, and all four motors respond. **Remove propellers or secure the drone first.**

```bash
cd ~/ros2_ws/src/sala4_crazyflie/cflib_python
python3 motorRawTest.py
```

If the script has a hardcoded URI, replace it with your scanned URI. Expected: all four motors spin briefly.

| Problem | Likely cause |
|---|---|
| No radio link | Wrong URI or Crazyradio permission issue. |
| Connects but motors do not spin | Stock firmware flashed instead of USC-CATT. |
| Permission denied | udev rules not installed or user not in `plugdev`. |
| Only some motors spin | Motor, wiring, or hardware issue. |

## 10. Install Vicon DataStream SDK 1.12

Download [Vicon DataStream SDK 1.12 for Linux x64](https://www.vicon.com/downloads/utilities-and-sdk/datastream-sdk) to `~/Downloads`, then:

```bash
sudo apt install -y unzip build-essential
mkdir -p ~/vicon-datastream-sdk-1.12
unzip -o ~/Downloads/ViconDataStreamSDK_1.12_*.zip -d ~/vicon-datastream-sdk-1.12
ls ~/vicon-datastream-sdk-1.12    # extracts into a build-hash folder, e.g. 20230413_145507h/
SDK_LIB=~/vicon-datastream-sdk-1.12/<build-hash>/Release/Linux64
ls "$SDK_LIB"                     # expect DataStreamClient.h and libViconDataStreamSDK_CPP.so
echo 'export LD_LIBRARY_PATH="'"$SDK_LIB"':${LD_LIBRARY_PATH}"' >> ~/.bashrc
source ~/.bashrc
echo "$LD_LIBRARY_PATH"           # should include the SDK Release/Linux64 folder
```

## 11. Configure the Vicon Network

The Vicon PC uses `192.168.10.1`. Configure the laptop's second Ethernet interface statically (no DHCP on this subnet):

| Setting | Value |
|---|---|
| IPv4 address | `192.168.10.2` |
| Netmask | `255.255.255.0` (`/24`) |
| Gateway | `192.168.10.1` |

Ubuntu GUI: Settings → Network → Wired → IPv4 → Manual. CLI: `nmcli con up "Wired connection 1"`. Then:

```bash
ping 192.168.10.1   # do not continue until this succeeds
```

## 12. Configure the Vicon Scene

On the Vicon PC (Nexus / Tracker / Shogun):

1. Mask the cameras.
2. Calibrate the system if needed.
3. Place the Crazyflie in the capture volume.
4. Create a subject/object for the Crazyflie.
5. Name the subject and write down the exact name — example: `Crazy_Test`.

The subject name is **case-sensitive** and must match exactly when running the bridge. If the bridge connects but streams zero packets, the subject name is usually wrong.

## 13. Test Vicon SDK Connectivity

```bash
cd ~/vicon-datastream-sdk-1.12
./smoke_test           # prints SDK version and connection status
./live_tracking_test   # lists live subject and segment names
```

Note: if `smoke_test` fails against `127.0.0.1:801` that only means no *local* Vicon server exists — the real server is `192.168.10.1`. The live tracking test must show your subject (e.g. `Crazy_Test`). **Do not attempt flight until live tracking works.**

## 14. Start the Vicon Bridge

The bridge reads Vicon pose over Ethernet and forwards it locally to the Python controller through UDP. Run it in its own terminal on the same computer as the controller:

```bash
cd ~/ros2_ws/src/sala4_crazyflie/cflib_python/vicon_bridge_cpp
./live_tracking_bridge 192.168.10.1 Crazy_Test 51001
```

| Argument | Meaning |
|---|---|
| `192.168.10.1` | Vicon PC IP address. |
| `Crazy_Test` | Vicon subject name (case-sensitive). |
| `51001` | Local UDP port the Python controller listens on. |

Expected healthy output: `[Vicon] ~200 fps | ... | errors 0`. The bridge streams `x y z qx qy qz qw` in metres to `127.0.0.1:51001`.

| Symptom | Fix |
|---|---|
| Connected but 0 packets | Subject name mismatch. |
| Cannot connect | Network issue or Vicon PC not reachable. |
| Low/unstable FPS | Vicon tracking problem. |
| Subject disappears | Markers not visible or object not reconstructed. |

## 15. Run the Hover Controller

Separate terminal; keep it **focused** during flight (the spacebar killswitch depends on the active terminal window):

```bash
cd ~/ros2_ws/src/sala4_crazyflie/cflib_python
python3 pid_pwm_position_viconpos.py --uri radio://0/100/2M/E7E7E7E701 --loop-hz 100
```

`--loop-hz 100` keeps the control loop below the Vicon frame rate (200 Hz) so each step consumes a fresh pose.

Preferred controller: `pid_pwm_position_viconpos.py` — sends Vicon *position only* via `send_extpos`; the onboard EKF handles attitude, making it robust to Vicon orientation flips. Alternative: `pid_pwm_position_viconpose.py` (full pose) — use only if the Vicon subject orientation is stable and axis-aligned.

## 16. Controller Parameters to Check Before Flight

| Parameter | What to set |
|---|---|
| URI | Your scanned Crazyflie URI. |
| `HOVER_HEIGHT` | Start low for first tests. |
| `USER_DEFINED_TRAJECTORY` | Desired hover or waypoint trajectory. |
| Landing behavior | Default auto-lands to 0.05 m after the final waypoint. |
| `--no-land` | Only to intentionally disable auto-landing. |

The controller logs position and setpoint data to `waypoint_data.json` (overwritten each run).

## 17. Recommended First Flight Procedure

Pre-flight checklist: USC-CATT firmware flashed · Crazyradio detected · correct URI in the controller · raw motor test passed · Vicon PC reachable at `192.168.10.1` · subject created, visible, name matches the bridge argument exactly · bridge shows ~200 fps · controller terminal focused · spacebar physically reachable · flight area clear · battery charged.

Terminal 1:
```bash
cd ~/ros2_ws/src/sala4_crazyflie/cflib_python/vicon_bridge_cpp
./live_tracking_bridge 192.168.10.1 Crazy_Test 51001
```

Terminal 2:
```bash
cd ~/ros2_ws/src/sala4_crazyflie/cflib_python
python3 pid_pwm_position_viconpos.py --uri <YOUR_URI> --loop-hz 100
```

During flight watch: bridge packet rate, height, drift, oscillation, controller terminal. Press `SPACEBAR` immediately if the drone tilts, climbs too fast, loses tracking, or behaves unpredictably.

## 18. Adding a Custom Controller

Each controller is a standalone Python script in `cflib_python/`; no reflashing needed for off-board changes.

```bash
cp pid_pwm_position_viconpos.py my_controller.py
```

Keep the required plumbing: Vicon UDP intake, `vicon_bridge.py` interface, `send_extpos` logic, logging, spacebar killswitch, raw motor output call, URI setup. Replace only the control-law section:

```
Current position from Vicon → Desired position/trajectory → Position error
→ Velocity/derivative estimate → Control law → Desired thrust and torques
→ Motor mixing → Raw PWM for motors 1–4 → Send raw motor command through cflib
```

Existing examples: `augmented_pid_pwm_position.py`, `mellinger_pwm_position.py`.

## 19. Troubleshooting

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

## 20. Quick Start Command Summary

Terminal 1: `./live_tracking_bridge 192.168.10.1 Crazy_Test 51001` (from `vicon_bridge_cpp/`)
Terminal 2: `python3 pid_pwm_position_viconpos.py --uri <YOUR_URI> --loop-hz 100` (from `cflib_python/`)
Emergency stop: `SPACEBAR`.

## 21. Reference Links

- USC-CATT organization: https://github.com/USC-CATT
- USC-CATT Crazyflie firmware: https://github.com/USC-CATT/crazyflie-firmware
- USC-CATT sala4_crazyflie: https://github.com/USC-CATT/sala4_crazyflie
- Bitcraze cflib install: https://www.bitcraze.io/documentation/repository/crazyflie-lib-python/master/installation/install/
- Bitcraze cfclient install: https://www.bitcraze.io/documentation/repository/crazyflie-clients-python/master/installation/install/
- Bitcraze USB permissions: https://www.bitcraze.io/documentation/repository/crazyflie-lib-python/master/installation/usb_permissions/
- Vicon DataStream SDK: https://www.vicon.com/software/datastream-sdk/
- Related reference work: https://github.com/OmAcharya-avtr/crazyflie-missions · https://github.com/OmAcharya-avtr/crazyflie-usc-workspace
