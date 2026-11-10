# Offline policy override; no claim of network namespace/firewall isolation.
{ lib }:
{
  services.avahi.enable = lib.mkForce false;
  services.geoclue2.enable = lib.mkForce false;
  nix.channel.enable = lib.mkForce false;
  nix.nixPath = lib.mkForce [];
  nix.registry = lib.mkForce {};
  nix.settings.substituters = lib.mkForce [];
  nix.settings.flake-registry = lib.mkForce "";
  systemd.network.wait-online.enable = lib.mkForce false;
  systemd.services.NetworkManager-wait-online.enable = lib.mkForce false;
}
