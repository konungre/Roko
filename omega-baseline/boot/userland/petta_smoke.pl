% Finite real PeTTa and Janus checks. No ECAN, MORK, model, or external action.
:- initialization(main, main).

main :-
    ( catch((getenv('PETTA_PATH', Root),
           atom_concat(Root, '/src/metta.pl', Source),
           consult(Source),
           process_metta_string("!(* 7 8)", Results),
           (Results == [56] -> true ; throw(unexpected_petta_result(Results))),
           format('ROKO_GUEST_PETTA_ARITHMETIC_PASSED result=56~n'),
           janus:py_call(builtins:sum([20,22]), PythonResult),
           (PythonResult == 42 -> true ; throw(unexpected_janus_result(PythonResult))),
           format('ROKO_GUEST_JANUS_PASSED result=42~n'),
           (getenv('OMEGA_PATH', Omega) -> true ; Omega = '/opt/roko/omega'),
           assertz(working_dir(Omega)),
           format(string(ImportUtils), '!(import! &self ~w/src/utils.py)', [Omega]),
           format(string(ImportLoop), '!(import! &self ~w/src/loop.metta)', [Omega]),
           process_metta_string(ImportUtils, _),
           process_metta_string(ImportLoop, _),
           process_metta_string("!(messagesClear)", _),
           process_metta_string("!(py-call (builtins.len (messagesGet)))", [0]),
           process_metta_string("!(messagesAppend (guest-evidence verified))", _),
           process_metta_string("!(py-call (builtins.len (messagesGet)))", [1]),
           process_metta_string("!(messagesClear)", _),
           process_metta_string("!(py-call (builtins.len (messagesGet)))", [0]),
           format('ROKO_GUEST_OMEGA_MESSAGES_PASSED counts=0,1,0~n')), Error,
          (print_message(error, Error), fail))
      -> system:halt(0)
      ; system:halt(1)
    ).
