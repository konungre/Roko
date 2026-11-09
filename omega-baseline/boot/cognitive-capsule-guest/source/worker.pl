% Bounded trusted fixture, never a general MeTTa/Prolog service.
% Request content is only data returned by fixed Janus calls. There is no
% interpolation of request data into source, consult paths or py-call names.
:- initialization(main, main).

main :-
    set_stream(user_output, encoding(utf8)),
    set_stream(user_error, encoding(utf8)),
    ( catch(gate(Json), Error, (print_message(error, Error), fail))
      -> format('~s~n', [Json]), halt(0)
      ; halt(1)
    ).

gate(Json) :-
    getenv('PETTA_PATH', Petta),
    atom_concat(Petta, '/src/metta.pl', Source), consult(Source),
    getenv('OMEGA_PATH', Omega), assertz(working_dir(Omega)),
    % These are fixed relative import paths under the manifest-checked Omega root.
    process_metta_string("!(import! &self src/utils.py)", [true]),
    process_metta_string("!(import! &self src/loop.metta)", [true]),
    janus:py_call(cognitive_bridge:initialize(), @(true)),
    process_metta_string("!(messagesClear)", [true]),
    process_metta_string("!(py-call (builtins.len (messagesGet)))", [0]),
    process_metta_string("!(messagesAppend (py-call (cognitive_bridge.evidence_json)))", [true]),
    process_metta_string("!(py-call (builtins.len (messagesGet)))", [1]),
    process_metta_string("!(py-call (cognitive_bridge.check_roundtrip (messagesGet)))", [true]),
    janus:py_call(cognitive_bridge:operation(), Operation, [py_string_as(string)]),
    compute(Operation, Answer),
    process_metta_string("!(messagesClear)", [true]),
    process_metta_string("!(py-call (builtins.len (messagesGet)))", [0]),
    janus:py_call(cognitive_bridge:runtime_attestation(), @(true)),
    janus:py_call(cognitive_bridge:finish(Answer), Json, [py_string_as(string)]).

compute("roundtrip", "roundtrip-only").
compute("arithmetic", Answer) :-
    janus:py_call(cognitive_bridge:operator(), Operator, [py_string_as(string)]),
    expression(Operator, Expression),
    process_metta_string(Expression, [Answer]), integer(Answer).

% Complete source allowlist. Operands are validated integers, not source text.
expression("+", "!(+ (py-call (cognitive_bridge.left)) (py-call (cognitive_bridge.right)))").
expression("-", "!(- (py-call (cognitive_bridge.left)) (py-call (cognitive_bridge.right)))").
expression("*", "!(* (py-call (cognitive_bridge.left)) (py-call (cognitive_bridge.right)))").
