% Fixed upstream MAGUS scoring and proposal selection. No application actions.
:- initialization(main, main).
main :-
    set_stream(user_output, encoding(utf8)),
    set_stream(user_error, encoding(utf8)),
    ( catch((routing_self_check, diagnostics(gate(Json))), Error,
             (print_message(error, Error), fail))
      -> format(user_output, '~s~n', [Json]), halt(0)
      ; halt(1) ).

diagnostics(Goal) :-
    current_output(Previous),
    setup_call_cleanup(set_output(user_error), Goal, set_output(Previous)).
routing_self_check :-
    current_output(Before),
    catch(diagnostics((format('ROKO_METAMO_OUTPUT_ROUTE_SENTINEL~n'),
                       throw(roko_output_route_sentinel))), roko_output_route_sentinel, true),
    current_output(After),
    (After == Before -> true ; throw(output_route_not_restored)).

gate(Json) :-
    getenv('PETTA_PATH', Petta), atom_concat(Petta, '/src/metta.pl', Source), consult(Source),
    getenv('ROKO_METAMO_SOURCE', Root), assertz(working_dir(Root)),
    janus:py_call(bridge:initialize(), @(true)),
    process_metta_string("!(import! &self (library lib_he))", [true]),
    janus:py_call(bridge:module_paths(), Paths, [py_string_as(string)]),
    format(user_error, 'ROKO_METAMO_STAGE imports~n', []),
    maplist(import_module, Paths),
    janus:py_call(bridge:probe_expressions(), Probes, [py_string_as(string)]),
    maplist(probe, Probes),
    janus:py_call(bridge:score_expressions(), Scores, [py_string_as(string)]),
    maplist(score, Scores),
    format(user_error, 'ROKO_METAMO_STAGE selection~n', []),
    janus:py_call(bridge:decision_expression(selected), Select, [py_string_as(string)]),
    process_metta_string(Select, [Selected]), atom(Selected),
    atom_concat(metamo_candidate_, Digits, Selected), atom_number(Digits, Index),
    integer(Index), between(0,7,Index),
    format(user_error, 'ROKO_METAMO_STAGE delta~n', []),
    janus:py_call(bridge:decision_expression(delta), DeltaExpr, [py_string_as(string)]),
    process_metta_string(DeltaExpr, [Delta]), is_list(Delta), length(Delta,8), maplist(number,Delta),
    janus:py_call(bridge:selected(Selected,Delta), @(true)),
    janus:py_call(bridge:finish(), Json, [py_string_as(string)]).

import_module(Path) :-
    string(Path), format(string(Expression), '!(import! &self ~s)', [Path]),
    process_metta_string(Expression, [true]), janus:py_call(bridge:imported(Path), @(true)).
probe(Expression) :-
    string(Expression), janus:py_call(bridge:probe_index(), Index), integer(Index), between(0,15,Index),
    format(user_error, 'ROKO_METAMO_STAGE probe ~d~n', [Index]),
    process_metta_string(Expression, [Value]),
    janus:py_call(bridge:probe(Value), @(true)).
score(Expression) :-
    string(Expression), janus:py_call(bridge:score_index(), Index), integer(Index), between(0,7,Index),
    format(user_error, 'ROKO_METAMO_STAGE score ~d~n', [Index]),
    process_metta_string(Expression, [Value]), number(Value),
    janus:py_call(bridge:score(Value), @(true)).
