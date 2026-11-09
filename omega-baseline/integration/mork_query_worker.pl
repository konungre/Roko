% Roko-owned fixed line protocol. Never evaluate caller strings as code.
:- use_module(library(readutil)).
:- initialization(main, main).
main :- catch(run, _, fail), !.
main :- halt(2).
run :- current_prolog_flag(argv, [Bridge]),
       use_foreign_library(Bridge),
       read_line_to_string(current_input, Atoms),
       read_line_to_string(current_input, Query),
       string(Atoms), string(Query),
       string_length(Atoms, A), A =< 1024,
       string_length(Query, Q), Q =< 256,
       mork("add-atoms", Atoms, "OK: loaded"),
       mork("match", Query, Rows),
       string(Rows), string_length(Rows, N), N =< 1024,
       format('MORK_FACTS_V1~n~sMORK_END~n', [Rows]).
