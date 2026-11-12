#!/usr/bin/env python3
"""Isolate a marked offline staging tree before creating a regular image file."""
import argparse
import json
import os
from pathlib import Path

FIREWALL = '''#!/bin/sh
set -eu
/sbin/iptables -P OUTPUT DROP
/sbin/iptables -F OUTPUT
/sbin/iptables -A OUTPUT -o lo -j ACCEPT
/sbin/iptables -A OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
/sbin/iptables -A OUTPUT -p udp --sport 68 --dport 67 -j ACCEPT
if [ -d /proc/sys/net/ipv6 ]; then
    /sbin/sysctl -w net.ipv6.conf.all.disable_ipv6=1
    /sbin/sysctl -w net.ipv6.conf.default.disable_ipv6=1
fi
'''

UNIT = '''[Unit]
Description=Recovery trial outbound isolation
DefaultDependencies=no
After=local-fs.target
Before=network-pre.target network.target
Wants=network-pre.target
OnFailure=emergency.target

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/n-data-trial-isolation
RemainAfterExit=yes

[Install]
WantedBy=sysinit.target
'''


def validate_tree(workspace):
    workspace = Path(workspace).resolve()
    if not workspace.name.startswith('n_data-trial-'):
        raise ValueError('Use a separate n_data-trial-* workspace')
    proof = workspace / 'trial-workspace.json'
    if json.loads(proof.read_text()).get('purpose') != 'n_data_sd_trial':
        raise ValueError('Staging workspace marker missing')
    root = workspace / 'root'
    if root.is_symlink() or not root.is_dir() or os.path.ismount(str(root)):
        raise ValueError('A regular, unmounted staging directory is required')
    if root.stat().st_dev != workspace.stat().st_dev:
        raise ValueError('Staging tree must not be a separate device')
    return root


def prepare(workspace):
    root = validate_tree(workspace)
    for relative in ['etc', 'etc/systemd/system', 'etc/fstab', 'root', 'usr/local/sbin']:
        resolved = (root / relative).resolve()
        if resolved != root and root not in resolved.parents:
            raise ValueError('Image path escapes mounted root: ' + relative)
    marker = root / 'etc/n_data_recovery_trial.json'
    if marker.exists():
        raise ValueError('Image is already marked as a trial')
    iptables = root / 'sbin/iptables'
    if not (iptables.exists() or iptables.is_symlink()):
        raise ValueError('iptables is required in the source image')
    units = root / 'etc/systemd/system'
    backup = root / 'root/recovery-original-units'
    backup.mkdir(parents=True, mode=0o700)
    masked = []

    def mask(name):
        target = units / name
        if target.exists() or target.is_symlink():
            target.rename(backup / name)
        target.symlink_to('/dev/null')
        masked.append(name)

    preserve = {'ssh.service', 'sshd.service', 'ssh@.service', 'dhcpcd.service',
                'dbus.service', 'NetworkManager.service', 'systemd-networkd.service',
                'systemd-resolved.service', 'wpa_supplicant.service', '-.mount', 'boot.mount'}
    selected = set()
    for path in units.iterdir():
        if path.name.endswith(('.service', '.timer', '.mount', '.automount')) and path.name not in preserve:
            selected.add(path.name)
    for directory in [root / 'lib/systemd/system', root / 'usr/lib/systemd/system']:
        if directory.is_dir() and not directory.is_symlink():
            selected.update(p.name for p in directory.glob('*.timer'))
    selected.update(['cron.service', 'anacron.service', 'atd.service', 'rc-local.service',
                     'tailscaled.service', 'vsftpd.service', 'vncserver-x11-serviced.service',
                     'xrdp.service', 'xrdp-sesman.service',
                     'display-manager.service', 'getty@tty1.service', 'dphys-swapfile.service',
                     'netfilter-persistent.service', 'iptables.service', 'ip6tables.service',
                     'ufw.service', 'firewalld.service', 'nftables.service',
                     'docker.service', 'containerd.service', 'watchdog.service', 'watchdogd.service',
                     'wd_keepalive.service', 'rpi-eeprom-update.service', 'rpi-eeprom-update.timer',
                     'home.mount', 'var.mount',
                     'mnt-vol1.mount', 'mnt-tbid.mount'])
    for name in sorted(selected):
        mask(name)
    fstab = root / 'etc/fstab'
    original = fstab.read_text()
    saved = root / 'root/recovery-original-fstab'
    saved.write_text(original); saved.chmod(0o600)
    result = []
    disabled_mounts = []
    for line in original.splitlines():
        fields = line.split()
        if fields and not fields[0].startswith('#') and len(fields) >= 3:
            if fields[1] not in ('/', '/boot', '/proc'):
                disabled_mounts.append(fields[1])
                line = '# RECOVERY_TEST_DISABLED ' + line
        result.append(line)
    fstab.write_text('\n'.join(result) + '\n')
    script = root / 'usr/local/sbin/n-data-trial-isolation'
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(FIREWALL); script.chmod(0o700)
    (units / 'n-data-trial-isolation.service').write_text(UNIT)
    wants = units / 'sysinit.target.wants'
    wants.mkdir(exist_ok=True)
    (wants / 'n-data-trial-isolation.service').symlink_to('/etc/systemd/system/n-data-trial-isolation.service')
    default = units / 'default.target'
    if default.exists() or default.is_symlink():
        default.rename(backup / 'default.target')
    default.symlink_to('/lib/systemd/system/multi-user.target')
    report = {'trial_only': True, 'masked_units': masked, 'disabled_mountpoints': disabled_mounts,
              'original_usb_must_be_disconnected': True, 'nas_writes_allowed': False,
              'outbound_policy': 'DROP; loopback, established replies, DHCPv4 only',
              'physical_boot_and_firewall_verification_pending': True}
    marker.write_text(json.dumps(report, indent=2))
    print(json.dumps({'trial_only': True, 'masked_unit_count': len(masked),
                      'disabled_mountpoints': disabled_mounts,
                      'physical_boot_verification_pending': True}))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True)
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise SystemExit('Root is required to preserve staging ownership')
    prepare(args.workspace)
