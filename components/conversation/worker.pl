:- initialization(main, main).
main :-
    catch(run, Error, (print_message(error, Error), halt(1))), halt(0).
run :-
    set_stream(user_input, encoding(utf8)),
    set_stream(user_output, encoding(utf8)),
    getenv('PETTA_PATH', Petta),
    atom_concat(Petta, '/src/metta.pl', Source), consult(Source),
    getenv('OMEGA_PATH', Omega), assertz(working_dir(Omega)),
    process_metta_string("!(import! &self src/utils.py)", [true]),
    process_metta_string("!(import! &self src/loop.metta)", [true]),
    getenv('ROKO_CONVERSATION_STEP', Step),
    read_file_to_string(Step, Program, []),
    process_metta_string(Program, _),
    janus:py_call(conversation:initialize(), @(true)),
    turns.
turns :-
    read_line_to_string(user_input, Line),
    ( Line == end_of_file -> true
    ; string_length(Line, Length), Length =< 20000,
      janus:py_call(conversation:prepare_json(Line), @(true)),
      process_metta_string("!(rokoConversationStep)", [Reply]),
      format('~s~n', [Reply]), flush_output,
      turns
    ).
