# Presenova: AI-Powered Multi-Modal Presentation Evaluation, Coaching & Synthesis Platform
## Complete Technical Specification, Architecture Manual & Developer Guide
**Version 2.0.0 (Production Release with Google Gemini Integration) — Final Year Project (FYP)**

---

## 1. Executive Overview

**Presenova** is an enterprise-grade, multi-modal AI presentation evaluation, rehearsal coaching, and automated presentation synthesis platform. It is designed to replace subjective, inconsistent presentation feedback with **deterministic, real-time telemetry**, multi-modal perception, and actionable artificial intelligence.

Presenova addresses all three pillars of presentation mastery:
1. **The Artifact (Slides & Content)**: Automated slide evaluation against the academic **7Cs Communication Framework**, structural design heuristics, grammar validation, and multi-archetype PPTX presentation generation.
2. **The Voice (Acoustic Delivery)**: Real-time speech transcription (via ultra-low latency Groq Whisper LPU), words-per-minute (WPM) cadence tracking, and verbal filler detection (`um`, `uh`, `like`, `you know`).
3. **The Speaker (Physical Composure & Presence)**: Real-time webcam perception using MediaPipe Face Mesh (478 landmarks with iris refinement) to quantify eye gaze deviation, head pose orientation, and confidence scoring.

### Multi-Target Support
- **Web Application**: React 18, TypeScript, Tailwind CSS, Vite, Recharts, Lucide Icons.
- **Desktop Application**: Electron 31 cross-platform desktop shell with native Google OAuth integration.
- **Mobile Application**: Flutter SDK (Android & iOS) with native camera/microphone recording and WebSocket streaming.
- **Central API Hub**: Python 3.12, Flask 3.0, Eventlet / Flask-SocketIO, Firebase Firestore, and Flask-JWT-Extended.

---

## 2. System Architecture & High-Level Design

```mermaid
graph TD
    subgraph Client Layer
        WebClient["React 18 / TypeScript Web App (Vite)"]
        DesktopClient["Electron 31 Desktop App"]
        MobileClient["Flutter Mobile App (Android/iOS)"]
    end

    subgraph Central API Hub [Flask / Python 3.12 - main.py]
        AuthBP["Auth Blueprint (auth.py)"]
        DocBP["Document Analyzer (phase_two.py)"]
        SpeechBP["Speech Analyzer (phase_four.py)"]
        CoachBP["AI Coach & Practice Mode (phase_five.py)"]
        LiveBP["Live Session Socket.IO (phase_live.py)"]
        GenBP["Presentation Generator (routes/presentation_generator.py)"]
        RewriteBP["Presentation Rewriter (routes/presentation_rewriter.py)"]
        VivaBP["Question Generator (routes/question_generator.py)"]
    end

    subgraph AI & Deterministic ML Engines
        GeminiProvider["Google Gemini API (gemini-3.5-flash / 3.6-flash)"]
        RandomForest["Scikit-Learn RandomForest (7Cs Predictor)"]
        SpaCyNLP["spaCy en_core_web_sm (Dependency Parser)"]
        VectorRAG["SentenceTransformers + FAISS IndexFlatIP"]
        MediaPipe["MediaPipe 478-Landmark FaceMesh + Iris Refinement"]
        GroqWhisper["Groq Whisper LPU (Speech-to-Text)"]
        LangTool["LanguageTool Grammar Engine (Cloud API)"]
        PPTXEngine["python-pptx High-End Layout Synthesizer"]
    end

    subgraph Dual-Persistence Layer
        DBRouter["models.py DB Router & Abstraction"]
        FirestoreDB[("Google Cloud Firestore")]
        MemoryDB[("Thread-Safe In-Memory Store (_MEMORY_STORE)")]
    end

    WebClient <-->|REST API + JWT| CentralAPIHub
    DesktopClient <-->|REST API + JWT| CentralAPIHub
    MobileClient <-->|REST API + JWT| CentralAPIHub
    WebClient <-->|WebSockets (Socket.IO)| LiveBP
    MobileClient <-->|WebSockets (Socket.IO)| LiveBP

    CoachBP --> GeminiProvider
    CoachBP --> LangTool
    GenBP --> GeminiProvider
    GenBP --> PPTXEngine
    DocBP --> RandomForest
    DocBP --> SpaCyNLP
    LiveBP --> MediaPipe
    SpeechBP --> GroqWhisper
    VivaBP --> VectorRAG

    CentralAPIHub --> DBRouter
    DBRouter -->|Primary| FirestoreDB
    DBRouter -->|Instant Auto-Fallback| MemoryDB
```

---

## 3. Detailed Phase Specifications

### Phase 1: Authentication & Identity Management (`auth.py`)
- **Dual-Authentication Pipeline**:
  - **Email & Password**: Native registration and login with Argon2 / Werkzeug password hashing.
  - **Google Firebase OAuth**: Client signs in with Google, exchanges the Firebase ID Token with `POST /api/auth/firebase-login`, which verifies the token via `firebase_admin.auth.verify_id_token()`.
- **JWT Token Architecture**:
  - Issues 24-hour expiration access tokens and refresh tokens via `Flask-JWT-Extended`.
  - Comprehensive error handlers: `@jwt.expired_token_loader`, `@jwt.invalid_token_loader`, `@jwt.unauthorized_loader`, returning structured JSON error payloads.
- **User Profile Endpoint**:
  - `GET /api/auth/me`: Authenticated endpoint returning user metadata, name, email, avatar, and registration timestamp.

---

### Phase 2: Document Extraction & Presentation Scoring (`phase_two.py`)
- **Supported File Formats**: `.pptx`, `.pdf`, `.docx`, `.txt`.
- **Magic-Byte Binary Signature Verification**: Prevents malicious MIME-type spoofing by checking file headers (`PK\x03\x04` for PPTX/DOCX, `%PDF-` for PDF, `\xd0\xcf\x11\xe0` for DOC).
- **The 7Cs Communication Framework Evaluation**:
  1. **Clarity**: Flesch-Kincaid grade level readability, sentence complexity.
  2. **Conciseness**: Word count density, bullet count heuristics (flagging slides with >6 bullets).
  3. **Concreteness**: Specific metrics, numerical data points, tangible nouns.
  4. **Correctness**: Grammar evaluation, passive voice ratio.
  5. **Coherence**: Sequential logical flow and transition signposts.
  6. **Completeness**: Presence of agenda, problem statement, solution, and conclusion.
  7. **Courteousness**: Inclusive, professional delivery tone.
- **Offline ML Scoring Engine**:
  - Employs a pre-trained Scikit-Learn `RandomForestRegressor` (`nlp_module/trained_weights.pkl`) operating on 19 extracted linguistic features.
  - Complete zero-latency offline evaluation — runs without requiring external internet or API keys.
- **7 Deep Sub-Analyzers**:
  - Design & Visual Density Analyzer
  - Numerical & Statistical Rigor Evaluator
  - Consistency & Structural Symmetry Checker
  - Narrative Arc & Executive Hook Assessor
  - Color Contrast & Legibility Validator
  - Slide Overflow & Clutter Flagging
  - Recommendation Matrix Generator

---

### Phase 3: Presentation Rewriter & Presentation Generator

#### A. Presentation Generator (`services/presentation_generator.py` & `routes/presentation_generator.py`)
- **Multi-Archetype Slide Architectures**:
  - **Title Slide (`title`)**: Strategic title with punchy executive subtitle.
  - **Horizontal Pills (`horizontal_pills`)**: 3-card overview of Strategic Objectives & Vision.
  - **SWOT Matrix (`swot`)**: 4-pillar quadrant analyzing Strengths, Weaknesses, Opportunities, and Threats.
  - **Visual Chart (`chart`)**: Generates real Matplotlib/python-pptx charts (Bar, Donut, Line) with empirical metrics.
  - **Circular Dials (`circular_dials`)**: Progress percentage rings visualizing operational KPIs and SLA retention.
  - **Process Chevrons (`process_chevrons`)**: Sequential 4-phase delivery pipeline (Discovery ➔ Build ➔ Validate ➔ Scale).
  - **Team Personas (`team_personas`)**: Leadership profile cards with headshots, executive titles, and background briefs.
  - **Stat Callouts (`stat_callout`)**: High-impact big KPI numbers with delta indicators (`▲ Precision`, `⚡ Speed`).
  - **Roadmap Timeline (`timeline`)**: Multi-phase deployment horizon cards.
  - **Editorial Split (`editorial_split`)**: Curated Unsplash royalty-free high-resolution photography split with bulleted key insights.
  - **Conclusion (`conclusion`)**: 3 executive takeaways and immediate stakeholder next-step CTA.
- **Curated Theme Engine**:
  - `corporate_blue_geom`: Deep Navy & Cyan with geometric corner chevrons.
  - `modern_infographic_yellow`: Slate Charcoal & Vibrant Yellow Accent Bar.
  - `creative_editorial`: Sand & Terracotta Minimalist layout.
  - `corporate_clean`: Minimalist Slate & Studio Sky Blue.
  - `modern_dark`: Sleek Obsidian & Neon Cyan.
  - `academic_elegant`: Rich Navy & Academic Gold.

#### B. Presentation Rewriter (`routes/presentation_rewriter.py`)
- Ingests existing substandard decks, extracts text per slide, parses grammar and passive voice via `spaCy`, and generates an upgraded, professional `.pptx` deck while preserving original core meaning.

---

### Phase 4: Acoustic & Speech Perception (`phase_four.py`)
- **Audio Pipeline**:
  - Accepts user audio recordings in `.wav`, `.mp3`, `.m4a`, `.webm`.
  - Transcribes audio via **Groq Whisper API** (`whisper-large-v3` running on ultra-fast Groq LPU hardware, typically transcribing in <400ms).
- **Speech Metrics**:
  - **Speaking Rate (WPM)**: Calculates Words-Per-Minute and evaluates against optimal thresholds (Optimal: 130–155 WPM; Too Slow: <115 WPM; Too Fast: >165 WPM).
  - **Filler Word Detection**: Identifies and counts verbal disfluencies (`um`, `uh`, `like`, `you know`, `actually`, `basically`, `sort of`).
  - **Pacing Feedback**: Provides specific guidance on intentional silence and deliberate pausing.

---

### Phase 5: Real-Time AI Coach & Practice Mode (`phase_five.py`)
- **Coaching Persona — Dr. Alexander Vance**:
  - World-class AI presentation and academic defense coach.
  - Emits **short, context-aware, direct feedback** (under 75 words / 2–3 sentences or focused bullet points).
  - Seamlessly handles off-topic or technical queries (e.g. ethical hacking, AI, engineering) by delivering a direct, sharp answer and naturally bridging it back to presentation delivery, viva defense, or communicating complex ideas clearly.
- **Gemini AI Integration (`services/ai/gemini_provider.py`)**:
  - **Primary Model**: `gemini-3.5-flash` for fast, intelligent generation.
  - **Fallback Chain**: `gemini-3.6-flash`, `gemini-flash-latest`, `gemini-flash-lite-latest`.
  - **Thinking Budget Optimization**: Configured with `thinking_budget=0` so the token budget is dedicated to immediate response generation without wasting time on internal thought chains.
  - **503 Auto-Failover**: If a Gemini model encounters temporary server spikes (`503 Service Unavailable`), the provider immediately fails over to the next candidate model in milliseconds.
- **LanguageTool Real-Time Grammar Check**:
  - Analyzes the user's input for grammatical errors, punctuation, and capitalization issues before generating feedback, providing subtle corrections (e.g., reminding them to capitalize slide titles).
- **Smart Local Fallback**:
  - If external network is completely disconnected, falls back to local TF-IDF + LogisticRegression intent engine without crashing, preventing repetitive canned greetings during ongoing conversations.

---

### Live Session & Real-Time Computer Vision (`phase_live.py`)
- **WebSocket Protocol (`/ws/live-session`)**:
  - Client streams webcam JPEG frames and audio chunks over low-latency WebSockets.
- **MediaPipe Perception Engine**:
  - **478-Landmark FaceMesh with Iris Refinement**: Evaluates landmarks `468–477` to calculate precise eye gaze center offset.
  - **Gaze Deviation Tracking**: Flags when the presenter looks away from the audience/camera.
  - **Head Pose Estimation**: Pitch, yaw, and roll deviation to measure presenter posture.
  - **Eye Aspect Ratio (EAR)**: Dynamic blink detection to monitor natural engagement vs staring/nervousness.
- **Session Telemetry & Report**:
  - Generates comprehensive live session analytics with time-series charts of eye contact %, posture composure %, and vocal delivery.

---

### Academic Viva & Question Generator (`routes/question_generator.py`)
- **Vector RAG (Retrieval-Augmented Generation)**:
  - Chunks presentation text into semantic 200-word passages.
  - Embeds passages using `SentenceTransformer('all-MiniLM-L6-v2')`.
  - Builds a local in-memory `FAISS IndexFlatIP` (Cosine Similarity) index.
- **Viva Defense Question Formulator**:
  - Generates rigorous academic thesis defense questions across three tiers:
    1. **Clarification**: Fundamentals, terminology, and core architecture.
    2. **Methodology & Rigor**: Baseline comparisons, algorithm trade-offs, and dataset validation.
    3. **Critical Defense**: Scalability limits, edge-case vulnerabilities, and commercial viability.

---

## 4. Subscription & Slide Count Tiering

Presenova provides flexible presentation synthesis tiers:

| Tier | Available Slide Counts | Features & Inclusions | Target User |
| :--- | :--- | :--- | :--- |
| **Free Trial** | **5, 10, 15 Slides** | Full 7Cs analysis, Gemini outline synthesis, core visual layouts, standard PPTX export | Students, Academic Rehearsals, Quick Briefings |
| **Pro / Paid** | **20 Slides (PRO 👑)** | 20-slide deep-dive decks, SWOT matrices, circular dials, process chevrons, team personas, priority export | Executives, Final Year Project Defenses, Conference Keynotes |

### Pro Upgrade & Demo Flow
1. **Interactive Buttons**: Target slide count displays `5 Slides`, `10 Slides`, `15 Slides` with `FREE TRIAL` badges and `20 Slides` with `PAID 👑` badge.
2. **Upgrade Modal**: Clicking `20 Slides` on a Free Trial account displays a modal detailing Pro features.
3. **Instant Demo Unlock**: Includes an instant **"👑 Upgrade to Pro (Activate Now)"** button allowing evaluators and testers to unlock and demonstrate 20-slide generation on demand, with a corresponding **"(Reset to Free)"** toggle.

---

## 5. Dual-Persistence Database Architecture (`models.py`)

Presenova employs an automated **dual-persistence storage router**:

```
           +---------------------------------------+
           |         API Request / Action          |
           +---------------------------------------+
                               |
                               v
           +---------------------------------------+
           |       models.py Database Router       |
           +---------------------------------------+
                               |
               +---------------+---------------+
               |                               |
               v (Primary)                     v (Fallback / Offline)
    +----------------------+       +-----------------------+
    | Google Cloud         |       | Thread-Safe In-Memory |
    | Firestore Database   |       | Store (_MEMORY_STORE) |
    +----------------------+       +-----------------------+
               |                               |
        (If timeout/error)                     |
               +-------------------------------+
```

### Core Entities:
- **`User`**: `id`, `uid`, `name`, `email`, `photo_url`, `provider` (`password` | `google`), `created_at`, `updated_at`.
- **`Upload`**: `id`, `user_id`, `filename`, `file_type`, `file_size`, `permanent_path`, `created_at`.
- **`Report`**: `id`, `user_id`, `upload_id`, `report_type` (`document` | `speech` | `practice` | `live`), `report_json`, `overall_score`, `created_at`.
- **`PresentationSession`**: `id`, `user_id`, `session_state`, `gaze_scores`, `wpm_timeline`, `filler_count`, `created_at`.

---

## 6. Complete REST & WebSocket API Directory

### Authentication Endpoints
| Method | Endpoint | Auth | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/auth/register` | None | Register new user via email/password |
| `POST` | `/api/auth/login` | None | Login with email/password; returns access & refresh tokens |
| `POST` | `/api/auth/firebase-login` | None | Exchange Firebase Google ID token for Flask JWT |
| `GET` | `/api/auth/me` | Bearer JWT | Get current authenticated user profile |
| `POST` | `/api/auth/refresh` | Refresh JWT | Renew expired access token |

### Evaluation & Analysis Endpoints
| Method | Endpoint | Auth | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/upload` | Optional JWT | Upload presentation file (.pptx, .pdf, .docx) for 7Cs analysis |
| `GET` | `/api/report/<report_id>` | Optional JWT | Fetch detailed multi-category evaluation scorecard |
| `POST` | `/api/analyze-speech` | Optional JWT | Upload audio file (.wav, .mp3, .m4a) for Groq Whisper WPM and filler analysis |
| `POST` | `/api/viva/generate-questions` | Optional JWT | Generate academic thesis defense questions via FAISS RAG |

### AI Coach & Practice Endpoints
| Method | Endpoint | Auth | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/practice-chat` | Optional JWT | Send message to Dr. Vance AI Coach; returns concise, context-aware Gemini feedback |

### Presentation Synthesis Endpoints
| Method | Endpoint | Auth | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/presentation-generator/outline` | Optional JWT | Synthesize structured multi-archetype outline (5, 10, 15, or 20 slides) |
| `POST` | `/api/presentation-generator/import-seed` | Optional JWT | Parse document seed and generate tailored presentation outline |
| `POST` | `/api/presentation-generator/generate-from-outline` | Optional JWT | Render and compile `.pptx` presentation deck |
| `GET` | `/api/presentation-generator/download/<filename>` | None | Download generated `.pptx` presentation deck |
| `GET` | `/api/presentation-generator/themes` | None | Fetch available curated visual themes |

### Real-Time WebSocket Channel
| Protocol | Namespace / Path | Direction | Description |
| :--- | :--- | :--- | :--- |
| `WSS` | `/ws/live-session` | Bi-directional | Stream webcam frames and audio chunks; receive real-time gaze and posture telemetry |

---

## 7. Developer & Deployment Guide

### Prerequisites
- **Python**: Version 3.12 (Dedicated `venv312` environment).
- **Node.js**: Version 18+ (with npm).
- **Git**: For version control.

### Installation & Environment Setup

#### 1. Backend Setup
```powershell
cd Presenova_Final

# Activate the dedicated Python 3.12 virtual environment
.\venv312\Scripts\activate

# Install dependencies (if setting up fresh)
pip install -r requirements.txt

# Download required spaCy model
python -m spacy download en_core_web_sm
```

#### 2. Configuration (`.env`)
Ensure `Presenova_Final/.env` is configured with:
```env
# Flask Configuration
FLASK_ENV=development
FLASK_DEBUG=1
HOST=0.0.0.0
PORT=5000

# Google Gemini API
GEMINI_API_KEY=your-gemini-api-key-here
GEMINI_MODEL=gemini-3.5-flash
GEMINI_FALLBACK_MODELS=gemini-3.6-flash,gemini-flash-latest,gemini-flash-lite-latest
GEMINI_TIMEOUT_SECONDS=15.0

# Firebase Firestore
FIREBASE_CREDENTIALS_PATH=firebase-service-account.json
FIREBASE_PROJECT_ID=presenova-fyp

# Groq Whisper (Speech-to-Text)
GROQ_API_KEY=your-groq-api-key-here

# JWT Security
JWT_SECRET_KEY=YOUR_GENERATED_JWT_SECRET_KEY_HERE

# LanguageTool Grammar Check
ENABLE_GRAMMAR_CHECK=1
LANGUAGETOOL_API_URL=https://api.languagetool.org/v2

# CORS Configuration
CORS_ORIGINS=http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173
```

#### 3. Frontend Setup
```powershell
cd Presenova_Final/frontend

# Install dependencies
npm install

# Run local development server
npm run dev

# Run production build validation
npm run build
```

---

## 8. Verification & Test Suite

Presenova contains automated test suites verifying all subsystems:

```powershell
cd Presenova_Final

# Test presentation generator layouts and multi-archetypes
.\venv312\Scripts\python.exe tests\test_professional_layouts.py

# Test enhanced presentation generator with Gemini fallback
.\venv312\Scripts\python.exe tests\test_enhanced_presentation_generator.py

# Test end-to-end multi-modal flow
.\venv312\Scripts\python.exe tests\test_end_to_end.py
```

---

---

## 9. Comprehensive File & Directory Structure

```
Presenova_Final/
├── .env                                  # Active environment variables (API keys, ports, JWT)
├── .env.example                          # Template environment variables
├── COMPLETE_PROJECT_DOCUMENTATION.md     # This comprehensive master documentation
├── FYP_DOCUMENTATION.md                  # Academic FYP report & theoretical formulation
├── GEMINI_SETUP.md                       # Dedicated Gemini API setup & configuration guide
├── main.py                               # Flask Application Factory & Socket.IO server entrypoint
├── models.py                             # Firestore & In-Memory dual-persistence abstraction
├── auth.py                               # Phase 1: Authentication & JWT endpoints
├── phase_two.py                          # Phase 2: 7Cs Document & Slide Evaluator
├── phase_four.py                         # Phase 4: Acoustic & Speech Perception (Groq Whisper)
├── phase_five.py                         # Phase 5: Dr. Alexander Vance AI Practice Coach
├── phase_live.py                         # Live Session WebSocket & MediaPipe FaceMesh engine
├── requirements.txt                      # Python library dependencies
├── pyrightconfig.json                    # IDE Pyright / Pylance path mapping
├── venv312/                              # Dedicated Python 3.12 Virtual Environment
│
├── routes/                               # Specialized Flask Blueprints
│   ├── presentation_generator.py         # 5, 10, 15, 20 slide synthesis & download routes
│   ├── presentation_rewriter.py          # Slide text enhancement & rewrite routes
│   ├── question_generator.py             # Academic viva defense question generator
│   └── ...
│
├── services/                             # Core Business Logic & AI Engines
│   ├── ai/
│   │   ├── gemini_provider.py            # Robust Gemini 3.5/3.6 client with auto-failover
│   │   └── base_provider.py              # Abstract AI provider interface
│   ├── presentation_generator.py         # python-pptx high-end slide layout compiler
│   ├── report_generator.py               # Multi-modal evaluation scorecard builder
│   └── ...
│
├── nlp_module/                           # Offline Machine Learning Models
│   ├── trained_weights.pkl               # 7Cs RandomForest offline model weights
│   └── feature_extractor.py              # 19-dimensional linguistic feature extractor
│
├── frontend/                             # Modern Web Client (Vite + React 18 + TS)
│   ├── src/
│   │   ├── pages/
│   │   │   ├── PresentationGenerator.tsx # Slide generator UI (5, 10, 15 Free / 20 Pro)
│   │   │   ├── PracticeMode.tsx          # Dr. Vance AI Coach chat interface
│   │   │   ├── LiveSession.tsx           # Real-time webcam & telemetry view
│   │   │   ├── DocumentAnalysis.tsx      # Slide upload & 7Cs radar dashboard
│   │   │   └── ...
│   │   ├── components/                   # Reusable UI widgets & upgrade modals
│   │   └── api/                          # Axios API clients & WebSocket connectors
│   ├── package.json                      # Frontend dependencies
│   └── vite.config.ts                    # Vite bundler configuration
│
└── tests/                                # Automated Test Suites
    ├── test_professional_layouts.py      # PPTX archetype visual layout tests
    ├── test_enhanced_presentation_generator.py # Gemini outline synthesis tests
    └── test_end_to_end.py                # Full pipeline integration verification
```

---

## 10. Troubleshooting & Common Operational Solutions

### 1. Python IDE / Pyright Cannot Resolve Dependencies
- **Cause**: VS Code or Pyright looking in an unpopulated `venv` folder instead of `venv312`.
- **Solution**: A directory junction `venv -> venv312` has been established, and `.vscode/settings.json` points `python.defaultInterpreterPath` to `.\\venv312\\Scripts\\python.exe`.

### 2. Google Gemini API `503 Service Unavailable` or Spike
- **Cause**: Google AI Studio upstream capacity spikes during peak hours.
- **Solution**: `services/ai/gemini_provider.py` automatically cascades across candidate models:
  `gemini-3.5-flash` ➔ `gemini-3.6-flash` ➔ `gemini-flash-latest` ➔ `gemini-flash-lite-latest`.
- **Lite Models Note**: Lite models reject `thinking_config(thinking_budget=0)`. The provider automatically suppresses thinking parameters on lite models to prevent `400 INVALID_ARGUMENT`.

### 3. Slide Generator Limits (5, 10, 15 vs 20 Slides)
- **Constraint**: Free Trial users can generate 5, 10, or 15 slides. 20 slides is a Pro feature.
- **Enforcement**: Validated on both frontend (`PresentationGenerator.tsx`) and backend (`routes/presentation_generator.py`).
- **Demo Mode**: Evaluators can click **"👑 Upgrade to Pro (Activate Now)"** inside the Pro Modal to test 20-slide generation instantaneously without payment processing.

---

## 11. FYP / Academic Viva Defense Cheatsheet

### Question 1: How does Presenova evaluate slide quality without human subjectivity?
> **Answer**: Presenova maps slide text and structure to the established academic **7Cs Communication Framework** (Clarity, Conciseness, Concreteness, Correctness, Coherence, Completeness, Courteousness). It extracts 19 quantitative linguistic and structural features (e.g., Flesch-Kincaid grade level, bullet density, numerical rigor, passive voice percentage) and runs them through a Scikit-Learn `RandomForestRegressor` trained on peer-reviewed presentation corpora.

### Question 2: Why use MediaPipe FaceMesh instead of standard OpenCV Haar cascades for gaze tracking?
> **Answer**: OpenCV Haar cascades only provide coarse bounding-box face detection, which cannot measure subtle eye gaze or head rotation. MediaPipe FaceMesh produces **478 3D landmarks**, including landmarks 468–477 specifically refined for the ocular iris. By computing the Euclidean vector between the iris center and the eye corners, Presenova achieves millimeter-accurate eye contact and gaze deviation scoring in real-time.

### Question 3: How does the AI Coach avoid generating slow or repetitive responses?
> **Answer**: The AI Coach operates on **Google Gemini 3.5 Flash** with `thinking_budget=0`, eliminating reasoning latency. It enforces a strict persona prompt under 75 words that delivers crisp, context-aware feedback with immediate practical tips. If offline, it uses a state-aware local fallback that tracks conversation history to eliminate repetitive greetings.

---

## 12. Conclusion & Summary

Presenova combines deterministic classical machine learning, real-time computer vision, low-latency audio processing, and Google Gemini AI to deliver a unified, comprehensive presentation mastery ecosystem. Whether generating executive decks from scratch, rehearsing with real-time gaze tracking, or preparing for an academic viva defense, Presenova provides objective, actionable, and state-of-the-art guidance.

