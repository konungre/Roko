"""Actual Omega registry/start/chat/validation/serialization; no action dispatch."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'vendor/PeTTa/repos/Omega/src'),str(ROOT/'adapters')]
import providers
from local_bounded import LocalBoundedProvider,inert_tool
provider=LocalBoundedProvider(ROOT)
providers.registerLLMProvider('LocalBounded',provider)
providers.llmProviderStart('LocalBounded')
try:
    request=providers.llmRequest(providers.llmRequestMessage('system','Answer briefly.'),
        [providers.llmRequestMessage('user','What is 2 plus 2? Reply with only the numeral.')],96,'none',[inert_tool()])
    response=providers.llmProviderChat(request)
    print(json.dumps({'raw_model_output':provider.last_raw,'error':response.error}),flush=True)
    assert not response.is_error(),response.error
    assert len(response.calls)==1 and not response.calls[0].is_error(),response
    call=response.calls[0]
    assert call.name=='record_answer' and call.arguments=={'text':provider.last_raw},call
    assert call.tool is request.tools[0]
    sexpr=providers.llmResponseToSExpr(response)
    assert sexpr.startswith('((local-proposal-0 (record_answer '),sexpr
    report={'contract_success':True,'arithmetic_correct':call.arguments['text']=='4','expected_answer':'4','raw_model_output':provider.last_raw,'proposal':sexpr,
            'executed_actions':0,'scope':'Omega registry -> start -> chat -> native validation -> serialization; no eval or dispatch'}
    print(json.dumps(report));Path('provider-result.json').write_text(json.dumps(report,indent=2)+'\n')
finally:provider.stop()
