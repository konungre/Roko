// Derived from pinned llama.cpp examples/simple/simple.cpp (MIT).
#include "llama.h"
#include <clocale>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>
#include <iostream>

// fill the batch with tokens at consecutive positions starting from pos_0, output logits only for the last one
static void batch_set_tokens(llama_batch_ext * batch, const llama_token * tokens, int32_t n_tokens, llama_pos pos_0) {
    llama_batch_ext_clear(batch);
    for (int32_t i = 0; i < n_tokens; ++i) {
        const int32_t idx = llama_batch_ext_add_token(batch, 0, tokens[i]);
        const llama_pos pos = pos_0 + i;
        llama_batch_ext_set_pos(batch, idx, &pos);
    }
    llama_batch_ext_set_output_logits(batch, n_tokens - 1, true);
}

static void print_usage(int, char ** argv) {
    printf("\nexample usage:\n");
    printf("\n    %s -m model.gguf [-n n_predict] [-ngl n_gpu_layers] [prompt]\n", argv[0]);
    printf("\n");
}

int main(int argc, char ** argv) {
    std::setlocale(LC_NUMERIC, "C");

    // path to the model gguf file
    std::string model_path;
    std::string grammar;
    // prompt to generate text from
    std::string prompt;
    // number of layers to offload to the GPU
    int ngl = 0;
    // number of tokens to predict
    int n_predict = 32;
    bool count_tokens = false;

    // parse command line arguments

    {
        int i = 1;
        for (; i < argc; i++) {
            if ((strcmp(argv[i], "-m") == 0 || strcmp(argv[i], "--model") == 0)) {
                if (i + 1 < argc) {
                    model_path = argv[++i];
                } else {
                    print_usage(argc, argv);
                    return 1;
                }
            } else if (strcmp(argv[i], "--count-tokens") == 0) {
                if (count_tokens) return 2;
                count_tokens = true;
            } else if (strcmp(argv[i], "--grammar") == 0) {
                if (i + 1 >= argc) return 2;
                grammar = argv[++i];
            } else if ((strcmp(argv[i], "-n") == 0 || strcmp(argv[i], "--max-tokens") == 0)) {
                if (i + 1 < argc) {
                    try {
                        n_predict = std::stoi(argv[++i]);
                    } catch (...) {
                        print_usage(argc, argv);
                        return 1;
                    }
                } else {
                    print_usage(argc, argv);
                    return 1;
                }
            } else if (strcmp(argv[i], "-ngl") == 0) {
                if (i + 1 < argc) {
                    try {
                        ngl = std::stoi(argv[++i]);
                    } catch (...) {
                        print_usage(argc, argv);
                        return 1;
                    }
                } else {
                    print_usage(argc, argv);
                    return 1;
                }
            } else {
                if (count_tokens && argv[i][0] == '-') return 2;
                // prompt starts here
                break;
            }
        }
        if (model_path.empty()) {
            print_usage(argc, argv);
            return 1;
        }
        if (i < argc) {
            prompt = argv[i++];
            for (; i < argc; i++) {
                prompt += " ";
                prompt += argv[i];
            }
        }
    }

    if (prompt.empty()) {
        char ch;
        while (std::cin.get(ch)) {
            if (prompt.size() >= 16384) { fprintf(stderr, "Prompt byte cap\n"); return 2; }
            prompt.push_back(ch);
        }
    }
    if (prompt.empty() || prompt.size() > 16384 || n_predict < 1 || n_predict > 128 || ngl != 0) return 2;
    llama_backend_init();

    // initialize the model

    llama_model_params model_params = llama_model_default_params();
    model_params.n_gpu_layers = ngl;
    // Keep weights mmap-backed within the fixed 6 GiB native address-space cap.
    // CPU_REPACK would allocate a second multi-GiB copy on optimized builds.
    model_params.use_extra_bufts = false;
    model_params.vocab_only = count_tokens;

    llama_model * model = llama_model_load_from_file(model_path.c_str(), model_params);

    if (model == NULL) {
        fprintf(stderr , "%s: error: unable to load model\n" , __func__);
        return 1;
    }

    const llama_vocab * vocab = llama_model_get_vocab(model);
    // tokenize the prompt

    // find the number of tokens in the prompt
    const int n_prompt = -llama_tokenize(vocab, prompt.c_str(), prompt.size(), NULL, 0, true, true);

    // allocate space for the tokens and tokenize the prompt
    std::vector<llama_token> prompt_tokens(n_prompt);
    if (llama_tokenize(vocab, prompt.c_str(), prompt.size(), prompt_tokens.data(), prompt_tokens.size(), true, true) < 0) {
        fprintf(stderr, "%s: error: failed to tokenize the prompt\n", __func__);
        return 1;
    }

    if (count_tokens) {
        printf("{\"input_tokens\":%d}\n", n_prompt);
        llama_model_free(model);
        llama_backend_free();
        return 0;
    }

    // initialize the context

    llama_context_params ctx_params = llama_context_default_params();
    // n_ctx is the context size
    if (n_prompt < 1 || n_prompt > 512 || n_predict < 1 || n_predict > 128) {
        fprintf(stderr, "ROKO_GENERATION {\"input_tokens\":%d,\"output_tokens\":0,\"finish_reason\":\"input_limit\"}\n", n_prompt);
        return 2;
    }
    ctx_params.n_threads = 4;
    ctx_params.n_threads_batch = 4;
    ctx_params.n_ctx = 1024;
    // n_batch is the maximum number of tokens that can be processed in a single call to llama_decode
    ctx_params.n_batch = n_prompt;
    // enable performance counters
    ctx_params.no_perf = false;

    llama_context * ctx = llama_init_from_model(model, ctx_params);

    if (ctx == NULL) {
        fprintf(stderr , "%s: error: failed to create the llama_context\n" , __func__);
        return 1;
    }

    // initialize the sampler

    auto sparams = llama_sampler_chain_default_params();
    sparams.no_perf = false;
    llama_sampler * smpl = llama_sampler_chain_init(sparams);

    if (!grammar.empty()) {
        auto constrained = llama_sampler_init_grammar(vocab, grammar.c_str(), "root");
        if (!constrained) { fprintf(stderr, "Invalid grammar\n"); return 2; }
        llama_sampler_chain_add(smpl, constrained);
    }
    llama_sampler_chain_add(smpl, llama_sampler_init_greedy());

    // Deliberately emit generated text only; prompt is input, not output.

    // prepare a batch for the prompt

    llama_batch_ext * batch = llama_batch_ext_init(ctx);
    int n_tokens = n_prompt; // number of tokens in the current batch

    batch_set_tokens(batch, prompt_tokens.data(), n_prompt, 0);

    if (llama_model_has_encoder(model)) {
        if (llama_process(ctx, LLAMA_PROCESS_TYPE_ENCODE, batch)) {
            fprintf(stderr, "%s : failed to eval\n", __func__);
            return 1;
        }

        llama_token decoder_start_token_id = llama_model_decoder_start_token(model);
        if (decoder_start_token_id == LLAMA_TOKEN_NULL) {
            decoder_start_token_id = llama_vocab_bos(vocab);
        }

        batch_set_tokens(batch, &decoder_start_token_id, 1, 0);
        n_tokens = 1;
    }

    // main loop

    const auto t_main_start = ggml_time_us();
    int n_decode = 0;
    bool reached_eos = false;
    llama_token new_token_id;

    for (int n_pos = 0; n_pos + n_tokens < n_prompt + n_predict; ) {
        // evaluate the current batch with the transformer model
        if (llama_process(ctx, LLAMA_PROCESS_TYPE_DECODE, batch)) {
            fprintf(stderr, "%s : failed to eval, return code %d\n", __func__, 1);
            return 1;
        }

        n_pos += n_tokens;

        // sample the next token
        {
            new_token_id = llama_sampler_sample(smpl, ctx, -1);

            // is it an end of generation?
            if (llama_vocab_is_eog(vocab, new_token_id)) {
                reached_eos = true;
                break;
            }

            char buf[128];
            int n = llama_token_to_piece(vocab, new_token_id, buf, sizeof(buf), 0, true);
            if (n < 0) {
                fprintf(stderr, "%s: error: failed to convert token to piece\n", __func__);
                return 1;
            }
            std::string s(buf, n);
            printf("%s", s.c_str());
            fflush(stdout);

            // prepare the next batch with the sampled token
            batch_set_tokens(batch, &new_token_id, 1, n_pos);
            n_tokens = 1;

            n_decode += 1;
        }
    }

    printf("\n");

    const auto t_main_end = ggml_time_us();
    fprintf(stderr, "ROKO_GENERATION {\"input_tokens\":%d,\"output_tokens\":%d,\"finish_reason\":\"%s\"}\n",
            n_prompt, n_decode, reached_eos ? "eos" : "length");

    fprintf(stderr, "%s: decoded %d tokens in %.2f s, speed: %.2f t/s\n",
            __func__, n_decode, (t_main_end - t_main_start) / 1000000.0f, n_decode / ((t_main_end - t_main_start) / 1000000.0f));

    fprintf(stderr, "\n");
    llama_perf_sampler_print(smpl);
    llama_perf_context_print(ctx);
    fprintf(stderr, "\n");

    llama_batch_ext_free(batch);
    llama_sampler_free(smpl);
    llama_free(ctx);
    llama_model_free(model);

    return 0;
}
