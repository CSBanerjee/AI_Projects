from langchain_openai import OpenAIEmbeddings
# OpenAIEmbeddings is a LangChain wrapper around the OpenAI Embeddings API.
# It handles authentication, batching, and retry logic automatically.
# When you call .embed_documents() it sends text to OpenAI and receives
# vectors (lists of numbers) back.
# This is the FIRST step in the pipeline that makes a real API call —
# loader.py and chunker.py work entirely locally with no internet needed.

from app.config import settings
# settings.EMBEDDING_MODEL → which OpenAI model converts text to vectors
#                            default: "text-embedding-3-small"
# settings.OPENAI_API_KEY  → authenticates every request to OpenAI
#                            without this, every embed() call fails with 401

from app.utils.logger import get_logger, log_event
# get_logger  → returns a named logger for this module (app.ingestion.embedder)
# log_event   → writes a structured key=value log line

log = get_logger(__name__)
# __name__ is automatically "app.ingestion.embedder" inside this file
# every log line from this module shows that name as the source


def get_embedding_model() -> OpenAIEmbeddings:
    # -> OpenAIEmbeddings means this function returns an OpenAIEmbeddings object
    #
    # This function is separated from embed() for two reasons:
    #
    # Reason 1 — Reusability:
    #   vector_store.py also needs the embedding model to search ChromaDB.
    #   By separating it here, both embedder.py and vector_store.py call
    #   get_embedding_model() instead of each constructing it independently.
    #   The model configuration lives in one place — this function.
    #
    # Reason 2 — Testability:
    #   Tests can mock get_embedding_model() to return a fake model without
    #   making real API calls or needing a real OPENAI_API_KEY.

    return OpenAIEmbeddings(
        model=settings.EMBEDDING_MODEL,
        # settings.EMBEDDING_MODEL → "text-embedding-3-small" from .env
        # This model converts text into 1536-dimensional vectors.
        # It must be the SAME model used everywhere in the project:
        #   - here in embedder.py  → when storing chunks during ingestion
        #   - in vector_store.py   → when searching ChromaDB at query time
        # Using different models for storage and search produces incompatible
        # vectors — retrieval would return garbage results.

        openai_api_key=settings.OPENAI_API_KEY
        # The secret key from .env that authenticates requests to OpenAI.
        # Without this, every API call returns HTTP 401 Unauthorized.
        # validate() in settings.py checks this key exists at startup
        # so by the time embed() is called, the key is guaranteed to be set.
    )


def embed(texts: list[str]) -> list[list[float]]:
    # texts: list[str]        → a list of plain text strings to embed
    #                           e.g. ["APAC discount is 20%", "Win rate target is 28%"]
    #                           in practice ingest.py passes the page_content
    #                           of every chunk — 60 strings for our 5 PDFs
    #
    # -> list[list[float]]    → returns a list of vectors
    #                           each vector is a list of 1536 floats
    #                           one vector per input text string
    #
    # Example:
    #   Input:  ["APAC discount is 20%", "Win rate is 28%"]
    #   Output: [[0.023, -0.847, 0.412, ...],   ← 1536 numbers for text 1
    #            [0.019, -0.831, 0.408, ...]]    ← 1536 numbers for text 2

    # create the embedding model using the function above
    # we call get_embedding_model() here rather than at module level so that
    # the model is only created when embed() is actually called — not at import time
    # this means importing embedder.py does not immediately trigger an API connection
    model = get_embedding_model()

    # model.embed_documents() sends all texts to OpenAI in one batched request
    # and returns a list of vectors — one per input text.
    #
    # "documents" in the method name means "texts to store" as opposed to
    # .embed_query() which is used for search queries at retrieval time.
    # Both methods use the same underlying model but signal intent differently.
    #
    # COST NOTE: this call costs real money.
    # text-embedding-3-small costs $0.02 per 1 million tokens.
    # 60 chunks at ~500 chars each ≈ 60 * 125 tokens ≈ 7,500 tokens ≈ $0.00015
    # The cost for this project is essentially zero but matters at scale.
    vectors = model.embed_documents(texts)

    # log a structured summary of the embedding operation.
    # appears in logs as:
    #   event=embeddings_created count=60 model=text-embedding-3-small dimensions=1536
    #
    # count      → how many texts were embedded (should match number of chunks)
    # model      → which OpenAI model was used — important for experiment tracking
    # dimensions → how many numbers are in each vector (always 1536 for this model)
    #
    # "if vectors else 0" handles the edge case where texts was an empty list —
    # in that case vectors is also empty and vectors[0] would raise an IndexError
    log_event(log, "info", "embeddings_created",
              count=len(vectors),
              model=settings.EMBEDDING_MODEL,
              dimensions=len(vectors[0]) if vectors else 0)

    # return the list of vectors to whoever called embed()
    # in the ingestion pipeline this is vector_store.add_documents()
    # which stores each vector alongside its chunk text in ChromaDB
    return vectors