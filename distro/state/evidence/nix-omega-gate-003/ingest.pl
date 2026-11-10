:- initialization(main,main).
main :- consult('/workspace/scratch/roko-symbolic-local-001/petta/src/metta.pl'),
assertz(working_dir('/workspace/scratch/roko-symbolic-local-001/omega')),
process_metta_string("!(import! &self src/utils.py)",[true]),
process_metta_string("!(import! &self src/providers.metta)",[true]),
process_metta_string("!(add-atom &self (roko-os-fact v1 private-profile-gate nix 1 observed profile-operation-1 h54bd34dd0bc6c42b1c0de469a6e787b2c7551bfceb8247446a41720be4ac284a h0000000000000000000000000000000000000000000000000000000000000000))",_),
process_metta_string("!(match &self (roko-os-fact v1 private-profile-gate nix 1 observed profile-operation-1 h54bd34dd0bc6c42b1c0de469a6e787b2c7551bfceb8247446a41720be4ac284a h0000000000000000000000000000000000000000000000000000000000000000) ok)",[ok]),
process_metta_string("!(add-atom &self (roko-os-fact v1 private-profile-gate nix 2 observed profile-operation-2 h45d99b212164ec9c484d984ed4d498c665364a3aa3cbe10f383c03d0c726dc52 h11632b9408459c42bf5d7e5a95638a11690f29a43f7c2da925c4715aae75ad2f))",_),
process_metta_string("!(match &self (roko-os-fact v1 private-profile-gate nix 2 observed profile-operation-2 h45d99b212164ec9c484d984ed4d498c665364a3aa3cbe10f383c03d0c726dc52 h11632b9408459c42bf5d7e5a95638a11690f29a43f7c2da925c4715aae75ad2f) ok)",[ok]),
process_metta_string("!(add-atom &self (roko-os-fact v1 private-profile-gate nix 3 observed profile-operation-3 hf88d1d36e4246dd1870d1b130ed967459ff9dfb9d74ba2d489876fac87be969c hcefefae975c5ae553f5d3230e3ffbda426b30d7638d15fbc2adee2e7fcfc8988))",_),
process_metta_string("!(match &self (roko-os-fact v1 private-profile-gate nix 3 observed profile-operation-3 hf88d1d36e4246dd1870d1b130ed967459ff9dfb9d74ba2d489876fac87be969c hcefefae975c5ae553f5d3230e3ffbda426b30d7638d15fbc2adee2e7fcfc8988) ok)",[ok]),
writeln('ROKO_NATIVE_PROFILE_OMEGA_PASS'),
halt(0).
