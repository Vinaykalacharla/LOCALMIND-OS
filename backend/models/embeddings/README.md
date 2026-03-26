Place local embedding models in this folder.

Supported options:
- A SentenceTransformers folder copied here, for example `all-MiniLM-L6-v2/`
- A path provided with `LOCALMIND_EMBEDDING_MODEL`

Recommended layout:

```text
backend/models/embeddings/
  all-MiniLM-L6-v2/
    config.json
    modules.json
    sentence_bert_config.json
    tokenizer.json
    vocab.txt
    model.safetensors
```

If no local embedding model is present, the app falls back to the built-in hashed TF-IDF embedder so retrieval still works fully offline.
