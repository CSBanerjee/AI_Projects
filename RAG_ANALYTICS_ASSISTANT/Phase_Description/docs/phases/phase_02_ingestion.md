# Phase 2 — Document Ingestion Pipeline

**Steps:** 6  
**Goal:** Load your source documents, split them into chunks, embed them,
and store them in ChromaDB.
The chunk size experiment is run after Phase 3 Step 3.3 — see phase_03_retrieval.md.

---

## Step 2.1 — Build app/ingestion/loader.py

**What you do:**

Load `.txt` files from the `docs/` folder using LangChain document loaders.

```python
from langchain_community.document_loaders import TextLoader
from app.utils.logger import get_logger, log_event
from app.config import settings

log = get_logger(__name__)
def load() -> list:
  docs_dir = settings.DOCS_DIR
  documents = []
  for filepath in sorted(docs_dir.iterdir()):
    if filepath.suffix.lower() == ".txt" and filepath.stat().st_size == 0:
    if filepath.suffix.lower() != ".txt":
      continue

    loader = TextLoader(str(filepath))
    docs = loader.load()
    documents.extend(docs)
    log_event(log, "info", "file_loaded",
                  file=filepath.name,
                  pages=len(docs))
  pdf_count = len([f for f in docs_dir.iterdir()
                     if f.suffix.lower() == ".txt"])
  log_event(log, "info", "documents_loaded",
              total_pages=len(documents),
              files=pdf_count)
  return documents

```

**Install required packages:**
```bash
uv pip install langchain-community
```

**Verify:**
```bash
PYTHONPATH=. python -c "
from app.ingestion import loader
docs = loader.load()
print(len(docs), 'documents loaded')
print(docs[0].metadata)
"
Expected: 5 documents loaded
```

---

## Step 2.2 — Build app/ingestion/chunker.py

**What you do:**

```python
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.config import settings
from app.utils.logger import get_logger, log_event
log = get_logger(__name__)
def split(documents: list) -> list:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
        length_function=len)
    chunks = splitter.split_documents(documents)
    for i, chunk in enumerate(chunks):
        chunk.metadata["chunk_index"] = i
        chunk.metadata["total_chunks"] = len(chunks)
    log_event(log, "info", "chunks_created",
              count=len(chunks),
              chunk_size=settings.CHUNK_SIZE,
              overlap=settings.CHUNK_OVERLAP)
    return chunks

```
> **Important:** Use `langchain_text_splitters` not `langchain.text_splitter`.
> The class moved packages in newer LangChain versions. See Finding 8 in FINDINGS.md.

**Install required packages:**
```bash
uv pip install langchain-text-splitters
```

**Verify:**
```bash
PYTHONPATH=. python -c "
from app.ingestion import loader, chunker
docs = loader.load()
chunks = chunker.split(docs)
print(len(chunks), 'chunks created')
print(chunks[0].page_content[:100])
print(chunks[0].metadata)
"
```

---

## Step 2.3 — Build app/ingestion/embedder.py

**What you do:**

```python
from langchain_openai import OpenAIEmbeddings
from app.config import settings
from app.utils.logger import get_logger, log_event
log = get_logger(__name__)

def get_embedding_model() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        model=settings.EMBEDDING_MODEL,
        openai_api_key=settings.OPENAI_API_KEY
    )


def embed(texts: list[str]) -> list[list[float]]:
    model = get_embedding_model()
    vectors = model.embed_documents(texts)
    log_event(log, "info", "embeddings_created",
              count=len(vectors),
              model=settings.EMBEDDING_MODEL,
              dimensions=len(vectors[0]) if vectors else 0)
    return vectors
```

**Verify (requires OPENAI_API_KEY in .env):**
```bash
PYTHONPATH=. python -c "
from app.ingestion import embedder
vectors = embedder.embed(['test sentence about APAC sales'])
print('Vector count:', len(vectors))
print('Dimensions:', len(vectors[0]))
"
```
Should print `1536`.

---

## Step 2.4 — Build app/store/vector_store.py

**What you do:**

```python
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings    
from app.config import settings
from app.utils.logger import get_logger, log_event

log = get_logger(__name__)

COLLECTION_NAME = "analytics_docs"

def get() -> Chroma:
    embeddings = OpenAIEmbeddings(
        model=settings.EMBEDDING_MODEL,
        openai_api_key=settings.OPENAI_API_KEY)

    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=settings.CHROMA_PERSIST_DIR
        )

def add_documents(chunks: list) -> None:

    vs = get()
    vs.add_documents(chunks)
    log_event(log, "info", "documents_stored", count=len(chunks))

def count() -> int:
    return get()._collection.count()

def reset() -> None:

    vs = get()
    vs.delete_collection()
    log.warning("event=vector_store_reset collection=analytics_docs")
```

> **Important:** Both `langchain-chroma` AND `chromadb` must be installed.
> `langchain-chroma` wraps `chromadb` — without `chromadb` the import fails.
> See Findings 14 and 15 in FINDINGS.md.

**Install required packages:**
```bash
uv pip install langchain-chroma chromadb
```

**Verify:**
```bash
PYTHONPATH=. python -c "
from app.store import vector_store
print(vector_store.count(), 'chunks stored')
"
```

---

## Step 2.5 — Build ingest.py — ingestion entry point

**What you do:**

```python
import argparse
import sys
from app.config import settings
from app.ingestion import loader, chunker
from app.store import vector_store
from app.utils.logger import get_logger, log_event

log = get_logger(__name__)

def main(reset: bool = False) -> None:
    settings.validate()
    if reset:
        log.warning("--reset flag set. Clearing ChromaDB collection.")
        vector_store.reset()
    log.info("Starting ingestion pipeline...")
    documents = loader.load()
    print(f"Documents loaded : {len(documents)}")
    chunks = chunker.split(documents)
    print(f"Chunks created   : {len(chunks)}")
    vector_store.add_documents(chunks)
    total = vector_store.count()
    print(f"Vectors stored   : {len(chunks)}")
    print(f"Collection total : {total}")
    log_event(log, "info", "ingestion_complete",
              documents=len(documents),
              chunks=len(chunks),
              total_in_store=total)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Ingest PDF documents into ChromaDB for the RAG pipeline."
        # description appears when someone runs: python ingest.py --help
    )

    parser.add_argument(
        "--reset",
        action="store_true",
        help="Clear the ChromaDB collection before re-ingesting. "
             "Use this when changing CHUNK_SIZE or when adding/removing documents."
    )

    args = parser.parse_args()
    main(reset=args.reset)
```

**Run:**
```bash
python ingest.py
python ingest.py --reset   # clear and rebuild
```

**Verify:**
```
Documents loaded : 20
Chunks created   : 60
Vectors stored   : 60
Collection total : 60
```

---

## Step 2.6 — Write tests/test_ingestion.py — 12 tests

**What you do:**

```python
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from langchain_core.documents import Document
from app.config import settings

class TestLoader:
    def test_skips_non_txt_files(self):
        with patch("app.ingestion.loader.TextLoader") as mock_loader, \
             patch("app.ingestion.loader.settings") as mock_settings:
            import tempfile
            tmp = Path(tempfile.mkdtemp())
            (tmp / "README.md").write_text("not a txt")
            (tmp / "report.txt").write_text("sales content")
            mock_settings.DOCS_DIR = tmp
            mock_loader.return_value.load.return_value = [
                Document(page_content="sales content", metadata={"source": "report.txt"})
            ]
            from app.ingestion import loader
            docs = loader.load()
            assert mock_loader.call_count == 1
            assert len(docs) == 1

    def test_skips_empty_txt_silently(self):
        with patch("app.ingestion.loader.TextLoader") as mock_loader, \
             patch("app.ingestion.loader.settings") as mock_settings:
            import tempfile
            tmp = Path(tempfile.mkdtemp())
            (tmp / "empty.txt").write_bytes(b"")
            mock_settings.DOCS_DIR = tmp
            from app.ingestion import loader
            docs = loader.load()
            assert mock_loader.call_count == 0
            assert docs == []

    def test_returns_correct_document_count(self):
        with patch("app.ingestion.loader.TextLoader") as mock_loader, \
             patch("app.ingestion.loader.settings") as mock_settings:
            import tempfile
            tmp = Path(tempfile.mkdtemp())
            for i in range(3):
                (tmp / f"doc{i}.txt").write_text("content")
            mock_settings.DOCS_DIR = tmp
            mock_loader.return_value.load.return_value = [
                Document(page_content="page", metadata={"source": "test.txt"})
            ]
            from app.ingestion import loader
            docs = loader.load()
            assert len(docs) == 3

    def test_metadata_attached_to_each_document(self):
        with patch("app.ingestion.loader.TextLoader") as mock_loader, \
             patch("app.ingestion.loader.settings") as mock_settings:
            import tempfile
            tmp = Path(tempfile.mkdtemp())
            (tmp / "test.txt").write_text("content")
            mock_settings.DOCS_DIR = tmp
            mock_loader.return_value.load.return_value = [
                Document(page_content="content", metadata={"source": "test.txt"})
            ]
            from app.ingestion import loader
            docs = loader.load()
            assert all("source" in d.metadata for d in docs)

class TestChunker:
    def test_chunk_size_respected(self):
        doc = Document(page_content="word " * 1000, metadata={"source": "test.pdf"})
        from app.ingestion import chunker
        chunks = chunker.split([doc])
        assert all(len(c.page_content) <= settings.CHUNK_SIZE + 50 for c in chunks)

    def test_metadata_preserved_on_every_chunk(self):
        doc = Document(page_content="content " * 200, metadata={"source": "test.pdf"})
        from app.ingestion import chunker
        chunks = chunker.split([doc])
        assert all("source" in c.metadata for c in chunks)
        assert all("chunk_index" in c.metadata for c in chunks)

    def test_chunk_index_is_sequential(self):
        doc = Document(page_content="word " * 500, metadata={"source": "test.pdf"})
        from app.ingestion import chunker
        chunks = chunker.split([doc])
        indices = [c.metadata["chunk_index"] for c in chunks]
        assert indices == list(range(len(chunks)))

class TestEmbedder:
    def test_returns_correct_dimensions(self):
        with patch("app.ingestion.embedder.OpenAIEmbeddings") as mock_emb:
            mock_emb.return_value.embed_documents.return_value = [[0.1] * 1536]
            from app.ingestion import embedder
            vectors = embedder.embed(["test"])
            assert len(vectors[0]) == 1536

    def test_embed_documents_called_once(self):
        with patch("app.ingestion.embedder.OpenAIEmbeddings") as mock_emb:
            mock_emb.return_value.embed_documents.return_value = [[0.1] * 1536]
            from app.ingestion import embedder
            embedder.embed(["test"])
            mock_emb.return_value.embed_documents.assert_called_once()

class TestVectorStore:
    def test_count_returns_integer(self):
        with patch("app.store.vector_store.Chroma") as mock_chroma, \
             patch("app.store.vector_store.OpenAIEmbeddings"):
            mock_chroma.return_value._collection.count.return_value = 42
            from app.store import vector_store
            assert vector_store.count() == 42

    def test_add_documents_calls_chroma(self):
        with patch("app.store.vector_store.Chroma") as mock_chroma, \
             patch("app.store.vector_store.OpenAIEmbeddings"):
            chunks = [Document(page_content="test", metadata={"source": "a.pdf"})]
            from app.store import vector_store
            vector_store.add_documents(chunks)
            mock_chroma.return_value.add_documents.assert_called_once_with(chunks)

    def test_reset_deletes_collection(self):
        with patch("app.store.vector_store.Chroma") as mock_chroma, \
             patch("app.store.vector_store.OpenAIEmbeddings"):
            from app.store import vector_store
            vector_store.reset()
            mock_chroma.return_value.delete_collection.assert_called_once()
```

**Run:**
```bash
PYTHONPATH=. python -m pytest tests/test_ingestion.py -v
```

**Verify:** 12 tests pass. Zero real OpenAI or ChromaDB calls made.

---

## Phase 2 complete checklist

- [ ] `loader.py` loads all 5 `.txt` files — `total_pages=5` in logs
- [ ] `chunker.py` splits with correct size and overlap — `chunk_index` in metadata
- [ ] `embedder.py` returns 1536-dimensional vectors
- [ ] `vector_store.py` stores and counts without error
- [ ] `python ingest.py` runs end-to-end — summary printed, `chroma_db/` populated
- [ ] 12 tests pass: `PYTHONPATH=. python -m pytest tests/test_ingestion.py -v`

**Document Ingestion Pipeline:**
┌──────────────────────────────────────┐
│          Step 2.5                    │
│        ingest.py (Main)              │
│ - Entry point                        │
│ - validate settings                  │
│ - orchestrates full pipeline         │
└──────────────────┬───────────────────┘
                   │
                   ▼
        ┌───────────────────────┐
        │ Reset requested?      │
        │ (--reset flag)        │
        └───────┬───────────────┘
                │ Yes
                ▼
┌──────────────────────────────────────┐
│          Step 2.4                    │
│      vector_store.reset()            │
│ - Clear Chroma collection            │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│          Step 2.1                    │
│        loader.py                     │
│ Document Loading                     │
│ - Read .txt files from docs/         │
│ - Skip empty/non-txt files           │
└──────────────────┬───────────────────┘
                   │ documents
                   ▼
┌──────────────────────────────────────┐
│          Step 2.2                    │
│        chunker.py                    │
│ Document Chunking                    │
│ - Split documents                    │
│ - Add metadata                       │
│   • chunk_index                      │
│   • total_chunks                     │
└──────────────────┬───────────────────┘
                   │ chunks
                   ▼
┌──────────────────────────────────────┐
│          Step 2.3                    │
│        embedder.py                   │
│ Embedding Generation                 │
│ - OpenAIEmbeddings                   │
│ - Convert chunks → vectors           │
│ - 1536 dimensions                    │
└──────────────────┬───────────────────┘
                   │ vectors
                   ▼
┌──────────────────────────────────────┐
│          Step 2.4                    │
│      vector_store.py                 │
│ Vector Storage                       │
│ - add_documents(chunks)              │
│ - Store in ChromaDB                  │
│ - Persist to chroma_db/              │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│          Step 2.5                    │
│     Pipeline Summary Output          │
│ - Documents loaded                   │
│ - Chunks created                     │
│ - Vectors stored                     │
│ - Collection total                   │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│          Step 2.6                    │
│      tests/test_ingestion.py         │
│ Testing & Validation                 │
│ - 12 unit tests                      │
│ - Mock OpenAI & ChromaDB             │
│ - Validate pipeline components       │
└──────────────────────────────────────┘

**Next:** Phase 3 — Retrieval