"""Actual upstream Omega embeddings and Chroma bridge, one process per phase."""
import json, math, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OMEGA=ROOT/'vendor/PeTTa/repos/Omega'
sys.path[:0]=[str(OMEGA/'src'),str(OMEGA/'providers'),str(OMEGA),str(ROOT/'vendor/PeTTa/repos/petta_lib_chromadb')]
import torch
torch.set_num_threads(2)
import lib_llm_ext as omega
import lib_chromadb as bridge
omega.initLocalEmbedding()
texts=['passage: The cat sleeps on a warm windowsill.','passage: An aircraft flies above the mountains.']
phase=sys.argv[1]
if phase=='write':
    for text in texts:
        embedding=omega.useLocalEmbedding(text)
        assert len(embedding)==1024
        assert all(math.isfinite(v) for v in embedding)
        assert abs(sum(v*v for v in embedding)-1)<0.001
        bridge.remember(text,embedding,'local-embedding-test')
query=omega.useLocalEmbedding('query: Where is the sleeping cat?')
hits=bridge.query(query,1)
assert hits[0][1]==texts[0],hits
assert bridge.COLLECTION.count()==2
report={'phase':phase,'dimension':len(query),'stored_count':bridge.COLLECTION.count(),'top_result':hits[0][1],'success':True,'embedding':'upstream Omega initLocalEmbedding/useLocalEmbedding'}
print(json.dumps(report),flush=True)
Path('result-'+phase+'.json').write_text(json.dumps(report,indent=2)+'\n')
