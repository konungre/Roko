; Bounded Omega conversation extension. All user/model/context text stays data.
; Upstream Omega owns message state; no sread/eval on model output.
(= (rokoConversationStep)
   (progn
     (change-state! &messages_all (py-call (conversation.history)))
     (messagesAppend (py-call (conversation.user_message)))
     (messagesAppend (py-call (conversation.infer (messagesGet))))
     (py-call (conversation.commit (messagesGet)))))
