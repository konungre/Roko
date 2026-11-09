; Bounded Omega conversation extension. All user/model/context text stays data.
; Upstream Omega owns message state; no sread/eval on model output.
(= (rokoConversationStep)
   (progn
     (change-state! &messages_all (py-call (conversation.history)))
     (messagesAppend (py-call (conversation.user_message)))
     (messagesAppend (py-call (conversation.infer (messagesGet))))
     (py-call (conversation.commit (messagesGet)))))

; Recovered profile retains native Omega request dispatch and response admission.
(= (rokoRecoveredStep)
   (progn
     (change-state! &messages_all (py-call (conversation.history)))
     (messagesAppend (py-call (conversation.user_message)))
     (let* (($request (py-call (recovered.request (messagesGet))))
            ($response (llmProviderChat $request))
            ($message (py-call (recovered.admit $response))))
        (progn (messagesAppend $message)
               (py-call (conversation.commit (messagesGet)))))))
