"""FastAPI Router for AI Copilot Intelligence (100% Cloud OpenRouter Processing)."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database.session import get_db
from packages.ai.openrouter_client import OpenRouterAuthError, OpenRouterClient

router = APIRouter(prefix="/api/v1/ai", tags=["Observatory AI Intelligence"])


class ChatMessage(BaseModel):
    role: str
    content: str


class AIQueryRequest(BaseModel):
    prompt: str = Field(..., min_length=2, max_length=1000)
    route_code: Optional[str] = None
    conversation_history: Optional[List[ChatMessage]] = None


PRE_MADE_PROMPTS = [
    {
        "id": "best_value_airline",
        "title": "Best Value Airline",
        "category": "Carrier Dynamics",
        "prompt": "Which airline is currently offering the lowest basic economy fares across the network, and how wide is the inter-airline price spread?",
    },
    {
        "id": "del_bom_surge",
        "title": "Why is DEL-BOM Surging?",
        "category": "Volatility Radar",
        "prompt": "Why are flight prices surging on the Delhi-Mumbai (DEL-BOM) corridor, and what is its current intraday volatility status and spread?",
    },
    {
        "id": "optimal_booking_window",
        "title": "Optimal Booking Window",
        "category": "Consumer Economics",
        "prompt": "When is the optimal advance booking horizon to buy domestic tickets, and how much can a consumer save at T+30 vs T+1?",
    },
    {
        "id": "mospi_executive_brief",
        "title": "MoSPI Executive Brief",
        "category": "Statistical Governance",
        "prompt": "Generate a concise executive briefing for the MoSPI Secretary summarizing national headline inflation, top surging routes, and airline price leadership.",
    },
    {
        "id": "fuel_hedging_impact",
        "title": "Jet Fuel (ATF) Impact",
        "category": "Macro Context",
        "prompt": "Did recent changes in IOCL Aviation Turbine Fuel (ATF) prices cause ticket prices to rise, and what is the non-causal hedging rule?",
    },
]


@router.get("/pre-made-prompts")
def get_pre_made_prompts():
    """Returns curated high-frequency prompt chips for the UI."""
    return {"prompts": PRE_MADE_PROMPTS}


@router.post("/query")
def execute_ai_query(
    request: AIQueryRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Executes a grounded statistical inquiry through OpenRouter cloud API.
    100% cloud processing: Strictly evaluates Observatory matrices and returns verifiable citations.
    """
    history = (
        [{"role": m.role, "content": m.content} for m in request.conversation_history]
        if request.conversation_history
        else None
    )

    try:
        result = OpenRouterClient.query(
            db=db,
            user_prompt=request.prompt,
            route_context=request.route_code,
            conversation_history=history,
        )
        return result
    except OpenRouterAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": "OPENROUTER_API_KEY_REQUIRED",
                "message": str(e),
                "setup_url": "https://openrouter.ai/keys",
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error_code": "OPENROUTER_GATEWAY_ERROR",
                "message": str(e),
            },
        )
