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
    (getenv('ROKO_FRESH_PROFILE', _) ->
      janus:py_call(fresh:initialize(), @(true)),
      setup_call_cleanup(true, turns, janus:py_call(fresh:finish(), @(true)))
    ; getenv('ROKO_RECOVERED_PROFILE', _) ->
      janus:py_call(recovered:initialize(), @(true)),
      setup_call_cleanup(true, turns, janus:py_call(recovered:finish(), @(true)))
    ; janus:py_call(conversation:initialize(), @(true)), turns).
turns :-
    read_request_line(user_input, Line),
    ( Line == end_of_file -> true
    ; string_length(Line, Length), Length =< 20000,
      janus:py_call(conversation:prepare_json(Line), @(true)),
      ((getenv('ROKO_RECOVERED_PROFILE', _); getenv('ROKO_FRESH_PROFILE', _)) ->
        process_metta_string("!(rokoRecoveredStep)", [Reply])
      ; process_metta_string("!(rokoConversationStep)", [Reply])),
      format(user_output, '~s~n', [Reply]), flush_output(user_output),
      turns
    ).

% Bound allocation while reading, before handing any text to JSON parsing.
% Oversize input terminates the session; no suffix is admitted as another turn.
read_request_line(Stream, Line) :-
    read_request_codes(Stream, 20000, [], Reversed, End),
    (End == eof, Reversed == [] -> Line = end_of_file
    ; reverse(Reversed, Codes), string_codes(Line, Codes)).
read_request_codes(Stream, Remaining, Acc, Codes, End) :-
    get_code(Stream, Code),
    (Code == -1 -> Codes = Acc, End = eof
    ; Code == 10 -> Codes = Acc, End = newline
    ; Remaining =< 0 -> throw(error(resource_error(request_length), read_request_line/2))
    ; Next is Remaining - 1,
      read_request_codes(Stream, Next, [Code|Acc], Codes, End)).
