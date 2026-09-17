import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  generatePresentation,
  generateOutline,
  generateFromOutline,
  importSeedFile,
  getGeneratorDownloadUrl,
  PresentationGenResponse,
  PresentationOutline,
  SlideOutline
} from '../services/presentationGeneratorApi';
import './PresentationGenerator.css';

interface SlideCountOption {
  count: number;
  label: string;
  isPaid?: boolean;
}

const SLIDE_COUNTS: SlideCountOption[] = [
  { count: 5, label: '5 Slides' },
  { count: 10, label: '10 Slides' },
  { count: 15, label: '15 Slides' },
  { count: 20, label: '20 Slides', isPaid: true },
];
const TONES = [
  { id: 'Professional', label: '🎯 Professional' },
  { id: 'Educational', label: '🎓 Educational' },
  { id: 'Persuasive', label: '🚀 Persuasive' },
  { id: 'Inspirational', label: '💡 Inspirational' }
];

const THEMES = [
  { id: 'corporate_blue_geom', name: 'Corporate Geometric', color: '#0096c7', bg: '#0b2545', desc: 'Navy & Cyan with Geometric Corner Chevrons' },
  { id: 'modern_infographic_yellow', name: 'Yellow & Slate Infographic', color: '#eab308', bg: '#0f172a', desc: 'Slate Charcoal & Vibrant Yellow Accent Bar' },
  { id: 'creative_editorial', name: 'Creative Editorial', color: '#ea580c', bg: '#fdfbf7', desc: 'Sura Magazine Sand & Terracotta Minimalist' },
  { id: 'corporate_clean', name: 'Corporate Clean', color: '#0284c7', bg: '#ffffff', desc: 'Minimalist Slate & Studio Sky Blue' },
  { id: 'modern_dark', name: 'Modern Dark', color: '#38bdf8', bg: '#0f172a', desc: 'Sleek Obsidian & Neon Cyan' },
  { id: 'creative_neon', name: 'Creative Neon', color: '#f43f5e', bg: '#18181b', desc: 'Vibrant Rose & Charcoal' },
  { id: 'academic_elegant', name: 'Academic Gold', color: '#f59e0b', bg: '#1e293b', desc: 'Elegant Gold & Dark Navy' }
];

const LAYOUT_OPTIONS = [
  { id: 'horizontal_pills', label: '🎯 Overview & Objectives (A, B, C Cards)', badge: 'A-B-C Pills' },
  { id: 'swot', label: '🛡️ SWOT Analysis (4-Pillar Matrix)', badge: 'SWOT Matrix' },
  { id: 'chart', label: '📊 Visual Chart / Financial Metrics', badge: 'Visual Chart' },
  { id: 'circular_dials', label: '⭕ Circular Percentage Progress Dials', badge: 'Circular Dials' },
  { id: 'process_chevrons', label: '⏩ Process Step Chevrons (1 ➔ 2 ➔ 3 ➔ 4)', badge: 'Chevrons' },
  { id: 'team_personas', label: '👥 Team & Leadership Cards (Headshots)', badge: 'Team Cards' },
  { id: 'editorial_split', label: '📰 Editorial Magazine Photo Split', badge: 'Editorial Split' },
  { id: 'stat_callout', label: '📈 Stat Callouts & Big KPI Numbers', badge: 'Stat KPI' },
  { id: 'timeline', label: '⏱️ Sequential Phased Roadmap', badge: 'Roadmap' },
  { id: 'comparison_grid', label: '🗂️ 2-3 Column Architecture Grid', badge: 'Grid Cards' },
  { id: 'visual_split', label: '📸 Visual Split Photo & Key Bullets', badge: 'Visual Split' }
];

type WizardStep = 1 | 2 | 3 | 4;
type InputMode = 'prompt' | 'document';

const PresentationGenerator: React.FC = () => {
  const navigate = useNavigate();

  // Wizard state
  const [step, setStep] = useState<WizardStep>(1);
  const [inputMode, setInputMode] = useState<InputMode>('prompt');

  // Input state
  const [topic, setTopic] = useState('');
  const [seedFile, setSeedFile] = useState<File | null>(null);
  const [slideCount, setSlideCount] = useState(5);
  const [tone, setTone] = useState('Professional');
  const [theme, setTheme] = useState('corporate_blue_geom');
  const [audience, setAudience] = useState('General Audience');

  // Custom theme overrides
  const [showSlideNumbers, setShowSlideNumbers] = useState(true);
  const [confidentialityTag, setConfidentialityTag] = useState('Presenova AI Presentation');

  // Multi-stage outline state
  const [outline, setOutline] = useState<PresentationOutline | null>(null);
  const [activeSlideIdx, setActiveSlideIdx] = useState<number>(0);

  // Status state
  const [loading, setLoading] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PresentationGenResponse | null>(null);

  // User plan state (Free trial vs Pro)
  const [isProUser, setIsProUser] = useState<boolean>(() => {
    return localStorage.getItem('presenova_user_plan') === 'pro';
  });
  const [showUpgradeModal, setShowUpgradeModal] = useState<boolean>(false);
  const [upgradeToast, setUpgradeToast] = useState<string | null>(null);

  const handleSelectSlideCount = (opt: SlideCountOption) => {
    if (opt.isPaid && !isProUser) {
      setShowUpgradeModal(true);
      return;
    }
    setSlideCount(opt.count);
  };

  const handleActivatePro = () => {
    localStorage.setItem('presenova_user_plan', 'pro');
    setIsProUser(true);
    setSlideCount(20);
    setShowUpgradeModal(false);
    setUpgradeToast('👑 Presenova Pro Activated! 20 Slides unlocked.');
    setTimeout(() => setUpgradeToast(null), 5000);
  };

  const handleDowngradeToFree = () => {
    localStorage.removeItem('presenova_user_plan');
    setIsProUser(false);
    if (slideCount > 15) setSlideCount(15);
    setUpgradeToast('Switched back to Free Trial (Up to 15 Slides).');
    setTimeout(() => setUpgradeToast(null), 4000);
  };

  // 1. Fetch Outline from Prompt or File Seed (Step 1 -> Step 2)
  const handleProceedToOutline = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();

    if (inputMode === 'prompt' && !topic.trim()) {
      setError('Please enter a presentation topic or prompt.');
      return;
    }
    if (inputMode === 'document' && !seedFile) {
      setError('Please select or drag-and-drop a document (.pdf, .docx, .pptx).');
      return;
    }

    if (slideCount > 15 && !isProUser) {
      setShowUpgradeModal(true);
      return;
    }

    setLoading(true);
    setLoadingMessage(inputMode === 'document' ? 'Parsing document seed and synthesizing outline...' : 'Generating structured outline & assigning smart visual layouts...');
    setError(null);

    try {
      if (inputMode === 'document' && seedFile) {
        const resp = await importSeedFile(seedFile, {
          slide_count: slideCount,
          tone,
          target_audience: audience.trim() || 'General Audience'
        });
        setOutline(resp.outline);
        setTopic(resp.outline.topic || seedFile.name);
      } else {
        const resp = await generateOutline({
          topic: topic.trim(),
          slide_count: slideCount,
          tone,
          target_audience: audience.trim() || 'General Audience'
        });
        setOutline(resp.outline);
      }
      setActiveSlideIdx(0);
      setStep(2);
    } catch (err: any) {
      setError(err.message || 'Failed to generate presentation outline.');
    } finally {
      setLoading(false);
    }
  };

  // 2. Direct 1-Click Fast Generation
  const handleFastGenerate = async () => {
    if (!topic.trim() && !seedFile) {
      setError('Please provide a topic or upload a document.');
      return;
    }

    setLoading(true);
    setLoadingMessage('Compiling presentation and rendering visual diagrams...');
    setError(null);

    try {
      if (seedFile) {
        const seedResp = await importSeedFile(seedFile, { slide_count: slideCount, tone, target_audience: audience });
        const finalResp = await generateFromOutline({
          outline: seedResp.outline,
          theme,
          custom_overrides: { show_slide_numbers: showSlideNumbers, confidentiality_tag: confidentialityTag }
        });
        setResult(finalResp);
        setOutline(seedResp.outline);
      } else {
        const finalResp = await generatePresentation({
          topic: topic.trim(),
          slide_count: slideCount,
          tone,
          theme,
          target_audience: audience.trim() || 'General Audience'
        });
        setResult(finalResp);
        if (finalResp.outline) setOutline(finalResp.outline);
      }
      setStep(4);
    } catch (err: any) {
      setError(err.message || 'Failed to generate presentation.');
    } finally {
      setLoading(false);
    }
  };

  // 3. Final Compilation from Confirmed Outline (Step 3 -> Step 4)
  const handleCompileFinalDeck = async () => {
    if (!outline) {
      setError('Outline is missing. Please restart generation.');
      return;
    }

    setLoading(true);
    setLoadingMessage('Generating visual charts with matplotlib and building PowerPoint slides...');
    setError(null);

    try {
      const finalResp = await generateFromOutline({
        outline,
        theme,
        custom_overrides: {
          show_slide_numbers: showSlideNumbers,
          confidentiality_tag: confidentialityTag
        }
      });
      setResult(finalResp);
      setStep(4);
    } catch (err: any) {
      setError(err.message || 'Failed to construct presentation.');
    } finally {
      setLoading(false);
    }
  };

  // Outline Editing Helpers
  const updateSlideTitle = (idx: number, newTitle: string) => {
    if (!outline) return;
    const updated = { ...outline };
    updated.slides[idx].title = newTitle;
    setOutline(updated);
  };

  const updateSlideLayout = (idx: number, newLayout: string) => {
    if (!outline) return;
    const updated = { ...outline };
    updated.slides[idx].suggested_layout = newLayout;
    updated.slides[idx].type = newLayout;
    setOutline(updated);
  };

  const deleteSlide = (idx: number) => {
    if (!outline || outline.slides.length <= 3) {
      setError('A presentation must have at least 3 slides.');
      return;
    }
    const updated = { ...outline };
    updated.slides.splice(idx, 1);
    // renumber
    updated.slides.forEach((s, i) => { s.slide_number = i + 1; });
    setOutline(updated);
    setActiveSlideIdx(Math.max(0, idx - 1));
  };

  const addSlide = () => {
    if (!outline || outline.slides.length >= 15) return;
    const updated = { ...outline };
    const newIdx = updated.slides.length + 1;
    const newSlide: SlideOutline = {
      slide_number: newIdx,
      title: `Strategic Focus Area #${newIdx - 2}`,
      key_takeaway: 'Key operational priority and objectives',
      type: 'chart',
      suggested_layout: 'chart',
      chart_data: {
        chart_type: 'bar',
        title: 'Projected Metric Growth',
        labels: ['Target A', 'Target B', 'Target C', 'Target D'],
        values: [45, 70, 88, 95]
      },
      bullets: [
        'Establish reliable benchmarks for operational efficiency.',
        'Continuous monitoring across target parameters.',
        'Deliver measurable impact according to project timeline.'
      ],
      speaker_notes: 'Highlight target performance metrics and operational significance.'
    };
    updated.slides.push(newSlide);
    setOutline(updated);
    setActiveSlideIdx(updated.slides.length - 1);
  };

  const resetAll = () => {
    setStep(1);
    setResult(null);
    setOutline(null);
    setError(null);
    setTopic('');
    setSeedFile(null);
  };

  return (
    <div className="pg-page">
      {/* HERO HEADER */}
      <div className="pg-hero">
        <div className="pg-hero-badge">⚡ Presenova Studio • Gamma-Style Visual Engine</div>
        <h1 className="pg-hero-title">AI Presentation Creator</h1>
        <p className="pg-hero-subtitle">
          Transform topics or existing documents into styled, visual PowerPoint decks.
          Generates empirical charts, KPI callouts, process chevrons, and 6x6 bullet cards locally!
        </p>

        {/* PROGRESS STEPPER */}
        <div className="pg-stepper">
          <div className={`pg-step-item ${step >= 1 ? 'active' : ''} ${step === 1 ? 'current' : ''}`} onClick={() => step > 1 && setStep(1)}>
            <span className="pg-step-num">1</span>
            <span className="pg-step-txt">Input & Seed</span>
          </div>
          <div className="pg-step-line" />
          <div className={`pg-step-item ${step >= 2 ? 'active' : ''} ${step === 2 ? 'current' : ''}`} onClick={() => outline && setStep(2)}>
            <span className="pg-step-num">2</span>
            <span className="pg-step-txt">Outline Checkpoint</span>
          </div>
          <div className="pg-step-line" />
          <div className={`pg-step-item ${step >= 3 ? 'active' : ''} ${step === 3 ? 'current' : ''}`} onClick={() => outline && setStep(3)}>
            <span className="pg-step-num">3</span>
            <span className="pg-step-txt">Theme & Visuals</span>
          </div>
          <div className="pg-step-line" />
          <div className={`pg-step-item ${step >= 4 ? 'active' : ''} ${step === 4 ? 'current' : ''}`}>
            <span className="pg-step-num">4</span>
            <span className="pg-step-txt">Download & Rehearse</span>
          </div>
        </div>
      </div>

      {error && <div className="pg-alert pg-alert-error">{error}</div>}

      {/* STEP 1: INPUT INGESTION */}
      {step === 1 && (
        <div className="pg-step-card">
          <div className="pg-tabs-header">
            <button
              type="button"
              className={`pg-tab-btn ${inputMode === 'prompt' ? 'active' : ''}`}
              onClick={() => { setInputMode('prompt'); setError(null); }}
            >
              ✍️ Prompt or Topic
            </button>
            <button
              type="button"
              className={`pg-tab-btn ${inputMode === 'document' ? 'active' : ''}`}
              onClick={() => { setInputMode('document'); setError(null); }}
            >
              📂 Upload Document Seed (.pptx, .pdf, .docx)
            </button>
          </div>

          <form onSubmit={handleProceedToOutline} className="pg-form">
            {inputMode === 'prompt' ? (
              <div className="pg-field">
                <label className="pg-label">Presentation Topic or Executive Prompt <span className="req">*</span></label>
                <textarea
                  className="pg-textarea"
                  rows={3}
                  placeholder="e.g. Autonomous Driving Systems, Generative AI in Healthcare, or FYP Thesis Defense"
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  disabled={loading}
                />
              </div>
            ) : (
              <div className="pg-field">
                <label className="pg-label">Select Document to Ingest & Transform <span className="req">*</span></label>
                <div className="pg-file-dropzone">
                  <input
                    type="file"
                    id="seed-file-input"
                    accept=".pdf,.docx,.pptx"
                    onChange={(e) => {
                      if (e.target.files && e.target.files[0]) {
                        setSeedFile(e.target.files[0]);
                        if (!topic) setTopic(e.target.files[0].name.replace(/\.[^/.]+$/, ''));
                      }
                    }}
                    style={{ display: 'none' }}
                  />
                  <label htmlFor="seed-file-input" className="pg-dropzone-label">
                    <span className="pg-dropzone-icon">📄</span>
                    {seedFile ? (
                      <div className="pg-file-selected">
                        <strong>Selected:</strong> {seedFile.name} ({(seedFile.size / 1024).toFixed(1)} KB)
                        <span className="pg-reselect-link">Click to choose another</span>
                      </div>
                    ) : (
                      <div>
                        <strong>Click to upload</strong> or drag document here
                        <p className="pg-dropzone-sub">Supports .pptx, .pdf, .docx (Max 25 MB)</p>
                      </div>
                    )}
                  </label>
                </div>
              </div>
            )}

            {/* Slide Count Selection */}
            <div className="pg-field">
              <div className="pg-label-row">
                <label className="pg-label">Target Slide Count</label>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span className={`pg-plan-tag ${isProUser ? 'pro' : ''}`}>
                    {isProUser ? '👑 Pro Plan Active (20 Slides Unlocked)' : '🎁 Free Trial (Up to 15 Slides)'}
                  </span>
                  {isProUser && (
                    <button
                      type="button"
                      onClick={handleDowngradeToFree}
                      style={{ background: 'none', border: 'none', color: '#64748b', fontSize: '0.75rem', cursor: 'pointer', textDecoration: 'underline' }}
                      title="Switch back to Free Trial for testing"
                    >
                      (Reset to Free)
                    </button>
                  )}
                </div>
              </div>

              {upgradeToast && (
                <div style={{
                  background: 'rgba(234, 179, 8, 0.15)',
                  border: '1px solid rgba(234, 179, 8, 0.4)',
                  color: '#facc15',
                  padding: '0.5rem 0.85rem',
                  borderRadius: '0.5rem',
                  fontSize: '0.85rem',
                  marginBottom: '0.65rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem'
                }}>
                  {upgradeToast}
                </div>
              )}

              <div className="pg-count-group">
                {SLIDE_COUNTS.map((opt) => {
                  const isSelected = slideCount === opt.count;
                  return (
                    <button
                      key={opt.count}
                      type="button"
                      className={`pg-count-btn ${isSelected ? 'active' : ''} ${opt.isPaid ? 'pg-count-btn-pro' : ''}`}
                      onClick={() => handleSelectSlideCount(opt)}
                      disabled={loading}
                      title={opt.isPaid && !isProUser ? '20 Slides requires Pro Plan' : `${opt.count} Slides`}
                    >
                      <span className="pg-count-num">{opt.count} Slides</span>
                      {opt.isPaid ? (
                        <span className={`pg-badge-pro ${isProUser ? 'unlocked' : 'locked'}`}>
                          {isProUser ? 'PRO UNLOCKED' : 'PAID 👑'}
                        </span>
                      ) : (
                        <span className="pg-badge-free">FREE</span>
                      )}
                    </button>
                  );
                })}
              </div>

              <div className="pg-slide-tier-hint">
                <span>
                  🎁 <strong>Free Trial:</strong> generate up to <strong>15 slides</strong>. <strong>20 Slides</strong> is a Paid feature.
                </span>
                {!isProUser && (
                  <button
                    type="button"
                    className="pg-unlock-link"
                    onClick={() => setShowUpgradeModal(true)}
                  >
                    Unlock 20 Slides 👑
                  </button>
                )}
              </div>
            </div>

            {/* Tone & Audience */}
            <div className="pg-row-fields">
              <div className="pg-field">
                <label className="pg-label">Delivery Tone</label>
                <select
                  className="pg-select"
                  value={tone}
                  onChange={(e) => setTone(e.target.value)}
                  disabled={loading}
                >
                  {TONES.map((t) => (
                    <option key={t.id} value={t.id}>{t.label}</option>
                  ))}
                </select>
              </div>

              <div className="pg-field">
                <label className="pg-label">Target Audience</label>
                <input
                  type="text"
                  className="pg-input"
                  placeholder="e.g. Thesis Committee, Executive Board, Students"
                  value={audience}
                  onChange={(e) => setAudience(e.target.value)}
                  disabled={loading}
                />
              </div>
            </div>

            {/* Action Buttons */}
            <div className="pg-action-group">
              <button
                type="submit"
                className="pg-btn pg-btn-primary"
                disabled={loading}
              >
                {loading ? 'Processing...' : 'Next: Review & Customize Outline ➔'}
              </button>

              <button
                type="button"
                className="pg-btn pg-btn-secondary"
                onClick={handleFastGenerate}
                disabled={loading}
              >
                ⚡ 1-Click Fast Generate (.pptx)
              </button>
            </div>
          </form>
        </div>
      )}

      {/* STEP 2: NARRATIVE OUTLINE CHECKPOINT */}
      {step === 2 && outline && (
        <div className="pg-step-card">
          <div className="pg-card-top-bar">
            <div>
              <h2 className="pg-card-title">📋 Outline Review & Smart Layout Assignment</h2>
              <p className="pg-card-sub">
                Gamma Checkpoint: Review card headings and choose the visual archetype (Chart, Stat, Timeline, Comparison) before rendering.
              </p>
            </div>
            <button type="button" className="pg-btn-sm" onClick={addSlide}>+ Add Slide Card</button>
          </div>

          <div className="pg-outline-grid">
            {/* Outline list */}
            <div className="pg-outline-list">
              {outline.slides.map((s, idx) => (
                <div
                  key={idx}
                  className={`pg-outline-item ${activeSlideIdx === idx ? 'selected' : ''}`}
                  onClick={() => setActiveSlideIdx(idx)}
                >
                  <div className="pg-outline-item-num">0{s.slide_number}</div>
                  <div className="pg-outline-item-info">
                    <div className="pg-outline-item-title">{s.title}</div>
                    <span className="pg-layout-pill">
                      {LAYOUT_OPTIONS.find(l => l.id === s.suggested_layout)?.badge || 'Slide Card'}
                    </span>
                  </div>
                  {outline.slides.length > 3 && idx > 0 && (
                    <button
                      type="button"
                      className="pg-delete-btn"
                      title="Delete Slide"
                      onClick={(e) => { e.stopPropagation(); deleteSlide(idx); }}
                    >
                      ✕
                    </button>
                  )}
                </div>
              ))}
            </div>

            {/* Active Slide Card Inspector */}
            {outline.slides[activeSlideIdx] && (
              <div className="pg-slide-inspector">
                <div className="pg-inspector-badge">Editing Slide #{outline.slides[activeSlideIdx].slide_number}</div>

                <div className="pg-field">
                  <label className="pg-label">Slide Title</label>
                  <input
                    type="text"
                    className="pg-input"
                    value={outline.slides[activeSlideIdx].title}
                    onChange={(e) => updateSlideTitle(activeSlideIdx, e.target.value)}
                  />
                </div>

                <div className="pg-field">
                  <label className="pg-label">Visual Layout Archetype</label>
                  <select
                    className="pg-select"
                    value={outline.slides[activeSlideIdx].suggested_layout || outline.slides[activeSlideIdx].type || 'split'}
                    onChange={(e) => updateSlideLayout(activeSlideIdx, e.target.value)}
                  >
                    {LAYOUT_OPTIONS.map((lo) => (
                      <option key={lo.id} value={lo.id}>{lo.label}</option>
                    ))}
                  </select>
                </div>

                {outline.slides[activeSlideIdx].suggested_layout === 'horizontal_pills' && (
                  <div className="pg-layout-note">
                    <span className="pg-note-icon">🎯</span>
                    <span><strong>Overview & Objectives:</strong> 3 stacked horizontal cards with circular letter badges (A, B, C) and clear strategic descriptions.</span>
                  </div>
                )}

                {outline.slides[activeSlideIdx].suggested_layout === 'swot' && (
                  <div className="pg-layout-note">
                    <span className="pg-note-icon">🛡️</span>
                    <span><strong>SWOT Analysis Matrix:</strong> 4 vertical pillar columns (Strengths, Weaknesses, Opportunities, Threats) with color-graded headers.</span>
                  </div>
                )}

                {outline.slides[activeSlideIdx].suggested_layout === 'circular_dials' && (
                  <div className="pg-layout-note">
                    <span className="pg-note-icon">⭕</span>
                    <span><strong>Circular Progress Dials:</strong> 3-4 circular progress gauges (e.g. 85%, 65%, 94%) rendered with Matplotlib alongside takeaway notes.</span>
                  </div>
                )}

                {outline.slides[activeSlideIdx].suggested_layout === 'process_chevrons' && (
                  <div className="pg-layout-note">
                    <span className="pg-note-icon">⏩</span>
                    <span><strong>Process Step Chevrons:</strong> Sequential interconnected arrow chevron cards (Step 01 ➔ Step 02 ➔ Step 03 ➔ Step 04).</span>
                  </div>
                )}

                {outline.slides[activeSlideIdx].suggested_layout === 'team_personas' && (
                  <div className="pg-layout-note">
                    <span className="pg-note-icon">👥</span>
                    <span><strong>Team & Leadership Cards:</strong> 3 profile cards with circular portrait headshots, names, roles, and bio summaries.</span>
                  </div>
                )}

                {outline.slides[activeSlideIdx].suggested_layout === 'editorial_split' && (
                  <div className="pg-layout-note">
                    <span className="pg-note-icon">📰</span>
                    <span><strong>Editorial Magazine Split:</strong> Full-height curated photo paired with large step callout (01.) and clean narrative typography.</span>
                  </div>
                )}

                {outline.slides[activeSlideIdx].suggested_layout === 'chart' && (
                  <div className="pg-layout-note">
                    <span className="pg-note-icon">📊</span>
                    <span><strong>Financial & Visual Chart:</strong> 2-column split with a Matplotlib empirical bar/column chart paired with key observation bullets.</span>
                  </div>
                )}

                {outline.slides[activeSlideIdx].suggested_layout === 'stat_callout' && (
                  <div className="pg-layout-note">
                    <span className="pg-note-icon">📈</span>
                    <span><strong>Stat Callout Layout:</strong> High-impact metric cards with big numbers and trend indicators will be constructed.</span>
                  </div>
                )}

                {outline.slides[activeSlideIdx].suggested_layout === 'timeline' && (
                  <div className="pg-layout-note">
                    <span className="pg-note-icon">⏱️</span>
                    <span><strong>Process Timeline Layout:</strong> Sequential phase milestone cards will be laid out horizontally.</span>
                  </div>
                )}

                {/* Bullets Preview */}
                {outline.slides[activeSlideIdx].bullets && outline.slides[activeSlideIdx].bullets!.length > 0 && (
                  <div className="pg-inspector-bullets">
                    <label className="pg-label">Talking Points (6x6 Brevity Enforced)</label>
                    <ul>
                      {outline.slides[activeSlideIdx].bullets!.map((b, bi) => (
                        <li key={bi}>{b}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Speaker Notes */}
                {outline.slides[activeSlideIdx].speaker_notes && (
                  <div className="pg-speaker-notes-box">
                    <strong>Speaker Script:</strong> {outline.slides[activeSlideIdx].speaker_notes}
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="pg-action-group">
            <button type="button" className="pg-btn pg-btn-secondary" onClick={() => setStep(1)}>
              ⬅ Back to Inputs
            </button>
            <button type="button" className="pg-btn pg-btn-primary" onClick={() => setStep(3)}>
              Next: Select Theme & Visual Styling ➔
            </button>
          </div>
        </div>
      )}

      {/* STEP 3: THEME STUDIO */}
      {step === 3 && outline && (
        <div className="pg-step-card">
          <h2 className="pg-card-title">🎨 Visual Theme & Global Design Studio</h2>
          <p className="pg-card-sub">
            Gamma Theme Engine: Visual tokens are applied globally across all cards without changing your text.
          </p>

          <div className="pg-theme-grid">
            {THEMES.map((th) => (
              <div
                key={th.id}
                className={`pg-theme-box ${theme === th.id ? 'active' : ''}`}
                onClick={() => setTheme(th.id)}
              >
                <div className="pg-theme-swatch" style={{ background: th.bg, borderColor: th.color }}>
                  <div className="pg-theme-accent-dot" style={{ background: th.color }} />
                  <div className="pg-theme-title-preview" style={{ color: th.color }}>Aa</div>
                </div>
                <div className="pg-theme-name">{th.name}</div>
                <div className="pg-theme-desc">{th.desc}</div>
              </div>
            ))}
          </div>

          <div className="pg-overrides-section">
            <h3 className="pg-overrides-title">⚙️ Presentation Metadata & Header/Footer Slots</h3>
            <div className="pg-row-fields">
              <label className="pg-checkbox-label">
                <input
                  type="checkbox"
                  checked={showSlideNumbers}
                  onChange={(e) => setShowSlideNumbers(e.target.checked)}
                />
                Display Slide Numbering ("Slide X of Y")
              </label>

              <div className="pg-field" style={{ flex: 1 }}>
                <label className="pg-label">Footer Brand / Confidentiality Tag</label>
                <input
                  type="text"
                  className="pg-input"
                  value={confidentialityTag}
                  onChange={(e) => setConfidentialityTag(e.target.value)}
                />
              </div>
            </div>
          </div>

          <div className="pg-action-group">
            <button type="button" className="pg-btn pg-btn-secondary" onClick={() => setStep(2)}>
              ⬅ Back to Outline
            </button>
            <button
              type="button"
              className="pg-btn pg-btn-primary"
              onClick={handleCompileFinalDeck}
              disabled={loading}
            >
              {loading ? 'Rendering PPTX & Visuals...' : '🚀 Build & Download Presentation (.pptx)'}
            </button>
          </div>
        </div>
      )}

      {/* STEP 4: RESULT & VISUAL PREVIEW & REHEARSAL HANDOFF */}
      {step === 4 && result && (
        <div className="pg-step-card pg-result-card">
          <div className="pg-success-banner">
            <div className="pg-success-icon">🎉</div>
            <div>
              <h2 className="pg-success-title">Presentation Generated Successfully!</h2>
              <p className="pg-success-sub">
                Constructed <strong>{result.slides_generated} slides</strong> in <strong>{THEMES.find(t => t.id === theme)?.name}</strong> theme with embedded visual charts and structured cards.
              </p>
            </div>
          </div>

          {/* DOWNLOAD & EXPORT HUB */}
          <div className="pg-download-hub">
            <a
              href={getGeneratorDownloadUrl(result.output_filename)}
              className="pg-btn pg-btn-download"
              download
            >
              📥 Download PowerPoint (.pptx) Deck
            </a>

            <button
              type="button"
              className="pg-btn pg-btn-pdf"
              onClick={() => window.print()}
            >
              📄 Print / Save Summary
            </button>

            <button
              type="button"
              className="pg-btn pg-btn-secondary"
              onClick={resetAll}
            >
              ✨ Create Another Deck
            </button>
          </div>

          {/* ASYMMETRIC REHEARSAL MOATS: DIRECT JUMP TO LIVE COACH & VIVA PREP */}
          <div className="pg-rehearsal-moat-box">
            <h3 className="pg-moat-title">🎯 Presenova Asymmetric Coaching Hub</h3>
            <p className="pg-moat-sub">
              Your deck is ready. Now practice your delivery using Presenova's unique vision, vocal telemetry, and thesis defense engines:
            </p>

            <div className="pg-moat-grid">
              <div className="pg-moat-card" onClick={() => navigate('/live-coach')}>
                <div className="pg-moat-card-icon">👁️</div>
                <div className="pg-moat-card-title">Live Teleprompter Coach</div>
                <p className="pg-moat-card-desc">
                  Rehearse with real-time MediaPipe iris gaze tracking, posture angle detection, and speech pacing speedometer.
                </p>
                <span className="pg-moat-link">Launch Live Coach ➔</span>
              </div>

              <div className="pg-moat-card" onClick={() => navigate('/practice')}>
                <div className="pg-moat-card-icon">🎓</div>
                <div className="pg-moat-card-title">AI Defense Rehearsal Partner</div>
                <p className="pg-moat-card-desc">
                  Simulate interactive Q&A cross-examinations with Dr. Alexander Vance powered by local intent classification.
                </p>
                <span className="pg-moat-link">Start Practice Chat ➔</span>
              </div>
            </div>
          </div>

          {/* SLIDE VISUAL CARDS PREVIEW */}
          {outline && (
            <div className="pg-deck-preview">
              <h3 className="pg-preview-title">📑 Deck Cards Overview ({outline.slides.length} Slides)</h3>
              <div className="pg-slides-preview-grid">
                {outline.slides.map((s, idx) => (
                  <div key={idx} className="pg-slide-preview-card">
                    <div className="pg-slide-card-header">
                      <span className="pg-slide-badge">Slide {s.slide_number}</span>
                      <span className="pg-layout-tag">{s.suggested_layout || s.type}</span>
                    </div>
                    <div className="pg-slide-preview-title">{s.title}</div>
                    {s.key_takeaway && (
                      <div className="pg-slide-preview-takeaway">💡 {s.key_takeaway}</div>
                    )}
                    {s.suggested_layout === 'chart' && (
                      <div className="pg-slide-chart-preview">
                        📊 [Matplotlib Visual Chart Embedded]
                      </div>
                    )}
                    {s.bullets && s.bullets.length > 0 && (
                      <ul className="pg-slide-preview-bullets">
                        {s.bullets.slice(0, 3).map((b, bi) => (
                          <li key={bi}>{b}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* LOADING OVERLAY */}
      {loading && (
        <div className="pg-loading-overlay">
          <div className="pg-spinner" />
          <div className="pg-loading-text">{loadingMessage || 'Processing...'}</div>
        </div>
      )}

      {/* PRO UPGRADE MODAL */}
      {showUpgradeModal && (
        <div className="pg-modal-overlay" onClick={() => setShowUpgradeModal(false)}>
          <div className="pg-upgrade-modal" onClick={(e) => e.stopPropagation()}>
            <button
              type="button"
              className="pg-modal-close-btn"
              onClick={() => setShowUpgradeModal(false)}
            >
              ×
            </button>
            <div className="pg-modal-icon-wrap">
              👑
            </div>
            <span className="pg-modal-badge">PAID FEATURE</span>
            <h3 className="pg-modal-title">Unlock 20-Slide Presentations</h3>
            <p className="pg-modal-desc">
              Your <strong>Free Trial</strong> allows you to generate up to <strong>15 slides</strong> per presentation. 
              Comprehensive <strong>20-slide deep-dive decks</strong> require a Presenova Pro plan.
            </p>

            <div className="pg-modal-features">
              <div className="pg-modal-feature-item">
                <span className="icon">✓</span>
                <span>Generate full 20-slide comprehensive decks</span>
              </div>
              <div className="pg-modal-feature-item">
                <span className="icon">✓</span>
                <span>Rich multi-archetype layouts (SWOT, Chevrons, Dials, KPIs)</span>
              </div>
              <div className="pg-modal-feature-item">
                <span className="icon">✓</span>
                <span>Deep domain synthesis with Gemini AI</span>
              </div>
            </div>

            <div className="pg-modal-actions">
              <button
                type="button"
                className="pg-btn-pro-unlock"
                onClick={handleActivatePro}
              >
                👑 Upgrade to Pro (Activate 20 Slides)
              </button>
              <button
                type="button"
                className="pg-btn-stay-free"
                onClick={() => {
                  setSlideCount(15);
                  setShowUpgradeModal(false);
                }}
              >
                Continue with 15 Slides (Free Trial)
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PresentationGenerator;
