; Experimental interface fixture only. This is NOT the upstream ECAN algorithm.
; Three trusted synthetic atoms with integer importance and a fixed resource budget.
(= (importance evidence-a) 6)
(= (importance evidence-b) 3)
(= (importance evidence-c) 1)
(= (focus $atom) (> (importance $atom) 3))
(= (one-step-rent $atom) (if (> (importance $atom) 0) (- (importance $atom) 1) 0))
!(test (focus evidence-a) True)
!(test (focus evidence-b) False)
!(test (focus evidence-c) False)
!(test (+ (+ (importance evidence-a) (importance evidence-b)) (importance evidence-c)) 10)
!(test (+ (+ (one-step-rent evidence-a) (one-step-rent evidence-b)) (one-step-rent evidence-c)) 7)
; Rent goes to a separate pool, so the fixture conserves the initial budget.
!(test (+ (+ (+ (one-step-rent evidence-a) (one-step-rent evidence-b)) (one-step-rent evidence-c)) 3) 10)
!(test (one-step-rent evidence-c) 0)
