# Evaluation prototype: no successful sandboxed build has been established here.
{ nixpkgsSource, expectedSourceNarHash, sourceHashes
, sourceRoot ? ../../omega-baseline/boot, system ? "x86_64-linux" }:
assert system == "x86_64-linux";
assert builtins.hashFile "sha256" (sourceRoot + "/init.c") == sourceHashes.init;
assert builtins.hashFile "sha256" (sourceRoot + "/build.py") == sourceHashes.builder;
let
  pinned = builtins.path {
    path = nixpkgsSource;
    sha256 = expectedSourceNarHash;
    name = "roko-nixpkgs-pinned";
  };
  pkgs = import pinned { inherit system; config.allowUnfree = false; };
  sources = builtins.path {
    path = sourceRoot + "/..";
    name = "roko-rescue-sources";
    filter = path: type:
      (type == "directory" && builtins.baseNameOf path == "boot") ||
      (type == "regular" && builtins.elem (builtins.baseNameOf path) [ "init.c" "build.py" ]);
  };
in pkgs.stdenv.mkDerivation {
  pname = "roko-pinned-rescue";
  version = "0.1";
  nativeBuildInputs = [ pkgs.python3 ];
  dontUnpack = true;
  dontConfigure = true;
  dontInstall = true;
  dontFixup = true;
  SOURCE_DATE_EPOCH = "0";
  TZ = "UTC";
  PYTHONDONTWRITEBYTECODE = "1";
  buildPhase = ''
    python3 -B ${sources}/boot/build.py --minimal --output "$out"
  '';
}
