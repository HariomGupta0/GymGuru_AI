import streamlit as st
from services.persistence.exercise_repository import get_or_create_user


def render_login_wall():
    if st.session_state.get("user_id") is not None:
        return True

    _, center_col, _ = st.columns([1, 2.2, 1])

    with center_col:
        st.markdown("""
        <div class="login-container">
            <div class="login-badge">🏋️ GymGuru AI • Next-Gen Fitness</div>
            <h1 class="login-title">Train Smarter.<br><span style="color:#A3E635;">Move Better.</span></h1>
            <p class="login-subtitle">
                Your personal AI-powered workout companion. Real-time joint angle tracking, 
                instant form correction, and proactive voice coaching.
            </p>
        </div>
        """, unsafe_allow_html=True)

        with st.form("login_form", clear_on_submit=False):
            st.markdown("<p style='font-weight:600; font-size:0.95rem; margin-bottom:0.3rem; color:#F8FAFC;'>Athlete Username</p>", unsafe_allow_html=True)
            username = st.text_input(
                "Athlete Username",
                placeholder="Enter unique name e.g. alex_fitness",
                label_visibility="collapsed"
            )

            st.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)
            submit_button = st.form_submit_button("Start Training ➔", width="stretch")

        if submit_button:
            if not username or not username.strip():
                st.error("⚠️ Please enter a valid username to start.")
                return False

            user = get_or_create_user(username.strip())
            st.session_state["user_id"] = user["id"]
            st.session_state["username"] = user["username"]
            st.rerun()

        st.markdown("""
        <div style="text-align: center; margin-top: 2rem; color: #64748B; font-size: 0.85rem;">
            <span>⚡ MediaPipe 3D Pose</span> &nbsp;•&nbsp; 
            <span>🧠 Groq Cloud Qwen-27B</span> &nbsp;•&nbsp; 
            <span>🔒 Local SQLite Privacy</span>
        </div>
        """, unsafe_allow_html=True)

    return False
