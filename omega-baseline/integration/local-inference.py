"""Bounded local model inference; no agent, tools, server, or external calls."""
import json,sys,time
from pathlib import Path
import torch
from transformers import AutoModelForCausalLM,AutoTokenizer
torch.set_num_threads(2)
start=time.monotonic()
path=sys.argv[1]
tokenizer=AutoTokenizer.from_pretrained(path,local_files_only=True,trust_remote_code=False)
model=AutoModelForCausalLM.from_pretrained(path,local_files_only=True,trust_remote_code=False,dtype=torch.float32)
model.eval()
messages=[{'role':'system','content':'Answer the question briefly.'},{'role':'user','content':'What is 2 plus 2? Reply with only the numeral.'}]
inputs=tokenizer.apply_chat_template(messages,add_generation_prompt=True,tokenize=True,return_dict=True,return_tensors='pt')
with torch.inference_mode():
 output=model.generate(**inputs,max_new_tokens=16,do_sample=False,pad_token_id=tokenizer.eos_token_id)
new=output[0][inputs['input_ids'].shape[1]:]
text=tokenizer.decode(new,skip_special_tokens=True).strip()
assert text, 'Empty local inference output'
report={'success':True,'output':text,'generated_tokens':len(new),'elapsed_seconds':round(time.monotonic()-start,2),'scope':'one direct inference; not Omega provider integration or an autonomy/quality benchmark'}
print(json.dumps(report));Path('inference-result.json').write_text(json.dumps(report,indent=2)+'\n')
