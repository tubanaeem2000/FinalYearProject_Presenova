"""
AI Evaluator Service
Centralized Google Gemini 1.5 Flash analysis and smart fallbacks for all modules.
Now includes LanguageTool Cloud grammar pre-pass to enrich the 7Cs analysis.
"""

import sys
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
if hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import os
import json
import random
import re
import logging
from dotenv import load_dotenv
from services.ai.gemini_provider import GeminiProvider
from services.language_tool_service import (
    check_grammar,
    summarise_grammar_issues,
    grammar_score as lt_grammar_score,
)
from services.ai.scoring_utils import clamp_score

logger = logging.getLogger(__name__)

# Load env variables
load_dotenv()

# Initialize Gemini Provider
_gemini_provider = GeminiProvider()
gemini_available = _gemini_provider.is_available()

if gemini_available:
    logger.info("[AI OK] Global AI Evaluator: Gemini Provider initialized successfully (%s)", _gemini_provider.model_name)
else:
    logger.warning("[AI WARN] Global AI Evaluator: GEMINI_API_KEY not configured or offline. Running with smart fallbacks.")


def evaluate_7cs(text: str, module_type: str, context_metrics: dict) -> dict:
    """
    Evaluates text (document slides, transcripts, or live presentation speech)
    and returns a standardized 7Cs scorecard.

    Now includes a LanguageTool Cloud grammar pre-pass:
    - Detects specific grammar/spelling errors before calling Gemini.
    - Injects the error list into the Gemini prompt for richer corrections.
    - Adds 'grammar_issues' and 'grammar_score' fields to the returned report.

    module_type options: 'document', 'speech', 'live'
    """
    # Safeguard text input
    if not text or not text.strip():
        text = "No content provided."

    # ===== STEP 0: GRAMMAR PRE-PASS (LanguageTool Cloud API) =====
    # Runs for ALL module types: document, speech, and live transcript.
    grammar_issues = []
    grammar_summary_text = ""
    computed_grammar_score = 100

    try:
        grammar_issues = check_grammar(text)
        word_count_for_grammar = len(text.split())
        computed_grammar_score = lt_grammar_score(grammar_issues, word_count_for_grammar)
        grammar_summary_text = summarise_grammar_issues(grammar_issues)
        if grammar_issues:
            logger.info("[GRAMMAR] LanguageTool detected %d issues (module=%s). Grammar score: %d/100", len(grammar_issues), module_type, computed_grammar_score)
        else:
            logger.info("[GRAMMAR] LanguageTool: No grammar issues detected (module=%s).", module_type)
    except Exception as _ge:
        logger.warning("[GRAMMAR WARN] Grammar pre-pass failed: %s. Continuing without grammar data.", _ge)
        grammar_issues = []
        grammar_summary_text = ""
        computed_grammar_score = 100

    # ===== HELPER: Grammar grade badge =====
    def _grammar_grade(score: int) -> str:
        if score >= 90: return 'A'
        if score >= 80: return 'B'
        if score >= 70: return 'C'
        if score >= 60: return 'D'
        return 'F'

    def _grammar_summary_short(score: int, issues: list) -> str:
        if score >= 90:
            return f"Excellent grammar ({score}/100). No significant issues detected."
        if score >= 80:
            return f"Good grammar ({score}/100). {len(issues)} minor issue(s) found."
        if score >= 70:
            return f"Acceptable grammar ({score}/100). {len(issues)} issue(s) should be corrected."
        return f"Grammar needs improvement ({score}/100). {len(issues)} issue(s) detected — review carefully."

    # ===== BUILD DYNAMIC FALLBACK RESPONSE =====
    fallback_json = {}
    insufficient_live_data = False  # FIX: Initialize before any if/elif that references it
    
    if module_type == 'document':
        filename = context_metrics.get("filename", "presentation.pdf")
        
        # Local Heuristic Analysis (when Gemini is unavailable)
        word_count = len(text.split())
        sentences = [s.strip() for s in re.split(r'[.!?]+', text) if len(s.strip()) > 5]
        sentence_count = len(sentences)
        text_lower = text.lower()
        filename_lower = filename.lower()
        
        # Compute sentence length variety (higher = more varied = better)
        if sentences:
            avg_len = sum(len(s.split()) for s in sentences) / len(sentences)
            variance = sum(abs(len(s.split()) - avg_len) for s in sentences) / len(sentences)
            sentence_variety_score = min(100, int(variance * 10))
        else:
            avg_len, variance, sentence_variety_score = 10, 0, 50

        # Start with a base score, then deduct/add based on heuristics
        score_base = 78
        reasons_for_low_score = []
        
        # Heuristic 1: Filename or content contains indicators of poor quality
        if any(w in filename_lower or w in text_lower for w in ["worst", "bad", "terrible", "poor", "fail", "unprepared", "draft", "incomplete"]):
            score_base -= 35
            reasons_for_low_score.append("Document/filename contains indications of low quality or draft status")
            
        # Heuristic 2: Length (very short is poor)
        if word_count < 50:
            score_base -= 20
            reasons_for_low_score.append("Extremely short content suggesting incomplete slides or notes")
        elif word_count < 150:
            score_base -= 10
            reasons_for_low_score.append("Short content, might lack details or depth")
            
        # Heuristic 3: Lack of structure (no slide/section indicators)
        has_structure = any(w in text_lower for w in ["slide", "introduction", "conclusion", "agenda", "overview", "summary"])
        if not has_structure:
            score_base -= 15
            reasons_for_low_score.append("Lacks clear structural markers (e.g., Slides, Agenda, or Conclusion)")
            
        # Heuristic 4: Grammar/clarity filler words count
        filler_words = ['um', 'uh', 'like', 'you know', 'basically', 'actually']
        filler_count = sum(text_lower.count(w) for w in filler_words)
        if filler_count > 5:
            score_base -= 10
            reasons_for_low_score.append("High density of verbal fillers or conversational language in written notes")

        # Heuristic 5: Factor in computed grammar score
        if computed_grammar_score < 70:
            score_base -= 8
            reasons_for_low_score.append(f"Grammar issues detected ({computed_grammar_score}/100 grammar score)")

        # Clamp score between 25 and 95
        overall_score = max(25, min(95, score_base))
        
        # ===== DYNAMIC CONTENT-AWARE STRENGTHS & RECOMMENDATIONS =====
        depth_adj = 'strong' if word_count > 400 else ('adequate' if word_count > 150 else 'limited')
        grammar_adj = 'excellent' if computed_grammar_score >= 85 else ('good' if computed_grammar_score >= 70 else 'below average')
        structure_adj = 'well-structured' if has_structure else 'loosely structured'
        variety_adj = 'varied and engaging' if sentence_variety_score >= 40 else 'somewhat monotonous'

        if overall_score < 60:
            dynamic_strengths = [
                f"Document contains {word_count} words — content exists and can be refined.",
                f"Grammar score: {computed_grammar_score}/100 ({grammar_adj}) — " + ("some positive aspects" if computed_grammar_score >= 60 else "significant room for improvement."),
                "Core topic intent is identifiable even in current state."
            ]
            dynamic_recs = [
                f"Restructure content with clear slide boundaries: Intro, {sentence_count // 3 or 1} body slides, and a Conclusion.",
                f"Remove the {filler_count} detected filler expressions; replace with precise professional vocabulary.",
                "Add at least 2-3 quantitative data points (percentages, timelines, KPIs) to support your main argument.",
                "Ensure each slide has a single clear topic sentence before elaborating."
            ]
            seven_cs_eval = {
                "Clear": f"The core message is {'' if has_structure else 'not '}clearly organized. {'' if has_structure else 'Add slide headers and agenda.'}",
                "Concise": f"At {word_count} words, the document is {'concise' if word_count < 300 else 'lengthy'} but {'lacks depth' if word_count < 100 else 'risks verbosity'}.",
                "Correct": f"Grammar score of {computed_grammar_score}/100 indicates {'noticeable errors requiring attention' if computed_grammar_score < 70 else 'minor correction opportunities'}.",
                "Complete": f"{'Critical sections like conclusion or call-to-action appear missing.' if not has_structure else 'Basic structure is present but could be expanded.'}",
                "Courteous": "The tone needs refinement to meet professional presentation standards.",
                "Concrete": f"Sentence length variety ({sentence_variety_score}/100) suggests {'abstract, generic content' if sentence_variety_score < 30 else 'some concrete examples'}. Add specific metrics.",
                "Consistent": "Formatting, terminology, and bullet usage need standardization across all slides."
            }
            seven_cs_scores = {
                "Clear": max(20, overall_score - 5),
                "Concise": max(20, overall_score - 12),
                "Correct": max(20, min(100, computed_grammar_score - 10)),
                "Complete": max(20, overall_score - 15),
                "Courteous": max(30, overall_score + 5),
                "Concrete": max(20, overall_score - 8),
                "Consistent": max(20, overall_score - 14)
            }
            # FIX: these were nested f-strings reusing the outer f-string's
            # quote character (e.g. f"...{'...' if x else f'...{"..." }'}...").
            # Python 3.12 (PEP 701) allows this; Python 3.11 (what Render
            # actually runs) raises "f-string: unterminated string" — this
            # silently broke every Document Analyzer request in production
            # while working fine in local dev. Precomputing each branch as a
            # plain variable avoids nested-quote issues entirely and is
            # correct on any Python version. Also fixes a real bug: the
            # action-2 string below was missing its f-prefix, so
            # "{filler_count}" was never actually interpolated.
            if grammar_issues:
                grammar_summary_line = (
                    f"{len(grammar_issues)} grammar issue(s) were flagged. "
                    f"Key areas: {grammar_summary_text[:200] if grammar_summary_text else 'See detailed grammar report.'}"
                )
            else:
                grammar_summary_line = "No significant grammar issues detected."
            action_2 = (
                f"Reduce the {filler_count} detected informal expressions to maintain professional register."
                if filler_count > 0 else "Maintain the professional register throughout all slides."
            )
            detailed_feedback = (
                f"STRUCTURE ASSESSMENT: This presentation scored {overall_score}/100. "
                f"It contains {word_count} words across an estimated {max(1, sentence_count // 5)} slides, "
                f"which is {'below the recommended 200+ words for a complete deck' if word_count < 200 else 'within acceptable range'}. "
                f"The content appears {structure_adj} with {'clear sectioning evident' if has_structure else 'no clear slide or section markers detected'}.\n\n"
                f"LANGUAGE QUALITY: Grammar score is {computed_grammar_score}/100 (Grade {_grammar_grade(computed_grammar_score)}). "
                f"{grammar_summary_line}. "
                f"Sentence length variety is rated {sentence_variety_score}/100 — aim for a mix of short (under 10 words) and developed (15–25 words) sentences.\n\n"
                f"TOP 3 PRIORITY ACTIONS: (1) {'Add clear slide-by-slide structure with titled sections.' if not has_structure else 'Deepen the content with domain-specific evidence and data.'}  "
                f"(2) {action_2}  "
                f"(3) {'Improve grammar quality — address the flagged issues before presenting.' if computed_grammar_score < 70 else 'Strengthen your call-to-action slide with a concrete next step or decision request.'}"
            )
        else:
            dynamic_strengths = [
                f"Content depth is {depth_adj}: {word_count} words provide {'comprehensive' if word_count > 300 else 'adequate'} coverage.",
                f"Grammar quality is {grammar_adj} at {computed_grammar_score}/100 (Grade {_grammar_grade(computed_grammar_score)}).",
                f"Sentence structure is {variety_adj} (variety score: {sentence_variety_score}/100)."
            ]
            dynamic_recs = [
                "Reinforce your strongest argument with an empirical data point, statistic, or case study.",
                f"{'Correct the ' + str(len(grammar_issues)) + ' grammar issue(s) for a polished final version.' if grammar_issues else 'Maintain grammar quality in any future edits.'}",
                "Add a memorable closing statement or call-to-action in your conclusion slide.",
                f"Ensure visual consistency: use {'the same' if has_structure else 'a unified'} font size, bullet style, and heading format on every slide."
            ]
            seven_cs_eval = {
                "Clear": f"Main points are {'' if has_structure else 'reasonably '}clear and follow a logical progression across {sentence_count} sentences.",
                "Concise": f"At {word_count} words, the document is {'appropriately concise' if word_count < 500 else 'somewhat lengthy — consider trimming verbose sections'}.",
                "Correct": f"Grammar score of {computed_grammar_score}/100 indicates {grammar_adj} language quality.",
                "Complete": f"The presentation {'covers all primary' if has_structure else 'covers most'} required sections. {'A conclusion or CTA slide would complete the deck.' if not has_structure else ''}",
                "Courteous": "The tone is professional and respectful of the target audience.",
                "Concrete": f"Sentence variety ({sentence_variety_score}/100) indicates {variety_adj} content. {'Consider adding more specific examples or data.' if sentence_variety_score < 50 else ''}",
                "Consistent": "The document maintains reasonably consistent structure and vocabulary throughout."
            }
            seven_cs_scores = {
                "Clear": min(100, overall_score + 4),
                "Concise": min(100, overall_score + 2),
                "Correct": min(100, computed_grammar_score),
                "Complete": min(100, overall_score + 3),
                "Courteous": min(100, overall_score + 6),
                "Concrete": min(100, overall_score + 1),
                "Consistent": min(100, overall_score + 2)
            }
            # FIX: same nested-f-string-with-reused-quotes issue as the
            # branch above (Python 3.11-incompatible, silently broke prod).
            if grammar_issues:
                grammar_summary_line = (
                    f"{len(grammar_issues)} minor grammar issue(s) were flagged: "
                    f"{grammar_summary_text[:150] if grammar_summary_text else 'Review the grammar report.'}"
                )
            else:
                grammar_summary_line = "No grammar issues detected — excellent writing quality."
            detailed_feedback = (
                f"STRUCTURE ASSESSMENT: This presentation scored {overall_score}/100 overall. "
                f"It contains {word_count} words across an estimated {max(1, sentence_count // 5)} slides — "
                f"{'a thorough and comprehensive deck' if word_count > 400 else 'a solid foundation'}. "
                f"The content is {structure_adj}, {'with recognizable section markers and clear slide flow' if has_structure else 'with room to strengthen the slide-by-slide organization'}.\n\n"
                f"LANGUAGE QUALITY: Grammar score is {computed_grammar_score}/100 (Grade {_grammar_grade(computed_grammar_score)}). "
                f"{grammar_summary_line}. "
                f"Sentence variety is {variety_adj} ({sentence_variety_score}/100), which {'helps' if sentence_variety_score >= 40 else 'could be improved to better'} maintain audience engagement.\n\n"
                f"TOP 3 PRIORITY ACTIONS: "
                f"(1) {'Fix the ' + str(len(grammar_issues)) + ' flagged grammar issue(s) before your final presentation.' if grammar_issues else 'Run a final proofreading pass to catch any late-stage edits.'}  "
                f"(2) {'Optimize spacing and visual balance across slides to prevent text crowding.' if word_count > 400 else 'Add 1-2 more data-rich slides to deepen your argument.'}  "
                f"(3) Inject a more memorable closing statement in your conclusion slide to leave a lasting impression."
            )

        fallback_json = {
            "overall_score": overall_score,
            "document_name": filename,
            "category_scores": {
                "Structure": min(100, max(20, overall_score + (5 if has_structure else -10))),
                "Clarity": min(100, max(20, overall_score + 2)),
                "Persuasion": min(100, max(20, overall_score - 3)),
                "Content_Quality": min(100, max(20, overall_score + (4 if word_count > 200 else -8))),
                "Call_to_Action": min(100, max(20, overall_score - 5)),
                "Grammar_and_Syntax": min(100, max(20, computed_grammar_score)),
                "Accuracy": min(100, max(20, overall_score + 5)),
                "Tone_Appropriateness": min(100, max(30, overall_score + 6)),
                "Audience_Alignment": min(100, max(20, overall_score + 1)),
                "Purpose_Fulfillment": min(100, max(20, overall_score + 2))
            },
            "context_analysis": {
                "context_accuracy_score": min(100, max(30, overall_score + 3)),
                "is_context_accurate": overall_score >= 60,
                "factual_correctness_summary": (
                    "The presentation content aligns logically with the topic domain."
                    if overall_score >= 60
                    else "The document shows contextual gaps and informal phrasing. Information lacks rigorous evidence."
                ),
                "inaccuracies_detected": [
                    "No major factual inaccuracies detected."
                ] if overall_score >= 60 else [
                    "Vague or unsupported claims in text body.",
                    "Lacks verifiable data points or specific domain context."
                ],
                "context_based_changes": [
                    "Consider backing up key statements with concrete citations or numerical metrics.",
                    "Sharpen technical terminology in body slides to ensure full domain precision."
                ]
            },
            "seven_cs_evaluation": seven_cs_eval,
            "seven_cs_scores": seven_cs_scores,
            "strengths": dynamic_strengths,
            "recommendations": dynamic_recs,
            "detailed_feedback": detailed_feedback,
            "improved_text": f"# {os.path.splitext(filename)[0].upper()} (IMPROVED VERSION)\n\n{text}\n\n---\n*Note: Polished for conciseness and style by the AI assistant.*",
            # Grammar enrichment
            "grammar_score": computed_grammar_score,
            "grammar_grade": _grammar_grade(computed_grammar_score),
            "grammar_summary_short": _grammar_summary_short(computed_grammar_score, grammar_issues),
            "grammar_issues": grammar_issues,
            "grammar_issues_count": len(grammar_issues),
        }
        
    elif module_type == 'speech':
        speech_speed_wpm = context_metrics.get("speech_speed_wpm", 130)
        filler_count = context_metrics.get("filler_count", 0)
        filler_percentage = context_metrics.get("filler_percentage", 0.0)
        repetition_count = context_metrics.get("repetition_count", 0)
        duration_seconds = context_metrics.get("duration_seconds", 0)
        
        score_base = 80
        if speech_speed_wpm > 160 or speech_speed_wpm < 80:
            score_base -= 15
        if filler_count > 10:
            score_base -= 20
        elif filler_count > 5:
            score_base -= 10
        if repetition_count > 5:
            score_base -= 10
        elif repetition_count > 0:
            score_base -= 5
            
        overall_score = max(30, min(95, score_base))
        
        fallback_json = {
            "overall_score": overall_score,
                "seven_cs_evaluation": {
                "Clear": "The speaking pace supports a reasonably clear delivery.",
                "Concise": f"Filler words count is {filler_count} ({filler_percentage:.1f}%), which affects conciseness.",
                "Correct": "The speech follows general grammatical rules.",
                "Complete": "The speaker covers the topic within the duration.",
                "Courteous": "The tone is professional and audience-appropriate.",
                "Concrete": "The transcript conveys specific ideas directly.",
                "Consistent": "The speech pace is consistent throughout."
            },
            "seven_cs_scores": {
                "Clear": max(30, overall_score - 2),
                "Concise": max(30, overall_score - 10),
                "Correct": 85,
                "Complete": 80,
                "Courteous": 90,
                "Concrete": 82,
                "Consistent": 80
            },
            "strengths": [
                "Good overall verbal presentation structure.",
                "Maintains consistent delivery tone.",
                "Good topic focus and organization."
            ],
            "recommendations": [
                "Try to minimize verbal pauses and filler words.",
                "Adjust your speaking speed to stay within the 120-160 WPM range.",
                "Vary vocabulary to reduce word repetitions."
            ],
            "detailed_feedback": f"Your speech had a pacing speed of {speech_speed_wpm} WPM and {filler_count} filler words. Focus on taking silent pauses instead of speaking fillers.",
            "improved_text": text
        }
        
    elif module_type == 'live':
        avg_eye = context_metrics.get("avg_eye", 0)
        avg_posture = context_metrics.get("avg_posture", 0)
        avg_wpm = context_metrics.get("avg_wpm", 0)
        fillers = context_metrics.get("fillers", 0)
        avg_qna = context_metrics.get("avg_qna", 0)
        interruptions = context_metrics.get("interruptions", [])
        has_visual_metrics = context_metrics.get("has_visual_metrics", False) or bool(avg_eye or avg_posture)
        has_voice_metrics = context_metrics.get("has_voice_metrics", False) or bool(avg_wpm or fillers)
        has_qna_scores = context_metrics.get("has_qna_scores", False) or bool(avg_qna)
        
        overall_score = context_metrics.get("overall_execution", 0)
        if overall_score == 0 and (has_visual_metrics or has_voice_metrics or has_qna_scores):
            sub_scores = []
            if avg_eye or avg_posture:
                sub_scores.append((avg_eye + avg_posture) / 2)
            if avg_wpm:
                wpm_score = min(100, max(20, 100 - (fillers * 4) - abs(avg_wpm - 140) // 2))
                sub_scores.append(wpm_score)
            if avg_qna:
                sub_scores.append(avg_qna)
            if sub_scores:
                overall_score = int(sum(sub_scores) / len(sub_scores))

        insufficient_live_data = not has_visual_metrics and not has_voice_metrics and not has_qna_scores and overall_score == 0
        
        strengths_list = []
        recs_list = []
        
        if not has_visual_metrics:
            recs_list.append("No video metrics were captured, so eye contact and posture could not be scored.")
        elif avg_eye >= 80:
            strengths_list.append(f"Maintained strong, consistent eye contact (average: {avg_eye}%).")
        else:
            recs_list.append(f"Try to look directly at the camera more frequently (average: {avg_eye}%).")
            
        if has_visual_metrics and avg_posture >= 80:
            strengths_list.append("Maintained professional upright posture throughout the session.")
        elif has_visual_metrics:
            recs_list.append("Avoid leaning or shifting; try to maintain a steady upright posture.")
            
        if not has_voice_metrics:
            recs_list.append("No voice transcript was captured, so pacing and filler-word metrics could not be scored.")
        elif fillers == 0:
            strengths_list.append("Excellent vocal control with zero verbal filler words used.")
        elif fillers <= 3:
            strengths_list.append(f"Strong verbal tracking with minimal fillers ({fillers} detected).")
        else:
            recs_list.append(f"Reduce filler word frequency (detected {fillers} instances of 'um', 'like', or 'you know').")
            
        if has_voice_metrics and 120 <= avg_wpm <= 160:
            strengths_list.append(f"Spoke at a highly engaging pace of {avg_wpm} WPM (optimal: 120-160 WPM).")
        elif has_voice_metrics and avg_wpm > 160:
            recs_list.append(f"Practice inserting natural pauses; speaking pace of {avg_wpm} WPM is slightly too fast.")
        elif has_voice_metrics:
            recs_list.append(f"Increase vocal energy; speaking pace of {avg_wpm} WPM is slightly too slow.")
            
        num_interruptions = len(interruptions)
        if num_interruptions == 0:
            qna_feedback = "No panelist interruptions occurred during this session."
        else:
            if not has_qna_scores:
                qna_feedback = "A panelist question was recorded, but no automated Q&A score was available."
            elif avg_qna >= 80:
                strengths_list.append(f"Handled academic questions confidently (Q&A score: {avg_qna}%).")
                qna_feedback = "Handled interruptions reasonably well; answers directly addressed the examiner's queries."
            else:
                recs_list.append("Formulate more structured answers when interrupted by academic panel questions.")
                qna_feedback = "Struggled slightly with directness under examiner questions."
                
        if len(strengths_list) < 2:
            strengths_list.append("Structured the presentation flow logically.")
        if len(recs_list) < 2:
            recs_list.append("Incorporate hand gestures or physical dynamics to increase audience engagement.")
            
        seven_cs_eval = {
            "Clear": f"The presenter maintained a steady gaze (average: {avg_eye}%) facilitating clear audience reception." if has_visual_metrics else "Eye-contact scoring was unavailable because no valid video samples were captured.",
            "Concise": (f"Pacing was efficient, but filler word count was {fillers} which slightly impacted conciseness." if fillers > 3 else f"Exemplary conciseness with minimal verbal filler words ({fillers} detected).") if has_voice_metrics else "Conciseness could not be scored from voice data because no transcript segments were captured.",
            "Correct": "Formal presentation language was grammatically correct and pronunciation was clear.",
            "Complete": "Demonstrated complete topic coverage and successfully responded to all panelist questions." if num_interruptions > 0 else "Presentation flow was uninterrupted, covering key points completely.",
            "Courteous": "Maintained an upright, professional posture and showed courtesy to examiners." if has_visual_metrics else "Posture-based courtesy signals were unavailable because video scoring did not run.",
            "Concrete": (f"The speaking pace of {avg_wpm} WPM supported a concrete delivery style." if 120 <= avg_wpm <= 160 else f"The speaking pace of {avg_wpm} WPM was slightly off-optimum, reducing concreteness.") if has_voice_metrics else "Concrete delivery could not be evaluated from speaking pace because audio scoring was unavailable.",
            "Consistent": f"Visual focus and body posture remained consistent (posture: {avg_posture}%) during delivery." if has_visual_metrics else "Consistency could not be scored from visual metrics because no valid video samples were captured."
        }
        
        if insufficient_live_data:
            fallback_json = {
                "overall_score": 0,
                "category_scores": {
                    "Structure": 0, "Clarity": 0, "Persuasion": 0,
                    "Content_Quality": 0, "Call_to_Action": 0,
                    "Grammar_and_Syntax": 0, "Accuracy": 0,
                    "Tone_Appropriateness": 0, "Audience_Alignment": 0,
                    "Purpose_Fulfillment": 0
                },
                "seven_cs_evaluation": {
                    c: "Not scored — no camera or microphone data was captured for this session."
                    for c in ["Clear", "Concise", "Correct", "Complete", "Courteous", "Concrete", "Consistent"]
                },
                "seven_cs_scores": {
                    c: 0 for c in ["Clear", "Concise", "Correct", "Complete", "Courteous", "Concrete", "Consistent"]
                },
                "strengths": [],
                "recommendations": [
                    "Turn on your camera and microphone before starting the session.",
                    "Speak clearly and stay in frame so eye contact and posture can be tracked."
                ],
                "qna_analysis": "No panelist interruptions occurred during this session.",
                "detailed_feedback": "No usable video or audio data was captured during this session, so no delivery score could be generated. Check your camera and microphone permissions and try again.",
                "improved_text": "No speech was captured during this session."
            }
        else:
            # Full structured fallback with verified ratings from captured telemetry
            clear_score = max(30, min(95, int((avg_eye * 0.6) + (85 if 120 <= avg_wpm <= 160 else 65) * 0.4))) if (has_visual_metrics or has_voice_metrics) else 70
            concise_score = max(25, min(95, 100 - (fillers * 6) - (abs(avg_wpm - 140) // 2 if has_voice_metrics else 10)))
            correct_score = computed_grammar_score
            complete_score = max(30, min(95, avg_qna if has_qna_scores else (82 if len(text.split()) > 15 else 65)))
            courteous_score = max(30, min(95, avg_posture if has_visual_metrics else 80))
            concrete_score = max(30, min(95, int((overall_score * 0.5) + (avg_qna * 0.5 if has_qna_scores else 40))))
            consistent_score = max(30, min(95, int((avg_eye * 0.5 + avg_posture * 0.5) if has_visual_metrics else 75)))

            fallback_json = {
                "overall_score": overall_score,
                "category_scores": {
                    "Structure": max(25, min(95, int(overall_score * 0.95))),
                    "Clarity": clear_score,
                    "Persuasion": max(25, min(95, int(avg_eye * 0.5 + avg_posture * 0.5 if has_visual_metrics else overall_score))),
                    "Content_Quality": max(25, min(95, avg_qna if has_qna_scores else int(overall_score * 0.9))),
                    "Call_to_Action": max(25, min(95, int(overall_score * 0.85))),
                    "Grammar_and_Syntax": computed_grammar_score,
                    "Accuracy": max(25, min(95, avg_qna if has_qna_scores else 80)),
                    "Tone_Appropriateness": courteous_score,
                    "Audience_Alignment": max(25, min(95, int(overall_score * 0.92))),
                    "Purpose_Fulfillment": overall_score
                },
                "seven_cs_evaluation": seven_cs_eval,
                "seven_cs_scores": {
                    "Clear": clear_score,
                    "Concise": concise_score,
                    "Correct": correct_score,
                    "Complete": complete_score,
                    "Courteous": courteous_score,
                    "Concrete": concrete_score,
                    "Consistent": consistent_score
                },
                "strengths": strengths_list,
                "recommendations": recs_list,
                "qna_analysis": qna_feedback,
                "detailed_feedback": (
                    f"Live presentation analysis for topic '{context_metrics.get('topic', 'Live Practice')}': "
                    f"Overall score achieved is {overall_score}/100. "
                    f"{'Average eye contact was ' + str(avg_eye) + '% and posture was ' + str(avg_posture) + '%. ' if has_visual_metrics else 'Visual metrics were not detected. '}"
                    f"{'Speaking rate averaged ' + str(avg_wpm) + ' WPM with ' + str(fillers) + ' filler words detected. ' if has_voice_metrics else ''}"
                    f"{'Academic panelist Q&A score was ' + str(avg_qna) + '%. ' if has_qna_scores else ''}"
                    f"Continue practicing to maintain high engagement and posture throughout your presentation."
                ),
                "improved_text": text if text and text != "No content provided." else f"Presentation rehearsal on topic: {context_metrics.get('topic', 'General')}"
            }

    # ===== BUILD DYNAMIC PROMPT FOR GEMINI =====
    analysis_prompt = ""
    if module_type == 'document':
        filename = context_metrics.get("filename", "presentation.pdf")
        # Attach grammar pre-pass summary if available
        grammar_section = f"""

--- GRAMMAR PRE-ANALYSIS (LanguageTool Cloud) ---
Grammar Quality Score: {computed_grammar_score}/100
Total Grammar/Spelling Issues Detected: {len(grammar_issues)}
{grammar_summary_text if grammar_summary_text else 'No grammar issues detected — text appears grammatically clean.'}
--- END GRAMMAR PRE-ANALYSIS ---
""" if grammar_issues or computed_grammar_score < 100 else ""

        analysis_prompt = f"""
You are an expert presentation coach and communications consultant. Your job is to analyze the following presentation text/slides, identify all errors, grammatical mistakes, structural weaknesses, and assess how well it adheres to the 7 Cs of Communication (Clear, Concise, Correct, Complete, Courteous, Concrete, Consistent).

IMPORTANT: A grammar pre-analysis has already been performed using LanguageTool. The grammar quality score is {computed_grammar_score}/100. Use this data to calibrate the 'Correct' dimension and Grammar_and_Syntax category score accurately.{grammar_section}
Then, generate a comprehensive report in JSON format.
Your response MUST be a single, valid JSON object matching the schema below. Do not wrap the JSON in markdown code blocks (e.g. ```json).

JSON Schema:
{{
  "overall_score": {overall_score},
  "document_name": "{filename}",
  "category_scores": {{
    "Structure": <score 0-100 based on logical flow, page/slide divisions, and agenda presence>,
    "Clarity": <score 0-100 based on word simplicity and ease of understanding>,
    "Persuasion": <score 0-100 based on argumentation quality and focus>,
    "Content_Quality": <score 0-100 based on depth, analysis, and facts>,
    "Call_to_Action": <score 0-100 based on presence and clarity of next steps/concluding goals>,
    "Grammar_and_Syntax": {computed_grammar_score},
    "Accuracy": <score 0-100 based on accuracy of statements, information, and logic>,
    "Tone_Appropriateness": <score 0-100 based on professional tone, respectfulness, and suitability>,
    "Audience_Alignment": <score 0-100 based on how well target audience needs are addressed>,
    "Purpose_Fulfillment": <score 0-100 based on achieving the presentation's primary goals>
  }},
  "context_analysis": {{
    "context_accuracy_score": <integer 0-100 indicating factual and logical accuracy of information in context>,
    "is_context_accurate": <boolean true if context/facts are valid and accurate, false if errors found>,
    "factual_correctness_summary": "<1-2 sentence explanation evaluating if the information and claims are factually/contextually correct or incorrect>",
    "inaccuracies_detected": [
      "<specific wrong, inaccurate, or misleading statement/claim 1 if any, or state 'No factual inaccuracies detected'>",
      "<specific wrong or inaccurate claim 2 if any>"
    ],
    "context_based_changes": [
      "<specific recommended change 1 to fix wrong information and align content with correct context>",
      "<specific recommended change 2 to fix wrong information and align content with correct context>"
    ]
  }},
  "seven_cs_evaluation": {{
    "Clear": "<1-2 sentence detailed evaluation on how clear the message and goals are>",
    "Concise": "<1-2 sentence detailed evaluation on whether it avoids fluff and redundant words>",
    "Correct": "<1-2 sentence detailed evaluation on grammar, spelling, facts, and formal tone — reference the {len(grammar_issues)} grammar issues found>",
    "Complete": "<1-2 sentence detailed evaluation on whether key slides/components are present>",
    "Courteous": "<1-2 sentence detailed evaluation on tone, professional level, and audience suitability>",
    "Concrete": "<1-2 sentence detailed evaluation on support by facts, metrics, or specific examples>",
    "Consistent": "<1-2 sentence detailed evaluation on formatting, bullet usage, style, and terminology consistency>"
  }},
  "seven_cs_scores": {{
    "Clear": <integer 0-100 based on clarity evaluation>,
    "Concise": <integer 0-100 based on conciseness evaluation>,
    "Correct": {computed_grammar_score},
    "Complete": <integer 0-100 based on completeness evaluation>,
    "Courteous": <integer 0-100 based on courteousness evaluation>,
    "Concrete": <integer 0-100 based on concreteness evaluation>,
    "Consistent": <integer 0-100 based on consistency evaluation>
  }},
  "strengths": [
    "<detailed strength 1 with slide reference>",
    "<detailed strength 2 with slide reference>",
    "<detailed strength 3 with slide reference>"
  ],
  "recommendations": [
    "<detailed recommendation 1 with slide reference>",
    "<detailed recommendation 2 with slide reference>",
    "<detailed recommendation 3 with slide reference>"
  ],
  "detailed_feedback": "<2-3 paragraph comprehensive analysis pointing out specific flaws, formatting issues, structure, and suggestions — mention grammar score of {computed_grammar_score}/100>",
  "improved_text": "<Complete, professional rewrite of the document content. Correct all errors, structure with clear slide headings, and present as a read-ready speech script.>"
}}

Original Presentation Text to Analyze:
{text}
"""
        
    elif module_type == 'speech':
        speech_speed_wpm = context_metrics.get("speech_speed_wpm", 130)
        filler_count = context_metrics.get("filler_count", 0)
        filler_percentage = context_metrics.get("filler_percentage", 0.0)
        repetition_count = context_metrics.get("repetition_count", 0)
        duration_seconds = context_metrics.get("duration_seconds", 0)

        # Attach grammar pre-pass summary if available
        grammar_section = f"""

--- GRAMMAR PRE-ANALYSIS (LanguageTool Cloud) ---
Grammar Quality Score: {computed_grammar_score}/100
Total Grammar/Spelling Issues Detected: {len(grammar_issues)}
{grammar_summary_text if grammar_summary_text else 'No grammar issues detected — transcript appears grammatically clean.'}
--- END GRAMMAR PRE-ANALYSIS ---
""" if grammar_issues or computed_grammar_score < 100 else ""

        analysis_prompt = f"""
You are an expert presentation coach and public speaking/communication consultant. Your job is to analyze the following speech transcript, identify all errors, grammatical mistakes, verbal pacing issues, and assess how well it adheres to the 7 Cs of Communication (Clear, Concise, Correct, Complete, Courteous, Concrete, Consistent).

IMPORTANT: A grammar pre-analysis has already been performed using LanguageTool. The grammar quality score is {computed_grammar_score}/100 based on {len(grammar_issues)} detected issues. Use this data to calibrate the 'Correct' dimension accurately.{grammar_section}
We have also calculated the following real-time speaking metrics from the audio recording for your context:
- Speaking pace: {speech_speed_wpm} WPM (optimal: 120-160 WPM)
- Filler words count: {filler_count} instances (filler percentage: {filler_percentage:.1f}%)
- Word repetition count: {repetition_count} instances
- Speaking duration: {duration_seconds} seconds

Using these metrics and the transcript text, generate a comprehensive report in JSON format.
Your response MUST be a single, valid JSON object matching the schema below. Do not wrap the JSON in markdown code blocks (e.g. ```json).

JSON Schema:
{{
  "overall_score": {overall_score},
  "category_scores": {{
    "Structure": <score 0-100 based on structure, organization of thoughts, and presence of introductory/concluding markers>,
    "Clarity": <score 0-100 based on ease of understanding, vocabulary choice, and vocal clarity indicated by pacing>,
    "Persuasion": <score 0-100 based on rhetorical appeal, conviction, and engagement level>,
    "Content_Quality": <score 0-100 based on argument depth, coherence, and logical connection of ideas>,
    "Call_to_Action": <score 0-100 based on presence of a clear concluding message, summary, or next steps>
  }},
  "seven_cs_evaluation": {{
    "Clear": "<1-2 sentence evaluation on the clarity of the speech message>",
    "Concise": "<1-2 sentence evaluation on wordiness, pacing, and filler word usage>",
    "Correct": "<1-2 sentence evaluation on grammatical accuracy — reference the {len(grammar_issues)} grammar issues detected by LanguageTool (score: {computed_grammar_score}/100)>",
    "Complete": "<1-2 sentence evaluation on whether the main point was thoroughly covered in the given duration>",
    "Courteous": "<1-2 sentence evaluation on professional tone, respectfulness, and reader-suitability>",
    "Concrete": "<1-2 sentence evaluation on focus, usage of specific details, data, or illustrative points>",
    "Consistent": "<1-2 sentence evaluation on uniformity of tone, phrasing, and speed consistency>"
  }},
  "seven_cs_scores": {{
    "Clear": <integer 0-100 based on clarity evaluation>,
    "Concise": <integer 0-100 based on conciseness evaluation>,
    "Correct": {computed_grammar_score},
    "Complete": <integer 0-100 based on completeness evaluation>,
    "Courteous": <integer 0-100 based on courteousness evaluation>,
    "Concrete": <integer 0-100 based on concreteness evaluation>,
    "Consistent": <integer 0-100 based on consistency evaluation>
  }},
  "strengths": [
    "<detailed strength 1 with transcript reference>",
    "<detailed strength 2 with transcript reference>",
    "<detailed strength 3 with transcript reference>"
  ],
  "recommendations": [
    "<actionable recommendations/corrections 1 with specific detail>",
    "<actionable recommendations/corrections 2 with specific detail>",
    "<actionable recommendations/corrections 3 with specific detail>"
  ],
  "detailed_feedback": "<2-3 paragraph comprehensive analysis pointing out specific vocal flaws, grammar issues (mention grammar score {computed_grammar_score}/100), pacing problems, and recommendations>",
  "improved_text": "<Complete, professional rewrite of the transcript. Remove all filler words (um, like, basically), repetitions, correct any grammatical errors, and format it with clear structural headings. This rewrite must be fully written out and ready to read aloud.>"
}}

Original Speech Transcript to Analyze:
{text}
"""
        
    elif module_type == 'live' and not insufficient_live_data:
        topic = context_metrics.get("topic", "General Topic")
        avg_eye = context_metrics.get("avg_eye", 0)
        avg_posture = context_metrics.get("avg_posture", 0)
        avg_wpm = context_metrics.get("avg_wpm", 0)
        fillers = context_metrics.get("fillers", 0)
        avg_qna = context_metrics.get("avg_qna", 0)
        overall_score = context_metrics.get("overall_execution", 0)

        # Attach grammar pre-pass summary for live transcript
        grammar_section = f"""

--- GRAMMAR PRE-ANALYSIS (LanguageTool Cloud) ---
Grammar Quality Score: {computed_grammar_score}/100
Total Grammar/Spelling Issues Detected: {len(grammar_issues)}
{grammar_summary_text if grammar_summary_text else 'No grammar issues detected — transcript appears grammatically clean.'}
--- END GRAMMAR PRE-ANALYSIS ---
""" if grammar_issues or computed_grammar_score < 100 else ""

        analysis_prompt = f"""
You are an expert presentation coach and public speaking/communication consultant. Your job is to analyze this live presentation summary and transcript, scoring the performance out of 100 based on the 7 Cs (Clear, Concise, Correct, Complete, Courteous, Concrete, Consistent).

IMPORTANT: A grammar pre-analysis has already been performed on the transcript using LanguageTool. Grammar score: {computed_grammar_score}/100 ({len(grammar_issues)} issues found). Use this to calibrate the 'Correct' dimension accurately.{grammar_section}
Presentation Context:
- Topic: {topic}
- Full Transcript: {text}
- Average Eye Contact Score: {avg_eye}/100
- Average Posture Score: {avg_posture}/100
- Average Speaking Pace: {avg_wpm} WPM
- Total Filler Words: {fillers}
- Q&A Panelist Interruption Score: {avg_qna}/100

Generate a comprehensive report in JSON format matching the schema below. Do not wrap in markdown tags.

JSON Schema:
{{
    "overall_score": {overall_score},
    "category_scores": {{
        "Structure": <score 0-100 based on organization and introductory/concluding markers>,
        "Clarity": <score 0-100 based on vocabulary choice, eye contact level, and pacing>,
        "Persuasion": <score 0-100 based on visual/vocal confidence and panel answers>,
        "Content_Quality": <score 0-100 based on response accuracy and argument depth>,
        "Call_to_Action": <score 0-100 based on concluding statements or key wrap-up points>
    }},
    "seven_cs_evaluation": {{
        "Clear": "<1-2 sentence detailed evaluation based on eye contact and clarity of delivery>",
        "Concise": "<1-2 sentence detailed evaluation based on verbal pacing and filler word usage>",
        "Correct": "<1-2 sentence evaluation on grammatical accuracy — reference grammar score {computed_grammar_score}/100 ({len(grammar_issues)} issues)>",
        "Complete": "<1-2 sentence detailed evaluation on topic coverage and response to panel questions>",
        "Courteous": "<1-2 sentence detailed evaluation on posture, examiner courtesy, and presenter demeanor>",
        "Concrete": "<1-2 sentence detailed evaluation on directness of answers and specificity of transcript content>",
        "Consistent": "<1-2 sentence detailed evaluation on posture stability and gaze pattern uniformity>"
    }},
    "seven_cs_scores": {{
        "Clear": <score 0-100>,
        "Concise": <score 0-100>,
        "Correct": {computed_grammar_score},
        "Complete": <score 0-100>,
        "Courteous": <score 0-100>,
        "Concrete": <score 0-100>,
        "Consistent": <score 0-100>
    }},
    "strengths": [
        "<strength 1 based on posture, eye contact or Q&A>",
        "<strength 2>",
        "<strength 3>"
    ],
    "recommendations": [
        "<improvement advice 1 regarding grammar, pacing, fillers or panel answers>",
        "<improvement advice 2>",
        "<improvement advice 3>"
    ],
    "qna_analysis": "<1-2 sentences evaluating student responses to interruptions>",
    "improved_text": "<Complete professional rewrite of the transcript. Clean up filler words, repetitions, correct all {len(grammar_issues)} grammar issues, structure with headings, and present as a read-ready speech script.>"
}}
"""

    # ===== RUN GEMINI INVOCATION =====
    if _gemini_provider.is_available() and analysis_prompt:
        try:
            analysis_json = _gemini_provider.generate_structured(analysis_prompt)
            if not isinstance(analysis_json, dict) or not analysis_json:
                raise ValueError("Gemini response is not a valid JSON dictionary")

            # Ensure document_name is set for document analysis
            if module_type == 'document' and 'document_name' not in analysis_json:
                analysis_json['document_name'] = context_metrics.get("filename", "presentation.pdf")

            # ===== ATTACH GRAMMAR DATA TO ALL MODULE RESPONSES =====
            # grammar_score and grammar_issues are always attached so the
            # frontend can show a grammar breakdown for every analysis type.
            analysis_json['grammar_score']  = computed_grammar_score
            analysis_json['grammar_issues'] = grammar_issues
            analysis_json['grammar_issues_count'] = len(grammar_issues)
            # Override Correct score with LanguageTool's authoritative value
            if 'seven_cs_scores' in analysis_json:
                analysis_json['seven_cs_scores']['Correct'] = computed_grammar_score
            if 'category_scores' in analysis_json and 'Grammar_and_Syntax' in analysis_json['category_scores']:
                analysis_json['category_scores']['Grammar_and_Syntax'] = computed_grammar_score

            return analysis_json
        except Exception as e:
            logger.warning("Global AI Evaluator: Gemini call failed (%s). Falling back to smart heuristics.", e)
            # Attach grammar data to fallback — all module types
            fallback_json['grammar_score']  = computed_grammar_score
            fallback_json['grammar_issues'] = grammar_issues
            fallback_json['grammar_issues_count'] = len(grammar_issues)
            if 'seven_cs_scores' in fallback_json:
                fallback_json['seven_cs_scores']['Correct'] = computed_grammar_score
            if 'category_scores' in fallback_json and 'Grammar_and_Syntax' in fallback_json['category_scores']:
                fallback_json['category_scores']['Grammar_and_Syntax'] = computed_grammar_score
            return fallback_json
    else:
        # Attach grammar data to fallback when Gemini is not available — all module types
        fallback_json['grammar_score']  = computed_grammar_score
        fallback_json['grammar_issues'] = grammar_issues
        fallback_json['grammar_issues_count'] = len(grammar_issues)
        if 'seven_cs_scores' in fallback_json:
            fallback_json['seven_cs_scores']['Correct'] = computed_grammar_score
        if 'category_scores' in fallback_json and 'Grammar_and_Syntax' in fallback_json['category_scores']:
            fallback_json['category_scores']['Grammar_and_Syntax'] = computed_grammar_score
        return fallback_json


def compare_documents(v1_text: str, v2_text: str, v1_score: int, v2_score: int, filename: str) -> dict:
    """
    Compares two versions of a presentation document.
    """
    # 1. Fallback JSON calculation
    score_diff = v2_score - v1_score
    improvements = []
    remaining = []
    
    if score_diff > 0:
        improvements.append(f"Overall presentation quality increased by {score_diff} points.")
        improvements.append("Enhanced slide layout and logical section flow.")
        improvements.append("Simplified language, improving clarity metrics.")
        improvements.append("Addressed main recommendations from Version 1 report.")
    elif score_diff == 0:
        improvements.append("Revisions were made, but overall score remained steady.")
        improvements.append("Minor adjustments in phrasing.")
    else:
        improvements.append("Minor edits made, but overall score decreased. Review structure.")
        
    if v2_score < 75:
        remaining.append("Continue working on bullet-point formatting to avoid text clutter.")
        remaining.append("Inject concrete statistics or metrics to make points more concrete.")
        remaining.append("Improve concluding call-to-action slide.")
    else:
        remaining.append("Polish speech delivery and pacing next.")
        
    synthesis = f"You made solid progress in revising this presentation. Your score moved from {v1_score}/100 to {v2_score}/100. The layout shows better organization and structure. Continue practicing your verbal delivery to match these visual improvements!"
    
    fallback_json = {
        "score_difference": score_diff,
        "key_improvements": improvements,
        "remaining_issues": remaining,
        "synthesis_summary": synthesis
    }
    
    # 2. Construct Prompt
    compare_prompt = f"""
Compare these two versions of a presentation and generate a structured JSON progress report.
Identify specific areas where the presenter improved grammar, formatting, clarity, structure, or content in Version 2 compared to Version 1. Also point out any remaining issues that still need attention.

JSON Schema output:
{{
  "score_difference": {score_diff},
  "key_improvements": [
    "<detailed improvement 1, e.g. Fixed spelling error in slide 2>",
    "<detailed improvement 2, e.g. Removed passive fillers and simplified slide 3>",
    "<detailed improvement 3>"
  ],
  "remaining_issues": [
    "<issue 1 still present in Version 2, e.g. slide 4 is still too wordy>",
    "<issue 2>"
  ],
  "synthesis_summary": "<1-2 paragraph description of the user's progress and coaching encouragement>"
}}

Version 1 Text:
{v1_text}

Version 2 Text:
{v2_text}
"""

    if _gemini_provider.is_available():
        try:
            result = _gemini_provider.generate_structured(compare_prompt)
            if isinstance(result, dict) and 'score_difference' in result:
                return result
            return fallback_json
        except Exception as e:
            logger.warning("Global AI Evaluator: Comparison call failed (%s). Using heuristics.", e)
            return fallback_json
    else:
        return fallback_json
