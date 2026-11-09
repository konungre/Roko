:- initialization(main, main).
main :-
    catch(diagnostics(run), Error, (print_message(error, Error), halt(1))), halt(0).
diagnostics(Goal) :-
    current_output(Previous),
    setup_call_cleanup(set_output(user_error), Goal, set_output(Previous)).
run :-
    set_stream(user_input, encoding(utf8)),
    set_stream(user_output, encoding(utf8)),
    getenv('PETTA_PATH', Petta),
    atom_concat(Petta, '/src/metta.pl', Source), consult(Source),
    getenv('OMEGA_PATH', Omega), assertz(working_dir(Omega)),
    process_metta_string("!(import! &self src/utils.py)", [true]),
    process_metta_string("!(import! &self src/loop.metta)", [true]),
    process_metta_string("!(import! &self src/providers.metta)", [true]),
    getenv('ROKO_CONVERSATION_STEP', Step),
    read_file_to_string(Step, Program, []),
    process_metta_string(Program, _),
    (getenv('ROKO_RECOVERED_PROFILE', _) ->
      janus:py_call(recovered:initialize(), @(true)),
      setup_call_cleanup(true, turns, janus:py_call(recovered:finish(), @(true)))
    ; janus:py_call(conversation:initialize(), @(true)), turns).
turns :-
    read_line_to_string(user_input, Line),
    ( Line == end_of_file -> true
    ; string_length(Line, Length), Length =< 20000,
      janus:py_call(conversation:prepare_json(Line), @(true)),
      (getenv('ROKO_RECOVERED_PROFILE', _) ->
        process_metta_string("!(rokoRecoveredStep)", [Reply])
      ; process_metta_string("!(rokoConversationStep)", [Reply])),
      format(user_output, '~s~n', [Reply]), flush_output(user_output),
      turns
    ).
