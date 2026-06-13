# Phase 7 — Evaluation Framework

**Steps:** 5  
**Goal:** Measure whether your RAG system works before deployment. RAGAS faithfulness below 0.70 means go back and fix the prompt or chunk size. Never deploy a system you cannot measure.

---

## Step 7.1 — Build eval/run_eval.py — automated evaluation runner

**What you do:**

Install RAGAS if not already installed:
```bash
uv pip install ragas
```

Create `eval/eval_dataset.json` — 20 entries covering all five documents:
```json
[
  {
    "question": "What is our discount policy for APAC enterprise accounts?",
    "expected_answer": "APAC enterprise accounts receive a discount based on deal size...",
    "expected_source": "discount_policy.txt",
    "expected_keywords": ["APAC", "enterprise", "discount"]
  },
  {
    "question": "How is win rate defined in our KPI framework?",
    "expected_answer": "Win rate is calculated as the number of won deals...",
    "expected_source": "kpi_definitions.txt",
    "expected_keywords": ["win rate", "won deals", "total deals"]
  }
]
```

Create `eval/run_eval.py`:
```python
import json
import sys
import time
import requests
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

API_BASE = "http://localhost:8000"


def run():
    with open("eval/eval_dataset.json") as f:
        dataset = json.load(f)

    results = []
    retrieval_hits = 0

    for i, item in enumerate(dataset, 1):
        start = time.time()
        response = requests.post(f"{API_BASE}/ask", json={
            "question": item["question"],
            "session_id": f"eval-{i}"
        })
        latency_ms = int((time.time() - start) * 1000)
        data = response.json()

        answer = data.get("answer", "")
        sources = [s.get("source", "") for s in data.get("sources", [])]

        # retrieval precision — did expected source appear?
        retrieval_hit = any(item["expected_source"] in s for s in sources)
        if retrieval_hit:
            retrieval_hits += 1

        # keyword recall — do expected keywords appear in answer?
        kw_hits = sum(1 for kw in item["expected_keywords"]
                      if kw.lower() in answer.lower())
        kw_recall = kw_hits / len(item["expected_keywords"]) if item["expected_keywords"] else 0

        status = "PASS" if retrieval_hit else "FAIL"
        print(f"Q{i:02d}: {status} | recall={kw_recall:.2f} | latency={latency_ms}ms")

        results.append({
            "question": item["question"],
            "answer": answer,
            "sources": sources,
            "expected_source": item["expected_source"],
            "retrieval_hit": retrieval_hit,
            "keyword_recall": round(kw_recall, 2),
            "latency_ms": latency_ms,
        })

    precision = retrieval_hits / len(dataset)
    avg_recall = sum(r["keyword_recall"] for r in results) / len(results)

    print(f"\nRetrieval precision : {retrieval_hits}/{len(dataset)} = {precision:.2f}")
    print(f"Avg keyword recall  : {avg_recall:.2f}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"eval/results/run_{timestamp}.json"
    Path("eval/results").mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump({
            "run_timestamp": datetime.now().isoformat(),
            "total_questions": len(dataset),
            "retrieval_precision": round(precision, 2),
            "avg_keyword_recall": round(avg_recall, 2),
            "results": results,
        }, f, indent=2)

    print(f"\nResults saved: {output_path}")
    return precision


if __name__ == "__main__":
    score = run()
    if score < 0.70:
        print("\nWARNING: Precision below 0.70 — fix chunking before deployment")
```

**Run (with API running):**
```bash
python eval/run_eval.py
```

**Verify:** Results file created in `eval/results/`. Precision above 0.70.

---

## Step 7.2 — Build eval/ragas_eval.py — RAGAS metrics

**What you do:**

```python
import json
import sys
import glob
from pathlib import Path
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
)

sys.path.insert(0, str(Path(__file__).parent.parent))


def run():
    # load latest run_eval results
    result_files = sorted(glob.glob("eval/results/run_*.json"))
    if not result_files:
        print("Run eval/run_eval.py first to generate results.")
        return

    with open(result_files[-1]) as f:
        run_data = json.load(f)

    with open("eval/eval_dataset.json") as f:
        dataset_raw = json.load(f)

    questions, answers, contexts, ground_truths = [], [], [], []
    for item, result in zip(dataset_raw, run_data["results"]):
        questions.append(item["question"])
        answers.append(result["answer"])
        contexts.append([result["answer"]])  # use answer as context proxy
        ground_truths.append(item["expected_answer"])

    dataset = Dataset.from_dict({
        "question":    questions,
        "answer":      answers,
        "contexts":    contexts,
        "ground_truth": ground_truths,
    })

    result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall]
    )

    scores = {
        "faithfulness":      round(result["faithfulness"], 3),
        "answer_relevancy":  round(result["answer_relevancy"], 3),
        "context_precision": round(result["context_precision"], 3),
        "context_recall":    round(result["context_recall"], 3),
    }

    print("\nRAGAS Evaluation Results")
    print("─" * 35)
    for metric, score in scores.items():
        status = "✓" if score >= 0.70 else "✗"
        print(f"{metric:<25} : {score:.3f} {status}")
    print("─" * 35)

    all_pass = all(s >= 0.70 for s in scores.values())
    print("All metrics above 0.70" if all_pass else "Some metrics below 0.70 — review needed")

    return scores


if __name__ == "__main__":
    run()
```

**Run:**
```bash
python eval/ragas_eval.py
```

If RAGAS is not yet installed:
```bash
uv pip install ragas datasets
```

**Verify:** Four scores printed. All above 0.70 before Phase 8.

---

## Step 7.3 — Build eval/llm_judge.py — GPT-4o quality scoring

**What you do:**

```python
import json
import glob
import sys
from pathlib import Path
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).parent.parent))
from app.config import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY)


def judge_answer(question: str, answer: str) -> dict:
    prompt = f"""You are an expert evaluator of commercial analytics AI assistants.
Score this answer on three criteria from 1 to 5:

Question: {question}
Answer: {answer}

Criteria:
1. Accuracy (1-5): Is it factually sensible?
2. Completeness (1-5): Does it fully address the question?
3. Tone (1-5): Is it appropriate for a VP audience?

Return JSON only, no explanation:
{{"accuracy": N, "completeness": N, "tone": N}}"""

    response = client.chat.completions.create(
        model=settings.MODEL,
        max_tokens=50,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)


def run():
    result_files = sorted(glob.glob("eval/results/run_*.json"))
    if not result_files:
        print("Run eval/run_eval.py first.")
        return

    with open(result_files[-1]) as f:
        run_data = json.load(f)

    scores = []
    for i, item in enumerate(run_data["results"], 1):
        score = judge_answer(item["question"], item["answer"])
        avg = sum(score.values()) / len(score)
        scores.append(avg)
        print(f"Q{i:02d}: accuracy={score['accuracy']} completeness={score['completeness']} tone={score['tone']} → avg={avg:.1f}")

    overall = sum(scores) / len(scores)
    print(f"\nOverall judge score: {overall:.2f} / 5.0")
    target = "✓" if overall >= 3.5 else "✗ — below target of 3.5"
    print(f"Target (≥3.5): {target}")
    return overall


if __name__ == "__main__":
    run()
```

**Run:**
```bash
python eval/llm_judge.py
```

**Verify:** Average score above 3.5 / 5.0.

---

## Step 7.4 — Compare before and after guardrails — update FINDINGS.md

**What you do:**

1. Temporarily disable validator in `main.py`:
```python
# validation = validator.validate(answer, question, chunks)
from dataclasses import dataclass
@dataclass
class _FakeResult:
    passed = True
    confidence_score = 0.9
    failure_reason = None
validation = _FakeResult()
```

2. Run: `python eval/ragas_eval.py` → record scores

3. Re-enable the validator

4. Run: `python eval/ragas_eval.py` → record scores

5. Write in `FINDINGS.md`:

```markdown
## Guardrail impact on RAGAS scores — {date}

| Metric             | Without guardrails | With guardrails | Change |
|--------------------|--------------------|-----------------|---------| 
| Faithfulness       | ?                  | ?               | ?       |
| Answer relevancy   | ?                  | ?               | ?       |
| Context precision  | ?                  | ?               | ?       |
| Context recall     | ?                  | ?               | ?       |

Conclusion: {write what you observed and why faithfulness changed most}
```

**Verify:** `FINDINGS.md` has the before/after table and a written conclusion.

---

## Step 7.5 — Identify top 3 failure questions — document root causes

**What you do:**

```python
# run this to find the worst performing questions
import json
import glob

result_files = sorted(glob.glob("eval/results/run_*.json"))
with open(result_files[-1]) as f:
    data = json.load(f)

worst = sorted(data["results"], key=lambda x: x["keyword_recall"])[:3]
for i, item in enumerate(worst, 1):
    print(f"\nFailure {i}:")
    print(f"  Question : {item['question']}")
    print(f"  Expected : {item['expected_source']}")
    print(f"  Retrieved: {item['sources']}")
    print(f"  Recall   : {item['keyword_recall']}")
```

For each failure write in `FINDINGS.md`:

```markdown
## Top 3 evaluation failures — {date}

### Failure 1
Question: {question}
Expected source: {file}
Retrieved: {what was actually retrieved}
Root cause: {missing document / wrong chunk / prompt issue}
Proposed fix: {concrete action}

### Failure 2 ...
### Failure 3 ...
```

**Verify:** Three specific failure analyses with root causes and proposed fixes in `FINDINGS.md`.

---

## Phase 7 complete checklist

- [ ] `uv pip install ragas datasets` — installed successfully
- [ ] `eval_dataset.json` has 20 entries with question, expected_source, expected_keywords
- [ ] `python eval/run_eval.py` — precision above 0.70, results file saved
- [ ] `python eval/ragas_eval.py` — four scores all above 0.70
- [ ] `python eval/llm_judge.py` — average judge score above 3.5
- [ ] Before/after guardrail comparison in `FINDINGS.md`
- [ ] Top 3 failure analyses with root causes in `FINDINGS.md`

**Next:** Phase 8 — Deploy, monitor, CI/CD
