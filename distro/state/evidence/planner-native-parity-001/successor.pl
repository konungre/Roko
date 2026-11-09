:- initialization(main,main).
main :- use_module(library(janus)), consult('/workspace/scratch/roko-symbolic-local-001/petta/src/metta.pl'),
process_metta_string("(desired-package hello \"/nix/store/00000000000000000000000000000000-fixture-hello\")",_),
process_metta_string("!(change-state! &package-plan (match &self (desired-package $name $path) (py-call (package_bridge_v2.plan_single $name $path \"{\\\"packages\\\": {}, \\\"revision\\\": \\\"fixture\\\", \\\"source\\\": \\\"native-successor-test\\\"}\"))))",_),
process_metta_string("!(py-call (package_bridge_v2.operation_count (get-state &package-plan)))",[1]),
process_metta_string("!(py-call (package_bridge_v2.authorizes_actions (get-state &package-plan)))",[false]),
process_metta_string("!(py-call (package_bridge_v2.has_planned_package (get-state &package-plan) \"hello\" \"/nix/store/00000000000000000000000000000000-fixture-hello\"))",[true]),writeln('SUCCESSOR_NATIVE_PARITY_PASS'),halt(0).
