% Authored fixed fixtures, not a public raw-query or MM2 interface.
% Not executed in this source checkpoint. Only run under a reviewed native gate.
:- initialization(main, main).
main :- catch(run, _, fail), !.
main :- halt(2).
run :- current_prolog_flag(argv, [Bridge]),
       use_foreign_library(Bridge),
       mork("get-atoms", "", ""),
       mork("queue-atom", "(friend sam tim)", "OK: queued"),
       mork("queue-atom", "(friend sam joe)", "OK: queued"),
       mork("flush", "", "OK: flushed"),
       mork("get-atoms", "", All),
       rows(All, ["(friend sam joe)", "(friend sam tim)"]),
       mork("match", "((friend sam $x) (friend sam $x))", Matches),
       rows(Matches, ["(friend sam joe)", "(friend sam tim)"]),
       mork("remove-atoms", "(friend sam joe)", "OK: loaded"),
       mork("match", "((friend sam $x) (friend sam $x))", Remaining),
       rows(Remaining, ["(friend sam tim)"]),
       mork("add-atoms", "(exec 0 (, (friend sam $x)) (O (- (friend sam $x)) (+ (freund sam $x))))", "OK: loaded"),
       mork("mm2-exec", "1", "OK: executed"),
       mork("match", "((freund sam $x) (freund sam $x))", Rewritten),
       rows(Rewritten, ["(freund sam tim)"]),
       mork("match", "((friend sam $x) (friend sam $x))", ""),
       mork("match", "(friend)", "ERR: invalid query tuple"),
       \+ mork("unknown-roko-fixture-command", "", _),
       writeln('MORK_QUALIFICATION_V1'),
       writeln('empty-space'), writeln('queue-and-flush'), writeln('read'),
       writeln('match'), writeln('remove'), writeln('one-step-rewrite'),
       writeln('invalid-query-tuple'), writeln('unknown-command'),
       writeln('MORK_END').
rows(Text, Expected) :- string(Text), string_length(Text, N), N =< 1024,
                        split_string(Text, "\n", "", Parts),
                        exclude(=(""), Parts, Nonempty),
                        msort(Nonempty, Expected).
