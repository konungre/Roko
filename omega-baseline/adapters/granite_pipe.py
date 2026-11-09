"""Socket-free Granite provider for inert, bounded tool-proposal evaluation."""
import hashlib,json,re,subprocess,threading,time
from pathlib import Path
import providers
import lib_llm_ext
ALLOWED={'record_answer':['text'],'record_contact':['name','city'],'record_invoice':['invoice','total']}

def parse_tool(text,request,*,allow_json_text=False):
    match=re.fullmatch(r'\s*<tool_call>\s*(.*?)\s*</tool_call>\s*',text,re.S)
    if not match:raise ValueError('Expected exactly one native Granite tool_call block')
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise ValueError('Duplicate JSON key')
            result[key]=value
        return result
    obj=json.loads(match[1],object_pairs_hook=unique)
    if not isinstance(obj,dict) or set(obj)!={'name','arguments'}:raise ValueError('Unexpected envelope')
    name=obj['name'];args=obj['arguments']
    if allow_json_text and isinstance(args,str):
        args=json.loads(args,object_pairs_hook=unique)
    if not isinstance(name,str) or name not in ALLOWED or not request.has_tool(name):raise ValueError('Unapproved operation')
    if not isinstance(args,dict) or set(args)!=set(ALLOWED[name]):raise ValueError('Unexpected arguments')
    if any(not isinstance(v,str) or len(v)>1000 for v in args.values()):raise ValueError('Arguments must be bounded strings')
    return providers.LLMResponse().add_tool_call(providers.LLMToolCall().with_name(name).with_id('granite-proposal-0').with_arguments(args))

class GranitePipeProvider(providers.LLMProvider):
    def __init__(self,root,*,constrained=False):
        self.constrained=constrained
        self.root=Path(root);self.tokenizer=None;self.last={}
    def start(self):
        self.lock=json.loads((self.root/'granite-model.lock.json').read_text())
        self.model=self.root/self.lock['path'];self.executable=self.root/'runtime/granite/omega-granite-infer'
        with self.model.open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()!=self.lock['sha256']:raise ValueError('Model hash mismatch')
        tokenizer_path=self.root/self.lock['tokenizer_path']
        for name,digest in self.lock['tokenizer_files'].items():
            if hashlib.sha256((tokenizer_path/name).read_bytes()).hexdigest()!=digest:raise ValueError('Tokenizer hash mismatch')
        from transformers import AutoTokenizer
        self.tokenizer=AutoTokenizer.from_pretrained(tokenizer_path,local_files_only=True,trust_remote_code=False)
        # Reuse upstream Omega schema conversion, without constructing a network client.
        self.converter=lib_llm_ext.AIProvider('GranitePipe','UNUSED','granite-local','http://unused.invalid')
    def stop(self):self.tokenizer=None
    def chat(self,request):
        self.last={}
        try:
            if self.tokenizer is None:raise ValueError('Provider not started')
            if type(request.max_tokens) is not int or not 1<=request.max_tokens<=128:raise ValueError('Output cap exceeded')
            if not 1<=len(request.tools)<=3:raise ValueError('Tool count limit')
            names=set()
            for t in request.tools:
                if t.name in names or t.name not in ALLOWED or [p.name for p in t.parameters]!=ALLOWED[t.name]:raise ValueError('Only declared inert tools allowed')
                names.add(t.name)
            if not 1<=len(request.messages)<=8:raise ValueError('Message count limit')
            if any(type(m) is not providers.LLMMessage or m.role not in ('system','user','assistant') or not isinstance(m.content,str) for m in request.messages):raise ValueError('Unsupported message')
            if sum(len(m.content) for m in request.messages)>6000:raise ValueError('Input character cap')
            raw_request=self.converter.convert_request(request)
            prompt=self.tokenizer.apply_chat_template(raw_request['messages'],tools=raw_request['tools'],add_generation_prompt=True,tokenize=False)
            token_count=len(self.tokenizer.encode(prompt,add_special_tokens=False))
            if token_count>1024:raise ValueError('Input token cap')
            args=[str(self.executable),'-m',str(self.model),'-n',str(request.max_tokens),'-ngl','0',prompt]
            if self.constrained:args[-1:-1]=['--grammar',tool_grammar(names)]
            started=time.monotonic();proc=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,close_fds=True)
            peak=[0];halt=threading.Event()
            def measure():
                while not halt.wait(.05):
                    try:
                        for line in Path(f'/proc/{proc.pid}/status').read_text().splitlines():
                            if line.startswith('VmHWM:'):peak[0]=max(peak[0],int(line.split()[1]))
                    except (FileNotFoundError,PermissionError):pass
            monitor=threading.Thread(target=measure,daemon=True);monitor.start()
            try:stdout,stderr=proc.communicate(timeout=90)
            except subprocess.TimeoutExpired:
                proc.kill();stdout,stderr=proc.communicate();raise TimeoutError('Native inference exceeded 90 seconds')
            finally:halt.set();monitor.join(timeout=2)
            self.last={'raw_output':stdout,'stderr':stderr,'returncode':proc.returncode,'elapsed_seconds':round(time.monotonic()-started,3),'peak_rss_kib':peak[0],'tokenizer_estimated_input_tokens':token_count}
            decoded=re.findall(r'(?m)^llama_perf_context_print:\s+eval time.*?([\d.]+) tokens per second',stderr)
            prompted=re.search(r'prompt eval time.*?/\s*(\d+) tokens',stderr)
            self.last['decode_tokens_per_second']=float(decoded[0]) if decoded else None
            self.last['native_prompt_tokens']=int(prompted[1]) if prompted else None
            if proc.returncode:raise RuntimeError('Native inference failed: '+str(proc.returncode))
            return parse_tool(stdout,request,allow_json_text=True)
        except Exception as e:return providers.LLMResponse().with_error(str(e))

def tool_grammar(names):
    """GBNF limits syntax and offered inert schemas, not truth or permission."""
    if not names or any(name not in ALLOWED for name in names):
        raise ValueError('Unknown grammar tools')
    literal=lambda value: json.dumps(value)
    alternatives=[]
    for name in sorted(names):
        fields=[]
        for key in ALLOWED[name]:
            fields.append(literal(json.dumps(key))+ ' ws ":" ws string')
        args=' ws "," ws '.join(fields)
        alternatives.append(literal('{"name":'+json.dumps(name)+',"arguments":{')+' ws '+args+' ws '+literal('}}'))
    return ('root ::= "<tool_call>" ws ('+' | '.join(alternatives)+') ws "</tool_call>"\n'
            + r'ws ::= [ \t\n\r]*'+'\n'
            + r'string ::= "\"" char* "\""'+'\n'
            + r'char ::= [^"\\\x00-\x1f] | "\\" (["\\/bfnrt] | "u" [0-9a-fA-F]{4})'+'\n')
