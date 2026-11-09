# Pinned ISO derivation prototype; evaluation is not a build/boot result.
{ nixpkgsSource, expectedSourceNarHash, enableCosmic ? false, adminPublicKey ? null
, system ? "x86_64-linux", firmwarePolicy ? "none", networkPolicy ? "offline"
, adminAccess ? "locked", adminPasswordHash ? null }:
assert builtins.elem firmwarePolicy [ "none" "redistributable" ];
assert builtins.elem networkPolicy [ "offline" "managed" ];
assert builtins.elem adminAccess [ "locked" "console-password" "ssh-key-and-password" ];
assert adminAccess == "locked" || (builtins.isString adminPasswordHash && builtins.match "\\$(y|6)\\$[^: \n]+" adminPasswordHash != null);
assert adminAccess != "ssh-key-and-password" || (networkPolicy == "managed" && builtins.isString adminPublicKey && builtins.match "ssh-ed25519 [A-Za-z0-9+/]+={0,3}( .*)?" adminPublicKey != null);
let
  pinned = builtins.path {
    path = nixpkgsSource;
    sha256 = expectedSourceNarHash;
    name = "roko-nixpkgs-pinned";
  };
in import ./system-eval.nix {
  inherit nixpkgsSource expectedSourceNarHash enableCosmic adminPublicKey system;
  liveMedia = true;
  extraModules = [
    (pinned + "/nixos/modules/installer/cd-dvd/iso-image.nix")
    ({ lib, pkgs, ... }: {
      system.autoUpgrade.enable = lib.mkForce false;
      nix.gc.automatic = lib.mkForce false;
      nix.optimise.automatic = lib.mkForce false;
      environment.etc."roko/first-boot.json".text = builtins.toJSON {
        schema = "roko-first-boot-policy-v1";
        offlineRequested = networkPolicy == "offline";
        networkIsolationProven = false;
        automaticUpgrade = false;
        automaticGenerationDeletion = false;
        modelReady = false;
        durableHistoryReady = false;
        credentialProvisioningRequired = adminAccess == "locked";
      };
      systemd.services.roko-startup-report = {
        description = "Roko boot-local policy diagnostics (not runtime readiness)";
        wantedBy = [ "multi-user.target" ];
        after = [ "local-fs.target" ];
        before = [ "multi-user.target" "display-manager.service" ];
        unitConfig.OnFailure = [ "roko-startup-report-failure.service" ];
        serviceConfig = {
          Type = "oneshot";
          RemainAfterExit = true;
          ExecStart = "${pkgs.python3}/bin/python3 ${./startup_report.py} --policy /etc/roko/first-boot.json --output /run/roko-startup/status.json";
          DynamicUser = true;
          RuntimeDirectory = "roko-startup";
          RuntimeDirectoryMode = "0750";
          RuntimeDirectoryPreserve = "yes";
          UMask = "0027";
          TimeoutStartSec = "15s";
          NoNewPrivileges = true;
          ProtectSystem = "strict";
          ProtectHome = true;
          PrivateTmp = true;
          PrivateNetwork = true;
          RestrictAddressFamilies = [ "AF_UNIX" ];
          CapabilityBoundingSet = "";
        };
      };
      systemd.services.roko-startup-report-failure = {
        description = "Report Roko startup diagnostic failure";
        serviceConfig = {
          Type = "oneshot";
          ExecStart = "${pkgs.coreutils}/bin/echo Roko startup diagnostics failed; runtime readiness is unknown. Inspect journalctl -u roko-startup-report.";
          DynamicUser = true;
          NoNewPrivileges = true;
          ProtectSystem = "strict";
          ProtectHome = true;
          PrivateNetwork = true;
        };
      };
      networking.networkmanager.enable = lib.mkForce (networkPolicy == "managed");
      networking.useDHCP = lib.mkForce false;
      hardware.enableAllFirmware = lib.mkForce false;
      hardware.enableRedistributableFirmware = lib.mkForce (firmwarePolicy == "redistributable");
      users.users.roko.hashedPassword = lib.mkForce (if adminAccess == "locked" then "!" else adminPasswordHash);
      security.sudo.enable = lib.mkForce (adminAccess != "locked");
      security.sudo.wheelNeedsPassword = true;
      services.openssh.enable = lib.mkForce (adminAccess == "ssh-key-and-password");
      services.openssh.settings = {
        PermitRootLogin = "no";
        AuthenticationMethods = "publickey";
        AllowUsers = [ "roko" ];
        PermitEmptyPasswords = false;
        PasswordAuthentication = false;
        KbdInteractiveAuthentication = false;
      };
      image.baseName = lib.mkForce "roko-live-evaluation";
      isoImage.volumeID = "ROKO_LIVE_EVAL";
      isoImage.makeEfiBootable = true;
      isoImage.makeBiosBootable = true;
      isoImage.makeUsbBootable = true;
      boot.loader.timeout = lib.mkForce 3;
      services.getty.autologinUser = lib.mkForce null;
      services.displayManager.autoLogin.enable = lib.mkForce false;
      environment.etc."roko/live-scope.json".text = builtins.toJSON {
        schema = "roko-live-evaluation-v1";
        inherit firmwarePolicy networkPolicy adminAccess;
        ephemeralRoot = true;
        persistentHistoryQualified = false;
        modelIncluded = false;
        bootTested = false;
        productionReady = false;
      };
    })
    ({ lib, ... }: lib.mkIf (networkPolicy == "offline") {
      nix.channel.enable = lib.mkForce false;
      nix.nixPath = lib.mkForce [];
      nix.registry = lib.mkForce {};
      nix.settings.substituters = lib.mkForce [];
      nix.settings.flake-registry = lib.mkForce "";
      systemd.network.wait-online.enable = lib.mkForce false;
      systemd.services.NetworkManager-wait-online.enable = lib.mkForce false;
    })
  ];
}
