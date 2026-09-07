# Fact Knowledge Layer

A high-precision document intelligence platform that extracts grounded atomic facts from complex unstructured PDF documents (tables, dense text, multi-column layouts, and figures), maps them into a relational schema, and cross-references facts across documents to reveal corroborations, contradictions, contextual reconciliations, and extraction anomalies.

---

## 🚀 Architecture Approach

The Fact Knowledge Layer operates as an end-to-end extraction and reconciliation pipeline:

1. **Document Ingestion & Multi-Modal Parsing:**
   - **Docling:** Primary layout analysis engine converting complex PDFs into structured reading orders, markdown tables, and layout-aware text chunks.
   - **PyMuPDF (`fitz`):** High-speed PDF rasterization, coordinate extraction, and visual bounding box clipping.

2. **Grounded Atomic Fact Extraction:**
   - Powered by **Google Gemini 2.5 Flash** (`google-genai` SDK) paired with **`instructor`** for strict Pydantic v2 schema enforcement.
   - Facts are extracted as granular, atomic assertions tagged with entities, attributes, values, units, temporal validity, and exact page/bounding box citations.

3. **Relational Knowledge Graph & Storage:**
   - Normalized relational persistence using **SQLite** and **SQLAlchemy ORM**.
   - Preserves lineage from source PDF page coordinates down to individual atomic assertions.

4. **Cross-Document Fact Reconciliation Engine:**
   - Evaluates factual overlap across documents to automatically classify:
     - **Corroborations:** Identical or semantically aligned factual claims confirmed across independent sources.
     - **True Contradictions:** Direct conflicts between document claims (e.g., mismatched figures, conflicting event dates, contradictory outcomes).
     - **Contextual Reconciliations:** Apparent discrepancies resolved through context (different reporting periods, currencies, accounting bases, or scopes).
     - **Failure Analysis:** Extraction anomalies, low-confidence parses, or model ambiguities detected by the engine and paired with mitigation logs.

5. **Interactive Split-Screen UI:**
   - **React 18 + Vite + Tailwind CSS + Lucide React**.
   - Integrated PDF viewport using **`react-pdf` (`pdfjs-dist`)** synchronized bi-directionally with interactive fact cards and page-jump overlays.

---

## 🛠️ Tech Stack

- **Backend:** Python 3.11+, FastAPI, Pydantic v2, `instructor`, `google-genai` (`gemini-2.5-flash`), SQLAlchemy, SQLite, `docling`, `PyMuPDF`.
- **Frontend:** React 18, Vite, Tailwind CSS, Lucide React, `react-pdf`.

---

## 📦 Setup Instructions

### Prerequisites
- Python 3.11+
- Node.js 18+ and npm
- A Gemini API Key from Google AI Studio

### 1. Environment Configuration
Copy the sample environment file and add your credentials:
```bash
cp .env.example .env
```
Edit `.env` and set your `GEMINI_API_KEY`:
```env
GEMINI_API_KEY=your_actual_gemini_api_key
DATABASE_URL=sqlite:///./facts.db
PORT=8000
```

### 2. Backend Setup
```bash
# Navigate to backend directory
cd backend

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run database migrations / initialization
python -m app.db.init_db

# Start FastAPI development server
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend Setup
```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start Vite development server
npm run dev
```

The application will be accessible at:
- **Web UI:** `http://localhost:5173`
- **Backend API Docs (Swagger):** `http://localhost:8000/docs`

---

## 🎥 Demo Video

- **Walkthrough Video:** `[Coming Soon - Add Loom / YouTube Link Here]`

---

## ⚠️ Known Limitations & Edge Cases

- **Non-Searchable / Scanned Documents:** PDFs without OCR text layers rely on Docling's OCR pipeline, which increases parsing latency.
- **Complex Nested Tables:** Deeply nested or merged header tables may require manual review if columns lack clear headers.
- **Large Document Processing:** Multi-hundred-page PDFs should be processed asynchronously in batches to respect rate limits and memory constraints.
- **SQLite Concurrency:** SQLite is default for development simplicity; production deployments should switch `DATABASE_URL` to PostgreSQL.

---

## 🤖 AI Tools & Models Used

- **Google Gemini 2.5 Flash:** Primary LLM for fast, cost-effective, structured fact extraction and reasoning over document pairs.
- **Instructor SDK:** Enforces type safety, runtime validation, and strict JSON schema generation with Gemini.
- **Google Antigravity:** Autonomous pair-programming agent environment for phased scaffolding, testing, and continuous delivery.

