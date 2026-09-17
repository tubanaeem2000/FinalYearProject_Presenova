import React, { useState, useRef, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { useLiveSession } from '../hooks/useLiveSession';
import VideoCapture from '../components/VideoCapture';
import LiveFeedbackOverlay from '../components/LiveFeedbackOverlay';
import ReportDashboard from '../components/ReportDashboard';
import { downloadProgressReportPDF } from '../services/pdfGenerator';
import './LiveCoach.css';

/**
 * LiveCoach Page
 * Real-time presentation practice with webcam/mic tracking (eye contact, posture, pacing, filler words)
 * and academic-panel Q&A interruptions, scored via Gemini 7Cs evaluation.
 */

const LiveCoach: React.FC = () => {
  const { user } = useAuth();
  const userId = user?.id || 'guest';

  // ===== WIZARD STATE (kept for potential re-enable, unused while comparison is disabled) =====
  const [_step, _setStep] = useState(1);

  // Version 1 (single-session) states
  const [_v1SessionId, setV1SessionId] = useState<string | null>(null);
  const [v1Report, setV1Report] = useState<any | null>(null);
  const [v1Topic, setV1Topic] = useState('');



  // Live session interactive state
  const [topic, setTopic] = useState('');
  const [seconds, setSeconds] = useState(0);
  const [answerText, setAnswerText] = useState('');
  const [cameraError, setCameraError] = useState<string | null>(null);

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const timerRef = useRef<any>(null);

  const {
    status,
    sessionId,
    currentQuestion,
    realtimeFeedback,
    hasHistory,
    historySummary,
    finalReport,
    error,
    sttAvailable,
    startSession,
    sendAnswer,
    stopSession,
  } = useLiveSession({ userId, videoRef });

  // Handle timer
  useEffect(() => {
    if (status === 'STREAMING') {
      timerRef.current = setInterval(() => {
        setSeconds((prev) => prev + 1);
      }, 1000);
    } else {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, [status]);

  // Save session report (always V1 — comparison disabled)
  useEffect(() => {
    if (status === 'FINISHED' && finalReport && sessionId) {
      if (!v1Report) {
        setV1Report(finalReport);
        setV1SessionId(sessionId);
        setV1Topic(topic);
      }
    }
  }, [status, finalReport, sessionId, topic, v1Report]);

  const handleStart = (e: React.FormEvent) => {
    e.preventDefault();
    if (!topic.trim()) return;
    setSeconds(0);
    setCameraError(null);
    startSession(topic);
  };

  const handleFinish = () => {
    stopSession();
  };

  const handleAnswerSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!answerText.trim()) return;
    sendAnswer(answerText);
    setAnswerText('');
  };



  // ===== DOWNLOAD REPORT (single-session — comparison disabled) =====
  const handleDownloadReport = () => {
    if (!v1Report) return;

    const categoryScores = [
      { name: 'Structure', v1: v1Report.category_scores?.Structure || 0, v2: v1Report.category_scores?.Structure || 0 },
      { name: 'Clarity', v1: v1Report.category_scores?.Clarity || 0, v2: v1Report.category_scores?.Clarity || 0 },
      { name: 'Persuasion', v1: v1Report.category_scores?.Persuasion || 0, v2: v1Report.category_scores?.Persuasion || 0 },
      { name: 'Content Quality', v1: v1Report.category_scores?.Content_Quality || 0, v2: v1Report.category_scores?.Content_Quality || 0 },
      { name: 'Call to Action', v1: v1Report.category_scores?.Call_to_Action || 0, v2: v1Report.category_scores?.Call_to_Action || 0 },
    ];

    const additionalMetrics = [
      { label: 'Average Eye Contact', v1: `${v1Report.session_metrics?.avg_eye_contact ?? 0}%`, v2: `${v1Report.session_metrics?.avg_eye_contact ?? 0}%`, change: '' },
      { label: 'Body Posture Accuracy', v1: `${v1Report.session_metrics?.avg_posture ?? 0}%`, v2: `${v1Report.session_metrics?.avg_posture ?? 0}%`, change: '' },
      { label: 'Average Confidence', v1: `${v1Report.session_metrics?.avg_confidence ?? 0}%`, v2: `${v1Report.session_metrics?.avg_confidence ?? 0}%`, change: '' },
      { label: 'Vocal Pitch Dynamics', v1: `${v1Report.session_metrics?.avg_vocal_pitch ?? 0}%`, v2: `${v1Report.session_metrics?.avg_vocal_pitch ?? 0}%`, change: '' },
      { label: 'Speaking Pace', v1: `${v1Report.session_metrics?.avg_wpm ?? 0} WPM`, v2: `${v1Report.session_metrics?.avg_wpm ?? 0} WPM`, change: '' },
      { label: 'Filler Words Count', v1: `${v1Report.session_metrics?.total_fillers ?? 0}`, v2: `${v1Report.session_metrics?.total_fillers ?? 0}`, change: '' },
      { label: 'Questions Handled', v1: `${v1Report.session_metrics?.interruptions_handled ?? 0}`, v2: `${v1Report.session_metrics?.interruptions_handled ?? 0}`, change: '' },
    ];

    downloadProgressReportPDF({
      title: 'Live Presentation Report',
      documentName: v1Topic || v1Report.topic || 'Live Practice Session',
      v1Score: v1Report.overall_score,
      v2Score: v1Report.overall_score,
      gain: 0,
      categoryScores,
      synthesis: v1Report.detailed_feedback || 'Your live presentation session has been analyzed.',
      improvements: v1Report.recommendations || [],
      remaining: [],
      additionalMetrics,
    }, 'Live_Coaching_Report.pdf');
  };



  const handleReset = () => {
    setTopic('');
    setSeconds(0);
    setAnswerText('');
    setCameraError(null);
    setV1SessionId(null);
    setV1Report(null);
    setV1Topic('');


  };

  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60).toString().padStart(2, '0');
    const s = (secs % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  };

  const isSessionActive = status === 'STREAMING' || status === 'INTERRUPTED_Q&A' || status === 'REPORT_GENERATING';

  return (
    <div className="live-coach-page container">


      {/* ACTIVE PRESENTATION HUD */}
      {isSessionActive && (
        <>
          {status === 'STREAMING' && (
            <div className="practice-arena fadeIn">
              {cameraError && (
                <div style={{ background: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.4)', color: '#fca5a5', padding: '10px 14px', borderRadius: '8px', marginBottom: '12px', fontSize: '14px', width: '100%', gridColumn: '1 / -1' }}>
                  <strong>⚠️ Camera Access Error:</strong> {cameraError} Please grant camera permissions or ensure no other app is using your webcam.
                </div>
              )}
              {error && (
                <div style={{ background: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.4)', color: '#fca5a5', padding: '10px 14px', borderRadius: '8px', marginBottom: '12px', fontSize: '14px', width: '100%', gridColumn: '1 / -1' }}>
                  <strong>⚠️ Session Error:</strong> {error}
                </div>
              )}
              {!sttAvailable && (
                <div style={{ background: 'rgba(245, 158, 11, 0.12)', border: '1px solid rgba(245, 158, 11, 0.35)', color: '#fbbf24', padding: '10px 14px', borderRadius: '8px', marginBottom: '12px', fontSize: '14px', width: '100%', gridColumn: '1 / -1' }}>
                  <strong>🎤 Voice scoring unavailable:</strong> Speech-to-text isn't configured on the server, so Speaking Pace, Filler Words, and Vocal Pitch Dynamics won't be tracked this session (they'll show 0, not a reflection of your delivery). Eye Contact, Posture, and Confidence are unaffected.
                </div>
              )}
              <div className="arena-left-pane">
                <div className="video-box-wrapper">
                  <VideoCapture 
                    videoRef={videoRef} 
                    isStreaming={true} 
                    onError={(msg) => setCameraError(msg)} 
                  />
                  <LiveFeedbackOverlay
                    eyeContact={realtimeFeedback.eyeContact}
                    posture={realtimeFeedback.posture}
                    hint={realtimeFeedback.hint}
                    isStreaming={true}
                    confidence={realtimeFeedback.confidence}
                    emotion={realtimeFeedback.emotion}
                  />
                </div>
                
                <div className="controls-hud">
                  <div className="timer-badge">{formatTime(seconds)}</div>
                  <button className="finish-btn-premium" onClick={handleFinish}>
                    Finish Presentation
                  </button>
                </div>
              </div>

              <div className="arena-right-pane">
                <div className="coach-feedback-hud">
                  <h2>Real-Time Metrics</h2>
                  <div className="meter-grid">
                    <div className="meter-card-hud">
                      <span className="meter-hud-lbl">Eye Contact</span>
                      <div className="meter-hud-ring-wrapper">
                        <span className="meter-hud-num">{realtimeFeedback.eyeContact}%</span>
                      </div>
                    </div>
                    <div className="meter-card-hud">
                      <span className="meter-hud-lbl">Body Posture</span>
                      <div className="meter-hud-ring-wrapper">
                        <span className="meter-hud-num">{realtimeFeedback.posture}%</span>
                      </div>
                    </div>
                    <div className="meter-card-hud">
                      <span className="meter-hud-lbl">Confidence</span>
                      <div className="meter-hud-ring-wrapper">
                        <span className="meter-hud-num">{realtimeFeedback.confidence}%</span>
                      </div>
                    </div>
                  </div>
                  {realtimeFeedback.emotion && (
                    <div style={{ marginTop: '1rem', padding: '0.6rem', background: 'rgba(255,255,255,0.05)', borderRadius: '6px', textAlign: 'center', border: '1px solid rgba(255,255,255,0.1)' }}>
                      <span style={{ fontSize: '0.7rem', color: '#94a3b8', display: 'block', marginBottom: '0.2rem', fontWeight: 600, letterSpacing: '0.05em' }}>FACIAL EMOTION</span>
                      <span style={{ fontSize: '1rem', fontWeight: 800, color: '#6366f1', textTransform: 'uppercase' }}>{realtimeFeedback.emotion}</span>
                    </div>
                  )}

                  {hasHistory && historySummary && (
                    <div className="hud-memory-card">
                      <h4>Topic Target Target</h4>
                      <p>In your last session for this topic, your score was {historySummary.previous_score}. Keep an eye on:</p>
                      <ul>
                        {historySummary.top_recommendations.map((rec: string, i: number) => (
                          <li key={i}>{rec}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {status === 'INTERRUPTED_Q&A' && (
            <div className="interruption-modal fadeIn">
              <div className="interruption-card">
                <div className="panelist-indicator">
                  <span className="panelist-avatar">P</span>
                  <div>
                    <h3>Academic Examiner</h3>
                    <span className="question-status-badge">QUESTION DETECTED</span>
                  </div>
                </div>

                <p className="interruption-question">"{currentQuestion}"</p>

                <form onSubmit={handleAnswerSubmit} className="answer-form">
                  <textarea
                    placeholder="Formulate and type your answer here..."
                    value={answerText}
                    onChange={(e) => setAnswerText(e.target.value)}
                    required
                    className="answer-textarea"
                    rows={4}
                  />
                  <button type="submit" className="submit-answer-btn">
                    Submit Response
                  </button>
                </form>
              </div>
            </div>
          )}

          {status === 'REPORT_GENERATING' && (
            <div className="generating-card fadeIn">
              <div className="spinner-hud"></div>
              <h2>Compiling Presentation Analytics</h2>
              <p>Processing vocal dynamics, eye-gaze tracking frames, and panel responses...</p>
            </div>
          )}
        </>
      )}

      {/* STATIC SCREENS (When session is NOT active) */}
      {!isSessionActive && (
        <>
          {v1Report ? (
            <>
              <div style={{ display: 'flex', justifyContent: 'flex-end', margin: '1rem 0' }}>
                <button
                  onClick={handleDownloadReport}
                  className="start-btn-premium"
                  style={{ margin: 0, padding: '0.6rem 2rem', fontSize: '0.95rem' }}
                >
                  Download Report
                </button>
              </div>
              <ReportDashboard 
                report={v1Report} 
                onReset={handleReset} 
                resetButtonLabel="Practice New Topic"
              />
            </>
          ) : (
            <div className="topic-selector-card fadeIn">
              <span className="coach-badge">LIVE PRACTICE SESSION</span>
              <h1>Interactive Presentation Practice</h1>
              <p className="subtitle">
                Enter a presentation topic. The coach will track your visual presence, eye contact, posture, and pacing. 
                An academic panel will occasionally interrupt you with real-time questions to test your depth.
              </p>

              <form onSubmit={handleStart} className="topic-form">
                <input
                  type="text"
                  placeholder="e.g., Blockchain Scaling, Machine Learning in Health..."
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  required
                  className="topic-input"
                />
                <button type="submit" className="start-btn-premium">
                  Start Practice Session
                </button>
              </form>
            </div>
          )}


        </>
      )}

      {error && (
        <div className="error-alert">
          <span>Error:</span> {error}
        </div>
      )}
    </div>
  );
};

export default LiveCoach;