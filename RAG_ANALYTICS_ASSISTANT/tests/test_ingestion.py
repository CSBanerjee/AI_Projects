"""
tests/test_ingestion.py — Phase 2 Step 2.6

Tests for the four ingestion modules:
  - loader.py        (TestLoader     — 4 tests)
  - chunker.py       (TestChunker    — 3 tests)
  - embedder.py      (TestEmbedder   — 2 tests)
  - vector_store.py  (TestVectorStore — 3 tests)

Total: 12 tests. Zero real OpenAI or ChromaDB calls made.

Run from the project root:
    PYTHONPATH=. python -m pytest tests/test_ingestion.py -v
"""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, call
from langchain_core.documents import Document
from app.config import settings


# ══════════════════════════════════════════════════════════════════════════════
# TestLoader
# ══════════════════════════════════════════════════════════════════════════════

class TestLoader:
    """
    Tests for loader.load().
    We mock PyPDFLoader and settings.DOCS_DIR so no real PDFs are read.
    """

    def test_skips_non_pdf_files(self):
        """
        Non-PDF files (README.md, .DS_Store etc.) must be silently skipped.
        PyPDFLoader must only be called for .pdf files.
        """
        with patch("app.ingestion.loader.PyPDFLoader") as mock_pdf, \
             patch("app.ingestion.loader.settings") as mock_settings:

            tmp = Path(tempfile.mkdtemp())
            (tmp / "README.md").write_text("not a pdf")
            (tmp / "report.pdf").write_bytes(b"%PDF-1.4 fake content")

            mock_settings.DOCS_DIR = tmp
            mock_pdf.return_value.load.return_value = [
                Document(page_content="pdf content", metadata={"source": "report.pdf"})
            ]

            from app.ingestion import loader
            docs = loader.load()

            # PyPDFLoader called once — only for report.pdf, not README.md
            assert mock_pdf.call_count == 1
            assert len(docs) == 1

    def test_skips_empty_pdf_silently(self):
        """
        A 0-byte PDF must be skipped before PyPDFLoader is called.

        Note: the current loader.py silently skips empty files without
        logging a warning — this is a known gap documented in FINDINGS.md.
        The test verifies only that the skip happens and no documents
        are returned. It does NOT check for a warning log.
        """
        with patch("app.ingestion.loader.PyPDFLoader") as mock_pdf, \
             patch("app.ingestion.loader.settings") as mock_settings:

            tmp = Path(tempfile.mkdtemp())
            (tmp / "empty.pdf").write_bytes(b"")   # 0-byte file

            mock_settings.DOCS_DIR = tmp

            from app.ingestion import loader
            docs = loader.load()

            # PyPDFLoader must never be called on a 0-byte file
            assert mock_pdf.call_count == 0
            # no documents returned
            assert docs == []

    def test_returns_correct_document_count(self):
        """
        3 PDF files × 1 Document each = 3 total Documents returned.
        """
        with patch("app.ingestion.loader.PyPDFLoader") as mock_pdf, \
             patch("app.ingestion.loader.settings") as mock_settings:

            tmp = Path(tempfile.mkdtemp())
            for i in range(3):
                (tmp / f"doc_{i}.pdf").write_bytes(b"%PDF-1.4 fake")

            mock_settings.DOCS_DIR = tmp
            mock_pdf.return_value.load.return_value = [
                Document(page_content="page content", metadata={"source": "test.pdf"})
            ]

            from app.ingestion import loader
            docs = loader.load()

            assert len(docs) == 3
            assert mock_pdf.call_count == 3

    def test_metadata_attached_to_each_document(self):
        """
        Every Document returned by load() must have 'source' in its metadata.
        """
        with patch("app.ingestion.loader.PyPDFLoader") as mock_pdf, \
             patch("app.ingestion.loader.settings") as mock_settings:

            tmp = Path(tempfile.mkdtemp())
            (tmp / "test.pdf").write_bytes(b"%PDF-1.4 fake")

            mock_settings.DOCS_DIR = tmp
            mock_pdf.return_value.load.return_value = [
                Document(
                    page_content="content",
                    metadata={"source": "/path/to/test.pdf", "page": 0}
                )
            ]

            from app.ingestion import loader
            docs = loader.load()

            assert all("source" in d.metadata for d in docs)


# ══════════════════════════════════════════════════════════════════════════════
# TestChunker
# ══════════════════════════════════════════════════════════════════════════════

class TestChunker:
    """
    Tests for chunker.split().
    No mocking needed — RecursiveCharacterTextSplitter has no external calls.
    """

    def test_chunk_size_respected(self):
        """
        No chunk should exceed CHUNK_SIZE + 50 characters.
        +50 buffer accounts for how the splitter handles boundaries.
        """
        doc = Document(
            page_content="word " * 1000,
            metadata={"source": "test.pdf"}
        )
        from app.ingestion import chunker
        chunks = chunker.split([doc])

        assert all(
            len(c.page_content) <= settings.CHUNK_SIZE + 50
            for c in chunks
        )

    def test_metadata_preserved_on_every_chunk(self):
        """
        Every chunk must have 'source', 'chunk_index', and 'total_chunks' in metadata.
        """
        doc = Document(
            page_content="content " * 200,
            metadata={"source": "test.pdf"}
        )
        from app.ingestion import chunker
        chunks = chunker.split([doc])

        assert all("source" in c.metadata for c in chunks)
        assert all("chunk_index" in c.metadata for c in chunks)
        assert all("total_chunks" in c.metadata for c in chunks)

    def test_chunk_index_is_sequential(self):
        """
        chunk_index must be 0, 1, 2 ... len(chunks)-1 with no gaps or repeats.
        """
        doc = Document(
            page_content="word " * 500,
            metadata={"source": "test.pdf"}
        )
        from app.ingestion import chunker
        chunks = chunker.split([doc])

        indices = [c.metadata["chunk_index"] for c in chunks]
        assert indices == list(range(len(chunks)))


# ══════════════════════════════════════════════════════════════════════════════
# TestEmbedder
# ══════════════════════════════════════════════════════════════════════════════

class TestEmbedder:
    """
    Tests for embedder.embed().
    We mock OpenAIEmbeddings so no real API call is made.
    """

    def test_returns_correct_dimensions(self):
        """
        Each vector returned by embed() must have exactly 1536 dimensions.
        """
        with patch("app.ingestion.embedder.OpenAIEmbeddings") as mock_emb:
            mock_emb.return_value.embed_documents.return_value = [[0.1] * 1536]

            from app.ingestion import embedder
            vectors = embedder.embed(["test sentence"])

            assert len(vectors[0]) == 1536

    def test_embed_documents_called_once(self):
        """
        embed_documents() must be called exactly once per embed() call.
        Multiple calls would waste API requests and cost money.
        """
        with patch("app.ingestion.embedder.OpenAIEmbeddings") as mock_emb:
            mock_emb.return_value.embed_documents.return_value = [[0.1] * 1536]

            from app.ingestion import embedder
            embedder.embed(["test sentence"])

            mock_emb.return_value.embed_documents.assert_called_once()


# ══════════════════════════════════════════════════════════════════════════════
# TestVectorStore
# ══════════════════════════════════════════════════════════════════════════════

class TestVectorStore:
    """
    Tests for vector_store.count(), add_documents(), and reset().
    We mock both Chroma and OpenAIEmbeddings.
    Nothing is written to chroma_db/ on disk.
    """

    def test_count_returns_integer(self):
        """
        count() must return the integer from ChromaDB._collection.count().
        """
        with patch("app.store.vector_store.Chroma") as mock_chroma, \
             patch("app.store.vector_store.OpenAIEmbeddings"):

            mock_chroma.return_value._collection.count.return_value = 42

            from app.store import vector_store
            result = vector_store.count()

            assert result == 42
            assert isinstance(result, int)

    def test_add_documents_calls_chroma(self):
        """
        add_documents() must pass the chunks list to Chroma.add_documents().
        """
        with patch("app.store.vector_store.Chroma") as mock_chroma, \
             patch("app.store.vector_store.OpenAIEmbeddings"):

            sample_chunks = [
                Document(
                    page_content="APAC discount is 20%.",
                    metadata={"source": "discount_policy.pdf", "chunk_index": 0}
                )
            ]

            from app.store import vector_store
            vector_store.add_documents(sample_chunks)

            mock_chroma.return_value.add_documents.assert_called_once_with(sample_chunks)

    def test_reset_deletes_collection(self):
        """
        reset() must call Chroma.delete_collection() to wipe ChromaDB.
        """
        with patch("app.store.vector_store.Chroma") as mock_chroma, \
             patch("app.store.vector_store.OpenAIEmbeddings"):

            from app.store import vector_store
            vector_store.reset()

            mock_chroma.return_value.delete_collection.assert_called_once()