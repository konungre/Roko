# Bootstrap prototype only. Host tool paths are explicit, not a hermetic closure.
{ bootstrapPython, bootstrapPath, sourceHashes, sourceRoot ? ../../omega-baseline/boot
, system ? "x86_64-linux" }:
assert system == "x86_64-linux";
assert builtins.hashFile "sha256" (sourceRoot + "/init.c") == sourceHashes.init;
assert builtins.hashFile "sha256" (sourceRoot + "/build.py") == sourceHashes.builder;
let
  sources = builtins.path {
    path = sourceRoot + "/..";
    name = "roko-rescue-sources";
    filter = path: type:
      (type == "directory" && builtins.baseNameOf path == "boot") ||
      (type == "regular" && builtins.elem (builtins.baseNameOf path) [ "init.c" "build.py" ]);
  };
in builtins.derivation {
  name = "roko-bootstrap-rescue";
  inherit system;
  builder = bootstrapPython;
  args = [ "-B" "${sources}/boot/build.py" "--minimal" "--output" (builtins.placeholder "out") ];
  PATH = bootstrapPath;
  PYTHONHOME = builtins.dirOf (builtins.dirOf bootstrapPython);
  LANG = "C";
  LC_ALL = "C";
  TZ = "UTC";
  SOURCE_DATE_EPOCH = "0";
  PYTHONDONTWRITEBYTECODE = "1";
}
