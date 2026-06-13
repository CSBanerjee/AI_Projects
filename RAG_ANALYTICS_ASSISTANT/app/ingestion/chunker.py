from langchain_text_splitters import RecursiveCharacterTextSplitter
# RecursiveCharacterTextSplitter is a LangChain class that splits long text
# into smaller overlapping pieces called chunks.
# "Recursive" means it tries to split on natural boundaries in this order:
#   1. paragraph breaks (\n\n)  — most preferred, keeps paragraphs whole
#   2. line breaks      (\n)    — second choice
#   3. spaces           (" ")   — third choice
#   4. characters       ("")    — last resort, cuts mid-word if necessary
# It works down this list until each piece is small enough to fit in CHUNK_SIZE.

from app.config import settings
# settings.CHUNK_SIZE    → max characters per chunk (default 500 from .env)
# settings.CHUNK_OVERLAP → how many characters the next chunk re-reads
# from the end of the previous chunk (default 50)
# Both values come from .env so you can change them without touching code.

from app.utils.logger import get_logger, log_event
# get_logger  → returns a named logger for this module
# log_event   → writes a structured key=value log line

log = get_logger(__name__)
# __name__ is automatically "app.ingestion.chunker" inside this file
# every log line from here will show that name as the source


def split(documents: list) -> list:
    # documents: list  → the list of Document objects returned by loader.load()
    #                    each Document = one page from a PDF
    #                    a 4-page PDF produces 4 Documents — all 5 PDFs = 20 Documents
    # -> list          → returns a new list of smaller Document objects (the chunks)
    #                    each chunk has the same .metadata as its parent Document
    #                    plus two new keys: chunk_index and total_chunks

    # ── Step 1: Create the splitter ───────────────────────────────────────────

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        # chunk_size is the MAXIMUM number of characters allowed in one chunk.
        # The splitter tries to stay at or below this number.
        # Default: 500 characters (set in .env as CHUNK_SIZE=500)
        # Too small (e.g. 200) → chunks lose context, precision drops
        # Too large  (e.g. 800) → chunks contain unrelated content, precision drops
        # 500 is the starting default — the optimal value will be confirmed
        # after running three chunk size experiments in Step 2.6
        # results of those experiments will be recorded in FINDINGS.md

        chunk_overlap=settings.CHUNK_OVERLAP,
        # chunk_overlap is how many characters from the END of chunk N are
        # re-read at the START of chunk N+1.
        # Default: 50 characters (set in .env as CHUNK_OVERLAP=50)
        #
        # Example with CHUNK_SIZE=500 and CHUNK_OVERLAP=50:
        #   Chunk 1: characters 0   → 500
        #   Chunk 2: characters 450 → 950   ← starts 50 chars before Chunk 1 ends
        #   Chunk 3: characters 900 → 1400
        #
        # Without overlap: a sentence that straddles the boundary between
        # chunk 1 and chunk 2 would be split in half — losing its meaning.
        # With overlap: that sentence appears in BOTH chunks — meaning preserved.

        length_function=len
        # length_function tells the splitter how to measure the size of a piece of text.
        # len is Python's built-in function that counts characters.
        # len("hello") → 5
        # The splitter calls len(text) to check whether a piece fits in chunk_size.
        # Alternative: tiktoken-based counter that counts tokens instead of characters.
        # We use len (characters) to keep it simple and avoid an extra dependency.
    )

    # ── Step 2: Split all documents into chunks ───────────────────────────────

    chunks = splitter.split_documents(documents)
    # split_documents() loops through every Document in the list and splits
    # each one's .page_content into smaller pieces.
    #
    # Input:  [Doc(page_content="2000 chars..."), Doc(page_content="1800 chars..."), ...]
    # Output: [Chunk("500 chars"), Chunk("500 chars"), Chunk("500 chars"), ...]
    #
    # Each output chunk is still a LangChain Document object with:
    #   .page_content → a smaller piece of the original page text
    #   .metadata     → COPIED from the parent Document
    #                   e.g. {"source": "/path/to/sales_playbook.pdf", "page": 0}
    #
    # The metadata copy is important — it tells us which file and page
    # each chunk came from. retriever.py uses this to show source citations.

    # ── Step 3: Add chunk index to metadata ───────────────────────────────────

    for i, chunk in enumerate(chunks):
        # enumerate() gives us both the position (i) and the item (chunk)
        # at each iteration of the loop.
        # i starts at 0 and counts up: 0, 1, 2, 3, ...

        chunk.metadata["chunk_index"] = i
        # chunk_index is the position of this chunk in the full list.
        # chunk_index=0  → first chunk overall
        # chunk_index=59 → 60th chunk overall  (actual count with current 5 PDFs)
        # Used for debugging — if a chunk retrieves badly, you can find it
        # by its index and inspect the surrounding chunks.

        chunk.metadata["total_chunks"] = len(chunks)
        # total_chunks tells us how many chunks were produced in total.
        # Every chunk gets the same total_chunks value.
        # Useful for knowing the scale of the collection:
        # "This chunk is 34 of 60 total."

    # ── Step 4: Log and return ────────────────────────────────────────────────

    log_event(log, "info", "chunks_created",
              count=len(chunks),
              chunk_size=settings.CHUNK_SIZE,
              overlap=settings.CHUNK_OVERLAP)
    # logs a structured summary line after all splitting is complete.
    # appears in logs as:
    #   event=chunks_created count=60 chunk_size=500 overlap=50
    # count      → total chunks produced across all 20 Document pages
    # chunk_size → the setting used (from .env) — useful for experiment tracking
    # overlap    → the overlap setting used — also useful for experiment tracking
    # Recording chunk_size and overlap in the log means you can look back at
    # any run and know exactly which settings produced which chunk count.

    return chunks
    # return the complete list of chunk Document objects to ingest.py
    # ingest.py will pass these chunks to embedder.py which converts
    # each chunk's .page_content into a 1536-dimensional vector