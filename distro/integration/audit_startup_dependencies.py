"""Small read-only selected-source inventory; no full evaluation or readiness grant."""
import argparse,hashlib,json
from pathlib import Path
from verify_cached_startup import verify
from memory_budget import observe
SPECS=[
 ('login-pam','nixos/modules/services/display-managers/greetd.nix',{'login-session-include':'modulePath = "login";'},'Verify actual generated greetd/login PAM stacks, provisioned fixture login and failure/lockout behavior.'),
 ('login-registration','nixos/modules/programs/shadow.nix',{'login-block':'login = {','session-registration':'startSession = true;'},'Verify the real non-root login registers a session without bypassing authentication.'),
 ('pam-systemd','nixos/modules/security/pam.nix',{'session-gate':'enable = cfg.startSession;','pam-systemd-module':'/lib/security/pam_systemd.so'},'Observe PAM session opening, runtime-directory ownership and cleanup; source presence is insufficient.'),
 ('logind-runtime','nixos/modules/system/boot/systemd/logind.nix',{'user-manager-template':'"user@.service"','runtime-directory-template':'"user-runtime-dir@.service"'},'Test active seat/session, user manager and safe logout/restart; do not restart host logind.'),
 ('base-system-bus','nixos/modules/system/boot/systemd.nix',{'independent-dbus-enable':'services.dbus.enable = true;'},'Verify generated local system/session bus units in both network modes; Avahi is not their required enable path.'),
 ('user-session-bus','nixos/modules/services/system/dbus.nix',{'session-socket':'systemd.user.sockets.dbus.wantedBy'},'Prove actual user-bus service identity and environment delivery; socket metadata cannot prove connectivity.'),
 ('audio-session','nixos/modules/services/desktops/pipewire/pipewire.nix',{'bus-lifecycle-link':'systemd.user.services.pipewire.bindsTo = [ "dbus.service" ];'},'Qualify PipeWire/WirePlumber socket activation and real playback/capture without WAN or weakened ACLs.'),
 ('cosmic-core','nixos/modules/services/desktop-managers/cosmic.nix',{'session-package':'systemd.packages = [ pkgs.cosmic-session ];','portal-selection':'xdg-desktop-portal-cosmic','input-service':'services.libinput.enable = true;'},'Realize full core package closure; test compositor/settings daemon/portal startup and teardown.'),
 ('gpu-input','nixos/modules/hardware/graphics.nix',{'driver-environment':'name = "graphics-drivers";'},'Test Intel DRM/Mesa/EGL, firmware policy, logind device ACLs and keyboard/input on target hardware; no broad group/privilege workaround.'),
 ('portal-dispatch','nixos/modules/config/xdg/portal.nix',{'portal-bus-packages':'services.dbus.packages = packages;'},'Exercise portal activation and bounded user-mediated file/screen sharing; metadata is not functional proof.')]
def audit(repository,source,output):
 repository,source,output=[Path(p).resolve() for p in (repository,source,output)];output.mkdir(mode=0o700)
 evidence=repository/'distro/integration/evidence';cached=verify(repository,json.loads((evidence/'cosmic-ordering-001/result.json').read_text()),json.loads((evidence/'session-network-modes-001/result.json').read_text()))
 revision=json.loads((repository/'distro/nix/nixpkgs-candidate.json').read_text())['revision'];rows=[]
 for name,file,markers,proof in SPECS:
  raw=(source/file).read_bytes();text=raw.decode();lines={}
  for label,marker in markers.items():
   hits=[i for i,line in enumerate(text.splitlines(),1) if marker in line]
   if not hits:raise ValueError('selected source marker absent: '+name+'/'+label)
   lines[label]=hits
  rows.append({'dependency':name,'file':file,'sha256':hashlib.sha256(raw).hexdigest(),'source_marker_lines':lines,'source_url':'https://github.com/NixOS/nixpkgs/blob/'+revision+'/'+file,'runtime_verified':False,'required_runtime_proof':proof})
 report={'selected_source_markers_present':True,'expected_source_revision':revision,'whole_source_pin_reverified':False,'dependencies':rows,'cached_fragment_consistency':cached,'memory':observe(),'full_evaluation_attempted':False,'guest_started':False,'host_activation':False,'image_ready':False,'execution_authorized':False,'scope':'selected source markers/line locations and narrow cached consistency; not generated config, dependency closure, authenticated native evidence or runtime health'}
 (output/'result.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('repository');p.add_argument('source');p.add_argument('output');a=p.parse_args();r=audit(a.repository,a.source,a.output);print(json.dumps({'selected_source_markers_present':True,'dependencies':len(r['dependencies']),'image_ready':False}))
