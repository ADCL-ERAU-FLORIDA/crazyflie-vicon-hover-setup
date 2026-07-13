"""
vicon_bridge_test.py
--------------------
Test script to verify Vicon position and attitude data.

Run the C++ bridge first:
    ./live_tracking_bridge <vicon_ip> <subject_name>

Then run this script in a separate terminal:
    python3 vicon_bridge_test.py

Move the drone physically and verify:
    - Move towards you      → x increases
    - Move to your right    → y increases
    - Move upward           → z increases
    - Rotate clockwise      → yaw decreases (right-hand rule)
"""

import math
import time
import sys
import os

# Allow running from any directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from vicon_bridge import ViconStateSource


def quat_to_euler_deg(qx, qy, qz, qw):
    """
    Convert quaternion to Euler angles (roll, pitch, yaw) in degrees.
    Uses ZYX convention (yaw → pitch → roll), same as Crazyflie EKF.
    """
    # Roll (x-axis rotation)
    sinr_cosp = 2.0 * (qw * qx + qy * qz)
    cosr_cosp = 1.0 - 2.0 * (qx * qx + qy * qy)
    roll = math.atan2(sinr_cosp, cosr_cosp)

    # Pitch (y-axis rotation)
    sinp = 2.0 * (qw * qy - qz * qx)
    sinp = max(-1.0, min(1.0, sinp))   # clamp for numerical safety
    pitch = math.asin(sinp)

    # Yaw (z-axis rotation)
    siny_cosp = 2.0 * (qw * qz + qx * qy)
    cosy_cosp = 1.0 - 2.0 * (qy * qy + qz * qz)
    yaw = math.atan2(siny_cosp, cosy_cosp)

    return math.degrees(roll), math.degrees(pitch), math.degrees(yaw)


def main():
    print("=" * 65)
    print("  Vicon Bridge Test")
    print("  Waiting for UDP packets on 127.0.0.1:51001 ...")
    print("=" * 65)

    v = ViconStateSource(host="127.0.0.1", udp_port=51001)
    v.start()

    # Wait up to 5 seconds for first valid sample
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        if v.is_connected():
            print("[OK] First sample received.\n")
            break
        time.sleep(0.05)
    else:
        print("[ERROR] No data received after 5 seconds.")
        print("        Is the C++ bridge running?")
        v.stop()
        return

    print(f"  {'X (m)':>8}  {'Y (m)':>8}  {'Z (m)':>8}  |  "
          f"{'Roll':>8}  {'Pitch':>8}  {'Yaw':>8}  |  "
          f"{'qx':>8}  {'qy':>8}  {'qz':>8}  {'qw':>8}")
    print("-" * 95)

    try:
        while True:
            s = v.get_latest()

            if not s.valid:
                print("[WARN] Stale sample — no data for >200 ms")
                time.sleep(0.1)
                continue

            roll_deg, pitch_deg, yaw_deg = quat_to_euler_deg(
                s.qx, s.qy, s.qz, s.qw
            )

            print(
                f"  {s.x_m:>+8.3f}  {s.y_m:>+8.3f}  {s.z_m:>+8.3f}  |  "
                f"{roll_deg:>+8.2f}  {pitch_deg:>+8.2f}  {yaw_deg:>+8.2f}  |  "
                f"{s.qx:>+8.4f}  {s.qy:>+8.4f}  {s.qz:>+8.4f}  {s.qw:>+8.4f}"
            )

            time.sleep(0.1)   # 10 Hz print rate — easy to read

    except KeyboardInterrupt:
        print("\n[Stopped]")
    finally:
        v.stop()


if __name__ == "__main__":
    main()
