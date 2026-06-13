import argparse
# argparse is Python's built-in library for parsing command-line arguments.
# It lets us accept flags like --reset when running:
#   python ingest.py --reset

import sys
# sys is Python's built-in library for system-level operations.
# sys.exit() is used to stop the program early if something goes wrong.

from app.config import settings
# settings.validate() checks all required keys and folders exist
# before the pipeline runs — catches problems early with clear messages.
# This is always the first call in any entry point.

from app.ingestion import loader, chunker
# loader  → reads all PDFs from docs/ and returns Document objects
# chunker → splits Document objects into smaller overlapping chunks

from app.store import vector_store
# vector_store → connects to ChromaDB to store, count, and reset chunks
# lives in app/store/ not app/ingestion/ because retriever.py also uses it

from app.utils.logger import get_logger, log_event
# get_logger  → returns a named logger for this module
# log_event   → writes a structured key=value log line

log = get_logger(__name__)
# __name__ is "__main__" when this file is run directly
# or "ingest" when it is imported by another module (e.g. api_server.py)


def main(reset: bool = False) -> None:
    # reset: bool = False  → if True, wipe ChromaDB before ingesting
    #                         default is False — normal run just adds documents
    # -> None              → this function returns nothing
    #
    # main() is separated from the if __name__ == "__main__" block so that
    # api_server.py can call ingest.main(reset=False) directly via the
    # POST /ingest endpoint — without spawning a subprocess.

    # ── Step 1: Validate environment ──────────────────────────────────────────
    settings.validate()
    # checks all of the following before touching any files or APIs:
    #   - OPENAI_API_KEY is set
    #   - JIRA_API_TOKEN is set
    #   - docs/ folder exists
    #   - docs/ folder is not empty
    #   - chroma_db/ exists (creates it if not)
    # if any check fails, raises a clear error and stops here
    # NOTE: validate() checks chroma_db/ is not empty — but on a fresh run
    # before ingest.py has ever been run, chroma_db/ WILL be empty.
    # This is the one case where validate() should be called AFTER reset()
    # or skipped — api_server.py handles this by calling validate() only
    # after ingestion is confirmed complete.

    # ── Step 2: Reset ChromaDB if --reset flag was passed ─────────────────────
    if reset:
        log.warning("--reset flag set. Clearing ChromaDB collection.")
        # log at WARNING because deleting all vectors is a destructive operation
        # WARNING means "this worked but pay attention — something significant happened"
        vector_store.reset()
        # permanently deletes the "analytics_docs" collection from ChromaDB
        # the next add_documents() call will create a fresh empty collection

    log.info("Starting ingestion pipeline...")
    # INFO level — normal operation, nothing unexpected

    # ── Step 3: Load documents ─────────────────────────────────────────────────
    documents = loader.load()
    # reads every .pdf file from docs/ and returns a flat list of
    # LangChain Document objects — one per page
    # our 5 PDFs with 20 pages total → 20 Document objects

    print(f"Documents loaded : {len(documents)}")
    # print() goes to the terminal for the developer running the script
    # log lines go to logs/rag_pipeline.log for permanent record
    # both are useful — print for immediate feedback, log for audit trail

    # ── Step 4: Split into chunks ──────────────────────────────────────────────
    chunks = chunker.split(documents)
    # splits each Document's page_content into smaller overlapping pieces
    # using CHUNK_SIZE and CHUNK_OVERLAP from .env
    # 20 pages at ~2000 chars each with CHUNK_SIZE=500 → approximately 60 chunks

    print(f"Chunks created   : {len(chunks)}")
    # shows how many chunks were produced — useful for the chunk size experiment
    # in Step 2.6 you will change CHUNK_SIZE and compare this number

    # ── Step 5: Store in ChromaDB ──────────────────────────────────────────────
    vector_store.add_documents(chunks)
    # sends all 60 chunks to ChromaDB
    # ChromaDB internally calls OpenAI embeddings API to convert each chunk
    # to a 1536-dimensional vector and stores both text + vector on disk
    # this is the only step that costs real money (approximately $0.00015)

    total = vector_store.count()
    # count() returns the total number of chunks now stored in ChromaDB
    # on a fresh run this equals len(chunks)
    # after multiple runs without --reset this would be higher (duplicates)
    # always use --reset when re-ingesting to avoid duplicates

    print(f"Vectors stored   : {len(chunks)}")
    # how many chunks were added in this run

    print(f"Collection total : {total}")
    # total chunks in ChromaDB after this run
    # on a fresh run: same as "Vectors stored"
    # without --reset after a previous run: higher (contains old chunks too)

    # ── Step 6: Log completion summary ────────────────────────────────────────
    log_event(log, "info", "ingestion_complete",
              documents=len(documents),
              chunks=len(chunks),
              total_in_store=total)
    # writes a structured summary to the log file:
    #   event=ingestion_complete documents=20 chunks=60 total_in_store=60
    # this is the permanent record of each ingestion run
    # useful for comparing runs during the chunk size experiment in Step 2.6


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # this block runs ONLY when the file is executed directly:
    #   python ingest.py
    #   python ingest.py --reset
    #
    # it does NOT run when ingest.py is imported by another module
    # (e.g. when api_server.py calls ingest.main())
    # this is a standard Python pattern for entry point scripts

    parser = argparse.ArgumentParser(
        description="Ingest PDF documents into ChromaDB for the RAG pipeline."
        # description appears when someone runs: python ingest.py --help
    )

    parser.add_argument(
        "--reset",
        action="store_true",
        # action="store_true" means:
        #   python ingest.py          → args.reset = False  (default)
        #   python ingest.py --reset  → args.reset = True
        # no value is needed after --reset — its presence alone sets it to True
        help="Clear the ChromaDB collection before re-ingesting. "
             "Use this when changing CHUNK_SIZE or when adding/removing documents."
    )

    args = parser.parse_args()
    # parse_args() reads sys.argv (the command-line arguments)
    # and stores the results in args
    # args.reset will be True or False depending on whether --reset was passed

    main(reset=args.reset)
    # call main() with the parsed flag
    # if --reset was passed: wipes ChromaDB then re-ingests
    # if --reset was not passed: just ingests (adds to existing collection)