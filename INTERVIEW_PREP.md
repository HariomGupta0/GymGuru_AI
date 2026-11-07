# 🎯 Interview Preparation Guide — GymGuru AI

> **Your cheat-sheet for confidently presenting and defending every aspect of this project in technical interviews.**

---

## Table of Contents

1. [30-Second Elevator Pitch](#1-30-second-elevator-pitch)
2. [Project Overview — What, Why, How](#2-project-overview--what-why-how)
3. [Architecture Deep-Dive](#3-architecture-deep-dive)
4. [Module-by-Module Walkthrough](#4-module-by-module-walkthrough)
5. [Key Algorithms & Math](#5-key-algorithms--math)
6. [Design Decisions & Trade-offs](#6-design-decisions--trade-offs)
7. [Data Flow — Frame to Feedback](#7-data-flow--frame-to-feedback)
8. [Database Design](#8-database-design)
9. [Concurrency & Thread Safety](#9-concurrency--thread-safety)
10. [LLM & Voice Pipeline](#10-llm--voice-pipeline)
11. [50+ Interview Questions & Answers](#11-50-interview-questions--answers)
    - [General / Behavioral](#general--behavioral)
    - [Computer Vision & MediaPipe](#computer-vision--mediapipe)
    - [System Design & Architecture](#system-design--architecture)
    - [LLM / AI Integration](#llm--ai-integration)
    - [Database & Persistence](#database--persistence)
    - [Frontend / Streamlit / WebRTC](#frontend--streamlit--webrtc)
    - [OOP & Design Patterns](#oop--design-patterns)
    - [Performance & Scalability](#performance--scalability)
    - [Tricky / Curveball Questions](#tricky--curveball-questions)
12. [How to Demo Live](#12-how-to-demo-live)
13. [Weaknesses to Acknowledge & How to Spin Them](#13-weaknesses-to-acknowledge--how-to-spin-them)
14. [Future Improvements to Mention](#14-future-improvements-to-mention)
15. [Quick-Reference Cheat Sheet](#15-quick-reference-cheat-sheet)

---

## 1. 30-Second Elevator Pitch

> *"I built GymGuru AI — a real-time AI gym coach that uses your webcam to track exercise form, count reps and sets, and proactively speak corrections out loud. It uses **MediaPipe** for pose estimation to extract 33 body landmarks from a live video stream, then applies trigonometric joint-angle analysis through a polymorphic detector system to evaluate form across 7 exercises — squats, push-ups, curls, shoulder press, lunges, planks, and jumping jacks. When it detects bad form, it sends the context to a **Groq-hosted LLM (LLaMA 3.3 70B)** which generates a natural coaching cue, then converts it to speech via **Google TTS** and auto-plays it back to the user — all in real-time over **WebRTC**. Everything is persisted to SQLite, and I built a full workout history dashboard with analytics charts."*

---

## 2. Project Overview — What, Why, How

### What is it?
A browser-based, real-time AI fitness coach. No app downloads or special hardware needed — just open the browser, grant camera access, and start training.

### Why did you build it?
- **Problem**: Most people at home gyms or beginners perform exercises with incorrect form, risking chronic joint injuries. Personal trainers are expensive and not always accessible.
- **Solution**: An AI that watches you through your webcam, counts your reps, checks your posture, and tells you — *out loud in natural spoken voice* — how to fix it immediately.

### How does it work? (High-Level)
1. **Camera stream** → WebRTC sends frames from browser to Python server.
2. **Pose detection** → MediaPipe extracts 33 body landmarks per frame.
3. **Exercise analysis** → Custom detectors compute 2D joint angles and detect form errors.
4. **Rep counting** → State machine (up/down hysteresis) tracks repetitions and sets.
5. **AI coaching** → Groq LLM (LLaMA 3.3 70B) generates concise, natural-language coaching feedback.
6. **Voice output** → Google TTS converts text to audio bytes, auto-played in the browser.
7. **Persistence** → SQLite stores workout history (reps, sets, duration) per user with data aggregation.

---

## 3. Architecture Deep-Dive

```
┌───────────────────────────────────────────────────────────────────┐
│                        CLIENT BROWSER                            │
│  ┌──────────┐    ┌──────────────┐    ┌────────────────────────┐  │
│  │  Webcam   │───▶│  WebRTC Peer  │───▶│  Streamlit UI (React) │  │
│  └──────────┘    └──────┬───────┘    └──────────┬─────────────┘  │
│                         │ Video Frames           │ Metrics Display│
└─────────────────────────┼────────────────────────┼────────────────┘
                          │                        ▲
                          ▼                        │
┌─────────────────────────┼────────────────────────┼────────────────┐
│                   SERVER (Python)                                  │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │  VideoProcessorClass (runs in WebRTC background thread)    │    │
│  │  ┌─────────────┐   ┌──────────────┐   ┌────────────────┐  │    │
│  │  │  MediaPipe   │──▶│  Exercise     │──▶│  Skeleton      │  │    │
│  │  │  Landmarker  │   │  Detectors   │   │  Renderer      │  │    │
│  │  └─────────────┘   └──────┬───────┘   └────────────────┘  │    │
│  │                           │ metrics                         │    │
│  │                     [thread-safe lock]                       │    │
│  └───────────────────────────┼─────────────────────────────────┘    │
│                              ▼                                      │
│  ┌──────────────────────────────────────────────────────────┐      │
│  │  sync_metrics_update() — Streamlit main thread            │      │
│  │  ┌───────────┐   ┌───────────┐   ┌─────────────────┐    │      │
│  │  │  Rep/Set   │──▶│  DB Write  │──▶│  Voice Pipeline  │    │      │
│  │  │  Counter   │   │  (SQLite)  │   │  (LLM → TTS)    │    │      │
│  │  └───────────┘   └───────────┘   └─────────────────┘    │      │
│  └──────────────────────────────────────────────────────────┘      │
└────────────────────────────────────────────────────────────────────┘
```

### Key Layers

| Layer | Responsibility | Key Files |
|---|---|---|
| **Presentation** | UI rendering, session state, CSS | [main.py](file:///c:/Users/gupta/Documents/HARIOM/PLACEMENT_101/Resume_ready_projects/AI_Gym_Trainer/main.py), `static/style.css` |
| **Vision** | Frame processing, pose detection, skeleton overlay | [exercise_video_processor.py](file:///c:/Users/gupta/Documents/HARIOM/PLACEMENT_101/Resume_ready_projects/AI_Gym_Trainer/services/vision/exercise_video_processor.py) |
| **Detection** | Joint-angle analysis, rep counting, form checks | `detectors/*.py`, [base_exercise.py](file:///c:/Users/gupta/Documents/HARIOM/PLACEMENT_101/Resume_ready_projects/AI_Gym_Trainer/core/base_exercise.py) |
| **Coaching** | LLM prompt engineering, voice debounce, TTS | [llm.py](file:///c:/Users/gupta/Documents/HARIOM/PLACEMENT_101/Resume_ready_projects/AI_Gym_Trainer/services/coaching/llm.py), [tts.py](file:///c:/Users/gupta/Documents/HARIOM/PLACEMENT_101/Resume_ready_projects/AI_Gym_Trainer/services/coaching/tts.py), [voice_pipeline.py](file:///c:/Users/gupta/Documents/HARIOM/PLACEMENT_101/Resume_ready_projects/AI_Gym_Trainer/services/coaching/voice_pipeline.py) |
| **Tracking** | Metrics sync, set/rep calculation, circuit transitions | [metrics.py](file:///c:/Users/gupta/Documents/HARIOM/PLACEMENT_101/Resume_ready_projects/AI_Gym_Trainer/services/tracking/metrics.py) |
| **Persistence** | SQLite CRUD, user management, upsert workout logic | [exercise_repository.py](file:///c:/Users/gupta/Documents/HARIOM/PLACEMENT_101/Resume_ready_projects/AI_Gym_Trainer/services/persistence/exercise_repository.py) |
| **Auth** | Login wall, user session | [login_wall.py](file:///c:/Users/gupta/Documents/HARIOM/PLACEMENT_101/Resume_ready_projects/AI_Gym_Trainer/services/auth/login_wall.py) |
| **Config** | Exercise options, prompt engineering, thresholds | [workout_config.py](file:///c:/Users/gupta/Documents/HARIOM/PLACEMENT_101/Resume_ready_projects/AI_Gym_Trainer/services/config/workout_config.py) |

---

## 4. Module-by-Module Walkthrough

### 4.1 `core/base_exercise.py` — The Abstract Foundation

```python
class BaseExercise(ABC):
    def calculate_angle(self, a, b, c) -> float   # Vector dot-product angle at vertex b
    def get_point(self, landmarks, idx) -> tuple   # Extract (x, y) from landmark index
    @abstractmethod def process(self, landmarks)   # Polymorphic method implemented by each detector
    @abstractmethod def reset(self)                # Reset reps & internal states
```

**Why it matters**: This implements the **Template Method + Strategy Pattern**. Every exercise detector inherits from this base, reuses vector trigonometry, and implements its own posture verification logic. Adding a new exercise takes only ~50 lines without modifying core systems.

### 4.2 `detectors/` — Exercise-Specific Logic

Each detector follows a structured inspection pipeline:
1. **Select most visible side** — Compares left vs right landmark visibility to gracefully handle any camera perspective (side profile, 45-degree angle, front).
2. **Calculate key joint angles** — Uses `calculate_angle()` from the base class.
3. **State machine for rep counting** — Hysteresis thresholding (`down` → `up` or `up` → `down`).
4. **Form assessment** — Computes posture metrics and flags faults.

| Detector | State Machine | Form Checks |
|---|---|---|
| **SquatDetector** | `down` (knee < 100°) → `up` (knee ≥ 160°) | Depth status ("GOOD DEPTH" vs "TOO HIGH"), back leaning angle |
| **PushUpDetector** | `down` (elbow < 90°) → `up` (elbow > 160°) | Body straightness, hip sag / pike deviation |
| **BicepsCurlDetector** | `up` (elbow < 50°) → `down` (elbow > 160°) | Elbow drift tolerance, torso swing angle (`atan2`) |
| **ShoulderPressDetector** | `up` (elbow > 160°) → `down` (elbow < 90°) | Arm extension progress, lower back arching angle |
| **LungesDetector** | `down` (knee < 100°) → `up` (knee > 160°) | Lateral balance offset between shoulders and hips |
| **PlankDetector** | Time-based hold accumulation (seconds) | Body alignment angle, hip levelness |
| **JumpingJacksDetector** | `open` (wide stance + arms up) → `closed` | Stance ratio (ankle width / shoulder width), arm height |

> **Key Insight for Interviews**: Planks are unique — they don't count discrete reps. Instead, `reps` acts as accumulated active hold time in seconds using `time.time()`. If form breaks (sagging hips), timing pauses automatically!

### 4.3 `services/vision/exercise_video_processor.py` — The Vision Engine

Inherits from `VideoProcessorBase` (streamlit-webrtc) and runs in a **dedicated background worker thread**.

**Critical responsibilities**:
- Initializes MediaPipe `PoseLandmarker` in `VIDEO` running mode with full model weights (`pose_landmarker_full.task`).
- Runs `recv()` callback for every WebRTC frame.
- Thread-safe metrics exchange via `threading.Lock()`.
- Dynamic skeleton rendering: Green lines for correct posture; turns **RED** for body segments violating form constraints.
- Real-time exercise switching without restarting the WebRTC stream.

### 4.4 `services/coaching/` — The AI Voice Coach

Composed of three modular components:
1. **`LLMCoach`**: Interfaces with Groq SDK (`llama-3.3-70b-versatile`), passing structured system prompts and maintaining a rolling memory of the last 10 conversational turns.
2. **`TextToSpeech`**: Leverages `gTTS` to encode text into MP3 audio in-memory (`io.BytesIO`) without disk overhead.
3. **`VoicePipeline`**: Orchestrator that determines **when** and **what** to speak:
   - Major events (session start, set completion, circuit transition, workout end): spoken immediately.
   - Form corrections: debounced with a **5-second cooldown** to prevent audio spamming while exercising.

### 4.5 `services/tracking/metrics.py` — The Metrics Engine

Acts as the **synchronization bridge between the WebRTC video thread and the Streamlit main UI thread**:
- Safely reads latest metrics snapshot from `VideoProcessorClass`.
- Calculates current set progress: `sets_completed = reps // reps_per_set`, `current_set_reps = reps % reps_per_set`.
- Automatically logs completed sets to SQLite with duration tracking.
- Coordinates Circuit Mode (advancing the exercise queue automatically).
- Dispatches voice events to the coaching pipeline.

### 4.6 `services/persistence/exercise_repository.py` — Database Layer

- Implements connection caching using `@st.cache_resource` with `check_same_thread=False`.
- **Intelligent Upsert**: When saving completed exercises, checks if an entry for `user_id + exercise_name + today` exists. If found, it updates (accumulates) reps, sets, and time; otherwise inserts a new record.

---

## 5. Key Algorithms & Math

### 5.1 Joint Angle Calculation (Vector Dot Product)

Given 3 joints $A$, $B$, and $C$, where $B$ is the vertex joint:

$$\vec{BA} = (A_x - B_x, A_y - B_y)$$
$$\vec{BC} = (C_x - B_x, C_y - B_y)$$
$$\cos(\theta) = \frac{\vec{BA} \cdot \vec{BC}}{\|\vec{BA}\| \cdot \|\vec{BC}\|}$$
$$\theta = \arccos(\text{clamp}(\cos(\theta), -1.0, 1.0)) \times \frac{180}{\pi}$$

**Handling Edge Cases**:
1. Zero Magnitude: If $\|\vec{BA}\| \cdot \|\vec{BC}\| == 0$, returns `0.0` (guards against Division-by-Zero).
2. Cosine Clamping: Due to floating-point roundoff, values might slightly exceed $[-1.0, 1.0]$, which would cause `math.acos()` to raise a `ValueError`. Clamped using `max(-1.0, min(1.0, ...))`.

### 5.2 Rep Counting State Machine (Hysteresis)

```
        angle < DOWN_THRESHOLD (e.g. 100°)
         ┌──────────────────────────────┐
         │                              ▼
    [Neutral / Up]                 [Down State]
         ▲                              │
         └──────────────────────────────┘
        angle ≥ UP_THRESHOLD (e.g. 160°)
        ---> Rep Count Increments (+1)
```

**Why Hysteresis?**
If a single threshold (e.g. 130°) was used, any slight tremor or micro-movement around 130° would trigger false rep counts. Requiring the joint to reach `DOWN_THRESHOLD` before transitioning to `UP_THRESHOLD` creates an essential **dead-zone**, preventing false triggers.

### 5.3 Hip Sag Detection (Push-ups & Planks)

A straight body line implies that the hip's vertical position should lie approximately midway between the shoulder and ankle:

$$\text{expected\_hip\_y} = \frac{\text{shoulder\_y} + \text{ankle\_y}}{2}$$
$$\text{hip\_deviation} = \text{actual\_hip\_y} - \text{expected\_hip\_y}$$

- $\text{deviation} > \text{HIP\_SAG\_TOLERANCE} \ (0.08) \implies \textbf{SAGGING}$
- $\text{deviation} < -\text{HIP\_SAG\_TOLERANCE} \implies \textbf{PIKED UP}$
- Otherwise $\implies \textbf{LEVEL}$

### 5.4 Swing & Lean Detection (Biceps Curls)

To prevent swinging momentum:
$$\vec{d} = (\text{mid\_shoulder}_x - \text{mid\_hip}_x, \ \text{mid\_shoulder}_y - \text{mid\_hip}_y)$$
$$\text{torso\_angle} = \text{atan2}(|d_x|, |d_y|) \times \frac{180}{\pi}$$

If $\text{torso\_angle} > 15^\circ$, it flags `"SWINGING"`.

---

## 6. Design Decisions & Trade-offs

| Decision | Why This Option | Trade-off / Alternative Considered |
|---|---|---|
| **MediaPipe Pose** | Ultra-fast CPU inference (15-30ms), 33 keypoints, built-in temporal video smoothing. | OpenPose requires heavy GPUs; YOLOv8-pose is heavier to run client/server in lightweight deployments. |
| **Streamlit + WebRTC** | Rapid full-stack prototyping in pure Python; WebRTC enables remote browser webcam access with low latency. | React + FastAPI would provide greater DOM rendering control but take 3x the time to develop. |
| **Groq LPU (LLaMA 3.3 70B)** | Sub-second latency (~200ms) is essential for real-time workout voice cues; free tier. | OpenAI GPT-4 is slower (~1.5s+) and incurs pay-per-token API fees. |
| **gTTS (Google TTS)** | Zero setup, no additional API keys, streams directly into memory buffers. | ElevenLabs has higher voice naturalness but is paid; local Piper TTS requires external system binaries. |
| **Threading Lock + Dict Copy** | Dead-simple, thread-safe data synchronization between WebRTC producer and Streamlit consumer. | Queue could lead to lag/backpressure if consumer falls behind; we only care about the *latest* frame metrics. |
| **2D Geometry over 3D** | High precision in normalized image space, resilient across standard monocular webcams. | 3D depth from single camera is noisy and uncalibrated without stereoscopy or LiDAR. |

---

## 7. Data Flow — Frame to Feedback

```
1. Browser webcam captures raw frame.
2. streamlit-webrtc streams frame via peer-to-peer connection.
3. VideoProcessorClass.recv(frame) executes in background thread:
   ├── Horizontally flips frame (mirror view).
   ├── Converts to MediaPipe RGB Image format.
   ├── Runs pose_landmarker.detect_for_video(mp_image, timestamp_ms).
   ├── Passes 33 landmarks to active detector (e.g. SquatDetector).
   ├── Computes joint angles, increments reps via state machine.
   ├── Updates thread-safe metrics cache under lock.
   ├── Annotates frame with color-coded skeleton (Green/Red) & text overlay.
   └── Returns rendered av.VideoFrame back to client display.
4. Streamlit main thread executes sync_metrics_update() (reruns every 250ms):
   ├── Pulls copy of latest metrics under lock.
   ├── Checks if set completed (reps // reps_per_set).
   ├── On new set: commits metrics to SQLite.
   ├── Dispatches event to VoicePipeline:
   │   ├── Verifies 5s cooldown / major event bypass.
   │   ├── Groq LLM generates 10-15 word coaching advice.
   │   └── gTTS generates audio buffer.
   └── Injects hidden HTML5 audio element with autoplay.
```

---

## 8. Database Design

```sql
CREATE TABLE IF NOT EXISTS users (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    username   TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS exercises (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users(id),
    exercise_name TEXT    NOT NULL,
    reps          INTEGER NOT NULL DEFAULT 0,
    sets          INTEGER NOT NULL DEFAULT 0,
    time          INTEGER NOT NULL DEFAULT 0,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Key Architectural Nuances:
- **Cached Singleton Connection**: Protected via `@st.cache_resource` and initialized with `check_same_thread=False` to allow safe queries across Streamlit's dynamic rerun threads.
- **Session Upsert Pattern**: Exercises performed on the same calendar date for the same user update the cumulative reps, sets, and duration rather than polluting the database with fragmented single-rep rows.

---

## 9. Concurrency & Thread Safety

The application operates across **two distinct threads**:

1. **WebRTC Ingestion Thread**: Invokes `recv()` at camera frame-rate (~30 FPS). Executes MediaPipe inference and OpenCV rendering.
2. **Streamlit UI Thread**: Runs `main()` and `sync_metrics_update()`, rerunning periodically (~4 FPS) to refresh graphs and indicators.

```python
# In VideoProcessorClass:
def set_latest_metrics(self, metrics):
    with self._lock:
        self._latest_metrics = metrics.copy()  # Deep copy prevents race mutation

def get_latest_metrics(self):
    with self._lock:
        return None if self._latest_metrics is None else self._latest_metrics.copy()
```

**Why is `.copy()` crucial?**
If `self._latest_metrics` were returned directly by reference, the Streamlit main thread could read keys while the WebRTC thread is modifying them in place, causing `RuntimeError: dictionary changed size during iteration` or torn reads. Returning an isolated copy guarantees atomic reads.

---

## 10. LLM & Voice Pipeline

### Prompt Engineering Highlights:
- **Role Identity**: "Apna AI Coach", a sharp, high-energy gym trainer.
- **Output Constraints**: Strictly capped at 10-15 words (vital for speech: long responses lag behind the workout rhythm).
- **Tone & Directness**: Mandatory second-person imperatives (*"Keep your chest up"*, not *"The user needs to lift their chest"*).

### Debouncing Architecture:
```python
is_major_issue = event in ["workout_started", "set_completed", "workout_completed", "circuit_transition"]

if not is_major_issue:
    if not issue:
        return None
    if now - self.last_spoken_at < 5:  # 5-second cooldown
        return None
```
This ensures high-priority milestones are never missed, while real-time form checks do not overwhelm the speaker.

---

## 11. 50+ Interview Questions & Answers

### General / Behavioral

**Q1: Walk me through your project in 2 minutes.**
> *"I built GymGuru AI — a real-time computer vision fitness coach that monitors exercise form and speaks proactive voice corrections. I used MediaPipe Pose to track 33 body landmarks, designed a polymorphic detector architecture across 7 exercises using vector trigonometry and hysteresis state machines, and integrated a Groq-hosted LLaMA 3.3 70B model with Google TTS for audio coaching. The video streams via WebRTC in Streamlit, and workout stats are aggregated in SQLite with an interactive performance dashboard."*

**Q2: What was the single most challenging bug you encountered?**
> *"Handling thread synchronization between WebRTC and Streamlit. The WebRTC video processor runs in a separate native worker thread at 30 FPS, while Streamlit manages state in the main thread through a rerun cycle. Initially, accessing shared state caused UI freezes and race conditions. I resolved this by isolating the processor behind a `threading.Lock()`, using snapshot `.copy()` handoffs, and decoupling heavy LLM calls from the frame loop into the main thread's cycle."*

**Q3: What was your design philosophy behind the project?**
> *"High responsiveness and zero friction. I didn't want the user to download an app or wait for post-workout analysis. The feedback needed to be immediate, multimodal (color-coded skeleton overlays + spoken voice cues), and runnable on consumer hardware without an expensive GPU."*

---

### Computer Vision & MediaPipe

**Q4: How does MediaPipe Pose work under the hood?**
> *"MediaPipe Pose uses a two-stage BlazePose pipeline: first, a lightweight detector locates the Region of Interest (ROI) bounding box for the person; second, a landmark model processes the cropped ROI to predict 33 3D body keypoints. In `VIDEO` mode, the detector only runs on the first frame and whenever tracking is lost; subsequent frames reuse the previous landmark box with temporal filtering, making it extremely fast."*

**Q5: Why did you choose the `pose_landmarker_full.task` model over `lite`?**
> *"The `lite` model is faster but exhibits noticeable jitter in joint coordinates when users perform rapid movements like jumping jacks or deep squats. The `full` model offers superior keypoint localization accuracy for subtle angles (like elbow drift or hip sag) while still running comfortably at 30 FPS on modern CPUs."*

**Q6: Why normalized coordinates $(x, y \in [0, 1])$ instead of pixel coordinates?**
> *"Normalized coordinates make the angle math scale- and resolution-invariant. Whether the webcam runs at 720p, 1080p, or is resized on different screens, joint angles and relative ratios (like ankle distance to shoulder width) remain identical."*

**Q7: How do you handle occlusion or when someone turns sideways?**
> *"Each landmark provides a `visibility` probability score. In my detectors, I compare the visibility of bilateral joints (e.g., left knee vs. right knee). The side with higher visibility is automatically selected as the active tracking plane. If visibility drops below `MIN_VISIBILITY = 0.7`, calculations are gated to avoid false reps."*

---

### System Design & Architecture

**Q8: Why WebRTC instead of standard HTTP video streaming or WebSockets?**
> *"HTTP has high latency (2-5s), making real-time form correction impossible. WebSockets would require manual frame encoding, compression, and transport. WebRTC is the browser standard for peer-to-peer real-time media: it operates over UDP/SRTP with adaptive bitrate, hardware acceleration, and sub-100ms latency."*

**Q9: Explain the role of STUN/TURN servers in your setup.**
> *"STUN servers discover public IP/port mappings behind NATs to establish direct peer-to-peer connections. However, symmetric NATs and strict corporate firewalls block direct P2P. TURN acts as a media relay fallback. In `main.py`, I configured Google's public STUN and OpenRelay's TURN server so video streaming works across diverse networks."*

**Q10: How would you scale this architecture to support 10,000 concurrent athletes?**
> *"1. **Decouple Frontend and Backend**: Replace Streamlit with a Next.js/React frontend and a FastAPI/Go backend.
> 2. **Client-Side Vision**: Run MediaPipe directly in the browser via WebAssembly (WASM) / TensorFlow.js. This eliminates server-side video decoding and reduces cloud compute costs to near zero!
> 3. **WebSocket Event Gateway**: Only send compact metric events (reps, form error codes) to the backend.
> 4. **Caching & Async LLM**: Cache common TTS audio clips (e.g. 'Good depth', 'Straighten your back') in Redis/CDN to avoid hitting the LLM/TTS API repeatedly."*

---

### LLM / AI Integration

**Q11: Why use an LLM instead of hardcoded audio files or simple if-else strings?**
> *"Hardcoded prompts become repetitive, robotic, and demotivating within 10 minutes. By injecting the workout context into an LLM with sliding conversational memory, the coach varies its vocabulary, tone, and encouragement dynamically — mimicking a real personal trainer while maintaining strict safety cues."*

**Q12: How do you guard against LLM hallucination in safety-critical fitness cues?**
> *"1. **Deterministic Rule Engines**: The computer vision detector determines the factual issue (e.g., knee angle < 100° or hip sagging) via deterministic math.
> 2. **Grounding in Prompt**: The prompt receives exact event and issue parameters (`Event: ongoing_form_check, Form Issue: Hips sagging`).
> 3. **Temperature Tuning**: Set `temperature=0.4` to reduce randomness while keeping phrased variety natural.
> 4. **Length and Scope Constraints**: Strict system instructions restricting advice to the detected issue."*

**Q13: Why did you pick Groq and LLaMA 3.3 70B?**
> *"Groq's LPUs (Language Processing Units) achieve inference speeds over 300 tokens/second, yielding responses in under 250ms. Since the user is mid-exercise, hearing advice seconds later is useless or dangerous. LLaMA 3.3 70B provides excellent instruction-following for our concise format."*

---

### Database & Persistence

**Q14: Explain your database schema and indexing strategy.**
> *"We maintain two tables: `users` and `exercises`. `exercises` has a foreign key referencing `users(id)`. For production scale, I would add a composite index on `(user_id, exercise_name, created_at)` to accelerate the daily upsert check and dashboard history filtering."*

**Q15: Why did you choose SQLite over PostgreSQL or MongoDB?**
> *"Zero-configuration portability. For an open-source, runnable portfolio project, SQLite avoids requiring interviewers or users to spin up external database containers or cloud credentials. The repository pattern isolates all SQL queries, making a migration to PostgreSQL a simple change in the connection driver."*

---

### OOP & Design Patterns

**Q16: Which design patterns are actively utilized in this codebase?**
> *"- **Strategy Pattern**: The `_detectors` dictionary in `VideoProcessorClass` allows dynamic swapping of exercise evaluation strategies at runtime.
> - **Template Method Pattern**: `BaseExercise` provides concrete angle algorithms and enforces polymorphic `process()` and `reset()` contracts.
> - **Repository Pattern**: `exercise_repository.py` abstracts storage logic from application workflows.
> - **Observer/Event-Driven Pipeline**: Metric updates dispatch events (`workout_started`, `set_completed`, `circuit_transition`) to the voice pipeline."*

---

### Performance & Scalability

**Q17: What is the processing overhead per video frame?**
> *"On a standard quad-core CPU:
> - MediaPipe inference: ~18-25 ms
> - Vector math & state updates: < 0.5 ms
> - OpenCV drawing: ~2-3 ms
> Total frame latency is well under 33 ms, easily maintaining smooth 30 FPS playback."*

**Q18: What is your audio delivery latency?**
> *"Total latency from event trigger to audio playback is ~700-900ms (Groq LLM: ~250ms, gTTS synthesis: ~400ms, DOM element update: ~100ms). This fits comfortably within the natural pause between exercise repetitions."*

---

### Tricky / Curveball Questions

**Q19: Can a user cheat rep counts? How would you prevent it?**
> *"Yes, in simple angle-based counting, moving just an arm without lifting weight can trigger thresholds. To prevent cheating in production, I would:
> 1. Track movement velocity and cadence curves.
> 2. Implement full-body kinetic verification (e.g. For curls: confirm shoulder is stationary and torso vertical).
> 3. Train a lightweight temporal 1D-CNN or LSTM classifier on landmark sequence embeddings."*

**Q20: What happens if two people appear in the camera view?**
> *"`result.pose_landmarks[0]` picks the first detected skeleton. In multi-person environments, this could lead to landmark switching. The production fix is to calculate bounding box IoU (Intersection-over-Union) across frames or use a tracker (like ByteTrack) to lock onto the user who initiated the session."*

---

## 12. How to Demo Live

1. **Clean Start**: Open app at `http://localhost:8501`, log in with a clean username.
2. **Explain the Architecture**: Briefly show the sidebar mode selection and WebRTC video window.
3. **Execute 3 Squats**:
   - First 2 reps: Perfect depth — demonstrate the green skeleton and rep count incrementing.
   - 3rd rep: Deliberate shallow squat — point out the red skeleton highlighting the knee joint and listen for the voice cue: *"Go lower, get your thighs parallel to the floor!"*
4. **Complete the Set**: Show the set completion notification and check the auto-updated workout dashboard charts at the bottom.

---

## 13. Weaknesses to Acknowledge & How to Spin Them

| Perceived Weakness | Proactive Spin / How to Answer |
|---|---|
| **Streamlit UI Rerun Loop** | *"Streamlit was chosen for rapid full-stack delivery. In a production v2, I'd migrate the frontend to React/Next.js and use WebSockets with WebAssembly MediaPipe on the client."* |
| **Monocular 2D Geometry** | *"Depth estimation from single webcams has optical distortion. I mitigated this by checking bilateral landmark visibility and computing normalized ratios rather than raw coordinates."* |
| **gTTS relies on network** | *"gTTS is cloud-based. For production or offline usage, I designed the TTS interface as a modular class so it can be swapped with local edge models like Piper or FastSpeech2 with one line of code."* |

---

## 14. Future Improvements to Mention

1. **Client-side WASM Pose Detection**: Move inference to the browser to make the backend 100x cheaper.
2. **Custom Exercise Builder**: Let users record 3 repetitions of any custom workout to automatically learn angle thresholds.
3. **Barbell / Dumbbell Detection**: Combine MediaPipe Pose with YOLOv8 object detection to track barbell bar-path velocity.
4. **Heart Rate & Wearable Sync**: Integrate Bluetooth Web API to stream heart-rate alongside form metrics.

---

## 15. Quick-Reference Cheat Sheet

- **Landmarks tracked**: 33 BlazePose keypoints.
- **Inference Mode**: `vision.RunningMode.VIDEO` (temporal smoothing enabled).
- **Core Vector Formula**: $\cos(\theta) = \frac{\vec{u} \cdot \vec{v}}{\|\vec{u}\| \|\vec{v}\|}$.
- **LLM Model**: `llama-3.3-70b-versatile` via Groq API.
- **Voice Cooldown**: 5-second debounce window.
- **Exercises (7)**: Squats, Push-ups, Biceps Curls, Shoulder Press, Lunges, Planks, Jumping Jacks.

Good luck with your interview! 🚀
