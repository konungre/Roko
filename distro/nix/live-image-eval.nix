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
    ({ lib, ... }: {
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
  ];
}
