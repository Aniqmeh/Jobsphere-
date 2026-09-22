import os
from datetime import datetime
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    session,
    send_from_directory
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename


# =========================================================
# APP CONFIGURATION
# =========================================================

app = Flask(__name__)

app.secret_key = "jobsphere_secret_key_2026"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Database Configuration (SQLite default)
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(BASE_DIR, 'jobsphere.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

RESUME_FOLDER = os.path.join(BASE_DIR, "resumes")
ALLOWED_EXTENSIONS = {"pdf", "doc", "docx"}

app.config["RESUME_FOLDER"] = RESUME_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB limit

db = SQLAlchemy(app)
with app.app_context():
    db.create_all()

# =========================================================
# CREATE FOLDERS
# =========================================================

os.makedirs(RESUME_FOLDER, exist_ok=True)


# =========================================================
# DATABASE MODELS
# =========================================================

# Association table for User-Job favorites (Many-to-Many)
favorites_table = db.Table(
    'favorites',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('job_id', db.Integer, db.ForeignKey('jobs.id'), primary_key=True)
)


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False)  # 'job_seeker' or 'job_poster'

    # Relationships
    jobs = db.relationship('Job', backref='poster', lazy=True, cascade="all, delete-orphan")
    applications = db.relationship('Application', backref='applicant', lazy=True)
    resumes = db.relationship('Resume', backref='owner', lazy=True)
    notifications = db.relationship('Notification', backref='user', lazy=True, cascade="all, delete-orphan")
    favorites = db.relationship('Job', secondary=favorites_table, backref=db.backref('favorited_by', lazy=True))

    def clean_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "role": self.role,
            "favorites": [job.id for job in self.favorites]
        }


class Job(db.Model):
    __tablename__ = 'jobs'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    company = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(150), nullable=False)
    salary = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    poster_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    applications = db.relationship('Application', backref='job', lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "company": self.company,
            "category": self.category,
            "location": self.location,
            "salary": self.salary,
            "description": self.description,
            "poster_id": self.poster_id
        }


class Resume(db.Model):
    __tablename__ = 'resumes'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    skills = db.Column(db.Text, default="")
    introduction = db.Column(db.Text, default="")
    profile_resume = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    applications = db.relationship('Application', backref='resume', lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "filename": self.filename,
            "original_filename": self.original_filename,
            "skills": self.skills,
            "introduction": self.introduction,
            "profile_resume": self.profile_resume,
            "created_at": self.created_at.isoformat() if self.created_at else ""
        }


class Application(db.Model):
    __tablename__ = 'applications'

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    resume_id = db.Column(db.Integer, db.ForeignKey('resumes.id'), nullable=False)
    
    applicant_name = db.Column(db.String(150), nullable=False)
    applicant_email = db.Column(db.String(150), nullable=False)
    contact = db.Column(db.String(50), nullable=False)
    introduction = db.Column(db.Text, nullable=False)
    
    status = db.Column(db.String(50), default="Applied")
    salary = db.Column(db.String(100), default="")
    interview_date = db.Column(db.String(50), default="")
    interview_time = db.Column(db.String(50), default="")
    remarks = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Historical snapshot of job data in case the original posting is deleted
    job_snapshot = db.Column(db.JSON, nullable=True)

    def get_job_info(self):
        if self.job:
            return self.job.to_dict()
        if self.job_snapshot:
            return self.job_snapshot
        return {
            "id": self.job_id,
            "title": "Deleted Job",
            "company": "Company not provided",
            "category": "JOB",
            "location": "Not provided",
            "salary": "",
            "description": "",
            "deleted": True
        }

    def to_dict(self):
        return {
            "id": self.id,
            "job_id": self.job_id,
            "user_id": self.user_id,
            "resume_id": self.resume_id,
            "applicant_name": self.applicant_name,
            "applicant_email": self.applicant_email,
            "contact": self.contact,
            "introduction": self.introduction,
            "status": self.status,
            "salary": self.salary,
            "interview_date": self.interview_date,
            "interview_time": self.interview_time,
            "remarks": self.remarks,
            "job_snapshot": self.job_snapshot,
            "created_at": self.created_at.isoformat() if self.created_at else ""
        }


class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(50), default="")
    message = db.Column(db.Text, nullable=False)
    job_id = db.Column(db.Integer, nullable=True)
    application_id = db.Column(db.Integer, nullable=True)
    read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.type,
            "status": self.status,
            "message": self.message,
            "job_id": self.job_id,
            "application_id": self.application_id,
            "read": self.read,
            "created_at": self.created_at.isoformat() if self.created_at else ""
        }


# Create database schema
with app.app_context():
    db.create_all()


# =========================================================
# NO CACHE HEADERS
# =========================================================

@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def get_current_user():
    user_id = session.get("user_id")
    if user_id is None:
        return None
    return db.session.get(User, user_id)


def allowed_file(filename):
    if not filename or "." not in filename:
        return False
    extension = filename.rsplit(".", 1)[1].lower()
    return extension in ALLOWED_EXTENSIONS


# =========================================================
# AUTH DECORATORS
# =========================================================

def login_required(function):
    @wraps(function)
    def decorated_function(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"success": False, "message": "Please login first."}), 401

        user = get_current_user()
        if not user:
            session.clear()
            return jsonify({"success": False, "message": "Session expired. Please login again."}), 401

        return function(*args, **kwargs)
    return decorated_function


def role_required(role):
    def decorator(function):
        @wraps(function)
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            if not user:
                return jsonify({"success": False, "message": "Please login first."}), 401

            if user.role != role:
                return jsonify({"success": False, "message": "You do not have permission for this section."}), 403

            return function(*args, **kwargs)
        return decorated_function
    return decorator


# =========================================================
# HOME
# =========================================================

@app.route("/")
@app.route("/index.html")
def home():
    return render_template("index.html")


# =========================================================
# CURRENT USER API
# =========================================================

@app.route("/api/me", methods=["GET"])
@app.route("/me", methods=["GET"])
def me():
    user = get_current_user()
    if not user:
        return jsonify({"success": False, "logged_in": False, "user": None})

    return jsonify({"success": True, "logged_in": True, "user": user.clean_dict()})


# =========================================================
# SIGNUP
# =========================================================

@app.route("/api/signup", methods=["POST"])
@app.route("/signup", methods=["POST"])
def signup():
    incoming = request.get_json(silent=True) or request.form.to_dict()

    name = str(incoming.get("name", "")).strip()
    email = str(incoming.get("email", "")).strip().lower()
    password = str(incoming.get("password", ""))
    role = str(incoming.get("role", "")).strip().lower()

    if role not in ["job_seeker", "job_poster"]:
        return jsonify({"success": False, "message": "Please select a valid portal."}), 400

    if not name:
        return jsonify({"success": False, "message": "Full name is required."}), 400

    if not email:
        return jsonify({"success": False, "message": "Email is required."}), 400

    if not password:
        return jsonify({"success": False, "message": "Password is required."}), 400

    existing_user = User.query.filter_by(email=email, role=role).first()
    if existing_user:
        return jsonify({"success": False, "message": "An account with this email already exists for this portal."}), 400

    new_user = User(
        name=name,
        email=email,
        password=password,
        role=role
    )

    db.session.add(new_user)
    db.session.commit()

    session.clear()
    session["user_id"] = new_user.id

    return jsonify({
        "success": True,
        "message": "Account created successfully.",
        "user": new_user.clean_dict()
    })


# =========================================================
# LOGIN
# =========================================================

@app.route("/api/login", methods=["POST"])
@app.route("/login", methods=["POST"])
def login():
    incoming = request.get_json(silent=True) or request.form.to_dict()

    email = str(incoming.get("email", "")).strip().lower()
    password = str(incoming.get("password", ""))
    role = str(incoming.get("role", "")).strip().lower()

    if not email:
        return jsonify({"success": False, "message": "Email is required."}), 400

    if not password:
        return jsonify({"success": False, "message": "Password is required."}), 400

    if role not in ["job_seeker", "job_poster"]:
        return jsonify({"success": False, "message": "Please select a valid portal."}), 400

    user = User.query.filter_by(email=email, password=password, role=role).first()

    if not user:
        return jsonify({"success": False, "message": "Incorrect email, password, or portal."}), 401

    session.clear()
    session["user_id"] = user.id

    return jsonify({
        "success": True,
        "message": "Login successful.",
        "user": user.clean_dict()
    })


# =========================================================
# LOGOUT
# =========================================================

@app.route("/api/logout", methods=["POST", "GET"])
@app.route("/logout", methods=["POST", "GET"])
def logout():
    session.clear()
    return jsonify({"success": True, "message": "Logged out successfully."})


# =========================================================
# GET JOBS
# =========================================================

@app.route("/api/jobs", methods=["GET"])
@app.route("/jobs", methods=["GET"])
def get_jobs():
    search = request.args.get("search", "").strip().lower()
    category = request.args.get("category", "").strip().lower()
    location = request.args.get("location", "").strip().lower()
    salary = request.args.get("salary", "").strip()

    query = Job.query

    if category:
        query = query.filter(Job.category.ilike(f"%{category}%"))

    if location:
        query = query.filter(Job.location.ilike(f"%{location}%"))

    jobs_list = query.all()
    filtered_jobs = []

    for job in jobs_list:
        if search:
            searchable = f"{job.title} {job.company} {job.category} {job.location}".lower()
            if search not in searchable:
                continue

        if salary:
            try:
                minimum_salary = float(salary.replace(",", ""))
                current_salary = float(job.salary.replace(",", ""))
                if current_salary < minimum_salary:
                    continue
            except (ValueError, TypeError):
                pass

        filtered_jobs.append(job.to_dict())

    return jsonify({"success": True, "jobs": filtered_jobs})


# =========================================================
# SINGLE JOB
# =========================================================

@app.route("/api/jobs/", methods=["GET"])
@app.route("/jobs/", methods=["GET"])
def get_single_job(job_id):
    job = db.session.get(Job, job_id)
    if not job:
        return jsonify({"success": False, "message": "Job not found."}), 404

    return jsonify({"success": True, "job": job.to_dict()})


# =========================================================
# CREATE JOB
# =========================================================

@app.route("/api/jobs", methods=["POST"])
@app.route("/post-job", methods=["POST"])
@app.route("/jobs", methods=["POST"])
@role_required("job_poster")
def create_job():
    user = get_current_user()
    incoming = request.get_json(silent=True) or request.form.to_dict()

    title = str(incoming.get("title", "")).strip()
    company = str(incoming.get("company", "")).strip()
    category = str(incoming.get("category", "")).strip()
    location = str(incoming.get("location", "")).strip()
    salary = str(incoming.get("salary", "")).strip()
    description = str(incoming.get("description", "")).strip()

    fields = [
        ("title", title, "Job title is required."),
        ("company", company, "Company name is required."),
        ("category", category, "Category is required."),
        ("location", location, "Location is required."),
        ("salary", salary, "Salary is required."),
        ("description", description, "Job description is required.")
    ]

    for field, value, message in fields:
        if not value:
            return jsonify({"success": False, "field": field, "message": message}), 400

    new_job = Job(
        title=title,
        company=company,
        category=category,
        location=location,
        salary=salary,
        description=description,
        poster_id=user.id
    )

    db.session.add(new_job)
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Job posted successfully.",
        "job": new_job.to_dict()
    })


# =========================================================
# MY JOBS (POSTER)
# =========================================================

@app.route("/api/my-jobs", methods=["GET"])
@app.route("/my-jobs", methods=["GET"])
@role_required("job_poster")
def my_jobs():
    user = get_current_user()
    jobs = [job.to_dict() for job in user.jobs]
    return jsonify({"success": True, "jobs": jobs})


# =========================================================
# FAVORITE / UNFAVORITE
# =========================================================

@app.route("/api/jobs//favorite", methods=["POST"])
@role_required("job_seeker")
def favorite_job(job_id):
    user = get_current_user()
    job = db.session.get(Job, job_id)

    if not job:
        return jsonify({"success": False, "message": "Job not found."}), 404

    if job in user.favorites:
        user.favorites.remove(job)
        message = "Job removed from favorites."
    else:
        user.favorites.append(job)
        message = "Job added to favorites."

    db.session.commit()
    fav_ids = [j.id for j in user.favorites]

    return jsonify({"success": True, "message": message, "favorites": fav_ids})


@app.route("/api/favorites", methods=["GET"])
@role_required("job_seeker")
def get_favorites():
    user = get_current_user()
    jobs = [job.to_dict() for job in user.favorites]
    fav_ids = [job.id for job in user.favorites]

    return jsonify({"success": True, "jobs": jobs, "favorites": fav_ids})


@app.route("/api/jobs//unfavorite", methods=["POST"])
@role_required("job_seeker")
def unfavorite_job(job_id):
    user = get_current_user()
    job = db.session.get(Job, job_id)

    if job and job in user.favorites:
        user.favorites.remove(job)
        db.session.commit()

    fav_ids = [j.id for j in user.favorites]
    return jsonify({"success": True, "message": "Job removed from favorites.", "favorites": fav_ids})


# =========================================================
# APPLY FOR JOB
# =========================================================

@app.route("/api/jobs//apply", methods=["POST"])
@app.route("/apply/", methods=["POST"])
@role_required("job_seeker")
def apply_for_job(job_id):
    user = get_current_user()
    job = db.session.get(Job, job_id)

    if not job:
        return jsonify({"success": False, "message": "Job not found."}), 404

    existing_app = Application.query.filter_by(job_id=job_id, user_id=user.id).first()
    if existing_app:
        return jsonify({"success": False, "message": "You have already applied for this job."}), 400

    applicant_name = request.form.get("name", "").strip() or user.name
    applicant_email = request.form.get("email", "").strip() or user.email
    contact = request.form.get("contact", "").strip()
    introduction = request.form.get("introduction", "").strip()

    if not applicant_name:
        return jsonify({"success": False, "field": "name", "message": "Your name is required."}), 400
    if not applicant_email:
        return jsonify({"success": False, "field": "email", "message": "Your email is required."}), 400
    if not contact:
        return jsonify({"success": False, "field": "contact", "message": "Contact number is required."}), 400
    if not introduction:
        return jsonify({"success": False, "field": "introduction", "message": "Introduction is required."}), 400

    file = request.files.get("resume")
    if file is None or not file.filename:
        return jsonify({"success": False, "field": "resume", "message": "Resume is required."}), 400

    if not allowed_file(file.filename):
        return jsonify({"success": False, "field": "resume", "message": "Only PDF, DOC, and DOCX files are allowed."}), 400

    extension = file.filename.rsplit(".", 1)[1].lower()

    # Create temporary record to assign primary key ID for filename naming
    new_resume = Resume(
        user_id=user.id,
        filename="",
        original_filename=secure_filename(file.filename),
        skills="",
        introduction=introduction,
        profile_resume=False
    )
    db.session.add(new_resume)
    db.session.flush()

    filename = secure_filename(f"application_resume_{user.id}_{new_resume.id}.{extension}")
    filepath = os.path.join(RESUME_FOLDER, filename)

    try:
        file.save(filepath)
    except OSError:
        db.session.rollback()
        return jsonify({"success": False, "message": "Unable to save resume."}), 500

    new_resume.filename = filename

    application = Application(
        job_id=job.id,
        user_id=user.id,
        resume_id=new_resume.id,
        job_snapshot=job.to_dict(),
        applicant_name=applicant_name,
        applicant_email=applicant_email,
        contact=contact,
        introduction=introduction,
        status="Applied"
    )
    db.session.add(application)
    db.session.flush()

    # Notify Job Poster
    poster = db.session.get(User, job.poster_id)
    if poster:
        notification = Notification(
            user_id=poster.id,
            type="application",
            status="Applied",
            message=f"{applicant_name} applied for your job '{job.title}'.",
            job_id=job.id,
            application_id=application.id
        )
        db.session.add(notification)

    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Application submitted successfully.",
        "application": application.to_dict()
    })


# =========================================================
# APPLICATION HISTORY (SEEKER)
# =========================================================

@app.route("/api/my-applications", methods=["GET"])
@app.route("/api/application-history", methods=["GET"])
@app.route("/api/applications/history", methods=["GET"])
@app.route("/my-applications", methods=["GET"])
@role_required("job_seeker")
def my_applications():
    user = get_current_user()
    applications = Application.query.filter_by(user_id=user.id).all()

    results = []
    for app_item in applications:
        item = app_item.to_dict()
        item["job"] = app_item.get_job_info()
        item["resume"] = app_item.resume.to_dict() if app_item.resume else None
        results.append(item)

    return jsonify({"success": True, "applications": results})


# =========================================================
# APPLICATION STATUS (SEEKER COUNTS)
# =========================================================

@app.route("/api/application-status", methods=["GET"])
@role_required("job_seeker")
def application_status():
    user = get_current_user()
    applications_list = Application.query.filter_by(user_id=user.id).all()

    applications = []
    counts = {
        "total": len(applications_list),
        "hired": 0,
        "shortlisted": 0,
        "under_review": 0,
        "rejected": 0,
        "applied": 0
    }

    for app_item in applications_list:
        item = app_item.to_dict()
        item["job"] = app_item.get_job_info()
        applications.append(item)

        status_lower = str(app_item.status or "Applied").strip().lower()
        if status_lower == "hired":
            counts["hired"] += 1
        elif status_lower == "shortlisted":
            counts["shortlisted"] += 1
        elif status_lower in ["under review", "under_review"]:
            counts["under_review"] += 1
        elif status_lower == "rejected":
            counts["rejected"] += 1
        else:
            counts["applied"] += 1

    return jsonify({"success": True, "counts": counts, "applications": applications})


# =========================================================
# POSTER APPLICANTS
# =========================================================

@app.route("/api/my-applicants", methods=["GET"])
@app.route("/api/applicants", methods=["GET"])
@app.route("/my-applicants", methods=["GET"])
@role_required("job_poster")
def my_applicants():
    poster = get_current_user()
    poster_job_ids = [job.id for job in poster.jobs]

    applications = Application.query.filter(
        (Application.job_id.in_(poster_job_ids)) | (Application.job_id.is_(None))
    ).all()

    results = []
    for app_item in applications:
        job_info = app_item.get_job_info()
        
        # Verify ownership via active job or snapshot
        job_poster_id = job_info.get("poster_id") if isinstance(job_info, dict) else None
        if not job_poster_id or int(job_poster_id) != poster.id:
            continue

        resume = app_item.resume
        resume_dict = resume.to_dict() if resume else None

        results.append({
            "application_id": app_item.id,
            "status": app_item.status,
            "job": job_info,
            "applicant": {
                "id": app_item.user_id,
                "name": app_item.applicant_name,
                "email": app_item.applicant_email,
                "contact": app_item.contact,
                "introduction": app_item.introduction
            },
            "resume": resume_dict,
            "resume_filename": resume.filename if resume else "",
            "resume_url": f"/resumes/{resume.filename}" if resume and resume.filename else "",
            "salary": app_item.salary,
            "interview_date": app_item.interview_date,
            "interview_time": app_item.interview_time,
            "remarks": app_item.remarks,
            "introduction": app_item.introduction
        })

    return jsonify({"success": True, "applicants": results})


# =========================================================
# APPLICANTS FOR A SPECIFIC JOB
# =========================================================

@app.route("/api/jobs//applicants", methods=["GET"])
@role_required("job_poster")
def job_applicants(job_id):
    poster = get_current_user()
    job = db.session.get(Job, job_id)

    if not job:
        return jsonify({"success": False, "message": "Job not found."}), 404

    if job.poster_id != poster.id:
        return jsonify({"success": False, "message": "You do not own this job."}), 403

    applications = Application.query.filter_by(job_id=job.id).all()
    applicants = []

    for app_item in applications:
        item = app_item.to_dict()
        item["job"] = job.to_dict()
        item["applicant"] = {
            "id": app_item.user_id,
            "name": app_item.applicant_name,
            "email": app_item.applicant_email,
            "contact": app_item.contact,
            "introduction": app_item.introduction
        }
        item["resume"] = app_item.resume.to_dict() if app_item.resume else None
        applicants.append(item)

    return jsonify({"success": True, "job": job.to_dict(), "applicants": applicants})


# =========================================================
# RESUME UPLOAD (PROFILE RESUME)
# =========================================================

@app.route("/api/resumes/upload", methods=["POST"])
@app.route("/api/resume/upload", methods=["POST"])
@role_required("job_seeker")
def upload_resume():
    user = get_current_user()

    file = request.files.get("resume")
    skills = request.form.get("skills", "").strip()
    introduction = request.form.get("introduction", "").strip()

    if file is None or not file.filename:
        return jsonify({"success": False, "field": "resume", "message": "Please select your resume file."}), 400

    if not allowed_file(file.filename):
        return jsonify({"success": False, "field": "resume", "message": "Only PDF, DOC, and DOCX files are allowed."}), 400

    if not skills:
        return jsonify({"success": False, "field": "skills", "message": "Please enter your skills."}), 400

    if not introduction:
        return jsonify({"success": False, "field": "introduction", "message": "Please enter your professional introduction."}), 400

    extension = file.filename.rsplit(".", 1)[1].lower()

    # Clear previous profile resume flags for this user
    Resume.query.filter_by(user_id=user.id, profile_resume=True).update({"profile_resume": False})

    new_resume = Resume(
        user_id=user.id,
        filename="",
        original_filename=secure_filename(file.filename),
        skills=skills,
        introduction=introduction,
        profile_resume=True
    )
    db.session.add(new_resume)
    db.session.flush()

    filename = secure_filename(f"resume_{user.id}_{new_resume.id}.{extension}")
    filepath = os.path.join(RESUME_FOLDER, filename)

    try:
        file.save(filepath)
    except OSError:
        db.session.rollback()
        return jsonify({"success": False, "message": "Unable to save resume file."}), 500

    new_resume.filename = filename
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Resume uploaded successfully.",
        "resume": new_resume.to_dict()
    })


# =========================================================
# CANDIDATE RESUMES
# =========================================================

@app.route("/api/resumes", methods=["GET"])
@app.route("/api/candidates", methods=["GET"])
@app.route("/candidates", methods=["GET"])
@role_required("job_poster")
def get_candidates():
    search = request.args.get("search", "").strip().lower()

    profile_resumes = Resume.query.filter_by(profile_resume=True).all()
    results = []

    for resume in profile_resumes:
        candidate = resume.owner
        if not candidate:
            continue

        skills = (resume.skills or "").lower()
        intro = (resume.introduction or "").lower()
        name = candidate.name.lower()
        email = candidate.email.lower()

        if search:
            searchable = f"{skills} {intro} {name} {email}"
            if search not in searchable:
                continue

        results.append({
            "resume": resume.to_dict(),
            "user": {
                "id": candidate.id,
                "name": candidate.name,
                "email": candidate.email
            }
        })

    return jsonify({"success": True, "resumes": results, "candidates": results})


# =========================================================
# RESUME FILE SERVING
# =========================================================

@app.route("/resumes/", methods=["GET"])
def serve_resume(filename):
    return send_from_directory(RESUME_FOLDER, filename, as_attachment=False)


# =========================================================
# NOTIFICATIONS
# =========================================================

@app.route("/api/notifications", methods=["GET"])
@app.route("/notifications", methods=["GET"])
@login_required
def get_notifications():
    user = get_current_user()
    notifications = Notification.query.filter_by(user_id=user.id).order_by(Notification.created_at.desc()).all()

    unread_count = sum(1 for n in notifications if not n.read)
    notifications_list = [n.to_dict() for n in notifications]

    return jsonify({"success": True, "notifications": notifications_list, "count": unread_count})


@app.route("/api/notifications/read", methods=["POST"])
@login_required
def mark_notifications_read():
    user = get_current_user()
    Notification.query.filter_by(user_id=user.id, read=False).update({"read": True})
    db.session.commit()

    return jsonify({"success": True, "message": "Notifications marked as read."})


# =========================================================
# UPDATE APPLICATION STATUS
# =========================================================

@app.route("/api/applications//status", methods=["POST"])
@role_required("job_poster")
def update_application_status(application_id):
    poster = get_current_user()
    incoming = request.get_json(silent=True) or request.form.to_dict()

    status = str(incoming.get("status", "")).strip()
    salary = str(incoming.get("salary", "")).strip()
    interview_date = str(incoming.get("interview_date", "")).strip()
    interview_time = str(incoming.get("interview_time", "")).strip()
    remarks = str(incoming.get("remarks", "")).strip()

    allowed_statuses = ["Applied", "Under Review", "Shortlisted", "Rejected", "Hired"]
    if status not in allowed_statuses:
        return jsonify({"success": False, "message": "Invalid application status."}), 400

    application = db.session.get(Application, application_id)
    if not application:
        return jsonify({"success": False, "message": "Application not found."}), 404

    job_info = application.get_job_info()
    job_poster_id = job_info.get("poster_id") if isinstance(job_info, dict) else None

    if not job_poster_id or int(job_poster_id) != poster.id:
        return jsonify({"success": False, "message": "You cannot update this application."}), 403

    # Field validations based on status
    if status == "Hired" and not salary:
        return jsonify({"success": False, "field": "salary", "message": "Salary is required when hiring a candidate."}), 400

    if status == "Shortlisted":
        if not interview_date:
            return jsonify({"success": False, "field": "interview_date", "message": "Interview date is required."}), 400
        if not interview_time:
            return jsonify({"success": False, "field": "interview_time", "message": "Interview time is required."}), 400

    if status in ["Rejected", "Under Review"] and not remarks:
        return jsonify({"success": False, "field": "remarks", "message": "Remarks are required."}), 400

    # Apply updates
    application.status = status
    application.salary = salary if status == "Hired" else ""
    application.interview_date = interview_date if status == "Shortlisted" else ""
    application.interview_time = interview_time if status == "Shortlisted" else ""
    application.remarks = remarks if status in ["Hired", "Shortlisted", "Rejected", "Under Review"] else ""

    # Notify Applicant
    job_title = job_info.get("title", "Job")
    if status == "Hired":
        message = f"Congratulations! You have been hired for '{job_title}'. Salary: {salary}."
    elif status == "Shortlisted":
        message = f"You have been shortlisted for '{job_title}'. Interview: {interview_date} at {interview_time}."
    elif status == "Rejected":
        message = f"Your application for '{job_title}' has been rejected. Remarks: {remarks}"
    elif status == "Under Review":
        message = f"Your application for '{job_title}' is now under review. Remarks: {remarks}"
    else:
        message = f"Your application for '{job_title}' has been updated."

    notification = Notification(
        user_id=application.user_id,
        type="application_status",
        status=status,
        message=message,
        job_id=application.job_id,
        application_id=application.id
    )
    db.session.add(notification)

    db.session.commit()

    return jsonify({"success": True, "message": f"Application marked as {status}.", "application": application.to_dict()})


# =========================================================
# DELETE JOB
# =========================================================

@app.route("/api/jobs/", methods=["DELETE"])
@role_required("job_poster")
def delete_job(job_id):
    poster = get_current_user()
    job = db.session.get(Job, job_id)

    if not job:
        return jsonify({"success": False, "message": "Job not found."}), 404

    if job.poster_id != poster.id:
        return jsonify({"success": False, "message": "You can only delete your own jobs."}), 403

    # Preserve snapshot for all current applications before breaking foreign key
    applications = Application.query.filter_by(job_id=job.id).all()
    for application in applications:
        application.job_snapshot = job.to_dict()
        application.job_id = None

    # Remove job from all user favorites
    job.favorited_by.clear()

    db.session.delete(job)
    db.session.commit()

    return jsonify({"success": True, "message": "Job deleted successfully.", "deleted_job_id": job_id})


# =========================================================
# ERROR HANDLERS
# =========================================================

@app.errorhandler(413)
def file_too_large(error):
    return jsonify({"success": False, "message": "File is too large. Maximum size is 10 MB."}), 413


@app.errorhandler(404)
def page_not_found(error):
    if request.path.startswith("/api/"):
        return jsonify({"success": False, "message": "API route not found.", "path": request.path}), 404
    return render_template("index.html")


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({"success": False, "message": "Internal server error."}), 500


# =========================================================
# APP RUNNER
# =========================================================

if __name__ == "__main__":
    print("")
    print("==========================================")
    print("        JOBSPHERE JOB PORTAL")
    print("==========================================")
    print("Server starting...")
    print("Open: http://127.0.0.1:5000/")
    print("==========================================")
    print("")

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )