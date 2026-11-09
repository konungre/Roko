"""Local Omega provider experiment. Produces one inert proposal; never dispatches.

This is deliberately NOT a drop-in autonomous provider: only record_answer(text)
is accepted. A host must inspect the proposal; no such effectful tool is installed.
"""
import hashlib
import json
from pathlib import Path
import providers

TOOL='record_answer'
MAX_INPUT_TOKENS=512
MAX_OUTPUT_TOKENS=128
MAX_MESSAGE_CHARS=4000


def inert_tool():
    return (providers.LLMTool().with_name(TOOL)
            .with_description('Return an answer for human inspection only. No action is executed.')
            .add_parameter(providers.LLMToolParameter().with_name('text')))


def parse_proposal(text):
    """Strict JSON only. No eval, code fences, repairs, or executable payloads."""
    def unique_object(pairs):
        obj={}
        for key,value in pairs:
            if key in obj: raise ValueError('Duplicate JSON key')
            obj[key]=value
        return obj
    if not isinstance(text,str) or len(text)>4096: raise ValueError('Invalid output size')
    value=json.loads(text,object_pairs_hook=unique_object)
    if not isinstance(value,dict) or set(value)!= {'name','arguments'}:
        raise ValueError('Expected exactly name and arguments')
    if value['name']!=TOOL: raise ValueError('Only inert record_answer proposals are accepted')
    args=value['arguments']
    if not isinstance(args,dict) or set(args)!={'text'}:
        raise ValueError('Expected exactly text argument')
    answer=args['text']
    if not isinstance(answer,str) or not answer.strip() or len(answer)>1000:
        raise ValueError('Answer must be a nonempty bounded string')
    if any(ord(c)<32 and c not in '\n\t' for c in answer):
        raise ValueError('Control characters are not accepted')
    return (providers.LLMResponse().add_tool_call(providers.LLMToolCall()
            .with_name(TOOL).with_id('local-proposal-0').with_arguments({'text':answer})))


def validate_request(request):
    if type(request.max_tokens) is not int or not 1<=request.max_tokens<=MAX_OUTPUT_TOKENS:
        raise ValueError('max_tokens must be between 1 and 128')
    if len(request.tools)!=1 or request.tools[0].name!=TOOL:
        raise ValueError('Only one inert record_answer tool may be offered')
    tool=request.tools[0]
    if [p.name for p in tool.parameters]!=['text']:
        raise ValueError('record_answer requires exactly the text parameter')
    if not 1<=len(request.messages)<=8: raise ValueError('Expected 1 to 8 messages')
    messages=[]
    for message in request.messages:
        # Tool histories are intentionally unsupported; accepting them would imply
        # an action loop that this provider explicitly does not implement.
        if type(message) is not providers.LLMMessage or message.role not in ('system','user','assistant'):
            raise ValueError('Unsupported message type or role')
        if not isinstance(message.content,str):raise ValueError('Message content must be text')
        messages.append({'role':message.role,'content':message.content})
    if sum(len(m['content']) for m in messages)>MAX_MESSAGE_CHARS:
        raise ValueError('Request exceeds character cap')
    return messages


class LocalBoundedProvider(providers.LLMProvider):
    def __init__(self,root):
        self.root=Path(root)
        self.model=None
        self.tokenizer=None
        self.last_raw=None

    def start(self):
        if self.model is not None:return
        manifest=json.loads((self.root/'models.lock.json').read_text())
        locked=next(x for x in manifest if x['repo']=='Qwen/Qwen2.5-0.5B-Instruct')
        snapshot=self.root/locked['snapshot']
        for name,digest in locked['files'].items():
            if hashlib.sha256((snapshot/name).read_bytes()).hexdigest()!=digest:
                raise ValueError('Changed model file: '+name)
        import torch
        from transformers import AutoModelForCausalLM,AutoTokenizer
        torch.set_num_threads(2)
        tokenizer=AutoTokenizer.from_pretrained(snapshot,local_files_only=True,trust_remote_code=False)
        model=AutoModelForCausalLM.from_pretrained(snapshot,local_files_only=True,trust_remote_code=False,dtype=torch.float32)
        model.eval()
        self.tokenizer,self.model=tokenizer,model

    def stop(self):
        self.model=self.tokenizer=None
        self.last_raw=None

    def chat(self,request):
        self.last_raw=None
        try:
            messages=validate_request(request)
            if self.model is None:raise ValueError('Provider has not been started')
            instructions='Answer the question briefly with plain answer text only. Do not emit tool calls.'
            system=[m['content'] for m in messages if m['role']=='system']
            messages=[{'role':'system','content':instructions+' '+ ' '.join(system)}]+[m for m in messages if m['role']!='system']
            inputs=self.tokenizer.apply_chat_template(messages,add_generation_prompt=True,
                tokenize=True,return_dict=True,return_tensors='pt')
            if inputs['input_ids'].shape[1]>MAX_INPUT_TOKENS:
                raise ValueError('Request exceeds token cap')
            import torch
            with torch.inference_mode():
                output=self.model.generate(**inputs,max_new_tokens=request.max_tokens,
                    do_sample=False,pad_token_id=self.tokenizer.eos_token_id)
            self.last_raw=self.tokenizer.decode(output[0][inputs['input_ids'].shape[1]:],skip_special_tokens=True).strip()
            # The model never selects an operation. Wrap its text in the one fixed,
            # inert proposal; do not interpret model JSON or executable syntax.
            return parse_proposal(json.dumps({'name':TOOL,'arguments':{'text':self.last_raw}}))
        except Exception as error:
            return providers.LLMResponse().with_error(str(error))


def verify_integer_answer(response,expected):
    """Narrow gate against an independently computed integer, not a general oracle.

The caller supplies a trusted expected result; never derive it from model output.
Returning an accepted proposal does not grant permission to execute anything.
"""
    if type(expected) is not int:
        return providers.LLMResponse().with_error('Trusted expected value must be an integer')
    if response.is_error() or len(response.calls)!=1:
        return providers.LLMResponse().with_error('Invalid candidate for symbolic verification')
    call=response.calls[0]
    if call.is_error() or call.name!=TOOL or call.arguments!={'text':str(expected)}:
        return providers.LLMResponse().with_error('Symbolic integer check rejected the model answer')
    return response
