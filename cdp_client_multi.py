#!/usr/bin/env python3
"""Record CUWB 2.0 Position V1 and MPU-9250 motion items as CSV events."""

import argparse
import csv
from datetime import datetime, timezone
import os
from pathlib import Path
import signal
import socket
import struct
import sys
import time

import cdp


COLUMNS = (
    "received_at_utc", "tag_serial", "packet_sequence", "item_type",
    "network_time_ticks", "x_mm", "y_mm", "z_mm", "position_sequence",
    "position_quality_raw", "smoothing", "accel_x_raw", "accel_y_raw", "accel_z_raw",
    "accel_scale_g", "accel_dlpf_hz", "gyro_x_raw", "gyro_y_raw",
    "gyro_z_raw", "gyro_scale_dps", "gyro_dlpf_hz",
)
ITEM_TYPES = {0x0100: "position", 0x0008: "accelerometer", 0x0009: "gyroscope"}
STOP = False
FLUSH = False


def stop_handler(_signum, _frame):
    global STOP
    STOP = True


def flush_handler(_signum, _frame):
    global FLUSH
    FLUSH = True


def rows_from_packet(packet, received_at_utc, tags=None):
    """Yield one row for each supported v2.0 data item in packet order."""
    serial = str(packet.serial_number)
    if tags is not None and serial.upper() not in tags:
        return

    for item in packet.data_items:
        kind = ITEM_TYPES.get(item.type)
        if kind is None:
            continue
        row = dict.fromkeys(COLUMNS, "")
        row.update(received_at_utc=received_at_utc, tag_serial=serial,
                   packet_sequence=packet.sequence, item_type=kind,
                   network_time_ticks=item.gnt)
        if kind == "position":
            row.update(x_mm=item.x, y_mm=item.y, z_mm=item.z,
                       position_sequence=item.sequence,
                       position_quality_raw=item.quality, smoothing=item.smoothing)
        elif kind == "accelerometer":
            row.update(accel_x_raw=item.x, accel_y_raw=item.y, accel_z_raw=item.z,
                       accel_scale_g=item.scale, accel_dlpf_hz=item.dlpf)
        else:
            row.update(gyro_x_raw=item.x, gyro_y_raw=item.y, gyro_z_raw=item.z,
                       gyro_scale_dps=item.scale, gyro_dlpf_hz=item.dlpf)
        yield row


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="CSV file to create (overwritten if it exists)")
    parser.add_argument("--group", default="239.255.76.67", help="CDP multicast group")
    parser.add_argument("--port", type=int, default=7667, help="CDP UDP port")
    parser.add_argument("--interface", default="0.0.0.0",
                        help="local IPv4 address for multicast membership")
    parser.add_argument("--tags", nargs="+", metavar="SERIAL",
                        help="optional tag serial allowlist; default is every reporting device")
    parser.add_argument("--pid-file", type=Path,
                        help="optional PID file for launch scripts")
    return parser.parse_args(argv)


def main(argv=None):
    global FLUSH
    args = arguments(argv)
    tags = {tag.upper() for tag in args.tags} if args.tags else None
    args.output.parent.mkdir(parents=True, exist_ok=True)

    signal.signal(signal.SIGINT, stop_handler)
    signal.signal(signal.SIGTERM, stop_handler)
    if hasattr(signal, "SIGUSR1"):
        signal.signal(signal.SIGUSR1, flush_handler)

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
        receiver.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        receiver.bind(("", args.port))
        membership = socket.inet_aton(args.group) + socket.inet_aton(args.interface)
        receiver.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, membership)
        receiver.settimeout(1.0)

        if args.pid_file:
            args.pid_file.parent.mkdir(parents=True, exist_ok=True)
            args.pid_file.write_text(str(os.getpid()) + "\n")

        try:
            with args.output.open("w", newline="", encoding="utf-8", buffering=1) as output:
                writer = csv.DictWriter(output, fieldnames=COLUMNS)
                writer.writeheader()
                count = 0
                last_report = time.monotonic()
                while not STOP:
                    data = None
                    try:
                        data, _address = receiver.recvfrom(65535)
                    except socket.timeout:
                        pass
                    if data is not None:
                        try:
                            packet = cdp.CDP(data)
                            received_at = datetime.now(timezone.utc).isoformat(timespec="microseconds")
                            for row in rows_from_packet(packet, received_at, tags):
                                writer.writerow(row)
                                count += 1
                        except (ValueError, IndexError, AttributeError, struct.error) as exc:
                            print(f"Skipping malformed CDP packet: {exc}", file=sys.stderr)
                    if FLUSH:
                        output.flush()
                        FLUSH = False
                    now = time.monotonic()
                    if now - last_report >= 10:
                        print(f"Recorded {count} data items", file=sys.stderr)
                        last_report = now
        finally:
            if args.pid_file:
                args.pid_file.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
