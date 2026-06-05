from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.dependencies import verify_api_key
from agents.query import QueryAgent

router = APIRouter(prefix="/query", tags=["query"])


class QueryRequest(BaseModel):
    q: str


@router.post("", dependencies=[Depends(verify_api_key)])
async def query(body: QueryRequest):
    if not body.q.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    agent = QueryAgent()
    result = await agent.run(body.q)
    return {
        "answer": result.answer,
        "iterations": result.iterations,
        "sources_used": result.sources,
    }
