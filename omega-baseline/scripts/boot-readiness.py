#!/usr/bin/env python3
"""Read-only host capability inventory. No mounts, devices, services or installs."""
import json,os,platform,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
names=['cosmic-session','cosmic-comp','cosmic-panel','cosmic-launcher','wayland-info','qemu-system-x86_64','grub-mkrescue','xorriso','systemd-repart','mkfs.ext4']
tools={name:shutil.which(name) for name in names}
report={
 'architecture':platform.machine(),
 'kernel':platform.release(),
 'visible_host_tools':tools,
 'workspace_swipl_present':(ROOT/'runtime/swipl/bin/swipl').is_file(),
 'workspace_granite_present':(ROOT/'runtime/granite/omega-granite-infer').is_file(),
 'display_environment_present':bool(os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')),
 'cosmic_session_launched':False,
 'boot_image_created':False,
 'boot_test_performed':False,
 'hardware_changes':False,
 'limitations':'PATH inventory of this container only, not a complete installed-software scan or target-machine compatibility proof. A runnable user-space cognitive fixture is not a Linux distribution or a bootable image.'
}
(ROOT/'results/boot-readiness.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
