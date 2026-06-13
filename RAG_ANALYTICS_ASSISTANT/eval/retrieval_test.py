"""
eval/retrieval_test.py — Phase 3 Step 3.3

Measures retrieval precision — how often the retriever finds the correct
source document for each question in eval_dataset.json.

Precision = number of questions where expected_source was retrieved
            ─────────────────────────────────────────────────────────
            total number of questions

Target: precision above 0.70 before moving to Phase 4.
If precision is below 0.70, adjust CHUNK_SIZE in .env and re-run ingest.py.

Run from the project root:
    python eval/retrieval_test.py

Requires:
    - ingest.py must have been run first (ChromaDB must not be empty)
    - OPENAI_API_KEY must be set in .env (retriever calls OpenAI to embed the question)
"""

import json
# json is Python's built-in library for reading JSON files
# we use it to load eval_dataset.json

import sys
# sys.path.insert() adds a folder to Python's import search path
# needed so we can import from app/ when running this script directly

from pathlib import Path
# Path helps us build the correct file path to eval_dataset.json
# regardless of which directory the script is run from

sys.path.insert(0, str(Path(__file__).parent.parent))
# Path(__file__)         → full path to this file: eval/retrieval_test.py
# .parent                → the eval/ folder
# .parent.parent         → the project root: rag_analytics_assistant/
# sys.path.insert(0, ...) → adds the project root to Python's import path
# this lets us write "from app.retrieval import retriever" from inside eval/

from app.retrieval import retriever
# retriever.search() is the function we are testing
# it takes a question and returns matching chunks from ChromaDB


def run() -> float:
    # -> float means this function returns the precision score as a decimal
    # e.g. 0.78 means 78% precision — 15.6 out of 20 questions retrieved correctly

    # ── Load the evaluation dataset ───────────────────────────────────────────
    with open("eval/eval_dataset.json") as f:
        dataset = json.load(f)
    # loads the 20 questions from eval_dataset.json into a list of dictionaries
    # each dictionary has: question, expected_answer, expected_source, expected_keywords

    hits = 0
    # tracks how many questions the retriever answered with the correct source document
    # starts at 0 and increments each time the expected source was found

    # ── Run each question through the retriever ───────────────────────────────
    for i, item in enumerate(dataset, 1):
        # enumerate(dataset, 1) gives us:
        #   i    → question number starting from 1 (not 0) for readable output
        #   item → the dictionary for this question

        docs = retriever.search(item["question"])
        # retriever.search() converts the question to a vector, searches ChromaDB,
        # and returns the top matching chunks as a list of Document objects
        # each Document has .metadata["source"] — the PDF file it came from

        sources = [d.metadata.get("source", "") for d in docs]
        # extract the source file path from each returned Document's metadata
        # e.g. ["/path/to/discount_policy.pdf", "/path/to/kpi_definitions.pdf"]
        # .get("source", "") uses "" as fallback if "source" key is missing

        hit = any(item["expected_source"] in s for s in sources)
        # check whether the expected source file appears in any of the returned sources
        # item["expected_source"] is e.g. "discount_policy.pdf"
        # "discount_policy.pdf" in "/path/to/discount_policy.pdf" → True
        # any() returns True if at least one source matches — we do not need all to match

        if hit:
            hits += 1
            # increment hits counter if the correct source was found

        status = "PASS" if hit else "FAIL"
        # PASS → the expected source document was among the retrieved chunks
        # FAIL → the expected source was not found — wrong chunks were returned

        print(f"Q{i:02d}: {status} — expected: {item['expected_source']}")
        # Q01: PASS — expected: discount_policy.pdf
        # Q02: FAIL — expected: kpi_definitions.pdf
        # :02d formats the number with leading zero so Q1 → Q01, Q10 stays Q10

    # ── Calculate and print precision ─────────────────────────────────────────
    precision = hits / len(dataset)
    # precision = correct retrievals / total questions
    # e.g. 16 hits / 20 questions = 0.80 precision

    print(f"\nRetrieval precision: {hits}/{len(dataset)} = {precision:.2f}")
    # prints: Retrieval precision: 16/20 = 0.80
    # :.2f formats to 2 decimal places

    # ── Warn if below threshold ───────────────────────────────────────────────
    if precision < 0.70:
        print("\nWARNING: Precision below 0.70")
        print("Action: Change CHUNK_SIZE in .env, run python ingest.py --reset, then retry")
        print("Try: CHUNK_SIZE=200, CHUNK_SIZE=500, CHUNK_SIZE=800")
        print("Record results in FINDINGS.md under the chunk size experiment section")
    else:
        print(f"\nPrecision above 0.70 — retrieval is working well enough for Phase 4")

    return precision
    # return the precision score so the chunk size experiment can compare
    # the three runs and record which chunk size performed best


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # only runs when this file is executed directly:
    #   python eval/retrieval_test.py
    # does NOT run when this file is imported by another script
    score = run()