import logging
from services.config.workout_config import PROMPT

FALLBACK_CUES = {
    "workout_started": "Let's crush this workout! Stay focused and drive strong!",
    "set_completed": "Great set! Take a breath and get ready for the next one!",
    "workout_completed": "Incredible job! Workout completed, be proud of the effort!",
    "circuit_transition": "Next exercise up! Reset your stance and let's go!",
    "no_pose_detected": "Step into the camera frame so I can track your form!",
}


class LLMCoach:
    def __init__(self, groq_client):
        self.client = groq_client
        self.history = []
        self.system_prompt = PROMPT

    def give_feedback(self, event, issue):
        prompt = f"Event: {event}"

        if issue:
            prompt += f" Form Issue: {issue}"

        messages = [
            {"role": "system", "content": self.system_prompt},
            *self.history[-2:],
            {"role": "user", "content": prompt}
        ]

        try:
            response = self.client.chat.completions.create(
                model="qwen/qwen3.8-27b",
                messages=messages,
                temperature=0.4,
                max_tokens=40,
            )

            text = response.choices[0].message.content.strip()
            self.history.append({"role": "assistant", "content": text})
            return text
        except Exception as e:
            logging.warning(f"Groq API call failed ({type(e).__name__}): {e}. Using fallback cue.")
            if issue:
                return issue
            return FALLBACK_CUES.get(event, "Keep your core tight and maintain clean form!")

    