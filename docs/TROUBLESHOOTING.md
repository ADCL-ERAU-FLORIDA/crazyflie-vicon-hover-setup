# Troubleshooting

## Firmware build fails with missing `arm_math.h`

Cause: submodules not initialized.

```bash
cd ~/crazyflie-firmware
git submodule update --init --recursive
make clean && make cf2_defconfig && make -j$(nproc)
```

## Crazyradio not detected

`lsusb | grep -i bitcraze` — if missing: unplug/reconnect the Crazyradio, try a different USB port, check the cable/adapter.

## Permission denied when using Crazyradio

`groups | grep plugdev` — if not in the group: install the Bitcraze udev rules, log out and back in, replug the radio.

## Scan finds no Crazyflie

Check: powered on · battery charged · Crazyradio plugged in · correct firmware flashed · drone not in bootloader mode · radio channel/address may differ from what you expect (verify in cfclient). Rescan:

```bash
python3 -c "import cflib.crtp; cflib.crtp.init_drivers(); print(cflib.crtp.scan_interfaces())"
```

## Raw motor test connects but motors do not spin

Likely: stock Bitcraze firmware flashed (no raw motor path), wrong script URI, or the script failed silently. Fix: reflash USC-CATT firmware, confirm `motorRawTest.py` uses your scanned URI, run with props off.

## Laptop cannot ping Vicon PC

`ping 192.168.10.1`. If it fails: Ethernet cable, correct interface, static IP set (laptop must be `192.168.10.2/24`, Vicon PC `192.168.10.1`), no other interface on the same subnet.

## Bridge connects but streams zero packets

Most common cause: **wrong Vicon subject name.** Check the exact subject/object name in the Vicon software (capitalization and underscores) and pass the identical string:

```bash
./live_tracking_bridge 192.168.10.1 Crazy_Test 51001
```

## Drone takes off but drifts badly

Possible: Vicon origin misaligned, noisy Vicon data, wrong coordinate convention, over-aggressive gains, hover height too high for a first test, incorrect motor mixing, battery voltage sag. Action: `SPACEBAR`; lower hover height; verify Vicon position data; retune gains (`controller/pid_constants.py`); test a smaller trajectory.

## Drone flips immediately

Possible: motor order mismatch, sign error in the control law, incorrect attitude/axis convention, bad Vicon orientation if using `send_extpose`, incorrect motor mixing. Action: `SPACEBAR` immediately; use `pid_pwm_position_viconpos.py` (extpos) instead of `pid_pwm_position_viconpose.py`; verify motor order, coordinate signs, and PWM mixing.
