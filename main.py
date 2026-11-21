import streamlit as st
import os
import time
import pandas as pd
import altair as alt
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
from services.auth.login_wall import render_login_wall
from services.state.session_defaults import initial_session_defaults
from services.config.workout_config import EXERCISE_OPTION
from services.ui.style_loader import load_css, inject_local_font, inject_webrtc_styles
from services.persistence.exercise_repository import init_db, get_users_exercises
from streamlit_webrtc import webrtc_streamer, WebRtcMode
from services.vision.exercise_video_processor import VideoProcessorClass
from services.tracking.metrics import sync_metrics_update
from groq import Groq
from services.coaching.llm import LLMCoach
from services.coaching.tts import TextToSpeech
from services.coaching.voice_pipeline import VoicePipeline, autoplay_audio


def get_form_badge_html(exercise, state):
    """Generates a high-visibility real-time form status pill."""
    if exercise == "Squats":
        depth = state.get("depth_status", "N/A")
        if depth in ["GOOD DEPTH", "PARALLEL"]:
            return '<span class="status-pill status-pill-good">🟢 GOOD DEPTH</span>'
        elif depth == "TOO HIGH":
            return '<span class="status-pill status-pill-fault">🔴 SHALLOW DEPTH</span>'
        return f'<span class="status-pill status-pill-neutral">⚪ {depth}</span>'
    elif exercise == "Push-ups":
        alignment = state.get("body_alignment", "N/A")
        hip = state.get("hip_status", "N/A")
        if alignment == "Good Form" and hip == "GOOD":
            return '<span class="status-pill status-pill-good">🟢 EXCELLENT FORM</span>'
        elif hip in ["SAGGING", "PIKED UP"]:
            return f'<span class="status-pill status-pill-fault">🔴 HIP {hip}</span>'
        elif alignment == "Poor Form":
            return '<span class="status-pill status-pill-fault">🔴 MISALIGNED</span>'
        return '<span class="status-pill status-pill-neutral">⚪ READY</span>'
    elif exercise == "Biceps Curls (Dumbbell)":
        swing = state.get("swing_status", "N/A")
        shoulder = state.get("shoulder_status", "N/A")
        if swing == "CHEATING":
            return '<span class="status-pill status-pill-fault">🔴 BODY SWINGING</span>'
        elif shoulder == "DRIFTING":
            return '<span class="status-pill status-pill-fault">🔴 ELBOW DRIFT</span>'
        return '<span class="status-pill status-pill-good">🟢 CONTROLLED FORM</span>'
    elif exercise == "Shoulder Press":
        ext = state.get("extension_status", "N/A")
        arch = state.get("back_arch_status", "N/A")
        if arch == "ARCHING":
            return '<span class="status-pill status-pill-fault">🔴 BACK ARCHING</span>'
        elif ext == "LOCKOUT":
            return '<span class="status-pill status-pill-good">🟢 FULL EXTENSION</span>'
        return '<span class="status-pill status-pill-neutral">⚪ PRESSING</span>'
    elif exercise == "Lunges":
        bal = state.get("balance_status", "N/A")
        if bal == "UNSTABLE":
            return '<span class="status-pill status-pill-fault">🔴 CHECK BALANCE</span>'
        return '<span class="status-pill status-pill-good">🟢 BALANCED</span>'
    elif exercise == "Planks":
        hip = state.get("hip_status", "N/A")
        align = state.get("body_alignment", "N/A")
        if hip in ["SAGGING", "PIKED UP"] or align == "Poor Form":
            return '<span class="status-pill status-pill-fault">🔴 SAGGING / BENT</span>'
        return '<span class="status-pill status-pill-good">🟢 SOLID PLANK</span>'
    elif exercise == "Jumping Jacks":
        stance = state.get("jack_status", "N/A")
        arms = state.get("arm_extension", "N/A")
        if stance == "WIDE" and arms == "UP":
            return '<span class="status-pill status-pill-good">🟢 FULL REACH</span>'
        return f'<span class="status-pill status-pill-neutral">⚪ {stance}</span>'
    return '<span class="status-pill status-pill-neutral">⚪ ACTIVE</span>'


def start_workout_action(workout_mode, plan_exercise, plan_sets, plan_reps, circuit_exercises, circuit_targets):
    """Initializes and launches a workout session safely."""
    if workout_mode == "Single Exercise":
        st.session_state.circuit_mode = False
        st.session_state.exercise_type = plan_exercise
        st.session_state.target_sets = int(plan_sets)
        st.session_state.reps_per_set = int(plan_reps)
    else:
        if not circuit_exercises:
            st.error("Please select at least one exercise for the circuit!")
            return False
        st.session_state.circuit_mode = True
        st.session_state.circuit_queue = circuit_exercises
        st.session_state.circuit_targets = circuit_targets
        st.session_state.circuit_index = 0
        first_ex = circuit_exercises[0]
        st.session_state.exercise_type = first_ex
        st.session_state.target_sets = int(circuit_targets[first_ex]["sets"])
        st.session_state.reps_per_set = int(circuit_targets[first_ex]["reps"])

    st.session_state.reps = 0
    st.session_state.sets_completed = 0
    st.session_state.current_set_reps = 0
    st.session_state.workout_started = True
    st.session_state.workout_started_at = time.time()
    st.session_state.set_cycle_started_at = time.time()
    st.session_state.last_saved_sets_completed = 0
    st.session_state.show_summary = False

    if st.session_state.get("voice_pipeline"):
        result = st.session_state.voice_pipeline.process_event(
            event="workout_started",
            exercise=st.session_state.exercise_type,
            metrics={}
        )
        if result:
            st.session_state.audio_to_play, st.session_state.coach_feedback = result

    st.session_state.last_notified_sets_completed = 0
    st.session_state.last_notified_workout_complete = False
    return True


def main():
    st.set_page_config(
        page_icon="🏋️",
        page_title="GymGuru AI • Real-Time Workout Coach",
        initial_sidebar_state="expanded",
        layout="wide"  # Responsive full-width dashboard layout
    )

    load_css(os.path.join(os.getcwd(), "static", "style.css"))
    inject_local_font(os.path.join(os.getcwd(), "static", "AdobeClean.otf"), "AdobeClean")

    init_db()

    if not render_login_wall():
        return

    initial_session_defaults()

    if "voice_pipeline" not in st.session_state:
        try:
            api_key = os.environ.get("GROQ_API_KEY", "")
            if not api_key and hasattr(st, "secrets") and "GROQ_API_KEY" in st.secrets:
                api_key = st.secrets["GROQ_API_KEY"]

            if not api_key:
                st.sidebar.warning("⚠️ Voice Coach disabled: GROQ_API_KEY not set.")
                st.session_state.voice_pipeline = None
            else:
                groq_client = Groq(api_key=api_key)
                llm_coach = LLMCoach(groq_client)
                tts = TextToSpeech()
                st.session_state.voice_pipeline = VoicePipeline(llm_coach, tts)
        except Exception as e:
            st.sidebar.error(f"⚠️ Voice Coach initialization failed: {e}")
            st.session_state.voice_pipeline = None

    workout_started = st.session_state.get("workout_started", False)
    show_summary = st.session_state.get("show_summary", False)

    # =========================================================
    # SIDEBAR CONTROLS & MONITORING
    # =========================================================
    with st.sidebar:
        st.markdown("""
        <div style="display:flex; align-items:center; gap:0.6rem; margin-bottom:0.8rem;">
            <span style="font-size:1.8rem;">🏋️</span>
            <div>
                <div style="font-size:1.25rem; font-weight:800; color:#F8FAFC; line-height:1.1;">GymGuru AI</div>
                <div style="font-size:0.8rem; color:#A3E635; font-weight:600;">AI FITNESS COACH</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if st.session_state.username:
            st.caption(f"Athlete: **@{st.session_state.username}** 🟢")

        st.toggle("🔇 Mute Voice Coach", value=False, key="mute_audio")
        st.divider()

        if workout_started:
            curr_ex = st.session_state.get("exercise_type", "")
            t_sets = st.session_state.get("target_sets", 0)
            r_set = st.session_state.get("reps_per_set", 0)

            st.markdown(f"""
            <div style="background:#151E2B; border:1px solid rgba(255,255,255,0.08); border-radius:12px; padding:1rem; margin-bottom:1rem;">
                <div style="font-size:0.8rem; color:#94A3B8; text-transform:uppercase; font-weight:700;">Active Exercise</div>
                <div style="font-size:1.2rem; font-weight:800; color:#38BDF8;">{curr_ex}</div>
                <div style="font-size:0.88rem; color:#F8FAFC; margin-top:0.25rem;">{t_sets} Sets × {r_set} Reps</div>
            </div>
            """, unsafe_allow_html=True)

            if st.session_state.get("circuit_mode", False):
                st.markdown("**Circuit Progression:**")
                c_idx = st.session_state.get("circuit_index", 0)
                c_queue = st.session_state.get("circuit_queue", [])
                c_targets = st.session_state.get("circuit_targets", {})
                for i, ex in enumerate(c_queue):
                    s_count = c_targets[ex]["sets"]
                    r_count = c_targets[ex]["reps"]
                    if i < c_idx:
                        st.markdown(f"~~{i+1}. {ex} ({s_count}x{r_count})~~ ✅")
                    elif i == c_idx:
                        st.markdown(f"👉 <span style='color:#A3E635; font-weight:700;'>{i+1}. {ex} ({s_count}x{r_count})</span>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"{i+1}. {ex} ({s_count}x{r_count})")

            st.markdown("<div style='margin-top:1.5rem;'></div>", unsafe_allow_html=True)
            if st.button("⏹️ End Workout Session", key="sidebar_end_btn", width="stretch"):
                st.session_state["workout_summary"] = {
                    "exercise": curr_ex,
                    "total_reps": st.session_state.get("reps", 0),
                    "sets_completed": st.session_state.get("sets_completed", 0),
                    "target_sets": t_sets,
                    "duration": time.time() - st.session_state.get("workout_started_at", time.time())
                }
                st.session_state["workout_started"] = False
                st.session_state["show_summary"] = True
                st.rerun()

    # =========================================================
    # TOP HEADER NAVIGATION BAR
    # =========================================================
    top_col1, top_col2 = st.columns([7, 3])
    with top_col1:
        st.markdown(f"""
        <div style="display:flex; align-items:center; gap:0.75rem; margin-bottom:1rem;">
            <div style="font-size:1.6rem; font-weight:800; color:#F8FAFC; letter-spacing:-0.02em;">
                GymGuru <span style="color:#A3E635;">AI</span>
            </div>
            <span style="background:rgba(163,230,53,0.12); border:1px solid rgba(163,230,53,0.3); color:#A3E635; font-size:0.75rem; font-weight:700; padding:0.2rem 0.6rem; border-radius:9999px;">
                V2.0 LIVE COACH
            </span>
        </div>
        """, unsafe_allow_html=True)
    with top_col2:
        st.markdown(f"""
        <div style="text-align:right; color:#94A3B8; font-size:0.9rem; margin-top:0.4rem;">
            Athlete: <span style="color:#F8FAFC; font-weight:700;">@{st.session_state.username}</span> 
            <span style="color:#22C55E; margin-left:4px;">●</span>
        </div>
        """, unsafe_allow_html=True)

    # =========================================================
    # SCREEN D: WORKOUT COMPLETION SUMMARY
    # =========================================================
    if show_summary:
        summary = st.session_state.get("workout_summary", {})
        sum_ex = summary.get("exercise", "Workout")
        sum_reps = summary.get("total_reps", 0)
        sum_sets = summary.get("sets_completed", 0)
        sum_target = summary.get("target_sets", 0)
        sum_dur = int(summary.get("duration", 0))

        s_hours = sum_dur // 3600
        s_mins = (sum_dur % 3600) // 60
        s_secs = sum_dur % 60
        dur_str = f"{s_hours:02d}:{s_mins:02d}:{s_secs:02d}"

        st.markdown(f"""
        <div class="hero-card" style="text-align:center; padding:3rem 2rem;">
            <div style="font-size:3.5rem; margin-bottom:0.5rem;">🎉</div>
            <h1 style="color:#F8FAFC; font-size:2.4rem; font-weight:800; margin-bottom:0.5rem;">
                Workout <span style="color:#A3E635;">Completed!</span>
            </h1>
            <p style="color:#94A3B8; font-size:1.1rem; max-width:600px; margin:0 auto 2rem auto;">
                Outstanding effort! Your session metrics have been analyzed and securely saved to your workout history.
            </p>
            <div style="display:flex; justify-content:center; gap:2.5rem; margin-bottom:2.5rem; flex-wrap:wrap;">
                <div style="background:#1C2736; border:1px solid rgba(255,255,255,0.08); border-radius:14px; padding:1.2rem 2rem; min-width:140px;">
                    <div style="font-size:0.85rem; color:#94A3B8; text-transform:uppercase; font-weight:600;">Exercise</div>
                    <div style="font-size:1.4rem; font-weight:800; color:#38BDF8;">{sum_ex}</div>
                </div>
                <div style="background:#1C2736; border:1px solid rgba(255,255,255,0.08); border-radius:14px; padding:1.2rem 2rem; min-width:140px;">
                    <div style="font-size:0.85rem; color:#94A3B8; text-transform:uppercase; font-weight:600;">Total Reps</div>
                    <div style="font-size:1.4rem; font-weight:800; color:#A3E635;">{sum_reps}</div>
                </div>
                <div style="background:#1C2736; border:1px solid rgba(255,255,255,0.08); border-radius:14px; padding:1.2rem 2rem; min-width:140px;">
                    <div style="font-size:0.85rem; color:#94A3B8; text-transform:uppercase; font-weight:600;">Sets Completed</div>
                    <div style="font-size:1.4rem; font-weight:800; color:#F8FAFC;">{sum_sets} / {sum_target}</div>
                </div>
                <div style="background:#1C2736; border:1px solid rgba(255,255,255,0.08); border-radius:14px; padding:1.2rem 2rem; min-width:140px;">
                    <div style="font-size:0.85rem; color:#94A3B8; text-transform:uppercase; font-weight:600;">Duration</div>
                    <div style="font-size:1.4rem; font-weight:800; color:#F8FAFC;">{dur_str}</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        _, b_col, _ = st.columns([1, 1.5, 1])
        with b_col:
            if st.button("Back to Dashboard ➔", kind="primary", width="stretch", key="back_dash_btn"):
                st.session_state["show_summary"] = False
                st.session_state["workout_summary"] = None
                st.rerun()

        return

    # =========================================================
    # SCREEN C: ACTIVE WORKOUT INTERFACE (WIDE 2-COLUMN DASHBOARD)
    # =========================================================
    if workout_started:
        exercise = st.session_state.get("exercise_type", "Squats")
        total_reps = st.session_state.get("reps", 0)
        current_set_reps = st.session_state.get("current_set_reps", 0)
        reps_per_set = st.session_state.get("reps_per_set", 10)
        sets_completed = st.session_state.get("sets_completed", 0)
        target_sets = st.session_state.get("target_sets", 3)

        col_cam, col_hud = st.columns([65, 35], gap="large")

        # --- LEFT COLUMN: LIVE WEBRTC CAMERA STREAM ---
        with col_cam:
            st.markdown(f"""
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.75rem;">
                <div style="display:flex; align-items:center; gap:0.6rem;">
                    <span class="status-pill status-pill-live">● LIVE CAMERA</span>
                    <span style="font-weight:700; font-size:1.2rem; color:#F8FAFC;">{exercise}</span>
                </div>
                <div style="color:#94A3B8; font-size:0.9rem; font-weight:600;">
                    Target: {target_sets} Sets × {reps_per_set} Reps
                </div>
            </div>
            """, unsafe_allow_html=True)

            # WebRTC Server ICE Resolution
            ice_servers = [
                {"urls": ["stun:stun.l.google.com:19302"]},
                {"urls": ["stun:stun1.l.google.com:19302"]},
                {"urls": ["stun:stun2.l.google.com:19302"]},
            ]

            turn_url = os.environ.get("TURN_URL", "")
            turn_username = os.environ.get("TURN_USERNAME", "")
            turn_password = os.environ.get("TURN_PASSWORD", "")

            if hasattr(st, "secrets"):
                turn_url = st.secrets.get("TURN_URL", turn_url)
                turn_username = st.secrets.get("TURN_USERNAME", turn_username)
                turn_password = st.secrets.get("TURN_PASSWORD", st.secrets.get("TURN_CREDENTIAL", turn_password))

            if turn_url:
                if isinstance(turn_url, str):
                    urls = [u.strip() for u in turn_url.split(",") if u.strip()]
                elif isinstance(turn_url, list):
                    urls = list(turn_url)
                else:
                    urls = [str(turn_url)]

                tcp_urls = []
                for u in urls:
                    if (u.startswith("turn:") or u.startswith("turns:")) and "transport=" not in u:
                        tcp_urls.append(f"{u}?transport=tcp")

                all_turn_urls = urls + [t for t in tcp_urls if t not in urls]

                ice_servers.append({
                    "urls": all_turn_urls,
                    "username": str(turn_username),
                    "credential": str(turn_password),
                })

            context = webrtc_streamer(
                key="exercise-analysis",
                mode=WebRtcMode.SENDRECV,
                video_processor_factory=VideoProcessorClass,
                rtc_configuration={"iceServers": ice_servers},
                media_stream_constraints={
                    "video": {
                        "width": {"ideal": 640},
                        "height": {"ideal": 480},
                        "frameRate": {"ideal": 30}
                    },
                    "audio": False
                },
                async_processing=True
            )

            inject_webrtc_styles()
            sync_metrics_update(context)

            # AI Voice Coach Speech Bubble
            if st.session_state.get("audio_to_play") and not st.session_state.get("mute_audio", False):
                autoplay_audio(st.session_state.audio_to_play)

            if st.session_state.get("coach_feedback"):
                st.markdown(f"""
                <div class="coach-bubble">
                    <div class="coach-bubble-icon">🤖</div>
                    <div class="coach-bubble-text">
                        <span style="color:#A3E635; font-size:0.8rem; text-transform:uppercase; letter-spacing:0.06em; display:block; margin-bottom:2px;">
                            AI Voice Coach
                        </span>
                        "{st.session_state.coach_feedback}"
                    </div>
                </div>
                """, unsafe_allow_html=True)

            if context.state.playing:
                time.sleep(0.25)
                st.rerun()

            inject_webrtc_styles()

        # --- RIGHT COLUMN: HIGH-VISIBILITY TELEMETRY HUD ---
        with col_hud:
            st.markdown("""
            <div style="font-size:0.85rem; font-weight:700; color:#94A3B8; text-transform:uppercase; letter-spacing:0.06em; margin-bottom:0.75rem;">
                Workout Telemetry
            </div>
            """, unsafe_allow_html=True)

            # 1. Giant Rep Counter (Readable from 6-8 feet away)
            st.markdown(f"""
            <div class="giant-rep-container">
                <div style="font-size:0.9rem; font-weight:700; color:#94A3B8; text-transform:uppercase; letter-spacing:0.06em; margin-bottom:2px;">
                    Set {sets_completed + 1} of {target_sets}
                </div>
                <div class="giant-rep-num">{current_set_reps}</div>
                <div class="giant-rep-target">of {reps_per_set} Reps Target</div>
            </div>
            """, unsafe_allow_html=True)

            # Set Progress Bar
            progress_pct = min(1.0, current_set_reps / max(1, reps_per_set))
            st.progress(progress_pct)

            # 2. Session Progress Summary
            m_col1, m_col2 = st.columns(2)
            with m_col1:
                st.metric("Total Reps", f"{total_reps} 🏋️")
            with m_col2:
                st.metric("Sets Done", f"{sets_completed} / {target_sets} 🔢")

            st.markdown("<div style='margin-top:0.8rem;'></div>", unsafe_allow_html=True)

            # 3. Dynamic Biomechanical Angle Telemetry & Form Status
            st.markdown(f"""
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.6rem;">
                <span style="font-size:0.85rem; font-weight:700; color:#94A3B8; text-transform:uppercase;">Live Form Check</span>
                {get_form_badge_html(exercise, st.session_state)}
            </div>
            """, unsafe_allow_html=True)

            # Exercise Specific Joint Metrics
            if exercise == "Squats":
                q1, q2 = st.columns(2)
                with q1:
                    st.metric("Knee Angle", f"{st.session_state.get('knee_angle', 0)}°")
                with q2:
                    st.metric("Back Angle", f"{st.session_state.get('back_angle', 0)}°")

            elif exercise == "Push-ups":
                p1, p2 = st.columns(2)
                with p1:
                    st.metric("Elbow Angle", f"{st.session_state.get('elbow_angle', 0)}°")
                with p2:
                    st.metric("Hip Sag", f"{st.session_state.get('hip_status', 'N/A')}")

            elif exercise == "Biceps Curls (Dumbbell)":
                b1, b2 = st.columns(2)
                with b1:
                    st.metric("Elbow Angle", f"{st.session_state.get('elbow_angle', 0)}°")
                with b2:
                    st.metric("Torso Swing", f"{st.session_state.get('swing_status', 'N/A')}")

            elif exercise == "Shoulder Press":
                s1, s2 = st.columns(2)
                with s1:
                    st.metric("Elbow Angle", f"{st.session_state.get('elbow_angle', 0)}°")
                with s2:
                    st.metric("Back Arch", f"{st.session_state.get('back_arch_status', 'N/A')}")

            elif exercise == "Lunges":
                l1, l2 = st.columns(2)
                with l1:
                    st.metric("Front Knee", f"{st.session_state.get('front_knee_angle', 0)}°")
                with l2:
                    st.metric("Balance", f"{st.session_state.get('balance_status', 'N/A')}")

            elif exercise == "Planks":
                pl1, pl2 = st.columns(2)
                with pl1:
                    st.metric("Body Angle", f"{st.session_state.get('body_angle', 180)}°")
                with pl2:
                    st.metric("Alignment", f"{st.session_state.get('body_alignment', 'N/A')}")

            elif exercise == "Jumping Jacks":
                j1, j2 = st.columns(2)
                with j1:
                    st.metric("Stance Ratio", f"{st.session_state.get('stance_ratio', 1.0)}")
                with j2:
                    st.metric("Arms", f"{st.session_state.get('arm_extension', 'N/A')}")

            # 4. End Workout Button
            st.markdown("<div style='margin-top:1.8rem;'></div>", unsafe_allow_html=True)
            if st.button("⏹️ Finish Workout", key="hud_end_btn", width="stretch"):
                st.session_state["workout_summary"] = {
                    "exercise": exercise,
                    "total_reps": total_reps,
                    "sets_completed": sets_completed,
                    "target_sets": target_sets,
                    "duration": time.time() - st.session_state.get("workout_started_at", time.time())
                }
                st.session_state["workout_started"] = False
                st.session_state["show_summary"] = True
                st.rerun()

        return

    # =========================================================
    # SCREEN B: IDLE DASHBOARD (WORKOUT SETUP & HISTORICAL ANALYTICS)
    # =========================================================
    st.markdown(f"""
    <div class="hero-card">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:1.5rem;">
            <div>
                <span class="login-badge" style="margin-bottom:0.6rem;">ATHLETE PORTAL</span>
                <h1 style="color:#F8FAFC; font-size:2.2rem; font-weight:800; margin-bottom:0.4rem; letter-spacing:-0.02em;">
                    Ready for your <span style="color:#A3E635;">next workout?</span>
                </h1>
                <p style="color:#94A3B8; font-size:1.05rem; max-width:620px; margin-bottom:0; line-height:1.5;">
                    Your AI fitness coach is ready to analyze your form in real-time, count your reps with hysteresis precision, 
                    and deliver voice cues through your webcam.
                </p>
            </div>
            <div style="background:rgba(28,39,54,0.6); border:1px solid rgba(255,255,255,0.08); border-radius:14px; padding:1.2rem 1.6rem; text-align:center;">
                <div style="font-size:0.85rem; color:#94A3B8; font-weight:600;">ACTIVE ATHLETE</div>
                <div style="font-size:1.4rem; font-weight:800; color:#38BDF8;">@{st.session_state.username}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # In-Page Workout Configuration Dashboard
    st.markdown("### 🎯 Configure Workout Session")
    config_tab1, config_tab2 = st.tabs(["Single Exercise Training", "Circuit Routine Mode"])

    with config_tab1:
        c1, c2, c3 = st.columns([4, 3, 3])
        with c1:
            plan_exercise = st.selectbox("Select Exercise", options=EXERCISE_OPTION, key="dash_plan_exercise")
        with c2:
            plan_sets = st.number_input("Target Sets", min_value=1, max_value=50, value=3, step=1, key="dash_plan_sets")
        with c3:
            plan_reps = st.number_input("Reps per Set", min_value=1, max_value=50, value=10, step=1, key="dash_plan_reps")

        st.markdown("<div style='margin-top:0.6rem;'></div>", unsafe_allow_html=True)
        if st.button("🚀 Start Single Workout", kind="primary", width="stretch", key="dash_start_single"):
            if start_workout_action("Single Exercise", plan_exercise, plan_sets, plan_reps, [], {}):
                st.rerun()

    with config_tab2:
        circuit_exercises = st.multiselect(
            "Select Exercises in Circuit Sequence",
            options=EXERCISE_OPTION,
            default=["Squats", "Push-ups"],
            key="dash_circuit_exercises"
        )
        circuit_targets = {}
        if circuit_exercises:
            st.markdown("<div style='margin-top:0.5rem;'></div>", unsafe_allow_html=True)
            c_cols = st.columns(len(circuit_exercises))
            for i, ex in enumerate(circuit_exercises):
                with c_cols[i]:
                    st.markdown(f"**{ex}**")
                    s = st.number_input(f"Sets", min_value=1, max_value=10, value=1, step=1, key=f"dash_s_{ex}")
                    r = st.number_input(f"Reps", min_value=1, max_value=50, value=10, step=1, key=f"dash_r_{ex}")
                    circuit_targets[ex] = {"sets": s, "reps": r}

        st.markdown("<div style='margin-top:0.6rem;'></div>", unsafe_allow_html=True)
        if st.button("🚀 Launch Circuit Session", kind="primary", width="stretch", key="dash_start_circuit"):
            if start_workout_action("Circuit Mode", None, None, None, circuit_exercises, circuit_targets):
                st.rerun()

    st.markdown("<div style='margin-top:2.5rem;'></div>", unsafe_allow_html=True)
    st.divider()

    # =========================================================
    # HISTORICAL ANALYTICS & RECENT LOGS
    # =========================================================
    st.markdown("### 📊 Athletic Performance History")

    user_id = st.session_state.get("user_id", 0)

    if isinstance(user_id, int):
        history_rows = get_users_exercises(user_id)

        df_arr = [
            {
                "Exercise": row["exercise_name"],
                "Reps": row["reps"],
                "Sets": row["sets"],
                "Time (sec)": row["time"],
                "Date": row["created_at"]
            }
            for row in history_rows
        ]

        df = pd.DataFrame(df_arr)

        if not df.empty:
            df["Date"] = pd.to_datetime(df["Date"]).dt.date

            # KPI Metric Cards
            total_reps_all = df["Reps"].sum()
            total_sets_all = df["Sets"].sum()
            total_seconds_all = df["Time (sec)"].sum()

            hours = int(total_seconds_all // 3600)
            minutes = int((total_seconds_all % 3600) // 60)
            seconds = int(total_seconds_all % 60)
            time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

            kpi1, kpi2, kpi3 = st.columns(3)
            with kpi1:
                st.metric("Total Lifetime Reps", f"{total_reps_all:,} 🏋️")
            with kpi2:
                st.metric("Completed Sets", f"{total_sets_all:,} 🔢")
            with kpi3:
                st.metric("Total Workout Time", f"{time_str} ⏱️")

            st.markdown("<div style='margin-top:1.5rem;'></div>", unsafe_allow_html=True)

            # Themed Altair Charts
            ch1, ch2 = st.columns(2, gap="large")

            with ch1:
                st.markdown("##### 🏋️ Exercise Volume Distribution (Reps)")
                vol_df = df.groupby("Exercise")["Reps"].sum().reset_index()
                vol_chart = (
                    alt.Chart(vol_df)
                    .mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6, color="#A3E635")
                    .encode(
                        x=alt.X("Exercise:N", title=None, axis=alt.Axis(labelAngle=-20, labelColor="#94A3B8")),
                        y=alt.Y("Reps:Q", title="Total Reps", axis=alt.Axis(labelColor="#94A3B8", gridColor="rgba(255,255,255,0.06)")),
                        tooltip=["Exercise", "Reps"]
                    )
                    .properties(height=260)
                    .configure_view(strokeWidth=0)
                    .configure(background="transparent")
                )
                st.altair_chart(vol_chart, use_container_width=True)

            with ch2:
                st.markdown("##### 📈 Daily Activity Trends")
                tr_df = df.groupby("Date")["Reps"].sum().reset_index().sort_values("Date")
                tr_chart = (
                    alt.Chart(tr_df)
                    .mark_area(
                        line={"color": "#38BDF8", "strokeWidth": 2.5},
                        color=alt.Gradient(
                            gradient="linear",
                            stops=[
                                alt.GradientStop(color="rgba(56, 189, 248, 0.4)", offset=0),
                                alt.GradientStop(color="rgba(56, 189, 248, 0.0)", offset=1),
                            ],
                            x1=1, x2=1, y1=1, y2=0
                        )
                    )
                    .encode(
                        x=alt.X("Date:T", title=None, axis=alt.Axis(labelColor="#94A3B8", format="%b %d")),
                        y=alt.Y("Reps:Q", title="Reps", axis=alt.Axis(labelColor="#94A3B8", gridColor="rgba(255,255,255,0.06)")),
                        tooltip=["Date", "Reps"]
                    )
                    .properties(height=260)
                    .configure_view(strokeWidth=0)
                    .configure(background="transparent")
                )
                st.altair_chart(tr_chart, use_container_width=True)

            st.markdown("<div style='margin-top:1.5rem;'></div>", unsafe_allow_html=True)

            with st.expander("📄 View Detailed Workout History Table"):
                agg_df = df.groupby(["Exercise", "Date"]).agg(
                    {
                        "Reps": "sum",
                        "Sets": "sum",
                        "Time (sec)": "sum"
                    }
                ).reset_index()
                agg_df.index += 1
                st.table(agg_df)
        else:
            st.info("ℹ️ No workout records found yet. Launch your first workout above to track your progress!")


if __name__ == "__main__":
    main()
