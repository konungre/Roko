; This is a real PeTTa match and Janus call; package paths/state are fixtures.
; No install/apply function is exposed by this bridge.
!(import! &self "__BRIDGE__")
(desired-package hello "/nix/store/00000000000000000000000000000000-fixture-hello")
!(change-state! &package-plan (match &self (desired-package $name $path)
    (py-call (package_bridge.plan_single $name $path "{\"packages\":{},\"revision\":\"fixture-empty\",\"source\":\"native-contract-fixture\"}"))))
!(test (py-call (package_bridge.operation_count (get-state &package-plan))) 1)
!(test (py-call (package_bridge.has_planned_package (get-state &package-plan) "hello" "/nix/store/00000000000000000000000000000000-fixture-hello")) true)
!(test (py-call (package_bridge.authorizes_actions (get-state &package-plan))) false)
