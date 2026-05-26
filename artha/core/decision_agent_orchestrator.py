import asyncio
from typing import Optional
from datetime import datetime, timezone
from artha.schemas.models import Signal, Decision, Verdict
from artha.core.logger import get_logger
from artha.core.decision_agent import GuruJiBrain

logger = get_logger(__name__)

class DecisionAgent:
    """
    Guru Ji — The decision brain.
    Evaluates signals using deterministic rules and an LLM fallback via GuruJiBrain.
    """
    def __init__(self, config: dict):
        self.config = config
        self.min_confidence = config.get("min_confidence", 0.7)
        self.brain = GuruJiBrain(config)

    async def decide(self, signal: Signal) -> Decision:
        # 1. Deterministic Gating
        verdict = Verdict.REJECT
        reason_code = "UNKNOWN"
        
        if signal.confidence < self.min_confidence:
            verdict = Verdict.REJECT
            reason_code = "LOW_CONFIDENCE"
        else:
            # Borderline case or automatic?
            # For v2, signals >= 0.95 are auto-TAKE
            if signal.confidence >= 0.95:
                verdict = Verdict.TAKE
                reason_code = "HIGH_CONFIDENCE_AUTO"
                return Decision(
                    signal_id=signal.signal_id,
                    verdict=verdict,
                    reason_code=reason_code,
                    llm_used=False
                )
            else:
                # 2. Invoke LangGraph Brain (LLM)
                try:
                    v, rc, reason, size = await self.brain.decide(signal)
                    return Decision(
                        signal_id=signal.signal_id,
                        verdict=v,
                        reason_code=rc,
                        llm_used=True,
                        llm_reasoning=reason,
                        sizing_hint=size
                    )
                except Exception as e:
                    logger.error(f"Guru Ji Brain failed, falling back to REJECT: {e}")
                    return Decision(
                        signal_id=signal.signal_id,
                        verdict=Verdict.REJECT,
                        reason_code="LLM_FAILURE_FALLBACK",
                        llm_used=False
                    )

        return Decision(
            signal_id=signal.signal_id,
            verdict=verdict,
            reason_code=reason_code,
            llm_used=False
        )
