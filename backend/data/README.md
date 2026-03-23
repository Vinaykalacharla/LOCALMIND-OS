Runtime data is written here when the backend is used locally.

This directory is intentionally excluded from git because it can contain:

- encrypted vault metadata
- uploaded source files
- indexed chunks
- FAISS index data
- graph cache
- query logs

Do not treat this folder as portable source code. It is runtime state.
