"""
vicon_bridge.py
---------------
Receives Vicon pose data over UDP and exposes it to the control loop.

Expected UDP packet format (space-separated floats, UTF-8):
    x  y  z  qx  qy  qz  qw 

Units: metres.

NOTE: Attitude angles (roll/pitch/yaw) from Vicon are stored here for
completeness but should NOT be fed to the Crazyflie PID controller.
Use the onboard EKF attitude (stateEstimate.roll/pitch/yaw) instead.
"""

from dataclasses import dataclass
import math
import socket
import threading
import time
from typing import Optional, Tuple


STALE_THRESHOLD_S = 0.2   


@dataclass
class ViconSample:
    t: float                          
    x_m: float                        
    y_m: float                        
    z_m: float                        
    qx: float = 0.0
    qy: float = 0.0
    qz: float = 0.0
    qw: float = 1.0
    valid: bool = False


class ViconStateSource:
    def __init__(
        self,
        host: str = "127.0.0.1",
        subject: str = "",
        udp_port: int = 51001,
    ):
        self.host     = host
        self.subject  = subject
        self.udp_port = udp_port

        self._latest: ViconSample = ViconSample(t=0.0, x_m=0.0, y_m=0.0, z_m=0.0, valid=False)
        self._lock    = threading.Lock()
        self._stop    = False
        self._thread: Optional[threading.Thread] = None

        self._prev_t:   Optional[float]                  = None
        self._prev_pos: Optional[Tuple[float, float, float]] = None
        self._vel: Tuple[float, float, float] = (0.0, 0.0, 0.0)

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop   = False
        self._thread = threading.Thread(target=self._run, daemon=True, name="ViconBridge")
        self._thread.start()

    def stop(self) -> None:
        self._stop = True
        if self._thread:
            self._thread.join(timeout=1.0)
        self._thread = None

    def get_latest(self) -> ViconSample:
        with self._lock:
            sample = self._latest

        age = time.monotonic() - sample.t
        if age > STALE_THRESHOLD_S and sample.valid:
            return ViconSample(
                t=sample.t,
                x_m=sample.x_m, y_m=sample.y_m, z_m=sample.z_m,
                qx=sample.qx, qy=sample.qy, qz=sample.qz, qw=sample.qw,
                valid=False,
            )
        return sample

    def get_velocity(self) -> Tuple[float, float, float]:
        return self._vel

    def is_connected(self) -> bool:
        return self.get_latest().valid

    def _run(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("127.0.0.1", self.udp_port))
        sock.settimeout(0.2)
        print(f"[Vicon] Listening on UDP 127.0.0.1:{self.udp_port}")

        while not self._stop:
            try:
                data, _ = sock.recvfrom(1024)
                text     = data.decode("utf-8").strip()
                parts    = text.split()
                if len(parts) < 7:
                    continue
                
                x_raw, y_raw, z_raw, qx, qy, qz, qw = map(float, parts[:7])

                x_m = x_raw
                y_m = y_raw
                z_m = z_raw

                now = time.monotonic()

                # Finite-difference velocity with low-pass filter
                if self._prev_t is not None and self._prev_pos is not None:
                    dt = max(now - self._prev_t, 1e-3)
                    raw_vx = (x_m - self._prev_pos[0]) / dt
                    raw_vy = (y_m - self._prev_pos[1]) / dt
                    raw_vz = (z_m - self._prev_pos[2]) / dt
                    alpha  = 0.2
                    self._vel = (
                        (1.0 - alpha) * self._vel[0] + alpha * raw_vx,
                        (1.0 - alpha) * self._vel[1] + alpha * raw_vy,
                        (1.0 - alpha) * self._vel[2] + alpha * raw_vz,
                    )

                self._prev_t   = now
                self._prev_pos = (x_m, y_m, z_m)

                sample = ViconSample(
                    t=now,
                    x_m=x_m, y_m=y_m, z_m=z_m,
                    qx=qx, qy=qy, qz=qz, qw=qw,
                    valid=True,
                )

                with self._lock:
                    self._latest = sample

            except socket.timeout:
                continue
            except Exception as exc:
                print(f"[Vicon UDP] Read error: {exc}")
                time.sleep(0.01)

        sock.close()
        print("[Vicon] Bridge stopped.")
