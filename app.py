"""
Jashn-e-Azadi Quiz — 14 August event quiz app (Vercel + Upstash Redis edition)
------------------------------------------------------------------------------
Same quiz as the local version, but built to run as a Vercel serverless
deployment with a public HTTPS domain, so staff can join from any WiFi or
mobile data — no local network/firewall issues at all.

Storage: Upstash Redis (free tier), added via the Vercel Marketplace, which
auto-injects UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN env vars.

See README.md for full deploy steps.
"""

import base64
import io
import json
import time
from pathlib import Path

from flask import Flask, redirect, render_template, request, session, url_for
from upstash_redis import Redis

BASE_DIR = Path(__file__).resolve().parent
QUESTIONS_PATH = BASE_DIR / "questions.json"

app = Flask(__name__)
app.secret_key = "change-this-secret-before-the-event"  # any random string; set via env var in prod if you like

redis = Redis.from_env()  # reads UPSTASH_REDIS_REST_URL / UPSTASH_REDIS_REST_TOKEN

# ---------------------------------------------------------------------------
# Load questions once per cold start
# ---------------------------------------------------------------------------
with open(QUESTIONS_PATH, "r", encoding="utf-8") as f:
    QUIZ = json.load(f)

QUIZ_TITLE = QUIZ.get("quiz_title", "Company Quiz")
DURATION_MINUTES = QUIZ.get("duration_minutes", 10)
DURATION_SECONDS = DURATION_MINUTES * 60
QUESTIONS = QUIZ["questions"]
ANSWER_KEY = {str(q["id"]): q["answer"] for q in QUESTIONS}
PUBLIC_QUESTIONS = [
    {"id": q["id"], "question": q["question"], "options": q["options"]}
    for q in QUESTIONS
]

# Large enough that score always dominates the tiebreaker time subtraction
# (duration is at most a few thousand seconds for any realistic quiz).
RANK_SCORE_FACTOR = 1_000_000


# ---------------------------------------------------------------------------
# Redis helpers
# ---------------------------------------------------------------------------
def submission_key(employee_id):
    return f"sub:{employee_id}"


def get_submission(employee_id):
    data = redis.hgetall(submission_key(employee_id))
    return data if data else None


def save_submission(employee_id, name, department, score, total, time_taken):
    redis.hset(
        submission_key(employee_id),
        values={
            "employee_name": name,
            "department": department or "",
            "score": str(score),
            "total_questions": str(total),
            "time_taken_seconds": str(time_taken),
        },
    )
    redis.sadd("submission_ids", employee_id)
    rank_score = score * RANK_SCORE_FACTOR - time_taken
    redis.zadd("leaderboard", {employee_id: rank_score})


def get_qr_data_uri(url):
    import qrcode

    img = qrcode.make(url, box_size=10, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def join():
    return render_template("join.html", quiz_title=QUIZ_TITLE, duration=DURATION_MINUTES)


@app.route("/join", methods=["POST"])
def do_join():
    employee_id = request.form.get("employee_id", "").strip()
    employee_name = request.form.get("employee_name", "").strip()
    department = request.form.get("department", "").strip()

    if not employee_id or not employee_name:
        return render_template(
            "join.html",
            quiz_title=QUIZ_TITLE,
            duration=DURATION_MINUTES,
            error="Please enter both your name and employee ID.",
        )

    existing = get_submission(employee_id)
    if existing:
        return render_template(
            "result.html",
            already_attempted=True,
            score=int(existing["score"]),
            total=int(existing["total_questions"]),
            time_taken=round(float(existing["time_taken_seconds"])),
            name=existing["employee_name"],
        )

    session["employee_id"] = employee_id
    session["employee_name"] = employee_name
    session["department"] = department
    session["start_time"] = time.time()
    return redirect(url_for("quiz"))


@app.route("/quiz")
def quiz():
    if "employee_id" not in session or "start_time" not in session:
        return redirect(url_for("join"))

    elapsed = time.time() - session["start_time"]
    remaining = max(0, DURATION_SECONDS - elapsed)
    if remaining <= 0:
        return submit_quiz(auto_timeout=True)

    return render_template(
        "quiz.html",
        quiz_title=QUIZ_TITLE,
        questions=PUBLIC_QUESTIONS,
        remaining_seconds=int(remaining),
    )


@app.route("/submit", methods=["POST"])
def submit_quiz(auto_timeout=False):
    if "employee_id" not in session or "start_time" not in session:
        return redirect(url_for("join"))

    employee_id = session["employee_id"]

    existing = get_submission(employee_id)
    if existing:
        return render_template(
            "result.html",
            already_attempted=True,
            score=int(existing["score"]),
            total=int(existing["total_questions"]),
            time_taken=round(float(existing["time_taken_seconds"])),
            name=existing["employee_name"],
        )

    time_taken = time.time() - session["start_time"]
    time_taken = min(time_taken, DURATION_SECONDS)

    score = 0
    if not auto_timeout:
        for q in QUESTIONS:
            submitted = request.form.get(f"q{q['id']}")
            if submitted == ANSWER_KEY[str(q["id"])]:
                score += 1

    name = session["employee_name"]
    department = session.get("department", "")
    save_submission(employee_id, name, department, score, len(QUESTIONS), time_taken)
    session.pop("start_time", None)

    rank_score = score * RANK_SCORE_FACTOR - time_taken
    higher_count = redis.zcount("leaderboard", rank_score + 0.0001, "+inf")
    rank = int(higher_count) + 1

    return render_template(
        "result.html",
        already_attempted=False,
        score=score,
        total=len(QUESTIONS),
        time_taken=round(time_taken),
        name=name,
        rank=rank,
        timed_out=auto_timeout,
    )


@app.route("/leaderboard")
def leaderboard():
    top = redis.zrevrange("leaderboard", 0, 9, withscores=True)
    rows = []
    for member, _score in top:
        data = redis.hgetall(submission_key(member))
        if data:
            rows.append(
                {
                    "employee_name": data["employee_name"],
                    "department": data.get("department", ""),
                    "score": int(data["score"]),
                    "total_questions": int(data["total_questions"]),
                    "time_taken_seconds": float(data["time_taken_seconds"]),
                }
            )
    return render_template("leaderboard.html", quiz_title=QUIZ_TITLE, rows=rows)


@app.route("/display")
def display():
    join_url = request.host_url  # public https domain, e.g. https://yourapp.vercel.app/
    qr_data_uri = get_qr_data_uri(join_url)
    return render_template(
        "display.html", quiz_title=QUIZ_TITLE, join_url=join_url, qr_data_uri=qr_data_uri
    )


@app.route("/admin/reset")
def admin_reset():
    """Wipe all submissions before the live event (use once, during rehearsal only)."""
    key = request.args.get("key", "")
    if key != "reset-me":  # change this before use
        return "Not authorized", 403
    ids = redis.smembers("submission_ids")
    for emp_id in ids:
        redis.delete(submission_key(emp_id))
    redis.delete("submission_ids")
    redis.delete("leaderboard")
    return "All submissions cleared."


# Local testing only — Vercel imports the `app` WSGI object directly via api/index.py
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
