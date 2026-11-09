"""Bounded guest resource sampling for the trusted native process tree."""
from pathlib import Path
import resource

RSS_LIMIT = 5 * 1024**3
AVAILABLE_FLOOR = 512 * 1024**2
ADDRESS_LIMIT = 6 * 1024**3


def limits():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_AS, (ADDRESS_LIMIT, ADDRESS_LIMIT))


def observe(rows):
    rss = 0
    peaks = 0
    for pid, row in rows.items():
        if row['state'] == 'Z':
            continue
        try:
            values = dict((line.split(':',1)[0], int(line.split()[1]) * 1024)
                          for line in Path(f'/proc/{pid}/status').read_text().splitlines()
                          if line.startswith(('VmRSS:', 'VmHWM:')))
            rss += values.get('VmRSS', 0)
            peaks += values.get('VmHWM', 0)
        except FileNotFoundError:
            continue
    available = None
    for line in Path('/proc/meminfo').read_text().splitlines():
        if line.startswith('MemAvailable:'):
            available = int(line.split()[1]) * 1024
    if available is None:
        raise ValueError('Missing guest memory admission')
    return {'aggregate_rss_bytes': rss, 'aggregate_hwm_bytes': peaks, 'guest_available_bytes': available}


def reason(observation):
    if observation['aggregate_rss_bytes'] > RSS_LIMIT:
        return 'native-tree-rss-cap'
    if observation['guest_available_bytes'] < AVAILABLE_FLOOR:
        return 'guest-available-reserve'
    return None
