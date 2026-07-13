# Safety Rules

This setup sends **raw PWM directly to the motors**. There is no high-level onboard safety controller protecting the vehicle from bad commands. Treat every armed session as live.

## Before every test

1. **Remove propellers** for installation, flashing, and raw motor tests.
2. Secure the drone during the first motor test.
3. Keep the controller terminal **focused** during flight — the killswitch reads keys from the active window.
4. `SPACEBAR` kills all motors immediately. Know where it is before takeoff.
5. Keep one hand near the keyboard during every flight test.
6. Use a low hover height for first tests.
7. Never run the controller in a background or headless terminal.
8. Do not fly if Vicon tracking is unstable or the subject is not visible.
9. Do not fly if the Vicon bridge shows zero packets.
10. Do not assume another drone's URI — always scan for your own (`cfclient` → Scan, or `cflib.crtp.scan_interfaces()`).

## Emergency controls

| Key | Action |
|---|---|
| `SPACEBAR` | Kill all motors immediately. |
| `1` | Trim motor 1 to 0.65×. |
| `2` | Trim motor 2 to 0.65×. |
| `3` | Trim motor 3 to 0.65×. |
| `4` | Trim motor 4 to 0.65×. |

## During flight, watch

- Vicon bridge packet rate (~200 fps, errors 0)
- Crazyflie height
- Drift
- Oscillation
- Controller terminal output

Press `SPACEBAR` immediately if the drone tilts, climbs too fast, loses tracking, or behaves unpredictably.

## Known failure mode (lab data, 2026-07-08)

At the edges of the capture volume (|x| ≈ 2 m in our cage), Vicon coverage can drop: the state snaps to ~origin, thrust saturates at 65535, and attitude commands hit ±32767 within 2–3 samples — an unrecoverable departure. Keep trajectories well inside the calibrated volume.
