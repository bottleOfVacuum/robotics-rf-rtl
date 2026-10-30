#!/usr/bin/env bash
# pi-link.sh — reach a Raspberry Pi on a switch with no router/DHCP.
# Nothing here writes to /etc; everything is undone by `down` or a reboot.
#
#   ./pi-link.sh find           # identify which ethernet port faces the switch
#   ./pi-link.sh up  <iface>    # bring link-local addressing up on that port
#   ./pi-link.sh test <iface>   # ping the Pi over that port
#   ./pi-link.sh down [<iface>] # remove the temporary config
set -u

PI_MAC="b8:27:eb:31:e9:58"
PI_LL="fe80::ba27:ebff:fe31:e958"   # derived from PI_MAC (EUI-64), fixed
CON="pi-link"

# Physical ethernet ports only: type 1 = ethernet, /device present = real hardware
# (skips docker0, bridges, veth, tun, wifi, loopback).
phys_eth() {
    for d in /sys/class/net/*; do
        n=${d##*/}
        [ "$(cat "$d/type" 2>/dev/null)" = 1 ] || continue
        [ -e "$d/device" ] || continue
        [ -d "$d/wireless" ] && continue
        echo "$n"
    done
}
carrier() { cat "/sys/class/net/$1/carrier" 2>/dev/null || echo 0; }
has_ll6() { ip -6 addr show dev "$1" scope link 2>/dev/null | grep -q inet6; }
nm_managed() {
    command -v nmcli >/dev/null || return 1
    st=$(nmcli -g GENERAL.STATE dev show "$1" 2>/dev/null) || return 1
    [[ "$st" != *unmanaged* ]]
}

cmd_find() {
    echo "Physical ethernet ports:"
    for i in $(phys_eth); do
        printf "  %-16s carrier=%s  addrs: %s\n" "$i" "$(carrier "$i")" \
            "$(ip -br addr show dev "$i" | awk '{$1=$2="";print}')"
    done
    echo
    # Pass 1: any port that already has a link-local v6 address and can reach the Pi.
    for i in $(phys_eth); do
        [ "$(carrier "$i")" = 1 ] || continue
        has_ll6 "$i" || continue
        if ping -6 -c 2 -W 1 "${PI_LL}%${i}" >/dev/null 2>&1; then
            echo "FOUND: the Pi answers on $i"
            echo "Next: ./pi-link.sh up $i"
            return 0
        fi
    done
    # Pass 2: ports with carrier but no usable address — identify by unplugging.
    echo "No port could reach the Pi yet (addresses probably stripped after a DHCP timeout)."
    echo "Unplug the cable that goes to the TL-SL1218MP, then press Enter."
    read -r
    before=""
    for i in $(phys_eth); do [ "$(carrier "$i")" = 0 ] && before="$before $i"; done
    echo "Plug it back in, wait ~3 s, then press Enter."
    read -r
    sleep 2
    for i in $before; do
        if [ "$(carrier "$i")" = 1 ]; then
            echo "FOUND: carrier returned on $i"
            echo "Next: ./pi-link.sh up $i"
            return 0
        fi
    done
    echo "Could not identify the port. Candidates with carrier now:"
    for i in $(phys_eth); do [ "$(carrier "$i")" = 1 ] && echo "  $i"; done
    return 1
}

cmd_up() {
    i=$1
    if nm_managed "$i"; then
        echo "$i is managed by NetworkManager: adding an in-memory profile (save no)."
        nmcli con show "$CON" >/dev/null 2>&1 && nmcli con delete "$CON" >/dev/null
        nmcli con add save no type ethernet ifname "$i" con-name "$CON" \
            ipv4.method link-local ipv6.method link-local connection.autoconnect no \
            && nmcli con up "$CON"
    else
        echo "$i is not NetworkManager-managed (netplan/systemd-networkd or bare)."
        echo "Adding transient addresses with ip(8); these vanish on reboot."
        sudo ip link set dev "$i" up
        sudo ip addr add "169.254.$((RANDOM%253+1)).$((RANDOM%253+1))/16" dev "$i" 2>/dev/null || true
    fi
    sleep 2
    ip -br addr show dev "$i"
    cmd_test "$i"
}

cmd_test() {
    i=$1
    echo "All IPv6 nodes on $i:"
    ping -6 -c 2 -W 1 "ff02::1%${i}" 2>/dev/null | awk '/bytes from/{print "  "$4}' | sort -u
    echo "Pinging the Pi:"
    if ping -6 -c 3 -W 2 "${PI_LL}%${i}" 2>&1 | tail -2; then
        echo
        echo "ssh <user>@${PI_LL}%${i}"
    fi
}

cmd_down() {
    if command -v nmcli >/dev/null && nmcli con show "$CON" >/dev/null 2>&1; then
        nmcli con delete "$CON"
    fi
    if [ -n "${1:-}" ]; then
        sudo ip -4 addr flush dev "$1" scope link 2>/dev/null || true
    fi
    echo "Temporary config removed."
}

case "${1:-}" in
    find) cmd_find ;;
    up)   [ -n "${2:-}" ] || { echo "usage: $0 up <iface>"; exit 2; }; cmd_up "$2" ;;
    test) [ -n "${2:-}" ] || { echo "usage: $0 test <iface>"; exit 2; }; cmd_test "$2" ;;
    down) cmd_down "${2:-}" ;;
    *) sed -n '2,9p' "$0"; exit 2 ;;
esac
