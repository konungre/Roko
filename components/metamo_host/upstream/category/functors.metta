
(: AppraisalComonad Type)
(: appraisalComonad (-> Symbol Symbol AppraisalComonad))

(: DecisionMonad Type)
(: decisionMonad (-> Symbol Symbol Symbol DecisionMonad))

(: DecisionResult Type)
(: decisionResult (-> ActionType Expression DecisionResult))

(: TranslationFunctor Type)
(: translationFunctor (-> Expression Expression TranslationFunctor))

;; Extract the symbol identifying the extraction function from an AppraisalComonad.
;; Example: (appraisalExtractSymbol (appraisalComonad myExtractFn myAppraiseFn)) -> myExtractFn
(= (appraisalExtractSymbol (appraisalComonad $extractFn $appraiseFn))
    $extractFn
)

;; Extract the symbol identifying the mapping/appraisal function from an AppraisalComonad.
;; Example: (appraisalMapSymbol (appraisalComonad myExtractFn myAppraiseFn)) -> myAppraiseFn
(= (appraisalMapSymbol (appraisalComonad $extractFn $appraiseFn))
    $appraiseFn
)

;; Alias for appraisalMapSymbol, extracting the appraisal function symbol.
;; Example: (appraisalAppraiseSymbol (appraisalComonad f g)) -> g
(= (appraisalAppraiseSymbol (appraisalComonad $extractFn $appraiseFn))
    $appraiseFn
)

;; Extract the symbol identifying the unit function from a DecisionMonad.
;; Example: (decisionUnitSymbol (decisionMonad u d s)) -> u
(= (decisionUnitSymbol (decisionMonad $unitFn $decideFn $scoreFn))
    $unitFn
)

;; Extract the symbol identifying the decision function from a DecisionMonad.
;; Example: (decisionMapSymbol (decisionMonad u d s)) -> d
(= (decisionMapSymbol (decisionMonad $unitFn $decideFn $scoreFn))
    $decideFn
)

;; Alias for decisionMapSymbol, extracting the decision function symbol.
;; Example: (decisionDecideSymbol (decisionMonad u d s)) -> d
(= (decisionDecideSymbol (decisionMonad $unitFn $decideFn $scoreFn))
    $decideFn
)

;; Extract the symbol identifying the candidate scoring function from a DecisionMonad.
;; Example: (decisionScoreSymbol (decisionMonad u d s)) -> s
(= (decisionScoreSymbol (decisionMonad $unitFn $decideFn $scoreFn))
    $scoreFn
)

;; Extract the chosen action from a DecisionResult.
;; Example: (decisionAction (decisionResult MOVE (0.1 -0.2))) -> MOVE
(= (decisionAction (decisionResult $action $deltaG))
    $action
)

;; Extract the proposed goal change (DeltaG) from a DecisionResult.
;; Example: (decisionDeltaG (decisionResult MOVE (0.1 -0.2))) -> (0.1 -0.2)
(= (decisionDeltaG (decisionResult $action $deltaG))
    $deltaG
)

;; Wrapper to extract features from a state using an appraisal comonad.
;; Example: (extract myAppraisal currentState)
(= (extract $appraisal $state)
    (extractWith $appraisal $state)
)

;; Executes the extraction function of an AppraisalComonad on a given state.
;; Example: (extractWith (appraisalComonad getFeatures g) myState) -> (eval (getFeatures myState))
(= (extractWith (appraisalComonad $extractFn $appraiseFn) $state)
    (eval ($extractFn $state))
)

;; Wrapper to appraise a stimulus given the current state using an appraisal comonad.
;; Example: (appraise myAppraisal currentState stimulus)
(= (appraise $appraisal $state $stimulus)
    (appraiseWith $appraisal $state $stimulus)
)

;; Executes the appraisal function of an AppraisalComonad on a state and stimulus.
;; Example: (appraiseWith (appraisalComonad f myAppraise) myState myStim) -> (eval (myAppraise myState myStim))
(= (appraiseWith (appraisalComonad $extractFn $appraiseFn) $state $stimulus)
    (eval ($appraiseFn $state $stimulus))
)

;; Wrapper to compute the identity/unit state for a decision monad.
;; Example: (unit myDecision currentState)
(= (unit $decision $state)
    (unitWith $decision $state)
)

;; Executes the unit function of a DecisionMonad on a given state.
;; Example: (unitWith (decisionMonad myUnit d s) myState) -> (eval (myUnit myState))
(= (unitWith (decisionMonad $unitFn $decideFn $scoreFn) $state)
    (eval ($unitFn $state))
)

;; Wrapper to make a decision from a set of candidates using a decision monad.
;; Example: (decide myDecision currentState (MOVE STAY))
(= (decide $decision $state $candidates)
    (decideWith $decision $state $candidates)
)

;; Executes the decision function of a DecisionMonad on state and candidates.
;; Example: (decideWith (decisionMonad u myDecide s) myState myCandidates) -> (eval (myDecide myState myCandidates))
(= (decideWith (decisionMonad $unitFn $decideFn $scoreFn) $state $candidates)
    (eval ($decideFn $state $candidates))
)

;; Wrapper to score a single candidate using a decision monad.
;; Example: (scoreCandidate myDecision currentState MOVE)
(= (scoreCandidate $decision $state $candidate)
    (scoreCandidateWith $decision $state $candidate)
)

;; Executes the scoring function of a DecisionMonad for a specific candidate.
;; Example: (scoreCandidateWith (decisionMonad u d myScore) myState myCandidate) -> (eval (myScore myState myCandidate))
(= (scoreCandidateWith (decisionMonad $unitFn $decideFn $scoreFn) $state $candidate)
    (eval ($scoreFn $state $candidate))
)

;; Extract the goal translation matrix from a TranslationFunctor.
;; Example: (translationGoalMatrix (translationFunctor gMatrix mMatrix)) -> gMatrix
(= (translationGoalMatrix (translationFunctor $goalTranslation $modTranslation))
    $goalTranslation
)

;; Extract the modulator translation matrix from a TranslationFunctor.
;; Example: (translationModulatorMatrix (translationFunctor gMatrix mMatrix)) -> mMatrix
(= (translationModulatorMatrix (translationFunctor $goalTranslation $modTranslation))
    $modTranslation
)

;; Validates that the goal translation matrix in the functor is square.
;; Example: (validateTranslationFunctor myFunctor) -> True (if gMatrix is square)
(= (validateTranslationFunctor (translationFunctor $goalTranslation $modTranslation))
    (matrixIsSquare $goalTranslation)
)

;; Simulates a peer's motivational state by applying translation matrices to goals and modulators.
;; Example: (simulatePeer myFunctor (motivation goals mods))
(= (simulatePeer (translationFunctor $goalTranslation $modTranslation) (motivation $goals $modulators))
    (motivation
        (clipVector (matrixVectorDot $goalTranslation $goals) 0.0 1.0)
        (clipVector (matrixVectorDot $modTranslation $modulators) 0.0 1.0)
    )
)
