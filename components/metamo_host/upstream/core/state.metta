;; Core state definitions for MetaMo

(: MotivationalState Type)
(: motivation (-> Expression Expression MotivationalState))

(: StimulusState Type)
(: stimulus (-> Expression StimulusState))

(: ActionType Type)
(: action (-> Symbol Expression Number Expression ActionType))

(= (motivationGoals (motivation $goals $modulators))
    $goals
)

(= (motivationModulators (motivation $goals $modulators))
    $modulators
)

(= (stimulusValues (stimulus $values))
    $values
)

(= (actionId (action $actionId $goalCorrelations $riskEstimate $deltaG))
    $actionId
)

(= (actionGoalCorrelations (action $actionId $goalCorrelations $riskEstimate $deltaG))
    $goalCorrelations
)

(= (actionRiskEstimate (action $actionId $goalCorrelations $riskEstimate $deltaG))
    $riskEstimate
)

(= (actionDeltaG (action $actionId $goalCorrelations $riskEstimate $deltaG))
    $deltaG
)

(= (copyMotivationState (motivation $goals $modulators))
    (motivation $goals $modulators)
)

(= (validateMotivationState (motivation $goals $modulators) $numGoals $numModulators)
    (if (and (== (size-atom $goals) $numGoals) (== (size-atom $modulators) $numModulators))
        True
        False
    )
)

(= (validateActionState (action $actionId $goalCorrelations $riskEstimate $deltaG) $numGoals)
    (if (and (== (size-atom $goalCorrelations) $numGoals) (== (size-atom $deltaG) $numGoals))
        True
        False
    )
)

(= (motivationStateDistance (motivation $goals $modulators) (motivation $goals2 $modulators2))
    (+ (eval (norm (listDifference $goals $goals2)))
       (eval (norm (listDifference $modulators $modulators2))))
)

(= (motivationStateDiff (motivation $goals $modulators) (motivation $goals2 $modulators2))
    (eval
        (roundNum
            (+ (calculateNormDifference $goals $goals2)
               (calculateNormDifference $modulators $modulators2))
            2
        )
    )
)
