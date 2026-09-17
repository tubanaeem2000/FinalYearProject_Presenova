"""
Phase Five: AI Coach / Practice Mode Blueprint
Role: Provide real-time AI coaching using Gemini for short, context-aware responses.

Key Features:
- Gemini-powered coaching (short, concise, contextual replies — max ~100 words)
- Graceful fallback to local TF-IDF + LogisticRegression if Gemini unavailable
- Dr. Alexander Vance persona
- Grammar analysis via LanguageTool pre-pass
- Context injection from document/speech analysis reports
"""

import os
import logging
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from services.rate_limiter import rate_limit
from datetime import datetime
from dotenv import load_dotenv
from services.language_tool_service import (
    check_grammar,
    summarise_grammar_issues,
    grammar_score as lt_grammar_score,
)

logger = logging.getLogger(__name__)

load_dotenv()

phase_five_bp = Blueprint('phase_five', __name__, url_prefix='/api')


# ─────────────────────────────────────────────────────────────
# Helper: extract readable context from the analysis report
# ─────────────────────────────────────────────────────────────
def _build_context_text(context_report: dict) -> str:
    """Turn analysis report dict into a compact plain-text summary for the prompt."""
    if not context_report:
        return "No analysis report provided."

    parts = []
    phase = context_report.get('phase', 'practice')
    parts.append(f"Session type: {phase}")

    # Support both single analysis and V1/V2 comparison format
    analysis = (
        context_report.get('analysis')
        or context_report.get('v1Analysis')
        or context_report.get('v1Report')
    )
    if analysis and isinstance(analysis, dict):
        score = analysis.get('overall_score')
        if score is not None:
            parts.append(f"Overall score: {score}/100")

        feedback = analysis.get('detailed_feedback')
        if feedback:
            parts.append(f"Feedback summary: {str(feedback)[:250]}")

        strengths = analysis.get('strengths') or []
        if strengths:
            parts.append(f"Strengths: {'; '.join(str(s) for s in strengths[:3])}")

        recs = analysis.get('recommendations') or []
        if recs:
            parts.append(f"Recommendations: {'; '.join(str(r) for r in recs[:3])}")

        cat = analysis.get('category_scores') or {}
        if cat:
            cat_str = ', '.join(f"{k}={v}" for k, v in list(cat.items())[:5])
            parts.append(f"Category scores: {cat_str}")

        # Speech-specific metrics
        wpm = analysis.get('speech_speed_wpm')
        if wpm:
            parts.append(f"Speaking pace: {wpm} WPM")
        fillers = analysis.get('filler_words_count')
        if fillers is not None:
            parts.append(f"Filler words detected: {fillers}")

    return '\n'.join(parts)


# ─────────────────────────────────────────────────────────────
# Gemini-powered coach response
# ─────────────────────────────────────────────────────────────
def _gemini_coach_response(
    message: str,
    context_text: str,
    grammar_context: str,
    history: list,
) -> str:
    """
    Call Gemini to get a SHORT, CONTEXT-AWARE coaching reply.
    Returns '' if Gemini is unavailable so the caller can fall back to local engine.
    """
    try:
        from services.ai.gemini_provider import GeminiProvider
        provider = GeminiProvider()
        if not provider.is_available():
            logger.info("[AI COACH] Gemini not available, will use local fallback.")
            return ''

        # Build a brief conversation history string (last 4 turns)
        history_text = ''
        recent = history[-4:] if len(history) > 4 else history
        if recent:
            lines = []
            for msg in recent:
                role = 'User' if msg.get('role') == 'user' else 'Coach'
                content = str(msg.get('content', ''))[:120]
                lines.append(f"{role}: {content}")
            history_text = '\n'.join(lines)

        system_instruction = (
            "You are Dr. Alexander Vance, an elite AI Presentation and Communication Coach. "
            "Respond directly, conversationally, and concisely — strictly under 75 words (2-4 sentences or 2 bullet points). "
            "If the user asks about an external or technical topic (e.g. ethical hacking, AI, engineering, career), "
            "give a brief direct answer or actionable tip, then naturally tie it back to presentation skills, viva defense, "
            "or explaining complex concepts to an audience. "
            "NEVER repeat a generic welcome greeting if the user asks a specific question. "
            "Always be specific, encouraging, and concise."
        )

        prompt = f"""PRESENTATION ANALYSIS CONTEXT:
{context_text}
{grammar_context}

RECENT CONVERSATION:
{history_text if history_text else "(No previous turns)"}

USER SAYS: {message}

Respond as Dr. Alexander Vance — short, direct, context-aware (under 75 words)."""

        response = provider.generate(
            prompt=prompt,
            temperature=0.7,
            max_output_tokens=350,
            system_instruction=system_instruction,
        )
        return response.strip() if response else ''

    except Exception as exc:
        logger.warning("[AI COACH] Gemini call failed: %s", exc)
        return ''


# ─────────────────────────────────────────────────────────────
# Local fallback (TF-IDF intent engine)
# ─────────────────────────────────────────────────────────────
def _local_fallback_response(message: str, context_report: dict, has_history: bool = False) -> str:
    """Use local intent classification engine when Gemini is unavailable."""
    try:
        from services.coach_intent_engine import process_coach_chat
        result = process_coach_chat(
            user_message=message,
            current_state="PRACTICE",
            session_context=context_report,
        )
        resp = result.get("response", "")
        # If user asked a specific question during an active conversation, do not repeat the canned greeting
        if has_history and "Hello! I am Dr. Alexander Vance" in resp:
            return (
                f"Regarding '{message[:60]}': focus on explaining this clearly with structured examples. "
                "Break complex points into three key takeaways for your audience. How would you introduce this on your first slide?"
            )
        return resp
    except Exception as exc:
        logger.warning("[AI COACH] Local fallback error: %s", exc)
        return ""


# ─────────────────────────────────────────────────────────────
# Main endpoint
# ─────────────────────────────────────────────────────────────
@phase_five_bp.route('/practice-chat', methods=['POST'])
@jwt_required(optional=True)
@rate_limit(limit_authenticated=30, limit_guest=5)
def practice_chat():
    """
    AI Coach chat endpoint.

    POST /api/practice-chat
    Body (JSON):
      {
        "message": "User's question or statement",
        "history": [{"role": "user"|"ai", "content": "..."}],
        "contextReport": { "phase": "...", "analysis": {...} }
      }

    Response:
      {
        "status": "success",
        "ai_response": "Coach reply (short, context-aware)",
        "powered_by": "gemini" | "local" | "fallback",
        "grammar_score": 95,
        "grammar_issues": [...],
        "grammar_issues_count": 0,
        "message_id": "msg_...",
        "timestamp": "..."
      }
    """
    try:
        # ── 1. Validate ───────────────────────────────────────────────────────
        data = request.get_json()
        if data is None:
            return jsonify({
                "success": False,
                "error": "InvalidJson",
                "message": "Request body must be valid JSON",
            }), 400

        message = data.get('message', '').strip()
        if not message:
            return jsonify({
                "success": False,
                "error": "MissingMessage",
                "message": "Please provide a 'message' field",
            }), 400

        history = data.get('history', [])
        context_report = data.get('contextReport', {})

        # ── 2. Grammar pre-pass (LanguageTool) ───────────────────────────────
        grammar_issues = []
        grammar_score_val = 100
        grammar_context = ""
        try:
            if len(message) > 10:
                grammar_issues = check_grammar(message)
                grammar_score_val = lt_grammar_score(grammar_issues, len(message.split()))
                grammar_summary = summarise_grammar_issues(grammar_issues, max_issues=5)
                if grammar_issues:
                    grammar_context = (
                        f"\nGRAMMAR NOTE ({len(grammar_issues)} issue(s), score {grammar_score_val}/100): "
                        f"{grammar_summary} — briefly mention the fix in your reply."
                    )
                    logger.info("[AI COACH] %d grammar issue(s) found.", len(grammar_issues))
        except Exception as _ge:
            logger.warning("[AI COACH] Grammar pre-pass failed: %s", _ge)

        # ── 3. Build analysis context ─────────────────────────────────────────
        context_text = _build_context_text(context_report)

        # ── 4. Try Gemini first ───────────────────────────────────────────────
        ai_response_text = _gemini_coach_response(message, context_text, grammar_context, history)
        powered_by = "gemini"

        # ── 5. Fall back to local engine if Gemini unavailable ────────────────
        if not ai_response_text:
            logger.info("[AI COACH] Using local intent engine as fallback.")
            ai_response_text = _local_fallback_response(message, context_report, has_history=bool(history))
            powered_by = "local"

        # ── 6. Last-resort hardcoded reply ────────────────────────────────────
        if not ai_response_text:
            ai_response_text = (
                "Keep practicing! Focus on clear pacing (130–150 WPM), "
                "eliminate filler words, and keep each slide to 6 bullets max."
            )
            powered_by = "fallback"

        # ── 7. Return response ────────────────────────────────────────────────
        logger.info("[AI COACH] Response ready. powered_by=%s", powered_by)
        return jsonify({
            "success": True,
            "status": "success",
            "ai_response": ai_response_text,
            "powered_by": powered_by,
            "message_id": f"msg_{int(datetime.now().timestamp() * 1000)}",
            "timestamp": datetime.now().isoformat(),
            "grammar_score": grammar_score_val,
            "grammar_issues": grammar_issues,
            "grammar_issues_count": len(grammar_issues),
        }), 200

    except Exception as e:
        logger.error("[AI COACH] Unexpected error: %s", e, exc_info=True)

        error_message = str(e)
        if "api_key" in error_message.lower() or "authentication" in error_message.lower():
            error_message = "API key issue. Please check your Gemini configuration."
        elif "quota" in error_message.lower() or "rate" in error_message.lower():
            error_message = "API quota exceeded. Please try again later."
        elif "timeout" in error_message.lower():
            error_message = "Request timed out. Please try again."

        return jsonify({
            "success": False,
            "error": "CoachError",
            "message": error_message,
        }), 500
