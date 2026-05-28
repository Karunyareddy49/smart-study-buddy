from flask import Flask, render_template, request, redirect, url_for
from google import genai
from dotenv import load_dotenv

import json
import os
from urllib.parse import unquote
from datetime import datetime

# ==========================================
# Load Environment Variables
# ==========================================
load_dotenv()

# ==========================================
# Flask App
# ==========================================
app = Flask(__name__, template_folder="templates")

# ==========================================
# Gemini API Setup
# ==========================================
api_key = os.getenv("GEMINI_API_KEY")

if not api_key or api_key == "your_api_key_here":
    print("⚠️ GEMINI_API_KEY not found")
    client = None
else:
    print("✅ Gemini API Connected")
    client = genai.Client(api_key=api_key)

# ==========================================
# Load Study Schedules Safely
# ==========================================
if (
    os.path.exists("study_schedules.json")
    and os.path.getsize("study_schedules.json") > 0
):
    try:
        with open("study_schedules.json", "r") as f:
            study_schedules = json.load(f)

    except json.JSONDecodeError:
        print("⚠️ Invalid JSON in study_schedules.json")
        study_schedules = []

else:
    study_schedules = []

# ==========================================
# Load AI Cache Safely
# ==========================================
if (
    os.path.exists("ai_cache.json")
    and os.path.getsize("ai_cache.json") > 0
):
    try:
        with open("ai_cache.json", "r") as f:
            ai_cache = json.load(f)

    except json.JSONDecodeError:
        print("⚠️ Invalid JSON in ai_cache.json")
        ai_cache = {}

else:
    ai_cache = {}

# ==========================================
# Subjects
# ==========================================
subjects = [
    "Math",
    "Science",
    "English",
    "Electronics"
]

# ==========================================
# Predefined Questions
# ==========================================
questions = {

    "Math": {
        "What is 2+2?": "2+2 = 4",
        "What is 10-3?": "10-3 = 7"
    },

    "Science": {
        "What is H2O?": "H2O is water",
        "Which planet is nearest to the sun?": "Mercury"
    },

    "English": {
        "Synonym of happy?": "Joyful"
    },

    "Electronics": {
        "What does LED stand for?":
        "Light Emitting Diode"
    }
}

# ==========================================
# Save AI Cache
# ==========================================
def save_cache():

    with open("ai_cache.json", "w") as f:
        json.dump(ai_cache, f, indent=2)

# ==========================================
# Save Study Schedules
# ==========================================
def save_schedules():

    with open("study_schedules.json", "w") as f:
        json.dump(study_schedules, f, indent=2)

# ==========================================
# Get AI Answer
# ==========================================
def get_answer(subject, question):

    if client is None:
        return "AI is not available."

    # Check predefined answers
    if question in questions.get(subject, {}):
        return questions[subject][question]

    # Check cache
    if question in ai_cache:
        return ai_cache[question]

    try:

        prompt = f"""
Explain this {subject} question simply for a student:

Question:
{question}
"""

        response = client.models.generate_content(
    model="gemini-3.5-flash",
    contents=prompt
)

        answer = response.text.strip()

        print("AI ANSWER:")
        print(answer)

        # Save to cache
        ai_cache[question] = answer
        save_cache()

        return answer

    except Exception as e:

        print("AI ERROR:", e)

        return f"Error generating answer: {e}"

# ==========================================
# Generate AI MCQs
# ==========================================
def generate_ai_mcqs(subject, num_questions=5):

    if client is None:

        return [
            {
                "question": f"Sample {subject} question {i+1}?",
                "options": [
                    "Option A",
                    "Option B",
                    "Option C",
                    "Option D"
                ],
                "answer": "Option A"
            }

            for i in range(num_questions)
        ]

    prompt = f"""
Generate {num_questions} multiple-choice questions for {subject}.

Return ONLY valid JSON in this format:

[
  {{
    "question": "Question text",
    "options": [
        "Option A",
        "Option B",
        "Option C",
        "Option D"
    ],
    "answer": "Option A"
  }}
]
"""

    try:

        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=prompt
        )

        text = response.text.strip()

        print("RAW MCQ RESPONSE:")
        print(text)

        # Extract JSON
        start = text.find("[")
        end = text.rfind("]") + 1

        if start == -1 or end == 0:
            raise ValueError("No valid JSON found")

        mcqs = json.loads(text[start:end])

        validated_mcqs = []

        for q in mcqs:

            if (
                isinstance(q, dict)
                and "question" in q
                and "options" in q
                and "answer" in q
                and len(q["options"]) == 4
            ):

                validated_mcqs.append(q)

        if not validated_mcqs:
            raise ValueError("No valid MCQs generated")

        return validated_mcqs

    except Exception as e:

        print("MCQ ERROR:", e)

        return [
            {
                "question": f"Sample {subject} question {i+1}?",
                "options": [
                    "Option A",
                    "Option B",
                    "Option C",
                    "Option D"
                ],
                "answer": "Option A"
            }

            for i in range(num_questions)
        ]

# ==========================================
# Home Page
# ==========================================
@app.route("/")
def home():

    return render_template(
        "home.html",
        subjects=subjects
    )

# ==========================================
# Subject Page
# ==========================================
@app.route("/subject/<subject>")
def subject_page(subject):

    return render_template(
        "subject_page1.html",
        subject=subject
    )

# ==========================================
# Questions Page
# ==========================================
@app.route("/subject/<subject>/questions")
def view_questions(subject):

    sub_questions = questions.get(subject, {})

    return render_template(
        "questions.html",
        subject=subject,
        questions=sub_questions
    )

# ==========================================
# Ask AI
# ==========================================
@app.route("/subject/<subject>/ask", methods=["GET", "POST"])
def ask_ai(subject):

    answer = None
    question = None

    if request.method == "POST":

        question = request.form["question"]

        answer = get_answer(subject, question)

    return render_template(
        "ask.html",
        subject=subject,
        question=question,
        answer=answer
    )

# ==========================================
# Direct Question Route
# ==========================================
@app.route("/subject/<subject>/<question>")
def direct_question(subject, question):

    question = unquote(question)

    answer = get_answer(subject, question)

    return render_template(
        "answer.html",
        subject=subject,
        question=question,
        answer=answer
    )

# ==========================================
# AI Quiz
# ==========================================
@app.route("/ai_quiz/<subject>", methods=["GET", "POST"])
def ai_quiz(subject):

    # Quiz Submission
    if request.method == "POST":

        mcqs_json = request.form.get(
            "mcqs_json",
            "[]"
        )

        try:
            mcqs = json.loads(mcqs_json)

        except:
            mcqs = []

        score = 0

        for i, q in enumerate(mcqs):

            selected = request.form.get(f"q{i}")

            if selected == q["answer"]:
                score += 1

        return render_template(
            "quiz_result.html",
            subject=subject,
            score=score,
            total=len(mcqs)
        )

    # Generate Quiz
    mcqs = generate_ai_mcqs(subject)

    return render_template(
        "quiz.html",
        subject=subject,
        mcqs=mcqs,
        mcqs_json=json.dumps(mcqs)
    )

# ==========================================
# Error Pages
# ==========================================
@app.errorhandler(404)
def page_not_found(e):

    return render_template(
        "error.html",
        code=404,
        message="Page not found"
    ), 404

@app.errorhandler(500)
def internal_error(e):

    return render_template(
        "error.html",
        code=500,
        message="Something went wrong"
    ), 500

# ==========================================
# Run Flask App
# ==========================================
if __name__ == "__main__":

    port = int(os.getenv("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=True
    )
