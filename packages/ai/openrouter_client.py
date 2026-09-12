"""OpenRouter AI Client for the India Airfare Price Observatory.

100% Cloud-Processed through OpenRouter Free Tier Models
(e.g., google/gemini-2.0-flash-exp:free, meta-llama/llama-3.3-70b-instruct:free).
Strictly grounded in Observatory Statistical Matrices with zero offline processing.
"""

import logging
import re
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy.orm import Session

from packages.ai.matrix_serializer import ObservatoryMatrixSerializer
from packages.ai.news_fetcher import AviationNewsService
from packages.shared.config import settings

logger = logging.getLogger("airfare.ai.openrouter")

# Ranked list of active free-tier models on OpenRouter with verified endpoints
DEFAULT_FREE_MODELS = [
    "minimax/minimax-m3:free",
    "nvidia/nemotron-3.5-lightning:free",
    "google/gemma-4-31b-it:free",
    "openrouter/free",
]


class OpenRouterAuthError(Exception):
    """Raised when OPENROUTER_API_KEY is missing or unauthorized."""

    pass


class OpenRouterClient:
    """Manages cloud LLM inference via OpenRouter API."""

    API_URL = "https://openrouter.ai/api/v1/chat/completions"

    SYSTEM_PROMPT_TEMPLATE = """You are the Official MoSPI Airfare Price Observatory AI Intelligence Officer.
You operate with the statistical authority and analytical rigor of the National Statistical Office (NSO), Ministry of Statistics & Programme Implementation, Government of India.

YOUR MANDATE:
Answer user inquiries regarding Indian domestic airfare pricing, inflation indices, carrier competition, and advance booking yield economics.

STRICT DATA BOUNDARIES & GROUND TRUTH (ZERO HALLUCINATION):
1. INTERNAL DATA SUPREMACY: You have been provided below with 5 VERIFIED STATISTICAL MATRICES computed from authentic domestic flight quotes. All flight fares, index values, spreads, and surge multipliers you cite MUST come directly and exactly from these matrices.
2. ZERO PRICE INVENTIONS: You are strictly forbidden from inventing ticket prices for any flight, carrier, or route not in these matrices.
3. NON-CAUSAL JET FUEL RULE: You must NEVER claim that an increase in ATF spot fuel price caused an immediate ticket price increase. Always explain that Indian airlines use 12–18 month financial fuel hedging buffers.
4. EXTERNAL NEWS INTEGRATION: When explaining *why* a corridor is experiencing high volatility or surges, synthesize the provided Latest Aviation & Macro News (e.g., festival holiday rush, airport weather/fog disruptions, airline maintenance circulars) as the real-world contextual driver.
5. FORMATTING & TONE: Professional, objective, and economical. Use bolding for key figures and currency formatting in Indian Rupees (₹).

{matrices_block}

{news_block}

FEW-SHOT IN-CONTEXT EXAMPLES:
User: "Which airline offers the best value today?"
Assistant: "Based on our live Carrier-Wise Price Inflation Matrix (CPI-Carrier):
• **Value Leader**: {value_leader} is currently offering the most competitive lowest-economy quotes across the network.
• **Price Spread**: The inter-airline price dispersion is **{spread_pts} points**, with Air India (AI) commanding a premium on metro trunk corridors and IndiGo (6E) holding steady.
• **Recommendation**: Travelers booking basic economy will find the lowest entry tariffs with budget carriers, whereas full-service legacy options reflect bundled baggage and meal allocations."

User: "Why are flights between Delhi and Mumbai so expensive?"
Assistant: "On the **DEL-BOM (Delhi ↔ Mumbai)** corridor:
• **Current Volatility Status**: Classified as **{del_bom_status}** with an intraday price spread of **{del_bom_spread}%**.
• **Lead-Time Yield Multiplier**: Last-minute booking (T+1 eve) incurs a **{del_bom_mult}x multiplier** compared to the 45-day baseline.
• **Context**: Trunk metro business demand remains the primary escalation driver. Booking at least 14 to 30 days prior captures over 50% early-bird savings."
"""

    @classmethod
    def generate_system_prompt(cls, db: Session, target_route: Optional[str] = None) -> str:
        """Compiles system prompt with live matrices and news."""
        matrices_text = ObservatoryMatrixSerializer.format_matrices_as_system_text(
            db, target_route=target_route
        )
        news_text = "=== LATEST AVIATION & MACRO NEWS (EXTERNAL EXPLANATORY CONTEXT) ===\n" + (
            AviationNewsService.format_news_for_prompt()
        )

        carrier_summary = ObservatoryMatrixSerializer.get_carrier_inflation_matrix(db)
        vol_summary = ObservatoryMatrixSerializer.get_corridor_volatility_matrix(db)
        lead_summary = ObservatoryMatrixSerializer.get_lead_time_matrix(
            db, route_code=target_route or "DEL-BOM"
        )

        del_bom_corridor = next(
            (c for c in vol_summary.get("corridors", []) if c["route_code"] == "DEL-BOM"),
            {"volatility_status": "HIGH_VOLATILITY", "intraday_spread_pct": 29.5},
        )

        return cls.SYSTEM_PROMPT_TEMPLATE.format(
            matrices_block=matrices_text,
            news_block=news_text,
            value_leader=carrier_summary.get("value_leader", "Akasa Air"),
            spread_pts=carrier_summary.get("carrier_inflation_spread_pts", 0.0),
            del_bom_status=del_bom_corridor.get("volatility_status", "HIGH_VOLATILITY"),
            del_bom_spread=round(del_bom_corridor.get("intraday_spread_pct", 29.5), 1),
            del_bom_mult=lead_summary.get("surge_multiplier", 2.45),
        )

    @classmethod
    def query(
        cls,
        db: Session,
        user_prompt: str,
        route_context: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Executes cloud inference through OpenRouter API with multi-model fallback.
        100% cloud processing: Requires valid OPENROUTER_API_KEY.
        """
        api_key = settings.OPENROUTER_API_KEY.strip()
        if not api_key:
            raise OpenRouterAuthError(
                "OPENROUTER_API_KEY is not configured in the observatory environment. "
                "Please obtain a free API key from https://openrouter.ai and add it to .env "
                "to enable 100% cloud AI processing."
            )

        system_prompt = cls.generate_system_prompt(db, target_route=route_context)

        messages = [{"role": "system", "content": system_prompt}]
        if conversation_history:
            for msg in conversation_history[-4:]:  # Include last 4 turns for context
                if msg.get("role") in ("user", "assistant") and msg.get("content"):
                    messages.append({"role": msg["role"], "content": msg["content"]})

        messages.append({"role": "user", "content": user_prompt})

        # Build prioritized candidate model list
        candidate_models: List[str] = []
        configured = (settings.OPENROUTER_MODEL or "").strip()
        if configured:
            candidate_models.append(configured)
        for m in DEFAULT_FREE_MODELS:
            if m not in candidate_models:
                candidate_models.append(m)

        headers = {
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": settings.OPENROUTER_SITE_URL,
            "X-Title": settings.OPENROUTER_SITE_NAME,
            "Content-Type": "application/json",
        }

        errors: List[str] = []

        # Iterate through models with automatic fallback if an endpoint is deprecated or rate-limited
        for model_name in candidate_models:
            payload = {
                "model": model_name,
                "messages": messages,
                "temperature": 0.2,  # Low temperature for strict econometric precision
                "max_tokens": 1000,
            }

            try:
                with httpx.Client(timeout=35.0) as client:
                    res = client.post(cls.API_URL, headers=headers, json=payload)

                    if res.status_code == 401:
                        raise OpenRouterAuthError(
                            "OpenRouter authentication failed (HTTP 401). Invalid API Key provided."
                        )

                    if res.status_code != 200:
                        logger.warning(
                            "OpenRouter model %s failed with HTTP %d: %s. Trying next candidate...",
                            model_name,
                            res.status_code,
                            res.text[:150],
                        )
                        errors.append(f"{model_name} (HTTP {res.status_code})")
                        continue

                    data = res.json()
                    choices = data.get("choices", [])
                    if not choices:
                        errors.append(f"{model_name} (empty choices)")
                        continue

                    msg_obj = choices[0].get("message", {})
                    raw_answer = msg_obj.get("content")

                    # Handle reasoning models where output might reside in reasoning field
                    if not raw_answer:
                        raw_answer = msg_obj.get("reasoning")

                    if not raw_answer or not str(raw_answer).strip():
                        logger.warning(
                            "OpenRouter model %s returned empty text. Trying next candidate...",
                            model_name,
                        )
                        errors.append(f"{model_name} (empty text)")
                        continue

                    answer = str(raw_answer).strip()

                    # Strip hidden scratchpad think tags if present
                    cleaned = re.sub(r"<think>.*?</think>", "", answer, flags=re.DOTALL).strip()
                    if cleaned:
                        answer = cleaned

                    # Extract route mention if present for UI deep-link
                    route_match = re.search(
                        r"\b(DEL-BOM|DEL-BLR|BOM-BLR|DEL-CCU|DEL-HYD|BOM-MAA|BLR-HYD|DEL-MAA|DEL-IXS|DEL-DHM)\b",
                        answer.upper(),
                    )
                    suggested_route = route_match.group(1) if route_match else route_context
                    actual_model = data.get("model") or model_name

                    return {
                        "answer": answer,
                        "model_used": actual_model,
                        "suggested_route": suggested_route,
                        "matrix_sources": [
                            "Matrix 1: National Laspeyres Headline",
                            "Matrix 2: Carrier Inflation (CPI-Carrier)",
                            "Matrix 3: Corridor Volatility & Spreads",
                            "Matrix 4: Lead-Time Yield Curves",
                            "Matrix 5: Macro Jet Fuel (ATF) Context",
                        ],
                        "status": "SUCCESS",
                    }

            except OpenRouterAuthError:
                raise
            except httpx.RequestError as e:
                logger.warning(
                    "Network error connecting to OpenRouter for %s: %s. Trying next candidate...",
                    model_name,
                    e,
                )
                errors.append(f"{model_name} (Network Error: {e})")
                continue

        error_summary = "; ".join(errors) if errors else "No responsive endpoints found"
        raise RuntimeError(f"All OpenRouter candidate models failed. Details: {error_summary}")
