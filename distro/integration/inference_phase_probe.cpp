// Read-only llama.cpp phase diagnostic, using the repository's pinned API.
// No model output executes actions; this is not a conversation or health oracle.
#include "llama.h"
#include <chrono>
#include <cstdio>
#include <cstring>
#include <sys/resource.h>
#include <unistd.h>
#include <vector>
static auto start=std::chrono::steady_clock::now();
static void phase(const char *name) {
 rusage usage{};getrusage(RUSAGE_SELF,&usage);
 double ms=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();
 fprintf(stderr,"ROKO_INFERENCE_PHASE {\"phase\":\"%s\",\"elapsed_ms\":%.3f,\"max_rss_kib\":%ld,\"uid\":%ld}\n",name,ms,usage.ru_maxrss,(long)getuid());fflush(stderr);
}
int main(int argc,char **argv) {
 phase("entered");
 if(argc!=3 || (strcmp(argv[1],"vocab")&&strcmp(argv[1],"load")&&strcmp(argv[1],"decode-one")))return 2;
 phase("backend-begin");llama_backend_init();phase("backend-end");
 auto params=llama_model_default_params();params.n_gpu_layers=0;params.use_extra_bufts=false;params.vocab_only=!strcmp(argv[1],"vocab");
 phase("model-load-begin");auto model=llama_model_load_from_file(argv[2],params);if(!model)return 3;phase("model-load-end");
 auto vocab=llama_model_get_vocab(model);const char *prompt="Hello";
 phase("tokenize-begin");int count=-llama_tokenize(vocab,prompt,5,nullptr,0,true,true);
 if(count<1||count>32)return 4;std::vector<llama_token> tokens(count);
 if(llama_tokenize(vocab,prompt,5,tokens.data(),count,true,true)!=count)return 4;phase("tokenize-end");
 if(!strcmp(argv[1],"decode-one")) {
  auto cp=llama_context_default_params();cp.n_ctx=64;cp.n_batch=count;cp.n_threads=1;cp.n_threads_batch=1;
  phase("context-begin");auto ctx=llama_init_from_model(model,cp);if(!ctx)return 5;phase("context-end");
  auto batch=llama_batch_ext_init(ctx);llama_batch_ext_clear(batch);
  for(int i=0;i<count;i++){auto index=llama_batch_ext_add_token(batch,0,tokens[i]);llama_pos pos=i;llama_batch_ext_set_pos(batch,index,&pos);}
  llama_batch_ext_set_output_logits(batch,count-1,true);
  phase("decode-begin");int result=llama_process(ctx,LLAMA_PROCESS_TYPE_DECODE,batch);phase("decode-end");
  llama_batch_ext_free(batch);llama_free(ctx);if(result)return 6;
 }
 phase("cleanup-begin");llama_model_free(model);llama_backend_free();phase("complete");
 printf("{\"mode\":\"%s\",\"input_tokens\":%d,\"conversation_qualified\":false,\"execution_authorized\":false}\n",argv[1],count);return 0;
}
