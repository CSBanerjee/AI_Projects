from app.store import vector_store
# vector_store gives us access to ChromaDB where all 60 chunks are stored
# we use vector_store.get() to get a live connection to the collection
# vector_store lives in app/store/ not app/retrieval/ because
# both ingestion (ingest.py) and retrieval (retriever.py) use it

from app.config import settings
# settings.TOP_K_RESULTS       → how many chunks to retrieve per question (default 3)
# settings.SIMILARITY_THRESHOLD → minimum score a chunk must reach (default 0.7)
#                                  chunks scoring below this are discarded

from app.utils.logger import get_logger, log_event
# get_logger  → returns a named logger for this module (app.retrieval.retriever)
# log_event   → writes a structured key=value log line

log = get_logger(__name__)
# __name__ is "app.retrieval.retriever" inside this file
# every log line from this module shows that name as the source


def search(question: str, source_document: str = None) -> list:
    # question: str              → the user's question as plain text
    #                              e.g. "What is our APAC discount policy?"
    # source_document: str = None → optional filter — if provided, only chunks
    #                              from this specific PDF are searched
    #                              e.g. "discount_policy.pdf"
    #                              default is None — search across all documents
    # -> list                    → returns a list of Document objects (the matching chunks)
    #                              each Document has .page_content and .metadata
    #                              returns [] (empty list) if nothing relevant found

    vs = vector_store.get()
    # get() creates a live connection to the ChromaDB "analytics_docs" collection
    # vs is our handle to everything stored in ChromaDB
    # we call get() here rather than at module level so the connection is only
    # made when search() is actually called — not at import time

    search_kwargs = {"k": settings.TOP_K_RESULTS}
    # search_kwargs is a dictionary of options we pass to the retriever
    # "k" tells ChromaDB how many chunks to return — default 3
    # so for every question, ChromaDB finds the 3 most similar chunks

    if source_document:
        search_kwargs["filter"] = {"source": source_document}
        # if a source_document was provided, add a metadata filter
        # this tells ChromaDB to only search chunks whose "source" metadata
        # matches the given filename — e.g. "discount_policy.pdf"
        # useful when you know the answer must come from a specific document

    retriever = vs.as_retriever(
        # as_retriever() converts the Chroma vector store into a LangChain retriever
        # a retriever is an object that takes a question and returns matching chunks
        search_type="similarity",
        # "similarity" means find chunks whose vectors are closest in direction
        # to the question vector — pure semantic similarity search
        # alternative: "mmr" (maximum marginal relevance) — reduces redundancy
        search_kwargs=search_kwargs
        # passes our k=3 and optional source filter to the retriever
    )

    results = retriever.invoke(question)
    # retriever.invoke() does the actual search:
    #   1. converts the question to a 1536-dimensional vector using OpenAI embeddings
    #   2. searches ChromaDB for the k most similar chunk vectors
    #   3. returns the matching chunks as a list of Document objects
    # results is a list of up to 3 Document objects

    if not results:
        # if ChromaDB found no matching chunks at all (empty list)
        # this can happen if ChromaDB is empty (ingest.py was never run)
        # or if the question is completely unrelated to any stored content
        log_event(log, "warning", "no_relevant_context",
                  question=question[:50])
        # log a warning so the developer knows a question returned nothing
        # question[:50] takes only the first 50 characters to keep the log line short
        return []
        # return an empty list — the pipeline will handle this as a low-confidence result

    # ── Similarity threshold check ────────────────────────────────────────────
    # retriever.invoke() returned results but we do not yet know how similar
    # they actually are. A result could be returned even if it is a poor match.
    # We need the actual similarity scores to apply our threshold filter.

    results_with_scores = vs.similarity_search_with_score(
        question, k=settings.TOP_K_RESULTS
        # similarity_search_with_score() does the same search as retriever.invoke()
        # but ALSO returns the distance score for each result
        # returns a list of tuples: [(Document, score), (Document, score), ...]
        # the score is a DISTANCE — lower distance = more similar
        # ChromaDB uses L2 distance: 0.0 = identical, 2.0 = completely different
    )

    best_score = 1 - results_with_scores[0][1]
    # results_with_scores[0]    → the first (best) result tuple: (Document, score)
    # results_with_scores[0][1] → the distance score of the best result
    # 1 - distance              → converts distance to similarity
    #   distance = 0.0 → similarity = 1.0 (perfect match)
    #   distance = 0.3 → similarity = 0.7 (good match)
    #   distance = 1.0 → similarity = 0.0 (no match)
    # we check the best result — if even the best chunk is below threshold,
    # all chunks are below threshold so we return nothing

    if best_score < settings.SIMILARITY_THRESHOLD:
        # if the best matching chunk scored below SIMILARITY_THRESHOLD (default 0.7)
        # the retrieved chunks are not relevant enough to use as context
        # returning them would cause the LLM to hallucinate or give wrong answers
        log_event(log, "warning", "below_threshold",
                  best_score=round(best_score, 3),
                  threshold=settings.SIMILARITY_THRESHOLD)
        # log the actual score and threshold so you can tune SIMILARITY_THRESHOLD
        # in .env if needed — e.g. lower it to 0.6 if too many questions escalate
        return []
        # return empty list — this triggers the escalation path in main.py

    # ── Attach similarity scores to metadata ──────────────────────────────────
    for doc, score in results_with_scores:
        # loop through every (Document, distance_score) pair
        doc.metadata["similarity_score"] = round(1 - score, 3)
        # convert distance to similarity and add it to the chunk's metadata
        # round() to 3 decimal places keeps it readable: 0.847 not 0.8472981...
        # the API uses this score to show "Match: 85%" in the frontend source cards

    log_event(log, "info", "retrieval_done",
              question=question[:50],
              chunks_found=len(results_with_scores),
              best_score=round(best_score, 3))
    # log a structured summary of this retrieval:
    #   question    → first 50 chars of the question
    #   chunks_found → how many chunks were returned (up to TOP_K_RESULTS)
    #   best_score   → similarity score of the best matching chunk
    # appears in logs as:
    #   event=retrieval_done question=What is our APAC discount... chunks_found=3 best_score=0.847

    return [doc for doc, _ in results_with_scores]
    # return only the Document objects — not the score tuples
    # [doc for doc, _ in results_with_scores] is a list comprehension:
    #   it loops through [(Doc, score), (Doc, score), ...]
    #   takes only the Doc from each tuple (ignores the score with _)
    #   the score is already saved in doc.metadata["similarity_score"] above
    # the returned list goes to prompt.py which injects these chunks into
    # the LLM prompt as context for generating the answer