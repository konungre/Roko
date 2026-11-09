% Fresh finite guest qualification, not the lost guest worker or a command service.
:- initialization(main, main).

main :-
    set_stream(user_output, encoding(utf8)),
    set_stream(user_error, encoding(utf8)),
    ( catch((routing_self_check, diagnostics(gate(Json))), Error, (print_message(error, Error), fail))
      -> format(user_output, '~s~n', [Json]), halt(0)
      ; halt(1)
    ).

% Fixed stream regression, no source/command input and no replacement worker.
% The sentinel tests cleanup on an exception in the same bounded worker.
diagnostics(Goal) :-
    current_output(Previous),
    setup_call_cleanup(set_output(user_error), Goal, set_output(Previous)).

routing_self_check :-
    current_output(Before),
    catch(diagnostics((format('ROKO_ECAN_OUTPUT_ROUTE_SENTINEL~n'),
                       throw(roko_output_route_sentinel))),
          roko_output_route_sentinel, true),
    current_output(After),
    (After == Before -> true ; throw(output_route_not_restored)).

gate(Json) :-
    getenv('PETTA_PATH', Petta),
    atom_concat(Petta, '/src/metta.pl', Source), consult(Source),
    getenv('ROKO_ECAN_SOURCE', Root), assertz(working_dir(Root)),
    janus:py_call(bank_bridge:initialize(), @(true)),
    process_metta_string("!(import! &self (library lib_import))", [true]),
    process_metta_string("!(import! &self (library lib_he))", [true]),
    process_metta_string("!(import! &self (library lib_spaces))", [true]),
    janus:py_call(bank_bridge:module_paths(), Paths, [py_string_as(string)]),
    maplist(import_module, Paths),
    janus:py_call(bank_bridge:indices(), Indices),
    janus:py_call(bank_bridge:capacity(), Capacity),
    integer(Capacity), between(1,16,Capacity),
    format(string(CapExpr), '!(updateAttentionParam MAX_AF_SIZE ~d)', [Capacity]),
    process_metta_string(CapExpr, _),
    maplist(set_row, Indices),
    maplist(stimulate_row, Indices),
    maplist(read_row, Indices),
    process_metta_string("!(getAfAtoms)", [Focus]), is_list(Focus),
    maplist(native_symbol, Focus),
    process_metta_string("!(getAttentionParam FUNDS_STI)", [STI]), number(STI),
    process_metta_string("!(getAttentionParam FUNDS_LTI)", [LTI]), number(LTI),
    janus:py_call(bank_bridge:focus_and_funds(Focus, STI, LTI), @(true)),
    janus:py_call(bank_bridge:finish(), Json, [py_string_as(string)]).

import_module(Path) :-
    string(Path),
    format(string(Expression), '!(import! &self ~s)', [Path]),
    process_metta_string(Expression, [true]),
    janus:py_call(bank_bridge:imported(Path), @(true)).

set_row(Index) :-
    integer(Index), between(0,15,Index),
    janus:py_call(bank_bridge:row(Index), [STI,LTI,Stimulus]),
    maplist(integer, [STI,LTI,Stimulus]),
    between(0,1000,STI), between(0,1000,LTI), between(0,10,Stimulus),
    format(string(Expression), '!(setAv ecan_atom_~d (~d ~d 0))', [Index,STI,LTI]),
    process_metta_string(Expression, Result), mutation_result(Result).

stimulate_row(Index) :-
    integer(Index), between(0,15,Index),
    janus:py_call(bank_bridge:row(Index), [_,_,Stimulus]),
    integer(Stimulus), between(0,10,Stimulus),
    format(string(Expression), '!(stimulate ecan_atom_~d ~d)', [Index,Stimulus]),
    process_metta_string(Expression, Result), mutation_result(Result).

mutation_result(Result) :-
    with_output_to(string(Text), write_term(Result, [quoted(true),max_depth(8)])),
    janus:py_call(bank_bridge:mutation(Text), @(true)).

read_row(Index) :-
    integer(Index), between(0,15,Index),
    format(string(GetSTI), '!(getSti ecan_atom_~d)', [Index]),
    format(string(GetLTI), '!(getLti ecan_atom_~d)', [Index]),
    process_metta_string(GetSTI, [STI]), number(STI),
    process_metta_string(GetLTI, [LTI]), number(LTI),
    janus:py_call(bank_bridge:score(Index, STI, LTI), @(true)).

native_symbol(Symbol) :-
    atom(Symbol), atom_concat(ecan_atom_, Digits, Symbol),
    atom_number(Digits, Index), integer(Index), between(0,15,Index).
