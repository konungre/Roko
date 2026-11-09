% Original upstream NAL-1 definitions, two premises, no memory/control loop.
:- initialization(main, main).

main :-
    set_stream(user_output, encoding(utf8)),
    set_stream(user_error, encoding(utf8)),
    ( catch((routing_self_check, diagnostics(gate(Json))), Error,
             (print_message(error, Error), fail))
      -> format(user_output, '~s~n', [Json]), halt(0)
      ; halt(1)
    ).

diagnostics(Goal) :-
    current_output(Previous),
    setup_call_cleanup(set_output(user_error), Goal, set_output(Previous)).

routing_self_check :-
    current_output(Before),
    catch(diagnostics((format('ROKO_NARS_OUTPUT_ROUTE_SENTINEL~n'),
                       throw(roko_route_sentinel))), roko_route_sentinel, true),
    current_output(After),
    (After == Before -> true ; throw(output_route_not_restored)).

gate(Json) :-
    getenv('PETTA_PATH', Petta),
    atom_concat(Petta, '/src/metta.pl', Source), consult(Source),
    janus:py_call(nars_bridge:initialize(), @(true)),
    janus:py_call(nars_bridge:module_paths(), Paths, [py_string_as(string)]),
    Paths=[_,_], maplist(load_fixed, Paths),
    janus:py_call(nars_bridge:values(), [F1i,C1i,F2i,C2i]),
    maplist(integer, [F1i,C1i,F2i,C2i]),
    between(0,1000,F1i), between(0,999,C1i),
    between(0,1000,F2i), between(0,999,C2i),
    F1 is F1i / 1000, C1 is C1i / 1000,
    F2 is F2i / 1000, C2 is C2i / 1000,
    % Only generated n0/n1/n2 symbols and four bounded numbers reach source.
    format(string(Expression),
      '!(|- ((n0 --> n1) (~17g ~17g)) ((n1 --> n2) (~17g ~17g)))',
      [F1,C1,F2,C2]),
    process_metta_string(Expression, Results),
    Results=[_,_], maplist(observe, Results),
    janus:py_call(nars_bridge:finish(), Json, [py_string_as(string)]).

load_fixed(Path) :-
    string(Path), load_metta_file(Path, []),
    janus:py_call(nars_bridge:imported(Path), @(true)).

index(n0,0).
index(n2,2).

observe([[Subject,'-->',Predicate],[F,C]]) :-
    ground([Subject,Predicate,F,C]),
    index(Subject,A), index(Predicate,B), A =\= B,
    number(F), number(C),
    janus:py_call(nars_bridge:observed(A,B,F,C), @(true)).
