from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from pathlib import Path
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "change-this-secret-key-before-deployment"
DB_PATH = Path(__file__).with_name("jobportal.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('jobseeker','employer','admin'))
        );
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employer_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            location TEXT NOT NULL,
            job_type TEXT NOT NULL,
            salary TEXT,
            description TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(employer_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            applicant_id INTEGER NOT NULL,
            cover_letter TEXT,
            status TEXT DEFAULT 'Pending',
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(job_id, applicant_id),
            FOREIGN KEY(job_id) REFERENCES jobs(id),
            FOREIGN KEY(applicant_id) REFERENCES users(id)
        );
        """)
        # Demonstration admin account (change password after first login).
        admin = db.execute("SELECT id FROM users WHERE email=?", ("admin@jobportal.test",)).fetchone()
        if not admin:
            db.execute("INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)",
                       ("Portal Admin", "admin@jobportal.test",
                        generate_password_hash("Admin@123"), "admin"))

def login_required(role=None):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                flash("Please sign in first.", "warning")
                return redirect(url_for("login"))
            if role and session.get("role") != role and session.get("role") != "admin":
                flash("You are not authorized to access that page.", "danger")
                return redirect(url_for("index"))
            return fn(*args, **kwargs)
        return wrapper
    return decorator

@app.route("/")
def index():
    q = request.args.get("q", "").strip()
    location = request.args.get("location", "").strip()
    sql = "SELECT jobs.*, users.name AS recruiter FROM jobs JOIN users ON jobs.employer_id=users.id WHERE 1=1"
    params = []
    if q:
        sql += " AND (jobs.title LIKE ? OR jobs.company LIKE ? OR jobs.description LIKE ?)"
        params += [f"%{q}%"] * 3
    if location:
        sql += " AND jobs.location LIKE ?"
        params.append(f"%{location}%")
    sql += " ORDER BY jobs.created_at DESC"
    with get_db() as db:
        jobs = db.execute(sql, params).fetchall()
    return render_template("index.html", jobs=jobs, q=q, location=location)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        role = request.form["role"]
        if role not in ("jobseeker", "employer") or not name or not email or len(password) < 8:
            flash("Enter valid details. Password must be at least 8 characters.", "danger")
            return redirect(url_for("register"))
        try:
            with get_db() as db:
                db.execute("INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)",
                           (name, email, generate_password_hash(password), role))
            flash("Registration successful. Please sign in.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("That email address is already registered.", "danger")
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        with get_db() as db:
            user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user and check_password_hash(user["password"], password):
            session.clear()
            session.update(user_id=user["id"], name=user["name"], role=user["role"])
            return redirect(url_for("index"))
        flash("Invalid email or password.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("index"))

@app.route("/post-job", methods=["GET", "POST"])
@login_required("employer")
def post_job():
    if request.method == "POST":
        fields = [request.form.get(k, "").strip() for k in
                  ("title", "company", "location", "job_type", "salary", "description")]
        if not all(fields[i] for i in (0, 1, 2, 3, 5)):
            flash("Please complete all required fields.", "danger")
        else:
            with get_db() as db:
                db.execute("""INSERT INTO jobs(employer_id,title,company,location,job_type,salary,description)
                              VALUES(?,?,?,?,?,?,?)""", (session["user_id"], *fields))
            flash("Job posted successfully.", "success")
            return redirect(url_for("index"))
    return render_template("post_job.html")

@app.route("/apply/<int:job_id>", methods=["POST"])
@login_required("jobseeker")
def apply(job_id):
    cover = request.form.get("cover_letter", "").strip()
    try:
        with get_db() as db:
            exists = db.execute("SELECT id FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not exists:
                flash("Job not found.", "danger")
            else:
                db.execute("INSERT INTO applications(job_id,applicant_id,cover_letter) VALUES(?,?,?)",
                           (job_id, session["user_id"], cover))
                flash("Application submitted.", "success")
    except sqlite3.IntegrityError:
        flash("You have already applied for this job.", "warning")
    return redirect(url_for("index"))

@app.route("/my-applications")
@login_required("jobseeker")
def my_applications():
    with get_db() as db:
        rows = db.execute("""SELECT applications.*, jobs.title, jobs.company, jobs.location
            FROM applications JOIN jobs ON applications.job_id=jobs.id
            WHERE applications.applicant_id=? ORDER BY applications.applied_at DESC""",
            (session["user_id"],)).fetchall()
    return render_template("my_applications.html", applications=rows)

@app.route("/employer/applications")
@login_required("employer")
def employer_applications():
    with get_db() as db:
        rows = db.execute("""SELECT applications.id, applications.cover_letter, applications.status,
            applications.applied_at, users.name AS applicant, users.email, jobs.title, jobs.company
            FROM applications JOIN jobs ON applications.job_id=jobs.id
            JOIN users ON applications.applicant_id=users.id
            JOIN jobs j2 ON j2.id=applications.job_id
            WHERE jobs.employer_id=? ORDER BY applications.applied_at DESC""",
            (session["user_id"],)).fetchall()
    return render_template("employer_applications.html", applications=rows)

@app.route("/application/<int:application_id>/status", methods=["POST"])
@login_required("employer")
def update_status(application_id):
    status = request.form.get("status")
    if status not in ("Pending", "Shortlisted", "Rejected", "Selected"):
        flash("Invalid status.", "danger")
    else:
        with get_db() as db:
            db.execute("""UPDATE applications SET status=? WHERE id=? AND job_id IN
                (SELECT id FROM jobs WHERE employer_id=?)""",
                (status, application_id, session["user_id"]))
        flash("Application status updated.", "success")
    return redirect(url_for("employer_applications"))

@app.route("/admin")
@login_required("admin")
def admin():
    with get_db() as db:
        counts = {
            "users": db.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            "jobs": db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0],
            "applications": db.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
        }
        jobs = db.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
    return render_template("admin.html", counts=counts, jobs=jobs)

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
