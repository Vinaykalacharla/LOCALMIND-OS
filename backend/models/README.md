Place optional local models here.

- `*.gguf` files enable the local LLM path when `llama-cpp-python` is installed.
- Keep model binaries local; they are intentionally excluded from git.
- The repository should contain documentation only, not large model artifacts.

Recommended for the current machine profile:

- `1.5B` to `3B` instruct models
- quantizations such as `Q4_K_M`

Example:

- `qwen2.5-1.5b-instruct-q4_k_m.gguf`

A local sentence-transformers cache can also live on the machine if you want embedding inference without network fetches.
