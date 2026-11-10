:- initialization(main,main).
main :- consult('/workspace/scratch/roko-symbolic-local-001/petta/src/metta.pl'),
assertz(working_dir('/workspace/scratch/roko-symbolic-local-001/omega')),
process_metta_string("!(import! &self src/utils.py)",[true]),
process_metta_string("!(import! &self src/providers.metta)",[true]),
process_metta_string("!(add-atom &self (roko-os-fact v1 private-profile-gate nix 1 observed profile-operation-1 hdafdb591d434aeed7d2c499b413231b0afc5305d39995e89a4291f44d17f6caa h0000000000000000000000000000000000000000000000000000000000000000))",_),
process_metta_string("!(match &self (roko-os-fact v1 private-profile-gate nix 1 observed profile-operation-1 hdafdb591d434aeed7d2c499b413231b0afc5305d39995e89a4291f44d17f6caa h0000000000000000000000000000000000000000000000000000000000000000) ok)",[ok]),
process_metta_string("!(add-atom &self (roko-os-fact v1 private-profile-gate nix 2 observed profile-operation-2 hf6ac463e38652eca15f9b00161c5c2743d05e784e971a2d3a0dfddc592b879de hfdaeca0759090f966f5bcd431bf46b91d9986f55db7f58ae42aaf6f13c25eefb))",_),
process_metta_string("!(match &self (roko-os-fact v1 private-profile-gate nix 2 observed profile-operation-2 hf6ac463e38652eca15f9b00161c5c2743d05e784e971a2d3a0dfddc592b879de hfdaeca0759090f966f5bcd431bf46b91d9986f55db7f58ae42aaf6f13c25eefb) ok)",[ok]),
process_metta_string("!(add-atom &self (roko-os-fact v1 private-profile-gate nix 3 observed profile-operation-3 habec97c40aaac9992ae07675c0240c07d7208e30396a4326e89e71c4c8c7eeb2 h912bc835887a5e63ff477af54d37765b89365942096a6e02540c174a9bd1cf40))",_),
process_metta_string("!(match &self (roko-os-fact v1 private-profile-gate nix 3 observed profile-operation-3 habec97c40aaac9992ae07675c0240c07d7208e30396a4326e89e71c4c8c7eeb2 h912bc835887a5e63ff477af54d37765b89365942096a6e02540c174a9bd1cf40) ok)",[ok]),
writeln('ROKO_NATIVE_PROFILE_OMEGA_PASS'),
halt(0).
