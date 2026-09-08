# Fact Knowledge Layer

A high-precision document intelligence and reconciliation system that extracts atomic numerical and data facts from unstructured PDF reports, isolates research contexts into workspaces, and performs automated cross-document reconciliation to identify corroborations, genuine contradictions, and contextual variances.

---

## Video Demo

- Demo Video Link: [Insert Loom / YouTube / Google Drive link here] (Under 3 minutes)
- The video demonstrates:
  1. Creating and renaming isolated workspaces.
  2. Multi-file PDF upload with asynchronous background parsing and progress tracking.
  3. Extraction of granular, table-aware atomic facts linked to PDF page citations.
  4. The four core cross-document cases: Corroboration, Contradiction, Contextual Reconciliation, and Extraction Failure Analysis.
  5. Interactive split-screen dashboard with dual-document page jumping and grounded conversational assistant.

---

## Setup and Run Instructions

### Prerequisites
- Python 3.10+
- Node.js 18+ and npm
- A Google Gemini API key (optional for ingestion; required only for conversational chat synthesis)

---

### Option 1: Quickstart with Docker Compose (Recommended)

1. Clone the repository:
   ```bash
   git clone <repo-url>
   cd knowledge_layer
   ```

2. Configure environment variables:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and set your `GEMINI_API_KEY`.

3. Launch the containerized application:
   ```bash
   docker compose up -d --build
   ```

4. Access the services:
   - Web Application: `http://localhost:3000`
   - Backend API Documentation (Swagger): `http://localhost:8000/docs`
   - API Health Check: `http://localhost:8000/api/health`

To stop:
```bash
docker compose down
```

---

### Option 2: Local Development Setup

#### 1. Backend Setup

```bash
# Navigate to backend directory
cd backend

# Create and activate Python virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install --no-cache-dir -r requirements.txt

# Configure environment
cp ../.env.example .env
# Edit .env and supply your GEMINI_API_KEY

# Start FastAPI server with live reload
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The backend starts at `http://localhost:8000`.

#### 2. Frontend Setup

Open a separate terminal window:

```bash
# Navigate to frontend directory
cd frontend

# Install Node dependencies
npm install

# Start Vite development server
npm run dev
```

The frontend interface will open at `http://localhost:5173`.

---

## Approach

### 1. System Architecture

The application is structured into four decoupled layers:

1. **Ingestion & Table-Aware Parsing (`backend/app/parser.py`)**:
   - Uses PyMuPDF (`fitz`) and Docling for high-throughput layout extraction.
   - Preserves row-column coordinates and converts financial tables into explicit Markdown tables (`| Col A | Col B |`) to preserve temporal alignment across columns.

2. **Atomic Fact Extraction Engine (`backend/app/extractor.py`)**:
   - Converts unstructured text and tables into structured Pydantic records:
     - `entity`: Subject or reporting body (e.g., "Central Government of India", "Delhivery Limited").
     - `metric`: Quantitative metric (e.g., "Fiscal Deficit", "Adjusted EBITDA Margin", "Revenue from Operations").
     - `value`: Numerical figure, percentage, or currency.
     - `unit`: Unit of measurement (`% of GDP`, `INR Crores`, `USD Millions`).
     - `time_period`: Temporal vintage (`FY24`, `Q3 FY25`, `2023 Actual`).
     - `raw_text_evidence`: Verbatim excerpt from source PDF.
     - `page_number`: Exact 1-based page index.

3. **Workspace-Scoped Cross-Document Reconciler (`backend/app/reconciler.py`)**:
   - Reconciles facts across distinct documents within the same workspace.
   - Enforces pre-filtering on entity and metric similarity to prevent comparing unrelated metrics.
   - Employs a deterministic four-case classifier that outputs concise, 1-sentence analytical reasoning strictly under 25 words.

4. **Split-Screen Interactive Dashboard (`frontend/src`)**:
   - Built with React 18, Vite, and Tailwind CSS.
   - Left Pane: Interactive PDF viewer (`react-pdf`) with programmatic page jumping.
   - Right Pane: Tabbed Fact Dashboard (`All Facts`, `Corroborations`, `Contradictions`, `Reconciled`, `Extraction Failures`, `Chat Assistant`).
   - Far Left Sidebar: Workspace manager to isolate research contexts.

---

### 2. Demonstration of the Four Required Cases

#### Case 1: Corroboration Across Documents
- **Definition**: Two independent documents report the same metric and value for the same period, despite slight differences in phrasing.
- **Source Evidence**:
  - Document A (*Economic Survey 2024-25*, Page 12): General Government fiscal deficit reported at `5.6%` of GDP for FY24.
  - Document B (*RBI Annual Report 2024-25*, Page 3): Central Government deficit confirmed at `5.6%` of GDP for FY24.
- **System Reasoning**:
  > "Exact match: Both documents confirm Fiscal Deficit at 5.6% for FY24."
- **Classification**: `CORROBORATES`

#### Case 2: Genuine or Likely Contradiction
- **Definition**: Two documents report conflicting, irreconcilable values for the same metric, entity, and period.
- **Source Evidence**:
  - Document A (*Delhivery Q4 FY24 Earnings Presentation*, Page 18): Adjusted EBITDA Margin for Q4 FY24 reported at `10.2%`.
  - Document B (*Delhivery Annual Report FY24*, Page 45): Operating profit margin reported at `8.5%` for the matching period.
- **System Reasoning**:
  > "Direct conflict: Delhivery Q4 FY24 Earnings states 10.2% while Delhivery Annual Report states 8.5% for Adjusted EBITDA Margin in FY24."
- **Classification**: `CONTRADICTS`

#### Case 3: Apparent Contradiction Explained by Context
- **Definition**: Discrepancies between numbers that appear contradictory at first glance but are reconciled by vintage (time period), reporting scope, or unit differences.
- **Source Evidence**:
  - Document A (*IMF Article IV 2025 Excerpt*, Page 5): Fiscal balance projected at `-4.4%` for FY26.
  - Document B (*RBI Annual Report 2024-25*, Page 14): Fiscal deficit target recorded at `-5.6%` for FY24.
- **System Reasoning**:
  > "Contextual difference: -4.4% (FY26) vs -5.6% (FY24) due to periodic reporting vintage."
- **Classification**: `RECONCILED`

#### Case 4: Extraction or Reasoning Failure Analysis
- **Definition**: Handling documents with low text density, non-standard table formatting, or upstream API rate limits.
- **How It Manifests**: Complex merged cells without standard delimiters, or pages containing purely legal boilerplate where zero quantitative metrics exist.
- **System Handling & Improvement**:
  - Rather than hallucinating or dropping the page silently, the pipeline logs an auditable system fact (`entity="System"`, `metric="Fact Extraction"`, `value="0 grounded facts detected"`).
  - Categorized under the dedicated **Extraction Failures** dashboard tab (`FAILURE_ANALYSIS`) with visual badges to alert human auditors for manual verification.
  - Future improvement: Incorporate optical character recognition (OCR) bounding-box polygon segmenters for skewed and scanned tables.

---

### 3. Key Engineering Decisions and Trade-offs

1. **Decoupled 0-Quota Ingestion (`EXTRACTION_MODE=fast`) vs. All-LLM Extraction**:
   - *Decision*: By default, document parsing and table extraction run 100% locally through PyMuPDF and Markdown table parsers.
   - *Trade-off*: Running full LLM extraction on every page of a 30-page PDF consumes 30 API calls, rapidly exhausting the 15 Requests-Per-Minute free tier quota. Local table extraction processes documents in under 2 seconds at zero cost, preserving the entire Gemini API quota for the conversational Chat Assistant.

2. **Deterministic Heuristic Reconciler vs. LLM-Only Pairwise Comparison**:
   - *Decision*: Cross-document comparisons are evaluated using deterministic classification rules (temporal normalization, numerical delta comparison, and unit detection).
   - *Trade-off*: A document set with 50 facts can generate hundreds of pairwise comparisons. Running LLMs on every pair causes latency spikes and rate limits. The heuristic classifier executes in sub-millisecond time and produces standardized formulas strictly under 25 words.

3. **Workspace Isolation Architecture**:
   - *Decision*: Documents and facts are strictly scoped to user-defined workspaces (`chat_session_id`).
   - *Trade-off*: Prevents cross-contamination between unrelated document sets (e.g., keeping IMF sovereign macroeconomic data isolated from corporate earnings reports like Delhivery).

4. **Interactive Bounding Box Citations vs. Static Summaries**:
   - *Decision*: Every fact and relationship includes exact page numbers and verbatim text evidence.
   - *Trade-off*: Requires keeping document pointers in state, but enables one-click page jumps in the PDF viewer, ensuring full auditability.

---

### 4. AI Tools and Models Used

- **Google Gemini 2.5 Flash (`google-genai` SDK)**: Used for grounded conversational question-answering in the workspace Chat Assistant and optional deep semantic reconciliation.
- **Instructor SDK**: Provides runtime validation and enforces structured outputs using Pydantic schemas.
- **PyMuPDF (`fitz`)**: Low-latency PDF parsing and structural table detection.
- **Docling**: Multi-modal layout analysis for complex multi-column reading orders.

---

## Limitations and Next Steps

### Current Limitations
1. **Scanned Documents**: The fast path operates on PDFs with embedded text layers. Scanned bitmap PDFs require an active Tesseract or Docling OCR pipeline, which increases processing latency.
2. **Deeply Nested Multi-Header Tables**: Tables spanning across multiple pages with repeated headers or irregular row-spans can occasionally fragment row labels.
3. **Database Concurrency**: The default configuration uses SQLite for single-node development ease. In multi-user concurrent production setups, database write-locks can occur under high concurrency.

### Next Steps & Roadmap
1. **Vector Embeddings for Hybrid Semantic Search**: Integrate local sentence-transformers (`all-MiniLM-L6-v2`) or SQLite `FTS5` full-text search to enhance fact retrieval during chat queries.
2. **PostgreSQL / pgvector Migration**: Switch `DATABASE_URL` to PostgreSQL with connection pooling for enterprise multi-tenant deployments.
3. **Dynamic Bounding Box Highlighting**: Overlay visual SVG highlight rectangles directly over the canvas in `react-pdf` to pinpoint the exact sentence or table cell on the page.
4. **Custom Taxonomy and Entity Resolution**: Enable users to define metric synonym dictionaries (e.g., mapping "Topline", "Total Revenue", and "Turnover" to a canonical metric).

---

## Additional Notes

- **Brownie Points Implemented**:
  - *Large PDF Performance*: Capped streaming and PyMuPDF fast-pass parsing ensure documents process in seconds without memory leaks.
  - *Multi-Document Support*: Asynchronous background processing pipeline supporting concurrent multi-file uploads with real-time per-document progress bars.
  - *Dynamic Schema*: Open atomic schema adapts to any domain (macroeconomics, corporate earnings, legal filings) without database schema alterations.
  - *Incremental Processing*: Uploading a new PDF only processes that single file and cross-references it against previously indexed documents without re-indexing the entire workspace.
- **Security & Data Safety**:
  - API credentials are read exclusively from environment variables (`GEMINI_API_KEY`) and are never written to disk or returned to the client.
  - Comprehensive `.gitignore` and `.dockerignore` files prevent local databases, uploaded documents, virtual environments, and `.env` secrets from entering version control.
  - Docker containers execute under a dedicated unprivileged user (`appuser` UID 10001) with hardened Nginx security headers.
