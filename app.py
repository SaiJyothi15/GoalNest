# app.py
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import os, json, datetime, random

app = Flask(__name__)
CORS(app)
app.secret_key = 'replace_with_a_secure_random_value'

USERS_FILE = 'users.json'     # { email: { name, email, password_hash, current_streak, longest_streak, last_date } }
TASKS_FILE = 'tasks.json'     # { email: [ {id, task, category, time, created_at, completed, completed_at} ] }
FEEDBACK_FILE = 'feedback.json'  # [ { user, feedback, time } ]

# ---------- bootstrap storage ----------
def _ensure(path, default):
    if not os.path.exists(path):
        with open(path, 'w') as f:
            json.dump(default, f, indent=2)

_ensure(USERS_FILE, {})
_ensure(TASKS_FILE, {})
_ensure(FEEDBACK_FILE, [])

# ---------- helpers ----------
def load_users():
    with open(USERS_FILE, 'r') as f:
        return json.load(f)

def save_users(data):
    with open(USERS_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def load_tasks_all():
    with open(TASKS_FILE, 'r') as f:
        return json.load(f)

def save_tasks_all(data):
    with open(TASKS_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def get_user_tasks(email):
    return load_tasks_all().get(email, [])

def save_user_tasks(email, tasks):
    all_tasks = load_tasks_all()
    all_tasks[email] = tasks
    save_tasks_all(all_tasks)

def append_feedback(entry):
    with open(FEEDBACK_FILE, 'r') as f:
        data = json.load(f)
    data.append(entry)
    with open(FEEDBACK_FILE, 'w') as f:
        json.dump(data, f, indent=2)

# ---------- routes ----------
@app.route('/')
def root():
    if 'email' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', name=session.get('name'))

# ---- auth ----
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email','').strip().lower()
        password = request.form.get('password','')
        users = load_users()
        user = users.get(email)
        if user and check_password_hash(user.get('password_hash',''), password):
            session['email'] = email
            session['name'] = user.get('name', email.split('@')[0])
            return redirect(url_for('root'))
        flash('Invalid credentials', 'danger')
        return render_template('login.html', error='Invalid credentials')
    return render_template('login.html')

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name','').strip()
        email = request.form.get('email','').strip().lower()
        password = request.form.get('password','')
        if not name or not email or not password:
            return render_template('register.html', error='All fields are required')
        users = load_users()
        if email in users:
            return render_template('register.html', error='Email already registered')
        users[email] = {
            'name': name,
            'email': email,
            'password_hash': generate_password_hash(password),
            'current_streak': 0,
            'longest_streak': 0,
            'last_date': ""   # ISO date of last day a task was completed (streak-counted)
        }
        save_users(users)
        save_user_tasks(email, [])
        flash('Account created! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ---- tasks & streaks ----
def today_date():
    return datetime.date.today()

def iso_date(d: datetime.date):
    return d.isoformat()

def parse_iso_date(s: str):
    return datetime.datetime.strptime(s, "%Y-%m-%d").date()
def load_user_tasks():
    if os.path.exists(TASKS_FILE):
        with open(TASKS_FILE, "r") as f:
            try:
                data = json.load(f)
                if isinstance(data, dict):  # ✅ must be dict
                    return data
                else:
                    return {}  # reset if it's list or wrong format
            except json.JSONDecodeError:
                return {}
    return {}

def save_user_tasks(email, tasks):
    all_tasks = load_user_tasks()
    all_tasks[email] = tasks
    with open(TASKS_FILE, "w") as f:
        json.dump(all_tasks, f, indent=4)


@app.route('/tasks', methods=['GET','POST','DELETE'])
def tasks():
    if 'email' not in session:
        return jsonify({"error":"unauthenticated"}), 401
    email = session['email']

    if request.method == 'GET':
        return jsonify(get_user_tasks(email))

    if request.method == 'POST':
        data = request.get_json() or request.form
        title = (data.get('task') or '').strip()
        category = data.get('category') or 'General'
        time_hhmm = data.get('time') or ''  # "HH:MM"
        if not title:
            return jsonify({"error":"task required"}), 400
        task_id = int(datetime.datetime.now().timestamp()*1000)
        task = {
            "id": task_id,
            "task": title,
            "category": category,
            "time": time_hhmm,
            "created_at": datetime.datetime.now().isoformat(),
            "completed": False,
            "completed_at": None
        }
        tasks = get_user_tasks(email)
        tasks.append(task)
        save_user_tasks(email, tasks)
        return jsonify(task), 201

    # DELETE
    data = request.get_json() or request.form
    task_id = data.get('id')
    if not task_id:
        return jsonify({"error":"id required"}), 400
    tasks = get_user_tasks(email)
    tasks = [t for t in tasks if str(t.get('id')) != str(task_id)]
    save_user_tasks(email, tasks)
    return jsonify({"success": True})

@app.route('/complete', methods=['POST'])
def complete():
    if 'email' not in session:
        return jsonify({"error":"unauthenticated"}), 401
    email = session['email']
    data = request.get_json() or request.form
    task_id = data.get('id')
    if not task_id:
        return jsonify({"error":"task id required"}), 400

    tasks = get_user_tasks(email)
    found = None
    for t in tasks:
        if str(t.get('id')) == str(task_id):
            found = t
            break
    if not found:
        return jsonify({"error":"task not found"}), 404

    # mark complete
    if not found.get('completed'):
        found['completed'] = True
        found['completed_at'] = datetime.datetime.now().isoformat()
        save_user_tasks(email, tasks)

        # streak logic: only increment once per calendar day
        users = load_users()
        user = users.get(email)
        today = today_date()
        last_s = user.get('last_date') or ''
        last = parse_iso_date(last_s) if last_s else None

        if not last:
            user['current_streak'] = 1
        else:
            delta = (today - last).days
            if delta == 0:
                # already counted today → do nothing
                pass
            elif delta == 1:
                user['current_streak'] = user.get('current_streak', 0) + 1
            else:
                user['current_streak'] = 1

        if user.get('current_streak', 0) > user.get('longest_streak', 0):
            user['longest_streak'] = user['current_streak']
        user['last_date'] = iso_date(today)
        users[email] = user
        save_users(users)

    return jsonify({"success": True})

@app.route('/streak')
def streak():
    """Return (and also enforce) current streak + longest.
       If the user missed at least one entire day since last_date, reset streak to 0.
    """
    if 'email' not in session:
        return jsonify({"streak": 0, "longest": 0})
    email = session['email']
    users = load_users()
    user = users.get(email, {})
    last_s = user.get('last_date') or ''
    if last_s:
        try:
            last = parse_iso_date(last_s)
            delta_days = (today_date() - last).days
            if delta_days >= 2:
                # missed at least one full day → reset
                user['current_streak'] = 0
                users[email] = user
                save_users(users)
        except Exception:
            pass
    return jsonify({"streak": user.get('current_streak', 0), "longest": user.get('longest_streak', 0)})

@app.route('/stats/daily')
def stats_daily():
    """Return last 14 days of completions for the mini chart."""
    if 'email' not in session:
        return jsonify({"labels":[], "data":[]})
    email = session['email']
    tasks = get_user_tasks(email)
    today = today_date()
    labels = []
    counts = []
    # build map date->count
    by_day = {}
    for t in tasks:
        if t.get('completed') and t.get('completed_at'):
            day = t['completed_at'][:10]  # YYYY-MM-DD
            by_day[day] = by_day.get(day, 0) + 1
    for i in range(13, -1, -1):
        d = today - datetime.timedelta(days=i)
        s = iso_date(d)
        labels.append(d.strftime("%d %b"))  # pretty label
        counts.append(by_day.get(s, 0))
    return jsonify({"labels": labels, "data": counts})

# ---- tips & quotes ----
@app.route('/recommendation')
def recommendation():
    tips = [
        "Break big tasks into smaller chunks.",
        "Try the 25/5 Pomodoro cycle.",
        "Mute notifications during focus time.",
        "Start with the smallest next step.",
        "Review your plan each morning.",
        "Reward yourself after finishing."
    ]
    return jsonify({"tip": random.choice(tips)})

@app.route('/quote')
def quote():
    quotes = [
        "Discipline is the bridge between goals and accomplishment.",
        "Start where you are. Use what you have. Do what you can.",
        "Success is the sum of small efforts, repeated day in and day out.",
        "It always seems impossible until it’s done."
    ]
    return jsonify({"quote": random.choice(quotes)})

# ---- feedback ----
@app.route('/feedback', methods=['GET','POST'])
def feedback():
    if request.method == 'POST':
        fb = request.form.get('feedback') or (request.get_json() or {}).get('feedback')
        append_feedback({
            "user": session.get('email'),
            "feedback": fb,
            "time": datetime.datetime.now().isoformat()
        })
        flash('Thanks for your feedback!', 'success')
        return redirect(url_for('root'))
    return render_template('feedback.html')

# ---- util ----
@app.route('/whoami')
def whoami():
    return jsonify({"email": session.get('email'), "name": session.get('name')})

if __name__ == '__main__':
    app.run(debug=True)
