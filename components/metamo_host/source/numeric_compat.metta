;; Roko compatibility layer, NOT upstream MetaMo code.
;; The exact upstream magus/decision.metta is loaded unchanged.
;; Replaces only the seven helpers reachable from MAGUS scoring with pure
;; MeTTa and PeTTa numeric builtins. The typed boundary permits six-decimal
;; input, avoiding numpy-vs-SWI half-tie differences at eight-digit rounding.
(= (absNumber $x) (abs-math $x))
(= (expNum $x) (exp $x))
(= (sigmoidNum $x) (/ 1.0 (+ 1.0 (exp (- 0.0 $x)))))
(= (positivePart $x) (if (> $x 0.0) $x 0.0))
(= (rokoRound8 $x) (/ (round-math (* $x 100000000.0)) 100000000.0))
(= (scaleArray $arr $factor)
    (if (== $arr ()) ()
        (let* ((($head $tail) (decons $arr)))
            (cons-atom (rokoRound8 (* $head $factor)) (scaleArray $tail $factor)))))
(= (clipVector $arr $low $high)
    (if (== $arr ()) ()
        (let* ((($head $tail) (decons $arr))
               ($clipped (if (< $head $low) $low (if (> $head $high) $high $head))))
            (cons-atom $clipped (clipVector $tail $low $high)))))
(= (rokoSumIndices $arr $indices)
    (if (== $indices ()) 0.0
        (let* ((($head $tail) (decons $indices)))
            (+ (index-atom $arr $head) (rokoSumIndices $arr $tail)))))
(= (meanAtIndices $arr $indices)
    (if (== $indices ()) 0.0
        (/ (rokoSumIndices $arr $indices) (size-atom $indices))))
