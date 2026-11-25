# TruthLens AI

TruthLens AI is an explainable, research-oriented fake-news analysis prototype
for Windows 10/11. It combines a FastAPI backend, React/TypeScript frontend,
local SQLite persistence, a TF-IDF/Logistic Regression baseline, optional
DistilBERT fine-tuning, and optional Google Fact Check API lookup.

> A model label is a dataset-pattern signal, not a finding of truth or falsity.
> Evidence from external sources must be read independently.

## Local quick start

### 1. Backend

```powershell
cd C:\Projects\TruthLens-AI
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/docs`.

### 2. Frontend

In a second terminal:

```powershell
cd C:\Projects\TruthLens-AI\frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

The site has three pages: **Analyze** (`/`), **Saved articles** (`/history`),
and **About / methodology** (`/about`). Use the Pages button on the left side
of the header to open the vertical page navigation. The home page includes
animated, labeled charts of the traditional model's recorded LIAR test metrics;
they are benchmark results, not evidence about an article. Saved articles are
loaded from the backend database. Choose **Light**, **Dark**, or **Device** in
the header to change the color theme; the selection is saved in this browser,
and Device follows the operating system appearance preference.

## Analysis workflow

1. Enter a headline and at least 40 characters of article text.
2. The frontend saves the submission through `POST /api/submissions`.
3. The frontend requests `POST /api/analyze`.
4. The configured classifier returns a LIAR benchmark label and token signals.
5. When the local DistilBERT model is trained, the API also returns a
   side-by-side traditional/transformer comparison; otherwise it marks that
   model as not trained.
6. External fact-check reviews are returned only when an API key is configured.

The local database is `data/truthlens.db` and is excluded from Git.
Submissions and their analysis result are stored in the `news_submissions`
table. Open the **Saved articles** page and select a row to inspect the
stored headline, article text, status, model label, language signals, and
available review citations. The UI intentionally does not display the
classifier's numeric score as a confidence or truth probability. History
search, status filters, date sorting, and pagination operate on the latest 20
records returned by the API. Reanalysis uses `POST /api/analyze`. The Saved
articles page supports permanent deletion after a confirmation prompt; it
removes the selected submission and its stored analysis through
`DELETE /api/submissions/{submission_id}`. A successful deletion returns
`204 No Content`; an unknown ID returns `404`. The deletion uses the configured
database provider (SQLite or Supabase), with credentials kept on the backend.
The API listing endpoint is `GET /api/submissions`; for example:

The analysis workspace includes a clearly labeled fictional sample for
demonstration. Model comparisons describe benchmark-label predictions, not
proof that an article is true or false. Claim-level evidence and a model build
version are not produced. The About page reports the traditional model's
held-out test accuracy (24.8%), macro-F1 (24.6%), macro-precision (24.6%), and
macro-recall (25.7%); transformer metrics are shown only after a local
fine-tuning run completes.

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/submissions?limit=20 |
  ConvertTo-Json -Depth 8
```

`GET /api/configuration` reports provider readiness as booleans and does not
return secret values. When Google Fact Check credentials are absent, analysis
returns an explicit `not_configured` status and no fabricated reviews.

To inspect the local SQLite file directly, from the project root:

```powershell
.\.venv\Scripts\python.exe -c "import sqlite3; c=sqlite3.connect('data/truthlens.db'); print(*c.execute('select id, headline, status, created_at from news_submissions order by created_at desc limit 20'), sep='\n'); c.close()"
```

## Optional configuration

Copy `backend/.env.example` to `backend/.env`. Supported settings:

- `DATABASE_PROVIDER=sqlite` or `supabase`
- `SQLITE_DATABASE_PATH=data/truthlens.db`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `GOOGLE_FACT_CHECK_API_KEY`
- `MODEL_PROVIDER=traditional` or `transformer`
- `TRANSFORMER_MODEL_PATH=backend/models/liar_distilbert`

Do not place the Supabase service-role key or fact-check API key in frontend
environment variables or source code.

Local development does not require either external credential: SQLite and the
traditional baseline are the supported offline path. Set the Supabase values
only when using a real Supabase project and its server-side service-role key.

## Training

Prepare data and train the traditional baseline:

```powershell
.\.venv\Scripts\python.exe backend\scripts\prepare_dataset.py
.\.venv\Scripts\python.exe backend\scripts\train_baseline.py
```

Install and run the optional DistilBERT pipeline:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-transformer.txt
.\.venv\Scripts\python.exe backend\scripts\train_transformer.py
```

Transformer fine-tuning uses the cached/downloaded DistilBERT checkpoint and
the LIAR train split. It is best run with a GPU; CPU training can take many
hours. Until the output model exists, the API reports the transformer as
`not_trained` and keeps the traditional baseline available. Compare models
only after fine-tuning and held-out test evaluation complete.

## Tests and build

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest -q
cd ..\frontend
npm run build
npm run lint
```

## Docker

With Docker Desktop running and its Linux engine available:

```powershell
docker compose up --build
```

- Frontend: `http://localhost:8080`
- API: `http://localhost:8000/docs`

Docker is optional. If Docker Desktop cannot start, run the API and frontend
with the local Python and Node commands above; do not treat a valid Compose
configuration as evidence that a container deployment is running.
