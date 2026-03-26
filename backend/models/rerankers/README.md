Place local reranker models in this folder.

Supported options:
- A CrossEncoder-compatible SentenceTransformers folder copied here
- A path provided with `LOCALMIND_RERANKER_MODEL`

Recommended layout:

```text
backend/models/rerankers/
  bge-reranker-base/
    config.json
    tokenizer.json
    sentence_bert_config.json
    modules.json
    model.safetensors
```

If no local reranker is present, reranking is disabled and the retrieval stack continues with hybrid semantic plus lexical scoring.
