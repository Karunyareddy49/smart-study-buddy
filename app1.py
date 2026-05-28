from flask import Flask, render_template, request, redirect, url_for
from google import genai
from dotenv import load_dotenv
import json
import os
from urllib.parse import unquote
from datetime import datetime

load_dotenv()

app = Flask(__name__, template_folder="templates")

api_key = os.getenv("GEMINI_API_KEY")
if not api_key or api_key == "your_api_key_here":
    print("⚠️ GEMINI_API_KEY not found")
    client = None
else:
    print("✅ Gemini API Connected")
    client = genai.Client(api_key=api_key)

if os.path.exists("study_schedules.json") and os.path.getsize("study_schedules.json") > 0:
    try:
        with open("study_schedules.json", "r") as f:
            study_schedules = json.load(f)
    except json.JSONDecodeError:
        print("⚠️ Invalid JSON in study_schedules.json")
        study_schedules = []
else:
    study_schedules = []

if os.path.exists("ai_cache.json") and os.path.getsize("ai_cache.json") > 0:
    try:
        with open("ai_cache.json", "r") as f:
            ai_cache = json.load(f)
    except json.JSONDecodeError:
        print("⚠️ Invalid JSON in ai_cache.json")
        ai_cache = {}
else:
    ai_cache = {}

subjects = ["Math", "Science", "English", "Electronics"]

questions = {
    "Math": {"What is 2+2?": "2+2 = 4", "What is 10-3?": "10-3 = 7"},
    "Science": {"What is H2O?": "H2O is water", "Which planet is nearest to the sun?": "Mercury"},
    "English": {"Synonym of happy?": "Joyful"},
    "Electronics": {"What does LED stand for?": "Light Emitting Diode"}
}

def save_cache():
    with open("ai_cache.json", "w") as f:
        json.dump(ai_cache, f, indent=2)

def save_schedules():
    with open("study_schedules.json", "w") as f:
        json.dump(study_schedules, f, indent=2)

def get_answer(subject, question):
    if client is None:
        return "AI is not available."
    if question in questions.get(subject, {}):
        return questions[subject][question]
    if question in ai_cache:
        return ai_cache[question]
    try:
        prompt = f"Explain this {subject} question simply for a student:\n\nQuestion:\n{question}"
        response = client.models.generate_content(model="gemini-3.5-flash", contents=prompt)
        answer = response.text.strip()
        ai_cache[question] = answer
        save_cache()
        return answer
    except Exception as e:
        return f"Error generating answer: {e}"

def generate_ai_mcqs(subject, num_questions=5):
    if client is None:
        return [{"question": f"Sample {subject} question {i+1}?", "options": ["Option A", "Option B", "Option C", "Option D"], "answer": "Option A"} for i in range(num_questions)]
    try:
        prompt = f"Generate {num_questions} multiple-choice questions for {subject}. Return ONLY valid JSON."
        response = client.models.generate_content(model="gemini-3.5-flash", contents=prompt)
        text = response.text.strip()
        start = text.find("[")
        end = text.rfind("]") + 1
        if start == -1 or end == 0:
            raise ValueError("No valid JSON")
        return json.loads(text[start:end])
    except:
        return [{"question": f"Sample {subject} question {i+1}?", "options": ["Option A", "Option B", "Option C", "Option D"], "answer": "Option A"} for i in range(num_questions)]

@app.route("/")
def home():
    return render_template("home.html", subjects=subjects)

@app.route("/subject/<subject>")
def subject_page(subject):
    return render_template("subject_page1.html", subject=subject)

@app.route("/subject/<subject>/questions")
def view_questions(subject):
    return render_template("questions.html", subject=subject, questions=questions.get(subject, {}))

@app.route("/subject/<subject>/ask", methods=["GET", "POST"])
def ask_ai(subject):
    answer = None
    question = None
    if request.method == "POST":
        question = request.form["question"]
        answer = get_answer(subject, question)
    return render_template("ask.html", subject=subject, question=question, answer=answer)

@app.route("/subject/<subject>/<question>")
def direct_question(subject, question):
    return render_template("answer.html", subject=subject, question=unquote(question), answer=get_answer(subject, unquote(question)))

@app.route("/ai_quiz/<subject>", methods=["GET", "POST"])
def ai_quiz(subject):
    if request.method == "POST":
        mcqs = json.loads(request.form.get("mcqs_json", "[]"))
        score = sum(1 for i, q in enumerate(mcqs) if request.form.get(f"q{i}") == q["answer"])
        return render_template("quiz_result.html", subject=subject, score=score, total=len(mcqs))
    mcqs = generate_ai_mcqs(subject)
    return render_template("quiz.html", subject=subject, mcqs=mcqs, mcqs_json=json.dumps(mcqs))

@app.route("/study-schedule", methods=["GET", "POST"])
def schedules():
    exam_presets = {
        "GATE ECE": {"name": "GATE ECE (6 months)", "duration_weeks": 26, "subjects": ["Math", "Electronics", "Science"]},
        "GATE CS": {"name": "GATE CS (6 months)", "duration_weeks": 26, "subjects": ["Math", "Science", "English"]},
        "Custom": {"name": "Custom Schedule", "duration_weeks": 0, "subjects": []}
    }
    return render_template("schedules.html", schedules=study_schedules, subjects=subjects, exam_presets=exam_presets)

@app.errorhandler(404)
def page_not_found(e):
    return render_template("error.html", code=404, message="Page not found"), 404

@app.errorhandler(500)
def internal_error(e):
    return render_template("error.html", code=500, message="Something went wrong"), 500

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)