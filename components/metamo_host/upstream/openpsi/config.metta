;; OpenPSI dimension configuration

(= (NUM_GOALS) 8)
(= (NUM_MODULATORS) 6)
(= (NUM_STIMULUS) 4)

;; Goal index atoms — pattern-matchable from the AtomSpace
;; Example: (match &self (GoalIndex gInd $i) $i) → 0
(GoalIndex gInd 0)
(GoalIndex gTrans 1)
(GoalIndex gHelp 2)
(GoalIndex gCurio 3)
(GoalIndex gNovel 4)
(GoalIndex gSelf 5)
(GoalIndex gEthic 6)
(GoalIndex gSoc 7)

;; Modulator index atoms
;; Example: (match &self (ModulatorIndex valence $i) $i) → 0
(ModulatorIndex valence 0)
(ModulatorIndex arousal 1)
(ModulatorIndex approach 2)
(ModulatorIndex resolution 3)
(ModulatorIndex threshold 4)
(ModulatorIndex securing 5)

;; Stimulus index atoms
;; Example: (match &self (StimulusIndex novelty $i) $i) → 0
(StimulusIndex novelty 0)
(StimulusIndex conduciveness 1)
(StimulusIndex risk 2)
(StimulusIndex effort 3)

;; OpenPSI behavioral constants
(= (LAMBDA_IND) 0.5)
(= (LAMBDA_TRANS) 0.5)
(= (THETA_SAFE) 0.3)
(= (G_MAX) 2.0)

;; ── OpenPSI convenience wrappers ──

;; Backward-compatible 4-arity stimulus constructor
;; Example: (openPsiStimulus 0.2 0.8 0.1 0.2)
(= (openPsiStimulus $novelty $conduciveness $risk $effort)
    (stimulus ($novelty $conduciveness $risk $effort))
)

;; Validate motivation state shape against OpenPSI dimensions
;; Example: (validateMotivationalStateShape myState)
(= (validateMotivationalStateShape $motivationState)
    (validateMotivationState $motivationState (NUM_GOALS) (NUM_MODULATORS))
)

;; Validate action state shape against OpenPSI goal count
;; Example: (validateActionShape $actionState)
(= (validateActionShape $actionState)
    (validateActionState $actionState (NUM_GOALS))
)

;; ── OpenPSI merge index categories ──
;; These define which goals/modulators are safety, exploratory, social, etc.
;; for the parallel merge consensus functions.

;; Goal weight index (gInd) and category groupings
(= (OPENPSI_GOAL_WEIGHT_IDX) 0)
(= (OPENPSI_SAFETY_GOAL_IDX) (0 2 6))
(= (OPENPSI_EXPLORATORY_GOAL_IDX) (1 3 4 5))
(= (OPENPSI_SOCIAL_GOAL_IDX) (7))

;; Modulator category groupings
(= (OPENPSI_CAUTION_MOD_IDX) (4 5))
(= (OPENPSI_EXPLORATORY_MOD_IDX) (1 2))
(= (OPENPSI_SHARED_MOD_IDX) (0 3))

;; OpenPSI parallel merge — passes project-specific index categories
;; Example: (parallelMerge stateA stateB 0.05)
(= (parallelMerge $stateA $stateB $coherenceCorrection)
    (motivation
        (eval (clipVector
            (parallelMergeGoals
                (motivationGoals $stateA) (motivationGoals $stateB) $coherenceCorrection
                (eval (OPENPSI_GOAL_WEIGHT_IDX))
                (eval (OPENPSI_SAFETY_GOAL_IDX))
                (eval (OPENPSI_EXPLORATORY_GOAL_IDX))
                (eval (OPENPSI_SOCIAL_GOAL_IDX))
            )
            0.0
            1.0
        ))
        (eval (clipVector
            (parallelMergeModulators
                (motivationModulators $stateA)
                (motivationModulators $stateB)
                (motivationGoals $stateA)
                (motivationGoals $stateB)
                $coherenceCorrection
                (eval (OPENPSI_GOAL_WEIGHT_IDX))
                (eval (OPENPSI_CAUTION_MOD_IDX))
                (eval (OPENPSI_EXPLORATORY_MOD_IDX))
                (eval (OPENPSI_SHARED_MOD_IDX))
            )
            0.0
            1.0
        ))
    )
)

; OpenPSI emotion configuration (Cai et al. 2013, §4.3, Table 2)
; There are 5 Emotion Dimension

;;   Activation         -> arousal
;;   Resolution         -> resolution
;;   Securing threshold -> securing
;;   Selection threshold-> threshold
;;   Pleasure           -> valence   (reuse valence)

;; Number of emotion dimensions (paper uses 5)
(= (NUM_EMOTION_DIMS) 5)

;; The 5 modulators that span the emotion space, in Table 2 order
(= (EMOTION_DIM_MODULATORS) (arousal resolution securing threshold valence))

;; Emotion index atoms

;; Type definitions for the emotion constructors (cf. core/state.metta)
(: EmotionIndexType Type)
(: EmotionIndex (-> Symbol Number EmotionIndexType))

(: EmotionModulatorType Type)
(: EmotionModulator (-> Symbol Symbol Symbol EmotionModulatorType))

(EmotionIndex happy 0)
(EmotionIndex sad   1)
(EmotionIndex angry 2)
(EmotionIndex fear  3)

;; Emotion × modulator indicator table (Table 2).
;; Indicators: EL=extremely low, L=low, M=medium, H=high, EH=extremely high, U=undefined.
;; (EmotionModulator <emotion> <modulator> <indicator>)

;; Happy:  Activation H, Resolution L, Securing U, Selection H, Pleasure H
(EmotionModulator happy arousal    H)
(EmotionModulator happy resolution L)
(EmotionModulator happy securing   U)
(EmotionModulator happy threshold  H)
(EmotionModulator happy valence    H)

;; Sad:    Activation L, Resolution H, Securing U, Selection EL, Pleasure EL
(EmotionModulator sad arousal    L)
(EmotionModulator sad resolution H)
(EmotionModulator sad securing   U)
(EmotionModulator sad threshold  EL)
(EmotionModulator sad valence    EL)

;; Angry:  Activation H, Resolution L, Securing U, Selection L, Pleasure EL
(EmotionModulator angry arousal    H)
(EmotionModulator angry resolution L)
(EmotionModulator angry securing   U)
(EmotionModulator angry threshold  L)
(EmotionModulator angry valence    EL)

;; Fear:   Activation EL, Resolution EH, Securing L, Selection U, Pleasure EL
(EmotionModulator fear arousal    EL)
(EmotionModulator fear resolution EH)
(EmotionModulator fear securing   L)
(EmotionModulator fear threshold  U)
(EmotionModulator fear valence    EL)

;; Fuzzy membership constants (eq. 15) — shared steepness + thresholds
(= (FUZZY_ALPHA) 50.0)
(= (FUZZY_T_EL) 0.15)
(= (FUZZY_T_L)  0.30)
(= (FUZZY_T_M)  0.50)
(= (FUZZY_T_H)  0.70)
(= (FUZZY_T_EH) 0.85)

;; Equal contribution weight per dimension (paper: 1/5)
(= (EMOTION_WEIGHT) 0.2)

;; Dominance threshold gamma — filters weak emotions (paper: 0.6)
(= (EMOTION_GAMMA) 0.6)








