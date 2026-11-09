;; Generic named state accessors


;; Get a named goal value from a motivation state
;; Requires: (GoalIndex $name $idx) atom in the space
;; Example: (getGoal (motivation (0.25 0.75 0.5) (...)) desire) → 0.75
(= (getGoal (motivation $goals $modulators) $name)
    (let $idx (match &self (GoalIndex $name $i) $i)
        (index-atom $goals $idx)
    )
)

;; Get a named modulator value from a motivation state
;; Requires: (ModulatorIndex $name $idx) atom in the space
;; Example: (getModulator (motivation (...) (0.5 0.6 0.7)) urgency) → 0.6
(= (getModulator (motivation $goals $modulators) $name)
    (let $idx (match &self (ModulatorIndex $name $i) $i)
        (index-atom $modulators $idx)
    )
)

;; Get a named stimulus value from a stimulus state
;; Requires: (StimulusIndex $name $idx) atom in the space
;; Example: (getStimulus (stimulus (0.2 0.8 0.1)) relevance) → 0.8
(= (getStimulus (stimulus $values) $name)
    (let $idx (match &self (StimulusIndex $name $i) $i)
        (index-atom $values $idx)
    )
)
