# CUWB 2.0 tag CSV recorder

`cdp_client_multi.py` records the CUWB 2.0 CDP stream from multiple tags. It supports the data items documented for this hardware: Position V1 (`0x0100`), MPU-9250 Accelerometer V2 (`0x0008`), and MPU-9250 Gyroscope V2 (`0x0009`). Distance V1 (`0x0101`) is a range between devices, **not** a tag's 3D position, so it is not used as a position fix.

## Run

Install the decoder in a Python environment if needed:

```sh
python -m pip install -r requirements.txt
```

On a machine that receives the CUWB server's multicast traffic:

```sh
python cdp_client_multi.py DATA/tags.csv --tags 01:00:0173 01:00:05CD
```

By default it listens on `239.255.76.67:7667`, matching the supplied server configurations. Omit `--tags` to record every device that emits one of the supported items. If multicast does not arrive on the intended network card, pass that card's **local IPv4 address** with `--interface`, for example `--interface 192.168.1.104`. Use `--group` and `--port` if the server uses another stream. Stop with Ctrl+C. The output is created with a header and overwritten at each start. To retain a run, use a new filename. `--pid-file DATA/TMP/pid_uwb.txt` is available for launch scripts; `SIGUSR1` flushes the CSV.

## Enable motion data at the source

The checked in `cuwb_server-2.0.0/default.cfg`, `BBB4916.cfg`, `BBB4916_tomo.cfg`, and `BBB2776.cfg` set `network.tag payload.mpu.send accel` and `send gyro` to `false`. In the **configuration actually loaded by the CUWB 2.0 server**, set both to `true`, then apply/restart that server configuration according to your deployment procedure. Otherwise the CSV will contain positions but no accelerometer or gyroscope rows. The `lol.cfg` example enables gyro but disables accel and targets different tag serials. The receiver cannot recover sensor samples that were never transmitted.

## CSV format

Each row is one data item, with `item_type` of `position`, `accelerometer`, or `gyroscope`. All rows contain `tag_serial`, CDP `packet_sequence`, `received_at_utc`, and the item's `network_time_ticks`; columns unrelated to that item are blank. This preserves multiple IMU samples in one packet, data when a position fix is missing, and each item's own timestamp. Match samples across types by tag and nearby network time if a combined time series is needed. The 32-bit network clock wraps, so handle wraparound for long recordings.

Position coordinates are signed millimeters from the configured origin. `position_sequence` and `smoothing` come from Position V1. `position_quality_raw` is retained but marked unused by the CUWB 2.0 documentation. Accelerometer and gyro axes are signed **raw** MPU-9250 readings. Their `*_scale_*` columns give the configured full scale (g or degrees/s) and `*_dlpf_hz` gives the filter rate; the script does not silently convert raw readings into physical units. The CUWB 2.0 docs describe network time as roughly 1.026 microseconds per tick. `received_at_utc` is the computer's packet receipt time, not a device measurement time.

The current `cdp-py` library includes newer CDP data item classes too; this recorder deliberately reads only the three item IDs supported by the supplied CUWB 2.0 protocol definition.

Protocol reference: https://cuwb.io/docs/v2.0/software-integration/cdp-output-definition/

Decoder: https://github.com/ciholas/cdp-py
# robotics-rf-rtl
