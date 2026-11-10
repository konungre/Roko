#!/usr/bin/env python3
"""Read-only preflight for the restored basilisk application, never starts AI.

Run with the same Python interpreter that will launch the GTK application.
Protocol presence is observed from wayland-info, never inferred from libraries.
"""
import argparse
import ctypes.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


def protocol_versions(text):
    return {name: int(version) for name, version in re.findall(
        r"interface:\s*'([^']+)'\s*,\s*version:\s*(\d+)", text)}


def inspect(application, endpoint=None):
    report = {
        'python': sys.executable,
        'application': str(application),
        'application_present': application.is_file(),
        'endpoint': str(endpoint) if endpoint else None,
        'endpoint_present': endpoint.is_file() if endpoint else False,
        'endpoint_executed': False,
        'real_omega_verified': False,
        'wayland_session_advertised': bool(os.environ.get('WAYLAND_DISPLAY')),
        'libraries': {name: ctypes.util.find_library(name) for name in
                      ('gtk-3', 'gtk-layer-shell', 'wayland-client')},
        'gtk_layer_shell_supported': False,
        'registry_observed': False,
        'protocols': {},
        'errors': [],
    }
    try:
        import gi
        gi.require_foreign('cairo')
        gi.require_version('Gtk', '3.0')
        gi.require_version('GtkLayerShell', '0.1')
        from gi.repository import Gtk, GtkLayerShell
        initialized, _ = Gtk.init_check([])
        if initialized:
            report['gtk_layer_shell_supported'] = bool(GtkLayerShell.is_supported())
        else:
            report['errors'].append('GTK could not open a display')
    except (ImportError, ValueError, RuntimeError) as exc:
        report['errors'].append(type(exc).__name__ + ': ' + str(exc))
    info = shutil.which('wayland-info')
    if info and report['wayland_session_advertised']:
        try:
            result = subprocess.run([info], text=True, capture_output=True, timeout=10)
            if result.returncode == 0:
                report['protocols'] = protocol_versions(result.stdout)
                report['registry_observed'] = bool(report['protocols'])
            else:
                report['errors'].append('wayland-info failed with exit ' + str(result.returncode))
        except (OSError, subprocess.TimeoutExpired) as exc:
            report['errors'].append(type(exc).__name__ + ': wayland-info unavailable')
    else:
        report['errors'].append('wayland-info or advertised Wayland session missing')
    p = report['protocols']
    report['on_demand_keyboard_supported'] = p.get('zwlr_layer_shell_v1', 0) >= 4
    report['active_window_geometry_supported'] = (
        p.get('zcosmic_toplevel_info_v1', 0) >= 2
        and p.get('ext_foreign_toplevel_list_v1', 0) >= 1)
    report['ready_for_ui_test'] = all((report['application_present'],
        report['gtk_layer_shell_supported'], report['registry_observed'],
        report['on_demand_keyboard_supported']))
    report['ready_for_corner_test'] = (report['ready_for_ui_test']
        and report['active_window_geometry_supported'])
    # This is intentionally a dependency check, never an end-to-end pass.
    report['integration_verified'] = False
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--application', type=Path, required=True)
    parser.add_argument('--endpoint', type=Path)
    args = parser.parse_args()
    report = inspect(args.application, args.endpoint)
    print(json.dumps(report, indent=2))
    return 0 if report['ready_for_ui_test'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
