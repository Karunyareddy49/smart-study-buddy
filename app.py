from flask import Flask, render_template, request
from google import genai
import json
import os
from urllib.parse import unquote
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, template_folder="templates")

# --------------------------
# Gemini Setup (FIXED)
# --------------------------
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("⚠️ GEMINI_API_KEY not set! AI disabled.")
    client = None
else:
    client = genai.Client(api_key=api_key)

# --------------------------
# Subjects
# --------------------------
subjects = ["Math", "Science", "English", "Electronics"]

questions = {
    "Math": {
        "What is 2+2?": "2+2 = 4",
        "What is 10-3?": "10-3 = 7"
    },
    "Science": {
        "What is H2O?": "H2O is water",
        "Which planet is nearest to the sun?": "Mercury"
    }
}

# --------------------------
# Cache
# --------------------------
if os.path.exists("ai_cache.json"):
    with open("ai_cache.json", "r") as f:
        ai_cache = json.load(f)
else:
    ai_cache = {}

# --------------------------
# Answer Function (FIXED)
# --------------------------
def get_answer(sub, question):

    if question in questions.get(sub, {}):
        return questions[sub][question]

    if question in ai_cache:
        return ai_cache[question]

    if client is None:
        return "AI not available. Set GEMINI_API_KEY."

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"Explain this {sub} question simply: {question}"
        )

        ans = response.text.strip()

        ai_cache[question] = ans
        with open("ai_cache.json", "w") as f:
            json.dump(ai_cache, f)

        return ans

    except Exception as e:
        print("AI error:", e)
        return "AI failed."

# --------------------------
# MCQs (FIXED)
# --------------------------
def generate_ai_mcqs(subject, num_questions=3):

    # ✅ Fallback (always safe)
    fallback = [
        {
            "question": "What is the value of x in 2x + 7 = 15?",
            "options": ["4", "8", "11", "22"],
            "answer_index": 0
        },
        {
            "question": "Area of rectangle (10 × 5)?",
            "options": ["15", "20", "50", "100"],
            "answer_index": 2
        },
        {
            "question": "8 + 2 * 3 - 6 / 2 = ?",
            "options": ["7", "11", "13", "16"],
            "answer_index": 1
        }
    ]

    if client is None:
        return fallback

    try:
        prompt = f"""
Generate EXACTLY {num_questions} multiple choice questions for {subject}.

STRICT RULES:
- 4 options only
- Answer MUST match one option exactly
- Output ONLY JSON

Format:
[
  {{
    "question": "...",
    "options": ["A", "B", "C", "D"],
    "answer": "A"
  }}
]
"""

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        text = response.text.strip()

        # ✅ Extract JSON safely
        start = text.find("[")
        end = text.rfind("]") + 1

        if start == -1 or end == 0:
            return fallback

        mcqs = json.loads(text[start:end])

        fixed_mcqs = []

        for q in mcqs:
            if (
                isinstance(q, dict)
                and "question" in q
                and "options" in q
                and "answer" in q
                and len(q["options"]) == 4
                and q["answer"] in q["options"]
            ):
                # ✅ Convert to index-based answer
                answer_index = q["options"].index(q["answer"])

                fixed_mcqs.append({
                    "question": q["question"],
                    "options": q["options"],
                    "answer_index": answer_index
                })

        if not fixed_mcqs:
            return fallback

        return fixed_mcqs

    except Exception as e:
        print("MCQ error:", e)
        return fallback

# --------------------------
# Routes
# --------------------------
@app.route("/")
@app.route("/subject/")
def home():
    return render_template("home.html", subjects=subjects)

@app.route("/subject/<sub>")
def subject_page(sub):
    return render_template("subject_page1.html", subject=sub)

# ✅ endpoint name FIXED
@app.route("/subject/<sub>/questions", endpoint="subject_questions")
def view_questions(sub):
    return render_template("questions.html", subject=sub, questions=questions.get(sub, {}))

@app.route("/subject/<sub>/ask", methods=["GET","POST"])
def ask_ai(sub):
    answer = None
    question = None

    if request.method == "POST":
        question = request.form["question"]
        answer = get_answer(sub, question)

    return render_template("ask.html", subject=sub, question=question, answer=answer)
@app.route("/ai_quiz/<sub>", methods=["GET","POST"])
def ai_quiz(sub):
    if request.method == "POST":
        mcqs = json.loads(request.form.get("mcqs_json", "[]"))

        score = 0
        results = []

        for i, q in enumerate(mcqs):
            selected = request.form.get(f"q{i}")
            correct = q.get("answer")

            if selected == correct:
                score += 1

            results.append({
                "question": q["question"],
                "selected": selected,
                "correct": correct,
                "options": q["options"]
            })

        return render_template(
            "quiz_result.html",
            subject=sub,
            score=score,
            total=len(mcqs),
            results=results   # ✅ IMPORTANT
        )

    mcqs = generate_ai_mcqs(sub)
    return render_template(
        "quiz.html",
        subject=sub,
        mcqs=mcqs,
        mcqs_json=json.dumps(mcqs)
    )
# KEEP LAST
@app.route("/subject/<sub>/<question>")
def direct_question(sub, question):
    question = unquote(question)
    return render_template(
        "answer.html",
        subject=sub,
        question=question,
        answer=get_answer(sub, question)
    )

# --------------------------
# Errors
# --------------------------
@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404, message="Page not found"), 404

@app.errorhandler(500)
def server_error(e):
    return render_template("error.html", code=500, message="Server error"), 500

# --------------------------
# Run
# --------------------------
if __name__ == "__main__":
    app.run(debug=True)