# LocalMind OS Frontend

Next.js App Router UI for the LocalMind OS offline demo.

## Run

```powershell
cd frontend
npm install
npm run dev
```

Open: http://localhost:3000

## Security

On first launch, the UI will ask you to create a passphrase before the rest of the application becomes available. On later launches, the same passphrase is required to unlock the backend.

## Pages
- `/` Dashboard (stats + insights)
- `/upload` Upload and ingest data
- `/search` Semantic chunk search
- `/chat` Grounded RAG Q&A
- `/graph` Knowledge graph view
