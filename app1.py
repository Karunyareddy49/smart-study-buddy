from flask import Flask, render_template, request
from google import genai
import json
import os
from urllib.parse import quote, unquote


app = Flask(__name__, template_folder="templates")

# ===== CREATE FLASK APP WITH EXPLICIT PATHS =====

# --------------------------
# Initialize Gemini client
# --------------------------
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY not set!")

client = genai.Client(api_key=api_key)

# --------------------------
# Subjects and pre-written questions (added some common ones)
# --------------------------
subjects = ["Math", "Science", "English", "Electronics"]

questions = {
    "Math": {
        "What is 2+2?": "2+2 = 4",
        "What is 10-3?": "10-3 = 7",
        "What is correlation?": "Correlation measures the relationship between two variables."
    },
    "Science": {
        "What is H2O?": "H2O is water",
        "Which planet is nearest to the sun?": "Mercury",
        "What is Ohm's law?": "Ohm's law states that V = IR, where V is voltage, I is current, and R is resistance."
    },
    "English": {
        "Synonym of happy?": "Joyful",
        "Antonym of fast?": "Slow"
    },
    "Electronics": {
        "What does LED stand for?": "Light Emitting Diode",
        "What is the unit of electric current?": "Ampere"
    }
}

# --------------------------
# AI Cache
# --------------------------
if os.path.exists("ai_cache.json"):
    with open("ai_cache.json", "r") as f:
        ai_cache = json.load(f)
else:
    ai_cache = {}

# --------------------------
# Helper to get answer with subject-aware prompt and logging
# --------------------------

def get_answer(sub, question):
    # 1. Check pre-written questions
    ans = questions.get(sub, {}).get(question)
    if ans:
        return ans

    # 2. Check cache
    if question in ai_cache:
        return ai_cache[question]

    # 3. Generate AI answer
    try:
        prompt = f"Answer this question in simple terms for a student in {sub}: {question}"
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        ans = response.text.strip()
        print(f"AI output for '{question}': {ans}")  # Debug log

        # Save in cache
        ai_cache[question] = ans
        with open("ai_cache.json", "w") as f:
            json.dump(ai_cache, f)

        return ans if ans else "Sorry, AI could not generate an answer."

    except Exception as e:
        print(f"AI generation failed for '{question}': {e}")
        return "Sorry, the answer could not be generated."

# --------------------------
# AI MCQs
def generate_ai_mcqs(subject, num_questions=5, difficulty="medium"):
    prompt = f"""
You are an expert exam question setter.

Generate {num_questions} {difficulty} difficulty multiple-choice questions
for a Level 3 quiz on the subject: {subject}.

STRICT RULES:
- EXACTLY 4 options per question
- Answer MUST be one of the options
- No explanations
- No markdown, no backticks
- Output ONLY valid JSON

JSON format:
[
  {{
    "question": "Question text",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "answer": "Option A"
  }}
]
"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        text = response.text.strip()

        # --- Safe JSON extraction ---
        start = text.find("[")
        end = text.rfind("]") + 1
        if start == -1 or end == 0:
            raise ValueError("No JSON array found in AI output")

        mcqs = json.loads(text[start:end])

        # --- Validation ---
        validated_mcqs = []
        for q in mcqs:
            if (
                isinstance(q, dict)
                and "question" in q
                and "options" in q
                and "answer" in q
                and isinstance(q["options"], list)
                and len(q["options"]) == 4
                and q["answer"] in q["options"]
            ):
                validated_mcqs.append(q)

        if not validated_mcqs:
            raise ValueError("All MCQs failed validation")

        return validated_mcqs

    except Exception as e:
        print("AI MCQs generation failed:", e)

        # --- Guaranteed fallback (never crashes demo) ---
        return [
            {
                "question": f"Sample {subject} question {i + 1}?",
                "options": ["Option A", "Option B", "Option C", "Option D"],
                "answer": "Option A"
            }
            for i in range(num_questions)
        ]
# --------------------------
# Routes
# --------------------------

@app.route("/")
def home():
    return render_template("home.html", subjects=subjects)

@app.route("/subject/<sub>")
def subject_page(sub):
    return render_template("subject_page1.html", subject=sub)

@app.route("/subject/<sub>/questions")
def view_questions(sub):
    sub_questions = questions.get(sub, {})
    return render_template(
        "questions.html",
        subject=sub,
        questions=sub_questions
    )
@app.route("/ai")
def ask_ai():
    try:
        if client is None:
            return "<h2>Gemini API not configured. AI features unavailable.</h2>"
        # Example AI call
        response = client.generate_text(prompt="Hello from Smart Study Buddy!")
        return f"<h2>AI Response:</h2><p>{response.text}</p>"
    except Exception as e:
        # Log error
        print("ERROR in /ai route:", e)
        return "<h2>Internal Server Error in AI route</h2>"
@app.route("/subject/<sub>/ask", methods=["GET","POST"])
def ask_ai2(sub):
    answer = None
    question = None

    if request.method == "POST":
        question = request.form["question"]
        answer = get_answer(sub, question)

    return render_template(
        "ask.html",
        subject=sub,
        question=question,
        answer=answer
    )


@app.route("/subject/<sub>/<question>")
def direct_question(sub, question):
    question = unquote(question)
    ans = get_answer(sub, question)
    return render_template("answer.html", subject=sub, question=question, answer=ans)

@app.route("/ai_quiz/<sub>", methods=["GET","POST"])
def ai_quiz(sub):
    if request.method == "POST":
        mcqs_json = request.form.get("mcqs_json","[]")
        try:
            mcqs = json.loads(mcqs_json)
        except:
            mcqs = []

        score = 0
        for i, q in enumerate(mcqs):
            selected = request.form.get(f"q{i}")
            if selected == q.get("answer"):
                score += 1

        return render_template("quiz_result.html", subject=sub, score=score, total=len(mcqs))

    mcqs = generate_ai_mcqs(sub, num_questions=5)
    return render_template("quiz.html", subject=sub, mcqs=mcqs, mcqs_json=json.dumps(mcqs))
@app.errorhandler(404)
def page_not_found(e):
    return render_template("error.html",
                           code=404,
                           message="Page not found 😕"), 404


@app.errorhandler(500)
def internal_error(e):
    return render_template("error.html",
                           code=500,
                           message="Something went wrong on our side 😓 Please try again."), 500
# --------------------------
# Run app
# --------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)