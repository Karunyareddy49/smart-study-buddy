import os
import json
from flask import send_from_directory
from flask import Flask, render_template, request
from urllib.parse import unquote
from google import genai


# --------------------------
# Flask App
# --------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static")
)

# --------------------------
# Gemini API setup (NEW SDK)
# ---------------
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("GEMINI_API_KEY not set")

# --------------------------
# Initialize Gemini Client (CORRECT)
# --------------------------
client = genai.Client(api_key=API_KEY)
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
# --------------------------
def generate_ai_mcqs(subject, num_questions=5):
    prompt = f"""
    Generate {num_questions} challenging multiple-choice questions for Level 3 quiz
    on the subject: {subject}.
    Format ONLY as valid JSON like this:
    [
      {{
        "question": "Question text",
        "options": ["option1", "option2", "option3", "option4"],
        "answer": "correct option"
      }}
    ]
    """
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        text = response.text.strip()
        start = text.find("[")
        end = text.rfind("]") + 1
        if start == -1 or end == -1:
            raise ValueError("No JSON found in AI output")
        mcqs = json.loads(text[start:end])
        # Validate
        for q in mcqs:
            if "question" not in q or "options" not in q or "answer" not in q:
                raise ValueError("Invalid MCQ structure")
        return mcqs
    except Exception as e:
        print("AI MCQs generation failed:", e)
        return [
            {"question": f"Sample {subject} Q1?", "options": ["A","B","C","D"], "answer": "A"},
            {"question": f"Sample {subject} Q2?", "options": ["A","B","C","D"], "answer": "B"},
            {"question": f"Sample {subject} Q3?", "options": ["A","B","C","D"], "answer": "C"},
            {"question": f"Sample {subject} Q4?", "options": ["A","B","C","D"], "answer": "D"},
            {"question": f"Sample {subject} Q5?", "options": ["A","B","C","D"], "answer": "A"}
        ]
# --------------------------
# Generate AI MCQs
# --------------------------

# --------------------------
# ROUTES
# --------------------------

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                              'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route("/")
def home():
    return render_template("home.html", subjects=subjects)

@app.route("/subject/<subject>")
def subject_page(subject):
    subject = subject.capitalize()
    if subject not in subjects:
        return "Subject Not Found", 404
    return render_template("subject_page1.html", subject=subject)

@app.route("/subject/<subject>/questions")
def subject_questions(subject):
    subject = subject.capitalize()
    if subject not in subjects:
        return "Subject Not Found", 404
    return render_template(
        "questions.html",
        subject=subject,
        questions=questions[subject]
    )

@app.route("/subject/<subject>/ask", methods=["GET", "POST"])
def ask(subject):
    subject = subject.capitalize()
    if subject not in subjects:
        return "Subject Not Found", 404

    if request.method == "POST":
        q = request.form["question"].strip()
        ans = get_answer(subject, q)
        return render_template(
            "answer.html",
            subject=subject,
            question=q,
            answer=ans
        )

    return render_template("ask.html", subject=subject)

@app.route("/subject/<subject>/<question>")
def direct_question(subject, question):
    subject = subject.capitalize()
    question = unquote(question)
    ans = get_answer(subject, question)
    return render_template(
        "answer.html",
        subject=subject,
        question=question,
        answer=ans
    )

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
# --------------------------
# Run App
# --------------------------
if __name__ == "__main__":
    app.run(debug=True)