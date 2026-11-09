"""Test-only native MeTTa bridge. No proposal execution."""
import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];O=ROOT/'vendor/PeTTa/repos/Omega'
sys.path[:0]=[str(O/'providers'),str(O/'src'),str(O),str(ROOT/'adapters')]
import providers
from granite_pipe import GranitePipeProvider,ALLOWED
from local_bounded import verify_integer_answer
provider=None

def register():
 global provider
 provider=GranitePipeProvider(ROOT);providers.registerLLMProvider('GranitePipe',provider);return True

def request():
 tools=[]
 for name,params in ALLOWED.items():
  t=providers.LLMTool().with_name(name).with_description('Record inert test data for inspection. No action is executed.')
  for p in params:t.add_parameter(providers.LLMToolParameter().with_name(p))
  tools.append(t)
 return providers.llmRequest(providers.llmRequestMessage('system','Use exactly one provided recording tool. Follow the requested output precisely.'),[providers.llmRequestMessage('user','What is 2 plus 2? Record only the numeral.')],128,'none',tools)

def structurally_valid(response):
 return bool(not response.is_error() and len(response.calls)==1 and not response.calls[0].is_error() and response.calls[0].name=='record_answer' and response.calls[0].tool is not None)

def arithmetic_gate(response,expected):return verify_integer_answer(response,expected)

def gate_consistent(response,gated,expected):
 correct=structurally_valid(response) and response.calls[0].arguments=={'text':str(expected)}
 return (not gated.is_error() and len(gated.calls)==1) if correct else (gated.is_error() and len(gated.calls)==0)

def save_report(response,gated,expected):
 report={'contract_success':structurally_valid(response),'arithmetic_correct':response.calls[0].arguments['text']==str(expected),'expected_answer':str(expected),'symbolic_gate_rejected':gated.is_error(),'gated_proposal':providers.llmResponseToSExpr(gated),'proposal':providers.llmResponseToSExpr(response),'raw_model_output':provider.last.get('raw_output'),'executed_actions':0,'scope':'Native MeTTa -> genuine Omega provider contract -> actual Granite Q4_K_M -> validated inert proposal + independent arithmetic check'}
 Path('native-provider-result.json').write_text(json.dumps(report,indent=2)+'\n');return True

def stop():provider.stop();return True
