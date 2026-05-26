import os
import json
import asyncio
from typing import Dict, Any, Tuple, Optional
from datetime import datetime, timezone

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END

from artha.schemas.models import Signal, Decision, Verdict
from artha.core.logger import get_logger

logger = get_logger(__name__)

class DecisionState(Dict):
    signal: Signal
    verdict: Optional[Verdict]
    reason_code: Optional[str]
    reasoning: Optional[str]
    sizing_hint: Optional[float]
    metadata: Dict[str, Any]

class GuruJiBrain:
    """
    Guru Ji — The AI reasoning engine using LangGraph.
    """
    def __init__(self, config: dict):
        self.config = config
        self.api_key = os.environ.get("ANTHROPIC_API_KEY")
        self.model_haiku = config.get("model_haiku", "claude-3-haiku-20240307")
        self.timeout = config.get("timeout", 2.0)
        
        # Initialize LLM
        self.llm = ChatAnthropic(
            model=self.model_haiku,
            anthropic_api_key=self.api_key,
            timeout=self.timeout,
            max_retries=1
        )
        
        # Build the graph
        self.workflow = self._build_graph()

    def _build_graph(self):
        builder = StateGraph(DecisionState)
        
        builder.add_node("evaluate_signal", self._llm_evaluate)
        builder.set_entry_point("evaluate_signal")
        builder.add_edge("evaluate_signal", END)
        
        return builder.compile()

    async def _llm_evaluate(self, state: DecisionState) -> DecisionState:
        signal = state["signal"]
        
        prompt = f"""
        You are Guru Ji, an expert systematic trading assistant. 
        Evaluate the following trading signal and provide a verdict: TAKE, REJECT, or TRACK.
        
        Signal Details:
        - Symbol: {signal.symbol}
        - Side: {signal.side}
        - Confidence: {signal.confidence}
        - Strategy: {signal.strategy_id}
        - Suggested Entry: {signal.suggested_entry}
        - Suggested SL: {signal.suggested_sl}
        - Suggested TP: {signal.suggested_tp}
        - Features: {json.dumps(signal.features)}
        
        Rules:
        1. TAKE: High conviction signals.
        2. REJECT: Clearly weak or conflicting signals.
        3. TRACK: Interesting but borderline signals for shadow monitoring.
        
        Respond ONLY in JSON format:
        {{
            "verdict": "TAKE" | "REJECT" | "TRACK",
            "reason_code": "SHORT_CODE",
            "reasoning": "Brief explanation",
            "sizing_hint": 0.5 to 1.0
        }}
        """
        
        try:
            # We use a wrapped call to handle sync/async bridge if needed, 
            # but LangChain ChatAnthropic.ainvoke is natively async.
            response = await self.llm.ainvoke([
                SystemMessage(content="You are Guru Ji, a trading AI."),
                HumanMessage(content=prompt)
            ])
            
            result = json.loads(response.content)
            state["verdict"] = Verdict(result["verdict"].lower())
            state["reason_code"] = result.get("reason_code", "LLM_DECISION")
            state["reasoning"] = result.get("reasoning", "")
            state["sizing_hint"] = result.get("sizing_hint", 1.0)
            
        except Exception as e:
            logger.error(f"Guru Ji LLM error: {e}")
            # Fallback will be handled by the caller
            raise e

        return state

    async def decide(self, signal: Signal) -> Tuple[Verdict, str, str, float]:
        """Runs the LangGraph workflow to get a decision."""
        if not self.api_key or self.api_key == "PLACEHOLDER":
            logger.warning("ANTHROPIC_API_KEY not set. Using stub fallback.")
            return Verdict.REJECT, "LLM_NOT_CONFIGURED", "API Key missing", 0.0

        initial_state = {
            "signal": signal,
            "verdict": None,
            "reason_code": None,
            "reasoning": None,
            "sizing_hint": 1.0,
            "metadata": {}
        }
        
        try:
            final_state = await self.workflow.ainvoke(initial_state)
            return (
                final_state["verdict"],
                final_state["reason_code"],
                final_state["reasoning"],
                final_state["sizing_hint"]
            )
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            raise e
