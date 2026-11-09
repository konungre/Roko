 :- initialization(main, main).
main :- consult('/workspace/scratch/roko-symbolic-local-001/petta/src/metta.pl'),
 process_metta_string("!(add-atom &self (roko-os-fact v1 executor nix 1 built m2jycqzjaj6i9vi7bapz6csi4da1r50k-roko-offline-generation h1d160f61fdd3bf2398a386a7b9fda0ec5d2879bdb1f17b4686b67343d288e511 h0000000000000000000000000000000000000000000000000000000000000000))", _),
 process_metta_string("!(match &self (roko-os-fact v1 executor nix 1 built $g h1d160f61fdd3bf2398a386a7b9fda0ec5d2879bdb1f17b4686b67343d288e511 h0000000000000000000000000000000000000000000000000000000000000000) $g)", R),
 (R = ['m2jycqzjaj6i9vi7bapz6csi4da1r50k-roko-offline-generation'] -> writeln('ROKO_STATE_ATOMSPACE_PASS'),halt(0);writeln(R),halt(1)).
