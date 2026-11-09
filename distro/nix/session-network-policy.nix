# Build-time choice. Managed mode preserves upstream and explicit user settings.
{ lib, offline }:
assert builtins.isBool offline;
lib.mkIf offline (import ./offline-startup.nix { inherit lib; })
