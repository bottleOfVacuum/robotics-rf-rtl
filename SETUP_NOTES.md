# CUWB 2.0 lab setup notes

What we learned while bringing the system up on 2026-10-30, and what matters
for scaling to 24 anchors on 6 Raspberry Pi hubs.

## Current topology (working)

```
                         enp0s31f6 (one NIC, two addresses)
 ┌──────────────────────┐  192.168.50.155/24  (lab LAN, DHCP)
 │ Host: ROB-BARTON-21U │  10.99.1.10/16      (UWB network, added by hand)
 │ cuwb_server 2.0.0    │──────────┐
 │ master 01:00:0172    │          │ switch (same L2 segment)
 │  on USB /dev/ttyACM0 │          │
 └──────────────────────┘   ┌──────┴───────────────────────────┐
                            │ Hub Pi "raspberrypi"             │
                            │ Raspberry Pi 2 Model B, Raspbian │
                            │ 8 (jessie), eth0 10.99.56.247/16 │
                            │ MAC b8:27:eb:d6:44:2d            │
                            │ dwusb_daemon (DWUSB gateway)     │
                            │  ttyACM0  anchor 01:00:0164      │
                            │  ttyACM1  anchor 01:00:0168      │
                            │  ttyACM2  anchor 01:00:05CD      │
                            │  ttyACM3  anchor 01:00:013C      │
                            └──────────────────────────────────┘
```

All UWB nodes are Ciholas DWUSB-SMA, firmware 0.6.9.0, USB ID `03eb:2404`.

Tags enrolled in `local.cfg`: `01:00:05CF` (the demo tracker) and
`01:00:0173`.

The MAC hardcoded in `pi-link.sh` (`b8:27:eb:31:e9:58`) is a Pi from an
earlier session at another site. It is not part of this setup.

## How the pieces talk

- **Anchors and gateways.** The Pi's `dwusb_daemon` opens every
  `/dev/ttyACM*` and exposes each node as a UDP endpoint on a random port.
  It does nothing on the network until `cuwb_server` discovers it over the
  **config multicast stream** and pushes TX settings. Once configured, the
  Pi logs `Applying TX settings: IP: 239.255.76.67, port: 7667`.
- **Discovery only works on 10.99.0.0/16.** The server's built-in help says
  the config multicast interface "should belong to the 10.99.0.0/16 subnet".
  The host therefore needs an address on that subnet, on the NIC facing the
  hubs.
- **The master** is a DWUSB plugged into the host by USB. It's listed under
  `"serial ports"` in the config.
- **Output.** Location data is multicast as CDP on `239.255.76.67:7667`. The
  server also uses `:7670`. Each anchor gets its own UDP connection from the
  host to its Pi endpoint.
- **Traffic volume.** Measured on 4 anchors: about 390 packets/s from the
  Pi and about 100/s from the server. Expect roughly 2,300 packets/s at 24
  anchors. That's trivial bandwidth, even on the Pi 2's 100 Mbit port.

## Problems fixed today, and their symptoms

| Symptom | Cause | Fix |
|---|---|---|
| Pi gateway idle; log says "TX settings have not changed since last configuration packet" | `config socket` interface was `"lo"` in every checked-in `.cfg` | Set it to the NIC facing the hubs (`enp0s31f6`) |
| Host can't reach the Pi over IPv4 | Host only had 192.168.50.x; the Pi is static 10.99.56.247 | Add `10.99.1.10/16` to `enp0s31f6` |
| Server ignores some anchors | Their serials weren't in the config (`05CD` was even listed as a tag) | List every anchor under `network.anchors` |
| `cuwb_server: libQt5SerialPort.so.5: cannot open shared object file` | Missing Qt library | `libqt5serialport5` installed system-wide; the bundled `libs/` copy was removed |
| Server can't open the master's `/dev/ttyACM0` | User not in `dialout` | `sudo usermod -aG dialout $USER`, then log in again |
| `module 'cdp' has no attribute 'CDP'` | `pip install cdp` installs an unrelated package ("Change Directory Plus") | `pip install -r requirements.txt` (`cdp-py==1.8.1`) |
| Multicast interfaces `enp2s0` / `ens1` don't exist | Configs copied from other machines | Use this host's interface name |

`cuwb_server-2.0.0/local.cfg` is the config for this machine, derived from
`default.cfg`. Anchor and master positions in it are placeholders
(`0, 0, 0`) until they've been surveyed.

## Bring-up and verification

```sh
# 1. Host address on the UWB subnet. This is transient; to make it permanent:
#    nmcli con modify "Wired connection 1" +ipv4.addresses 10.99.1.10/16
nmcli dev modify enp0s31f6 +ipv4.addresses 10.99.1.10/16

# 2. Server (one host process only), plus the GUI if wanted
cd cuwb_server-2.0.0
./cuwb_server --host-only -c local.cfg
./cuwb_server --gui-only  -c local.cfg

# 3. Record CDP
python cdp_client_multi.py out.csv --interface 10.99.1.10
```

Healthy server output includes, for each anchor:

```
ConfigurationServer: Received announce from device with serial number 0100xxxx
EthernetLink: Successfully connected to device 01:00:xxxx on udpm://10.99.56.247:<port>
DPU: sending config data to node N to add it to the network
```

and for the master:
`UsbLink: successfully opened the serial port: ttyACM0` … `Now Sending Syncs`.

Useful checks:

```sh
ss -uanp | grep cuwb               # one ESTAB line per connected anchor
ls -l /dev/serial/by-id/           # USB-attached nodes, with their serials
ssh pi@<hub> 'grep -a dwusb_daemon /var/log/syslog | tail -30'
```

If the Pi's IPv4 address is unknown, reach it over IPv6 link-local. Discover
it with `ping -6 ff02::1%enp0s31f6` and look for `fe80::ba27:eb…`. Modern
Pi images may not derive the link-local address from the MAC, so match on
the MAC in `ip -6 neigh` rather than computing the address.

## Hub Pi details

- Login: default Raspbian credentials, unchanged. **Change them** before
  deploying more hubs.
- Network: static, in `/etc/network/interfaces`. That file's
  `source-directory` line has a typo (`/detc/...`); it's harmless but worth
  fixing.
- Gateway software lives in `/home/pi/dwusb/`. It's started by
  `/etc/init.d/dwusb_daemon`, which loops `start_script.sh` to restart the
  daemon if it dies. `start_script.sh` and `stop_script.sh` contain
  hardcoded sudo passwords in plain text.
- `configure_vlan.sh` and `vlan_1.9-3.2_armhf.deb` exist but no VLAN is in
  use (TX settings report `vLan: 0`).
- No RTC and no NTP, so the clock reads June 2016 and syslog timestamps
  are not real time. This doesn't affect UWB timing.
- Auto-update is enabled: the daemon may flash `sma_0.6.9.0.bin` onto
  attached nodes.

## Scaling to 24 anchors on 6 PoE hubs

### Addressing and naming
- Put every hub on 10.99.0.0/16 with a static address, for example
  `10.99.56.241`–`.246`. Re-address the current hub or keep `.247`, but
  record the choice. The host stays at `10.99.1.10`.
- Give each hub a unique hostname (`uwb-hub-01` … `-06`). Every hub is
  currently `raspberrypi`, and avahi is running, so duplicate names will
  collide on mDNS.
- Keep a table of hub → IP → MAC → the four anchor serials and their
  positions. The server identifies anchors by serial only, so this table is
  the only way to map a serial back to a physical location.

### Cloning hubs
- Clone the working SD card (2.2 GB used on 8 GB). Then on each clone:
  - set the address in `/etc/network/interfaces`
  - set `/etc/hostname` and `/etc/hosts`
  - regenerate SSH host keys: `sudo rm /etc/ssh/ssh_host_* && sudo dpkg-reconfigure openssh-server`
  - change the password
- The DWUSB gateway needs no per-hub configuration: it learns its TX
  settings from the server.

### Power
- The PoE hubs are already built and are expected to behave like the
  current hub: one Pi with 4 USB-attached anchors, all running
  `dwusb_daemon`.

### Network
- Keep every hub and the host's UWB NIC on **one L2 segment or VLAN**.
  Discovery and data are both multicast (`239.255.76.67`).
- If anchors stay connected but data stops after a few minutes, suspect
  IGMP snooping without a querier on the switch. Enable an IGMP querier or
  disable snooping for that VLAN.
- The host currently shares `enp0s31f6` between the lab LAN (192.168.50.x)
  and the UWB network, so CDP output also leaks onto the lab LAN, with
  multicast TTL 4. Consider a dedicated NIC for the UWB network, and TTL 1
  (the server's own recommended setting).

### Server config for 24 anchors
- Each anchor needs an entry under `network.anchors`: serial, antenna delay
  (`16442` used so far), `"backhaul": "wired"`, and surveyed `x`, `y`, `z`
  in metres. The master needs a position too.
- The server needs at least 4 anchors to see a tag before it will compute a
  position.
- **Master visibility:** at warehouse scale, every anchor may not hear the
  single master's syncs. The current plan is to raise the node on a tripod
  to maximise line of sight. Check the CUWB 2.0 docs on multiple masters
  if coverage still falls short.
- Battery-powered nodes also have to be listed in the config by serial.
- Tags must be listed under `network.tags`. To get IMU data, enable
  `tag payload.mpu.send accel` / `send gyro` (see `README.md`).
