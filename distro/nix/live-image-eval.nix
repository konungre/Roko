# Pinned ISO derivation prototype; evaluation is not a build/boot result.
{ nixpkgsSource, expectedSourceNarHash, enableCosmic ? false, adminPublicKey ? null
, system ? "x86_64-linux" }:
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
        ephemeralRoot = true;
        persistentHistoryQualified = false;
        modelIncluded = false;
        bootTested = false;
        productionReady = false;
      };
    })
  ];
}
