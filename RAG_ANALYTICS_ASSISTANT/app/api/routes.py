import uuid
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import main as pipeline
from app.store import vector_store
from app.utils import cost_tracker
from app.utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter()


class AskRequest(BaseModel):
    question: str = Field(min_length=5, max_length=500)
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    history: list = []
    # conversation history sent by the frontend from localStorage
    # enables follow-up questions to reference previous answers

class AskResponse(BaseModel):
    type: str
    answer: str = None
    sources: list = []
    session_id: str = None
    escalation_id: str = None
    message: str = None

class ConfirmRequest(BaseModel):
    escalation_id: str
    confirmed: bool

class ConfirmResponse(BaseModel):
    jira_key: str = None
    jira_url: str = None
    message: str

class HealthResponse(BaseModel):
    status: str
    chunk_count: int
    model: str


@router.post("/ask", response_model=AskResponse)
def ask(request: AskRequest):
    result = pipeline.run(request.question, request.session_id, request.history)
    return AskResponse(**result)


@router.post("/ask/stream")
def ask_stream(request: AskRequest):
    from app.generation import prompt as p, llm_client
    from app.retrieval import retriever
    from app.guardrails import input_guard
    from app.utils import session_store

    guard = input_guard.check(request.question)
    if not guard.is_safe:
        raise HTTPException(status_code=400, detail=guard.reason)

    chunks  = retriever.search(request.question)
    # use history from the request body (sent by frontend from localStorage)
    # this is more reliable than server-side session_store for streaming
    history = request.history or session_store.get_history(request.session_id)
    messages = p.build(request.question, chunks, history)

    def generate():
        full_answer = []
        for token in llm_client.stream(messages):
            if token:
                full_answer.append(token)
                yield token
        # save to session history AFTER streaming completes
        # this enables follow-up questions to reference this answer
        session_store.add_turn(
            request.session_id,
            request.question,
            ''.join(full_answer)
        )

    return StreamingResponse(generate(), media_type="text/plain")


@router.post("/ask/escalate")
def escalate(request: AskRequest):
    result = pipeline.run(request.question, request.session_id)
    if result["type"] != "escalation":
        return {"type": "answer", "message": "This question was answered directly."}
    return result


@router.post("/ask/confirm-escalation", response_model=ConfirmResponse)
def confirm_escalation(request: ConfirmRequest):
    escalation = pipeline.pending_escalations.get(request.escalation_id)
    if not escalation:
        raise HTTPException(status_code=404, detail="Escalation not found.")

    if not request.confirmed:
        del pipeline.pending_escalations[request.escalation_id]
        return ConfirmResponse(message="Okay, no problem. Feel free to ask another question.")

    from app.hitl import jira_client
    result = jira_client.create_story(
        question=escalation["question"],
        session_id=escalation["session_id"],
        confidence=escalation["confidence"],
        chunks=escalation["chunks"],
    )
    del pipeline.pending_escalations[request.escalation_id]
    return ConfirmResponse(
        jira_key=result["jira_key"],
        jira_url=result["jira_url"],
        message=f"Done. Jira story {result['jira_key']} has been created. "
                f"Your analytics team will investigate and respond there."
    )


@router.post("/ingest")
def ingest():
    import ingest as ingest_pipeline
    ingest_pipeline.main(reset=False)
    return {"message": "Ingestion complete.", "chunks": vector_store.count()}


@router.get("/health", response_model=HealthResponse)
def health():
    from app.config import settings
    return HealthResponse(
        status="ok",
        chunk_count=vector_store.count(),
        model=settings.MODEL
    )


@router.get("/stats")
def stats():
    from app.utils.db import get_connection
    conn = get_connection()
    row = conn.execute("""
        SELECT COUNT(*) as total_queries,
               COALESCE(SUM(total_cost_usd), 0) as total_cost,
               COALESCE(AVG(latency_ms), 0) as avg_latency
        FROM query_log
        WHERE date(timestamp) = date('now')
    """).fetchone()
    return {
        "queries_today": row["total_queries"],
        "cost_today_usd": round(row["total_cost"], 4),
        "avg_latency_ms": round(row["avg_latency"]),
    }