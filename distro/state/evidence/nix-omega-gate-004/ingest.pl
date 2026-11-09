:- initialization(main,main).
main :- consult('/workspace/scratch/roko-symbolic-local-001/petta/src/metta.pl'),
assertz(working_dir('/workspace/scratch/roko-symbolic-local-001/omega')),
process_metta_string("!(import! &self src/utils.py)",[true]),
process_metta_string("!(import! &self src/providers.metta)",[true]),
process_metta_string("!(add-atom &self (roko-os-fact v1 private-profile-gate nix 1 observed profile-operation-1 h52d780458935c03fa7f313f0889a9a738ae0fd95c0263f8533e46986e48d83e7 h0000000000000000000000000000000000000000000000000000000000000000))",_),
process_metta_string("!(match &self (roko-os-fact v1 private-profile-gate nix 1 observed profile-operation-1 h52d780458935c03fa7f313f0889a9a738ae0fd95c0263f8533e46986e48d83e7 h0000000000000000000000000000000000000000000000000000000000000000) ok)",[ok]),
process_metta_string("!(add-atom &self (roko-os-fact v1 private-profile-gate nix 2 observed profile-operation-2 h7d286edd5e4b8dd079a7940f16d2535c466a507cc01075d45aa78f599737a4a9 he3d2239472b2e53179a1ab7a22fbe17ecac10e0f2ecb562593b5972ff50e8a66))",_),
process_metta_string("!(match &self (roko-os-fact v1 private-profile-gate nix 2 observed profile-operation-2 h7d286edd5e4b8dd079a7940f16d2535c466a507cc01075d45aa78f599737a4a9 he3d2239472b2e53179a1ab7a22fbe17ecac10e0f2ecb562593b5972ff50e8a66) ok)",[ok]),
process_metta_string("!(add-atom &self (roko-os-fact v1 private-profile-gate nix 3 observed profile-operation-3 h5d7c9f5e72c5a0f934e513f0aaf7b922161f18e1742cdfeb0be05437cc100536 h24cfcc3a4cfcf68d311e8ca7af7b797c0bf24eb3ec00020e0662774c96c8caf0))",_),
process_metta_string("!(match &self (roko-os-fact v1 private-profile-gate nix 3 observed profile-operation-3 h5d7c9f5e72c5a0f934e513f0aaf7b922161f18e1742cdfeb0be05437cc100536 h24cfcc3a4cfcf68d311e8ca7af7b797c0bf24eb3ec00020e0662774c96c8caf0) ok)",[ok]),
writeln('ROKO_NATIVE_PROFILE_OMEGA_PASS'),
halt(0).
