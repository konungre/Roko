#!/usr/bin/env python3
"""Read-only Linux evidence collection. No mounts, devices opened, or downloads."""
import argparse
import json
from pathlib import Path
import platform


def read(path):
    try:
        return path.read_text().strip()
    except (OSError, UnicodeError):
        return None


def collect(proc=Path('/proc'), sys=Path('/sys'), machine=None):
    machine = platform.machine() if machine is None else machine
    cpuinfo = read(proc / 'cpuinfo')
    flags = []
    if cpuinfo:
        for line in cpuinfo.splitlines():
            if line.startswith('flags') and ':' in line:
                flags.append(set(line.split(':', 1)[1].split()))
    common = sorted(set.intersection(*flags)) if flags else None
    meminfo = read(proc / 'meminfo')
    memory = None
    if meminfo:
        for line in meminfo.splitlines():
            fields = line.split()
            if len(fields) == 3 and fields[0] == 'MemTotal:' and fields[2] == 'kB':
                try:
                    memory = int(fields[1]) * 1024
                    if memory <= 0:
                        memory = None
                except ValueError:
                    pass
    displays = []
    pci = sys / 'bus/pci/devices'
    if pci.is_dir():
        for device in sorted(pci.iterdir()):
            klass = read(device / 'class')
            if klass and klass.startswith('0x03'):
                driver = device / 'driver'
                displays.append({'pci_address': device.name,
                                 'vendor': read(device / 'vendor'),
                                 'device': read(device / 'device'),
                                 'driver': driver.resolve().name if driver.is_symlink() else None})
    return {
        'schema_version': 1,
        'scope': 'Observed host only; not a guest boot, GPU acceleration, firmware, or COSMIC qualification',
        'architecture': machine,
        'x86_64': machine in ('x86_64', 'amd64'),
        'memory_bytes': memory,
        'cpu_flags_common': common,
        'avx2_on_all_observed_cpus': 'avx2' in common if common is not None else None,
        'display_controllers': displays,
        'intel_display_observed': any(d['vendor'] == '0x8086' for d in displays),
        'uefi_observed': (sys / 'firmware/efi').is_dir(),
        'drm_cards': sorted(p.name for p in (sys / 'class/drm').glob('card[0-9]*') if '-' not in p.name),
        'qualification': 'unverified',
        'required_hardware_tests': ['UEFI boot and recovery', 'Intel accelerated COSMIC session',
                                    'display hotplug and suspend/resume', 'audio, Wi-Fi and Bluetooth',
                                    'offline model memory pressure', 'persistence after power loss'],
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    print(json.dumps(collect(), indent=2, sort_keys=True))
