# Evaluation-only system candidate. No image build, installation or activation.
{ nixpkgsSource, expectedSourceNarHash, enableCosmic ? false, adminPublicKey ? null
, system ? "x86_64-linux", liveMedia ? false, extraModules ? [] }:
assert system == "x86_64-linux";
assert adminPublicKey == null || builtins.isString adminPublicKey;
let
  pinned = builtins.path {
    path = nixpkgsSource;
    sha256 = expectedSourceNarHash;
    name = "roko-nixpkgs-pinned";
  };
in import (pinned + "/nixos/lib/eval-config.nix") {
  inherit system;
  modules = [ ({ ... }: {
    system.stateVersion = "26.05";
    networking.hostName = "roko-evaluation";
    networking.useDHCP = false;
    services.openssh.enable = false;
    documentation.enable = false;
    nixpkgs.config.allowUnfree = false;
    boot.loader.systemd-boot.enable = !liveMedia;
    boot.loader.efi.canTouchEfiVariables = false;
    fileSystems = if liveMedia then {} else {
      "/" = { device = "/dev/disk/by-label/ROKO_ROOT"; fsType = "ext4"; };
      "/boot" = { device = "/dev/disk/by-label/ROKO_EFI"; fsType = "vfat"; };
      "/home" = { device = "/dev/disk/by-label/ROKO_STATE"; fsType = "ext4"; options = [ "nodev" "nosuid" ]; };
    };
    users.mutableUsers = false;
    users.users.root.hashedPassword = "!";
    users.users.roko = {
      isNormalUser = true;
      hashedPassword = "!";
      extraGroups = [ "wheel" ];
      openssh.authorizedKeys.keys = if adminPublicKey == null then [] else [ adminPublicKey ];
    };
    security.sudo.enable = false;
    services.desktopManager.cosmic.enable = enableCosmic;
    services.displayManager.cosmic-greeter.enable = enableCosmic;
    hardware.graphics.enable = enableCosmic;
    environment.etc."roko/evaluation-scope.json".text = builtins.toJSON {
      schema = "roko-system-evaluation-v1";
      packageManager = "nix";
      cosmicRequested = enableCosmic;
      modelIncluded = false;
      atomspaceExecutionAuthority = false;
      licensingResolved = false;
      productionReady = false;
    };
  }) ] ++ extraModules;
}
