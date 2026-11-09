// Derived from the pinned llama.cpp simple example (MIT) and the existing Roko helper.
#include "llama.h"
#include <clocale>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <string>
#include <vector>
#include <sys/resource.h>
#include <unistd.h>

static int fail(const char *message) {
    std::fprintf(stderr, "roko-granite-guest: %s\n", message);
    return 2;
}

static void fill(llama_batch_ext *batch, const llama_token *tokens, int32_t count, llama_pos start) {
    llama_batch_ext_clear(batch);
    for (int32_t i = 0; i < count; ++i) {
        const int32_t index = llama_batch_ext_add_token(batch, 0, tokens[i]);
        const llama_pos position = start + i;
        llama_batch_ext_set_pos(batch, index, &position);
    }
    llama_batch_ext_set_output_logits(batch, count - 1, true);
}

int main(int argc, char **argv) {
    alarm(300);
    const rlimit no_core = {0, 0};
    if (setrlimit(RLIMIT_CORE, &no_core)) return fail("cannot disable core dumps");
    std::setlocale(LC_NUMERIC, "C");
    std::string model_path, grammar;
    int predict = 0;
    if (argc != 7) return fail("expected --model PATH --max-tokens N --grammar GBNF; prompt on stdin");
    for (int i = 1; i < argc; i += 2) {
        if (std::strcmp(argv[i], "--model") == 0 && model_path.empty()) model_path = argv[i + 1];
        else if (std::strcmp(argv[i], "--grammar") == 0 && grammar.empty()) grammar = argv[i + 1];
        else if (std::strcmp(argv[i], "--max-tokens") == 0 && predict == 0) {
            const char *value = argv[i + 1];
            if (std::strlen(value) < 1 || std::strlen(value) > 2 || std::strspn(value, "0123456789") != std::strlen(value)) {
                return fail("invalid output token count");
            }
            predict = std::atoi(value);
        } else return fail("unknown or duplicate option");
    }
    if (model_path.empty() || model_path.size() > 4096 || grammar.empty() || grammar.size() > 8192 || predict < 1 || predict > 64) {
        return fail("argument limit exceeded");
    }
    std::string prompt;
    char input[1024];
    while (const size_t size = std::fread(input, 1, sizeof(input), stdin)) {
        prompt.append(input, size);
        if (prompt.size() > 16384) return fail("prompt byte cap exceeded");
    }
    if (std::ferror(stdin) || prompt.empty()) return fail("invalid prompt input");

    llama_backend_init();
    auto params = llama_model_default_params();
    params.n_gpu_layers = 0;
    params.load_mode = LLAMA_LOAD_MODE_MMAP;
    params.use_extra_bufts = false;
    std::unique_ptr<llama_model, decltype(&llama_model_free)> model(
        llama_model_load_from_file(model_path.c_str(), params), llama_model_free);
    if (!model) return fail("model load failed");
    if (llama_model_has_encoder(model.get())) return fail("unexpected encoder model");
    const llama_vocab *vocab = llama_model_get_vocab(model.get());
    const int required = llama_tokenize(vocab, prompt.data(), prompt.size(), nullptr, 0, true, true);
    if (required >= 0 || required < -512) return fail("native prompt token cap exceeded");
    const int count = -required;
    std::vector<llama_token> tokens(count);
    if (llama_tokenize(vocab, prompt.data(), prompt.size(), tokens.data(), count, true, true) != count) {
        return fail("prompt tokenization failed");
    }
    auto context = llama_context_default_params();
    context.n_ctx = 1024;
    context.n_batch = 512;
    context.n_ubatch = 32;
    context.n_seq_max = 1;
    context.n_rs_seq = 0;
    context.n_threads = 1;
    context.n_threads_batch = 1;
    context.no_perf = false;
    std::unique_ptr<llama_context, decltype(&llama_free)> ctx(
        llama_init_from_model(model.get(), context), llama_free);
    if (!ctx) return fail("context allocation failed");
    auto sampling = llama_sampler_chain_default_params();
    sampling.no_perf = false;
    std::unique_ptr<llama_sampler, decltype(&llama_sampler_free)> sampler(
        llama_sampler_chain_init(sampling), llama_sampler_free);
    if (!sampler) return fail("sampler allocation failed");
    llama_sampler *constraint = llama_sampler_init_grammar(vocab, grammar.c_str(), "root");
    if (!constraint) return fail("invalid grammar");
    llama_sampler_chain_add(sampler.get(), constraint);
    llama_sampler_chain_add(sampler.get(), llama_sampler_init_greedy());
    std::unique_ptr<llama_batch_ext, decltype(&llama_batch_ext_free)> batch(
        llama_batch_ext_init(ctx.get()), llama_batch_ext_free);
    if (!batch) return fail("batch allocation failed");
    fill(batch.get(), tokens.data(), count, 0);
    size_t bytes = 0;
    int position = count;
    int generated = 0;
    for (int i = 0; i < predict; ++i) {
        if (llama_process(ctx.get(), LLAMA_PROCESS_TYPE_DECODE, batch.get())) return fail("decode failed");
        const llama_token token = llama_sampler_sample(sampler.get(), ctx.get(), -1);
        if (llama_vocab_is_eog(vocab, token)) break;
        char piece[256];
        const int size = llama_token_to_piece(vocab, token, piece, sizeof(piece), 0, true);
        if (size < 0 || (bytes += size) > 32768) return fail("output byte cap exceeded");
        if (std::fwrite(piece, 1, size, stdout) != static_cast<size_t>(size) || std::fflush(stdout)) return fail("output failure");
        ++generated;
        fill(batch.get(), &token, 1, position++);
    }
    std::putchar('\n');
    std::fprintf(stderr, "ROKO_GRANITE_LIMITS prompt_tokens=%d generated_tokens=%d n_ctx=1024 n_ubatch=32 repack=0 threads=1\n", count, generated);
    llama_perf_sampler_print(sampler.get());
    llama_perf_context_print(ctx.get());
    rusage usage{};
    if (getrusage(RUSAGE_SELF, &usage)) return fail("resource accounting failed");
    std::fprintf(stderr, "ROKO_GRANITE_USAGE max_rss_kib=%ld minor_faults=%ld major_faults=%ld\n",
                 usage.ru_maxrss, usage.ru_minflt, usage.ru_majflt);
    return 0;
}
