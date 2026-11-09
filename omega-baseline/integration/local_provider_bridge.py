"""Test bridge only; no startup side effects, no proposal dispatch."""
import json
from pathlib import Path
import providers
from local_bounded import LocalBoundedProvider,inert_tool,verify_integer_answer
ROOT=Path(__file__).resolve().parents[1]
provider=None

def register():
    global provider
    provider=LocalBoundedProvider(ROOT)
    providers.registerLLMProvider('LocalBounded',provider)
    return True

def request():
    return providers.llmRequest(providers.llmRequestMessage('system','Answer briefly.'),
        [providers.llmRequestMessage('user','What is 2 plus 2? Reply with only the numeral.')],96,'none',[inert_tool()])

def structurally_valid(response):
    return bool(not response.is_error() and len(response.calls)==1 and
        not response.calls[0].is_error() and response.calls[0].name=='record_answer' and
        response.calls[0].arguments=={'text':provider.last_raw} and
        response.calls[0].tool is not None)

def arithmetic_gate(response,expected):
    return verify_integer_answer(response,expected)

def gate_consistent(response,gated,expected):
    correct=structurally_valid(response) and response.calls[0].arguments=={'text':str(expected)}
    return (not gated.is_error() and len(gated.calls)==1) if correct else (gated.is_error() and len(gated.calls)==0)

def save_report(response,gated,expected):
    report={'contract_success':structurally_valid(response),
        'arithmetic_correct':response.calls[0].arguments['text']==str(expected),
        'expected_answer':str(expected),'symbolic_gate_rejected':gated.is_error(),
        'gated_proposal':providers.llmResponseToSExpr(gated),'raw_model_output':provider.last_raw,
        'proposal':providers.llmResponseToSExpr(response),'executed_actions':0,
        'scope':'MeTTa -> Omega provider registry/chat/validation -> actual local Qwen -> serialized inert proposal; never evaluated'}
    Path('native-provider-result.json').write_text(json.dumps(report,indent=2)+'\n')
    return True

def stop():
    provider.stop()
    return True
