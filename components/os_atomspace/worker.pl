% Fresh PeTTa/Omega space, fixed typed-claim ingestion and phase queries only.
:- initialization(main, main).
main :-
    set_stream(user_output, encoding(utf8)),
    current_output(Previous),
    catch(setup_call_cleanup(set_output(user_error), run(Json), set_output(Previous)),
          Error, (print_message(error, Error), halt(1))),
    format(user_output, '~s~n', [Json]), halt(0).
run(Json) :-
    getenv('PETTA_PATH', Petta), atom_concat(Petta, '/src/metta.pl', Source), consult(Source),
    getenv('OMEGA_PATH', Omega), assertz(working_dir(Omega)),
    process_metta_string("!(import! &self src/utils.py)", [true]),
    process_metta_string("!(import! &self src/loop.metta)", [true]),
    process_metta_string("!(import! &self src/providers.metta)", [true]),
    janus:py_call(os_state_bridge:initialize(), @(true)),
    janus:py_call(os_state_bridge:expressions(), Expressions, [py_string_as(string)]),
    maplist(ingest, Expressions),
    janus:py_call(os_state_bridge:phases(), Phases, [py_string_as(string)]),
    maplist(query_phase, Phases),
    janus:py_call(os_state_bridge:finish(), Json, [py_string_as(string)]).
ingest(Expression) :- process_metta_string(Expression, _).
query_phase(Phase) :-
    janus:py_call(os_state_bridge:query(Phase), Expression, [py_string_as(string)]),
    process_metta_string(Expression, Rows),
    janus:py_call(os_state_bridge:observed(Phase,Rows), @(true)).
