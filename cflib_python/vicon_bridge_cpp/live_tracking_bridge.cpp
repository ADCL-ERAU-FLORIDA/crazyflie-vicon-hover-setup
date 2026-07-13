#include <arpa/inet.h>
#include <chrono>
#include <cmath>
#include <cstring>
#include <iostream>
#include <string>
#include <thread>
#include <unistd.h>

#include "DataStreamClient.h"

using namespace ViconDataStreamSDK::CPP;

int main(int argc, char** argv) {
  std::string host    = "192.168.10.1";
  std::string subject = "Crazy_Test";
  int udp_port        = 51001;

  if (argc >= 2) host     = argv[1];
  if (argc >= 3) subject  = argv[2];
  if (argc >= 4) udp_port = std::stoi(argv[3]);

  Client client;

  auto connect_result = client.Connect(host);
  std::cout << "Connect result: " << static_cast<int>(connect_result.Result) << std::endl;
  if (connect_result.Result != Result::Success) {
    std::cerr << "Failed to connect to Vicon host: " << host << std::endl;
    return 1;
  }

  auto seg_result = client.EnableSegmentData();
  std::cout << "EnableSegmentData result: " << static_cast<int>(seg_result.Result) << std::endl;
  if (seg_result.Result != Result::Success) {
    std::cerr << "Failed to enable segment data." << std::endl;
    return 1;
  }

  int sock = socket(AF_INET, SOCK_DGRAM, 0);
  if (sock < 0) {
    std::perror("socket");
    return 1;
  }

  sockaddr_in addr{};
  addr.sin_family      = AF_INET;
  addr.sin_port        = htons(static_cast<uint16_t>(udp_port));
  addr.sin_addr.s_addr = inet_addr("127.0.0.1");

  std::cout << "Streaming subject '" << subject
            << "' to UDP 127.0.0.1:" << udp_port << std::endl;

  // FIX: removed per-frame std::cout.
  // At 100 Hz each flushed terminal write is a blocking syscall that adds
  // jitter and can starve the GetFrame() loop.  Print a status line once
  // per second instead.
  uint64_t frame_count    = 0;
  uint64_t error_count    = 0;
  auto     last_print_time = std::chrono::steady_clock::now();

  while (true) {
    auto frame_result = client.GetFrame();
    if (frame_result.Result != Result::Success) {
      ++error_count;
      std::this_thread::sleep_for(std::chrono::milliseconds(2));
      continue;
    }

    auto t = client.GetSegmentGlobalTranslation(subject, subject);
    auto r = client.GetSegmentGlobalRotationQuaternion(subject, subject);

    if (t.Result != Result::Success) {
      ++error_count;
      std::this_thread::sleep_for(std::chrono::milliseconds(2));
      continue;
    }

    // Vicon returns millimetres; convert to metres.
    double x_m   = t.Translation[0] / 1000.0;
    double y_m   = t.Translation[1] / 1000.0;
    double z_m   = t.Translation[2] / 1000.0;

    // EulerXYZ angles in radians.  Only used for logging; the Python
    // controller uses EKF attitude, not these values.
    double qx = 0.0, qy = 0.0, qz = 0.0, qw = 1.0;
    if (r.Result == Result::Success) {
        qx = r.Rotation[0];
        qy = r.Rotation[1];
        qz = r.Rotation[2];
        qw = r.Rotation[3];
    }

    char buf[256];
    int n = std::snprintf(
        buf, sizeof(buf),
        "%.6f %.6f %.6f %.6f %.6f %.6f %.6f\n",
        x_m, y_m, z_m, qx, qy, qz, qw);

    sendto(sock, buf, n, 0,
           reinterpret_cast<sockaddr*>(&addr), sizeof(addr));

    ++frame_count;

    // Print a brief status line once per second — low enough to not cause jitter.
    auto now = std::chrono::steady_clock::now();
    double elapsed_s = std::chrono::duration<double>(now - last_print_time).count();
    if (elapsed_s >= 1.0) {
      std::cout << "[Vicon] "
                << static_cast<int>(frame_count / elapsed_s) << " fps | "
                << "pos " << x_m << " " << y_m << " " << z_m
                << " | errors " << error_count
                << std::endl;
      frame_count    = 0;
      error_count    = 0;
      last_print_time = now;
    }
  }

  close(sock);
  client.Disconnect();
  return 0;
}
