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
    print(f"🔍 DEBUG: Question='{question}', sub='{sub}'")
    print(f"🔍 DEBUG: API key exists: {'GEMINI_API_KEY' in os.environ}")
    
    # Pre-written (WORKS)
    ans = questions.get(sub, {}).get(question)
    if ans:
        print("✅ Using pre-written answer")
        return ans

    # Cache
    if question in ai_cache:
        print("✅ Using cached answer")
        return ai_cache[question]

    # MAX DEBUGGING
    try:
        print("🔍 DEBUG: Calling Gemini...")
        print(f"🔍 DEBUG: Available models: {list(client.models.list())}")
        
        response = client.models.generate_content(
            model="gemini-pro",  # Most stable
            contents=question    # Simple test
        )
        ans = response.text.strip()
        print(f"✅ AI SUCCESS: {ans[:50]}...")
        
        ai_cache[question] = ans
        with open("ai_cache.json", "w") as f:
            json.dump(ai_cache, f)
        return ans
        
    except Exception as e:
        error_msg = f"AI ERROR: {str(e)}"
        print(error_msg)
        return error_msg

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
# Routes
# --------------------------

@app.route("/")
def home():
    return render_template("home.html", subjects=subjects)
@app.route("/subject/")
def subject_empty():
    return '<h1>No subject selected</h1><p><a href="/">← Choose a subject</a></p>'

@app.route("/subject/<sub>")
def subject_page(sub):
    if sub not in subjects:
        return f'<h1>{sub} not available</h1><p><a href="/">← Choose from: {", ".join(subjects)}</a></p>'
    return render_template("subject_page1.html", subject=sub)


@app.route("/subject/<sub>/questions")
def view_questions(sub):
    sub_questions = questions.get(sub, {})
    return render_template("questions.html", subject=sub, questions=sub_questions)

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

# --------------------------
# Run app
# --------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
