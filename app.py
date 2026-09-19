import os
import json
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

from werkzeug.utils import secure_filename


# =========================================================
# APP CONFIGURATION
# =========================================================

app = Flask(__name__)

app.secret_key = "jobsphere_secret_key_2026"

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

DATA_FILE = os.path.join(
    BASE_DIR,
    "data.json"
)

RESUME_FOLDER = os.path.join(
    BASE_DIR,
    "resumes"
)

ALLOWED_EXTENSIONS = {
    "pdf",
    "doc",
    "docx"
}

app.config["RESUME_FOLDER"] = RESUME_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024


# =========================================================
# CREATE FOLDERS
# =========================================================

os.makedirs(
    RESUME_FOLDER,
    exist_ok=True
)


# =========================================================
# NO CACHE
# =========================================================

@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = (
        "no-store, no-cache, must-revalidate, max-age=0"
    )
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


# =========================================================
# DEFAULT DATA
# =========================================================

DEFAULT_DATA = {
    "users": [],
    "jobs": [],
    "applications": [],
    "resumes": []
}


# =========================================================
# DATABASE
# =========================================================

def load_data():

    if not os.path.exists(DATA_FILE):

        data = {
            "users": [],
            "jobs": [],
            "applications": [],
            "resumes": []
        }

        save_data(data)

        return data

    try:

        with open(
            DATA_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

    except (
        json.JSONDecodeError,
        OSError
    ):

        # Do NOT silently destroy existing data.
        # If the file cannot be read, return safe empty
        # structure rather than overwriting immediately.

        return {
            "users": [],
            "jobs": [],
            "applications": [],
            "resumes": []
        }

    if not isinstance(data, dict):
        data = {}

    if "users" not in data:
        data["users"] = []

    if "jobs" not in data:
        data["jobs"] = []

    if "applications" not in data:
        data["applications"] = []

    if "resumes" not in data:
        data["resumes"] = []

    if not isinstance(data["users"], list):
        data["users"] = []

    if not isinstance(data["jobs"], list):
        data["jobs"] = []

    if not isinstance(data["applications"], list):
        data["applications"] = []

    if not isinstance(data["resumes"], list):
        data["resumes"] = []


    # -----------------------------------------------------
    # Upgrade users
    # -----------------------------------------------------

    changed = False

    for user in data["users"]:

        if "favorites" not in user:
            user["favorites"] = []
            changed = True

        if not isinstance(
            user.get("favorites"),
            list
        ):
            user["favorites"] = []
            changed = True

        if "notifications" not in user:
            user["notifications"] = []
            changed = True

        if not isinstance(
            user.get("notifications"),
            list
        ):
            user["notifications"] = []
            changed = True


    # -----------------------------------------------------
    # Upgrade applications
    # -----------------------------------------------------

    for application in data["applications"]:

        defaults = {
            "contact": "",
            "introduction": "",
            "salary": "",
            "interview_date": "",
            "interview_time": "",
            "remarks": "",
            "status": "Applied"
        }

        for key, value in defaults.items():

            if key not in application:
                application[key] = value
                changed = True


        # -------------------------------------------------
        # Preserve old job information.
        #
        # This is important because if a poster deletes a
        # job, application history must NOT disappear.
        # -------------------------------------------------

        if not application.get("job_snapshot"):

            job = get_job_by_id(
                application.get("job_id"),
                data
            )

            if job:

                application["job_snapshot"] = dict(job)
                changed = True


    if changed:

        save_data(data)

    return data


def save_data(data):

    temp_file = DATA_FILE + ".tmp"

    with open(
        temp_file,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            indent=4,
            ensure_ascii=False
        )

    os.replace(
        temp_file,
        DATA_FILE
    )


# =========================================================
# ID HELPERS
# =========================================================

def next_id(items):

    if not items:
        return 1

    values = []

    for item in items:

        try:
            values.append(
                int(item.get("id", 0))
            )
        except (
            ValueError,
            TypeError
        ):
            pass

    if not values:
        return 1

    return max(values) + 1


# =========================================================
# USER HELPERS
# =========================================================

# FIX: get_current_user now accepts the already-loaded
# `data` dict. If a route already called load_data(), it
# MUST pass that same object here so that the returned user
# is the *same object living inside data["users"]* — not a
# copy from a second, separate load_data() call. Mutating a
# copy and then calling save_data(data) on the original
# silently threw away every change (this was the root cause
# of favorites/notifications not saving).
def get_current_user(data=None):

    user_id = session.get(
        "user_id"
    )

    if user_id is None:
        return None

    if data is None:
        data = load_data()

    for user in data["users"]:

        try:

            if int(user.get("id", 0)) == int(user_id):
                return user

        except (
            ValueError,
            TypeError
        ):
            continue

    return None


def get_user_by_id(
    user_id,
    data
):

    if user_id is None:
        return None

    for user in data["users"]:

        try:

            if int(user.get("id", 0)) == int(user_id):
                return user

        except (
            ValueError,
            TypeError
        ):
            continue

    return None


def clean_user(user):

    if not user:
        return None

    return {
        "id": user.get("id"),
        "name": user.get("name", ""),
        "email": user.get("email", ""),
        "role": user.get("role", ""),
        "favorites": user.get(
            "favorites",
            []
        )
    }


# =========================================================
# JOB HELPERS
# =========================================================

def get_job_by_id(
    job_id,
    data
):

    if job_id is None:
        return None

    for job in data["jobs"]:

        try:

            if int(job.get("id", 0)) == int(job_id):
                return job

        except (
            ValueError,
            TypeError
        ):
            continue

    return None


def get_application_job(
    application,
    data
):

    job = get_job_by_id(
        application.get("job_id"),
        data
    )

    if job:
        return job

    snapshot = application.get(
        "job_snapshot"
    )

    if isinstance(
        snapshot,
        dict
    ):
        return snapshot

    return None


# =========================================================
# APPLICATION HELPERS
# =========================================================

def get_application_by_id(
    application_id,
    data
):

    for application in data["applications"]:

        try:

            if (
                int(application.get("id", 0))
                ==
                int(application_id)
            ):
                return application

        except (
            ValueError,
            TypeError
        ):
            continue

    return None


# =========================================================
# RESUME HELPERS
# =========================================================

def get_resume_by_id(
    resume_id,
    data
):

    if resume_id is None:
        return None

    for resume in data["resumes"]:

        try:

            if (
                int(resume.get("id", 0))
                ==
                int(resume_id)
            ):
                return resume

        except (
            ValueError,
            TypeError
        ):
            continue

    return None


def allowed_file(filename):

    if not filename:
        return False

    if "." not in filename:
        return False

    extension = (
        filename
        .rsplit(".", 1)[1]
        .lower()
    )

    return extension in ALLOWED_EXTENSIONS


# =========================================================
# AUTH DECORATORS
# =========================================================

def login_required(function):

    @wraps(function)
    def decorated_function(
        *args,
        **kwargs
    ):

        if not session.get("user_id"):

            return jsonify({
                "success": False,
                "message": "Please login first."
            }), 401

        user = get_current_user()

        if not user:

            session.clear()

            return jsonify({
                "success": False,
                "message": "Session expired. Please login again."
            }), 401

        return function(
            *args,
            **kwargs
        )

    return decorated_function


def role_required(role):

    def decorator(function):

        @wraps(function)
        def decorated_function(
            *args,
            **kwargs
        ):

            user = get_current_user()

            if not user:

                return jsonify({
                    "success": False,
                    "message": "Please login first."
                }), 401

            if user.get("role") != role:

                return jsonify({
                    "success": False,
                    "message": "You do not have permission for this section."
                }), 403

            return function(
                *args,
                **kwargs
            )

        return decorated_function

    return decorator


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


@app.route("/index.html")
def index_page():

    return render_template(
        "index.html"
    )


# =========================================================
# CURRENT USER
# =========================================================

@app.route(
    "/api/me",
    methods=["GET"]
)
@app.route(
    "/me",
    methods=["GET"]
)
def me():

    user = get_current_user()

    if not user:

        return jsonify({
            "success": False,
            "logged_in": False,
            "user": None
        })

    return jsonify({
        "success": True,
        "logged_in": True,
        "user": clean_user(user)
    })


# =========================================================
# SIGNUP
# =========================================================

@app.route(
    "/api/signup",
    methods=["POST"]
)
@app.route(
    "/signup",
    methods=["POST"]
)
def signup():

    data = load_data()

    incoming = request.get_json(
        silent=True
    )

    if incoming is None:
        incoming = request.form.to_dict()

    name = str(
        incoming.get("name", "")
    ).strip()

    email = str(
        incoming.get("email", "")
    ).strip().lower()

    password = str(
        incoming.get("password", "")
    )

    role = str(
        incoming.get("role", "")
    ).strip().lower()


    if role not in [
        "job_seeker",
        "job_poster"
    ]:

        return jsonify({
            "success": False,
            "message": "Please select a valid portal."
        }), 400


    if not name:

        return jsonify({
            "success": False,
            "message": "Full name is required."
        }), 400


    if not email:

        return jsonify({
            "success": False,
            "message": "Email is required."
        }), 400


    if not password:

        return jsonify({
            "success": False,
            "message": "Password is required."
        }), 400


    # Same email can exist only once for the same portal.
    # This keeps seeker and poster accounts separate.

    for user in data["users"]:

        if (
            str(
                user.get("email", "")
            ).lower()
            == email
            and
            user.get("role")
            == role
        ):

            return jsonify({
                "success": False,
                "message": "An account with this email already exists for this portal."
            }), 400


    new_user = {

        "id": next_id(
            data["users"]
        ),

        "name": name,

        "email": email,

        "password": password,

        "role": role,

        "favorites": [],

        "notifications": []
    }


    data["users"].append(
        new_user
    )

    save_data(data)

    session.clear()

    session["user_id"] = (
        new_user["id"]
    )


    return jsonify({

        "success": True,

        "message": "Account created successfully.",

        "user": clean_user(
            new_user
        )
    })


# =========================================================
# LOGIN
# =========================================================

@app.route(
    "/api/login",
    methods=["POST"]
)
@app.route(
    "/login",
    methods=["POST"]
)
def login():

    data = load_data()

    incoming = request.get_json(
        silent=True
    )

    if incoming is None:
        incoming = request.form.to_dict()

    email = str(
        incoming.get("email", "")
    ).strip().lower()

    password = str(
        incoming.get("password", "")
    )

    role = str(
        incoming.get("role", "")
    ).strip().lower()


    if not email:

        return jsonify({
            "success": False,
            "message": "Email is required."
        }), 400


    if not password:

        return jsonify({
            "success": False,
            "message": "Password is required."
        }), 400


    if role not in [
        "job_seeker",
        "job_poster"
    ]:

        return jsonify({
            "success": False,
            "message": "Please select a valid portal."
        }), 400


    found_user = None


    for user in data["users"]:

        if (
            str(
                user.get("email", "")
            ).lower()
            == email
            and
            str(
                user.get("password", "")
            )
            == password
            and
            user.get("role")
            == role
        ):

            found_user = user
            break


    if not found_user:

        return jsonify({
            "success": False,
            "message": "Incorrect email, password, or portal."
        }), 401


    session.clear()

    session["user_id"] = (
        found_user["id"]
    )


    return jsonify({

        "success": True,

        "message": "Login successful.",

        "user": clean_user(
            found_user
        )
    })


# =========================================================
# LOGOUT
# =========================================================

@app.route(
    "/api/logout",
    methods=["POST", "GET"]
)
@app.route(
    "/logout",
    methods=["POST", "GET"]
)
def logout():

    session.clear()

    return jsonify({
        "success": True,
        "message": "Logged out successfully."
    })


# =========================================================
# GET JOBS
# =========================================================

@app.route(
    "/api/jobs",
    methods=["GET"]
)
@app.route(
    "/jobs",
    methods=["GET"]
)
def get_jobs():

    data = load_data()

    search = request.args.get(
        "search",
        ""
    ).strip().lower()

    category = request.args.get(
        "category",
        ""
    ).strip().lower()

    location = request.args.get(
        "location",
        ""
    ).strip().lower()

    salary = request.args.get(
        "salary",
        ""
    ).strip()


    filtered_jobs = []


    for job in data["jobs"]:

        title = str(
            job.get("title", "")
        ).lower()

        company = str(
            job.get("company", "")
        ).lower()

        job_category = str(
            job.get("category", "")
        ).lower()

        job_location = str(
            job.get("location", "")
        ).lower()


        if search:

            searchable = " ".join([
                title,
                company,
                job_category,
                job_location
            ])

            if search not in searchable:
                continue


        if category:

            if category not in job_category:
                continue


        if location:

            if location not in job_location:
                continue


        if salary:

            try:

                minimum_salary = float(
                    salary.replace(",", "")
                )

                current_salary = float(
                    str(
                        job.get("salary", "0")
                    ).replace(",", "")
                )

                if current_salary < minimum_salary:
                    continue

            except (
                ValueError,
                TypeError
            ):
                pass


        filtered_jobs.append(
            job
        )


    return jsonify({

        "success": True,

        "jobs": filtered_jobs
    })


# =========================================================
# SINGLE JOB
# =========================================================

@app.route(
    "/api/jobs/<int:job_id>",
    methods=["GET"]
)
@app.route(
    "/jobs/<int:job_id>",
    methods=["GET"]
)
def get_single_job(job_id):

    data = load_data()

    job = get_job_by_id(
        job_id,
        data
    )

    if not job:

        return jsonify({
            "success": False,
            "message": "Job not found."
        }), 404


    return jsonify({

        "success": True,

        "job": job
    })


# =========================================================
# CREATE JOB
# =========================================================

@app.route(
    "/api/jobs",
    methods=["POST"]
)
@app.route(
    "/post-job",
    methods=["POST"]
)
@app.route(
    "/jobs",
    methods=["POST"]
)
@role_required("job_poster")
def create_job():

    data = load_data()

    user = get_current_user(data)  # FIX: pass shared data

    incoming = request.get_json(
        silent=True
    )

    if incoming is None:
        incoming = request.form.to_dict()


    title = str(
        incoming.get("title", "")
    ).strip()

    company = str(
        incoming.get("company", "")
    ).strip()

    category = str(
        incoming.get("category", "")
    ).strip()

    location = str(
        incoming.get("location", "")
    ).strip()

    salary = str(
        incoming.get("salary", "")
    ).strip()

    description = str(
        incoming.get("description", "")
    ).strip()


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

            return jsonify({
                "success": False,
                "field": field,
                "message": message
            }), 400


    new_job = {

        "id": next_id(
            data["jobs"]
        ),

        "title": title,

        "company": company,

        "category": category,

        "location": location,

        "salary": salary,

        "description": description,

        # VERY IMPORTANT:
        # Every job belongs to the poster who created it.

        "poster_id": user["id"]
    }


    data["jobs"].append(
        new_job
    )

    save_data(data)


    return jsonify({

        "success": True,

        "message": "Job posted successfully.",

        "job": new_job
    })


# =========================================================
# MY JOBS
# =========================================================

@app.route(
    "/api/my-jobs",
    methods=["GET"]
)
@app.route(
    "/my-jobs",
    methods=["GET"]
)
@role_required("job_poster")
def my_jobs():

    data = load_data()

    user = get_current_user(data)  # FIX: pass shared data

    jobs = []


    for job in data["jobs"]:

        try:

            if (
                int(
                    job.get(
                        "poster_id",
                        0
                    )
                )
                ==
                int(user["id"])
            ):

                jobs.append(job)

        except (
            ValueError,
            TypeError
        ):
            continue


    return jsonify({

        "success": True,

        "jobs": jobs
    })


# =========================================================
# FAVORITE
# =========================================================

@app.route(
    "/api/jobs/<int:job_id>/favorite",
    methods=["POST"]
)
@role_required("job_seeker")
def favorite_job(job_id):

    data = load_data()

    # FIX (critical): must pass `data` here. Without it,
    # get_current_user() re-reads the file into a brand new
    # dict, so `user` below was a completely separate object
    # from `data`. Mutating user["favorites"] then had no
    # effect on `data`, and save_data(data) wrote out the
    # OLD favorites list — the toggle silently never saved.
    user = get_current_user(data)

    job = get_job_by_id(
        job_id,
        data
    )

    if not job:

        return jsonify({
            "success": False,
            "message": "Job not found."
        }), 404


    favorites = user.get(
        "favorites",
        []
    )

    clean_favorites = []


    for value in favorites:

        try:

            value = int(value)

            if value not in clean_favorites:
                clean_favorites.append(value)

        except (
            ValueError,
            TypeError
        ):
            continue


    if int(job_id) in clean_favorites:

        clean_favorites.remove(
            int(job_id)
        )

        message = (
            "Job removed from favorites."
        )

    else:

        clean_favorites.append(
            int(job_id)
        )

        message = (
            "Job added to favorites."
        )


    user["favorites"] = (
        clean_favorites
    )

    save_data(data)


    return jsonify({

        "success": True,

        "message": message,

        "favorites": clean_favorites
    })


# =========================================================
# FAVORITES
# =========================================================

@app.route(
    "/api/favorites",
    methods=["GET"]
)
@role_required("job_seeker")
def get_favorites():

    data = load_data()

    user = get_current_user(data)  # FIX: pass shared data

    favorites = user.get(
        "favorites",
        []
    )

    favorite_ids = set()


    for value in favorites:

        try:
            favorite_ids.add(
                int(value)
            )

        except (
            ValueError,
            TypeError
        ):
            continue


    jobs = []


    for job in data["jobs"]:

        try:

            if (
                int(job.get("id", 0))
                in favorite_ids
            ):

                jobs.append(job)

        except (
            ValueError,
            TypeError
        ):
            continue


    return jsonify({

        "success": True,

        "jobs": jobs,

        "favorites": list(
            favorite_ids
        )
    })


# =========================================================
# UNFAVORITE
# =========================================================

@app.route(
    "/api/jobs/<int:job_id>/unfavorite",
    methods=["POST"]
)
@role_required("job_seeker")
def unfavorite_job(job_id):

    data = load_data()

    # FIX (critical): same bug as favorite_job above — must
    # pass `data` so `user` is the same object we save.
    user = get_current_user(data)

    favorites = user.get(
        "favorites",
        []
    )

    cleaned = []


    for value in favorites:

        try:

            if int(value) != int(job_id):
                cleaned.append(
                    int(value)
                )

        except (
            ValueError,
            TypeError
        ):
            continue


    user["favorites"] = cleaned

    save_data(data)


    return jsonify({

        "success": True,

        "message": "Job removed from favorites.",

        "favorites": cleaned
    })


# =========================================================
# APPLY FOR JOB
# =========================================================

@app.route(
    "/api/jobs/<int:job_id>/apply",
    methods=["POST"]
)
@app.route(
    "/apply/<int:job_id>",
    methods=["POST"]
)
@role_required("job_seeker")
def apply_for_job(job_id):

    data = load_data()

    user = get_current_user(data)  # FIX: pass shared data

    job = get_job_by_id(
        job_id,
        data
    )


    if not job:

        return jsonify({
            "success": False,
            "message": "Job not found."
        }), 404


    # -----------------------------------------------------
    # IMPORTANT:
    # Check duplicate application for THIS USER ONLY.
    # -----------------------------------------------------

    for application in data["applications"]:

        try:

            same_job = (
                int(
                    application.get(
                        "job_id",
                        0
                    )
                )
                ==
                int(job_id)
            )

            same_user = (
                int(
                    application.get(
                        "user_id",
                        0
                    )
                )
                ==
                int(user["id"])
            )

            if same_job and same_user:

                return jsonify({
                    "success": False,
                    "message": "You have already applied for this job."
                }), 400

        except (
            ValueError,
            TypeError
        ):
            continue


    applicant_name = request.form.get(
        "name",
        ""
    ).strip()

    applicant_email = request.form.get(
        "email",
        ""
    ).strip()

    contact = request.form.get(
        "contact",
        ""
    ).strip()

    introduction = request.form.get(
        "introduction",
        ""
    ).strip()


    if not applicant_name:
        applicant_name = user.get(
            "name",
            ""
        ).strip()

    if not applicant_email:
        applicant_email = user.get(
            "email",
            ""
        ).strip()


    if not applicant_name:

        return jsonify({
            "success": False,
            "field": "name",
            "message": "Your name is required."
        }), 400


    if not applicant_email:

        return jsonify({
            "success": False,
            "field": "email",
            "message": "Your email is required."
        }), 400


    if not contact:

        return jsonify({
            "success": False,
            "field": "contact",
            "message": "Contact number is required."
        }), 400


    if not introduction:

        return jsonify({
            "success": False,
            "field": "introduction",
            "message": "Introduction is required."
        }), 400


    # =====================================================
    # APPLICATION RESUME
    # =====================================================

    file = request.files.get(
        "resume"
    )


    if file is None:

        return jsonify({
            "success": False,
            "field": "resume",
            "message": "Resume is required."
        }), 400


    if not file.filename:

        return jsonify({
            "success": False,
            "field": "resume",
            "message": "Please select your resume."
        }), 400


    if not allowed_file(
        file.filename
    ):

        return jsonify({
            "success": False,
            "field": "resume",
            "message": "Only PDF, DOC, and DOCX files are allowed."
        }), 400


    extension = (
        file.filename
        .rsplit(".", 1)[1]
        .lower()
    )


    resume_id = next_id(
        data["resumes"]
    )


    filename = secure_filename(
        f"application_resume_{user['id']}_{resume_id}.{extension}"
    )


    filepath = os.path.join(
        RESUME_FOLDER,
        filename
    )


    try:

        file.save(
            filepath
        )

    except OSError:

        return jsonify({
            "success": False,
            "message": "Unable to save resume."
        }), 500


    resume = {

        "id": resume_id,

        "user_id": user["id"],

        "filename": filename,

        "original_filename": secure_filename(
            file.filename
        ),

        "skills": "",

        "introduction": introduction
    }


    data["resumes"].append(
        resume
    )


    # =====================================================
    # APPLICATION
    # =====================================================

    application_id = next_id(
        data["applications"]
    )


    application = {

        "id": application_id,

        # The job being applied to.
        "job_id": job_id,

        # VERY IMPORTANT:
        # This is the logged-in applicant.
        "user_id": user["id"],

        "resume_id": resume_id,

        # Keep job information permanently for history.
        "job_snapshot": dict(job),

        "applicant_name": applicant_name,

        "applicant_email": applicant_email,

        "contact": contact,

        "introduction": introduction,

        "status": "Applied",

        "salary": "",

        "interview_date": "",

        "interview_time": "",

        "remarks": "",

        "created_at": datetime.now().isoformat()
    }


    data["applications"].append(
        application
    )


    # =====================================================
    # NOTIFY ONLY THE JOB POSTER
    # =====================================================

    poster_id = job.get(
        "poster_id"
    )

    poster = get_user_by_id(
        poster_id,
        data
    )


    if poster:

        if not isinstance(
            poster.get("notifications"),
            list
        ):
            poster["notifications"] = []


        poster["notifications"].append({

            "id": next_id(
                poster["notifications"]
            ),

            "type": "application",

            "status": "Applied",

            "message": (
                f"{applicant_name} applied for your job "
                f"'{job.get('title', 'Job')}'."
            ),

            "job_id": job_id,

            "application_id": application_id,

            "read": False,

            "created_at": datetime.now().isoformat()
        })


    save_data(data)


    return jsonify({

        "success": True,

        "message": "Application submitted successfully.",

        "application": application
    })


# =========================================================
# APPLICATION HISTORY
# =========================================================

@app.route(
    "/api/my-applications",
    methods=["GET"]
)
@app.route(
    "/api/application-history",
    methods=["GET"]
)
@app.route(
    "/api/applications/history",
    methods=["GET"]
)
@app.route(
    "/my-applications",
    methods=["GET"]
)
@role_required("job_seeker")
def my_applications():

    data = load_data()

    user = get_current_user(data)  # FIX: pass shared data

    results = []


    # =====================================================
    # ONLY APPLICATIONS BELONGING TO CURRENT USER
    # =====================================================

    for application in data["applications"]:

        try:

            if (
                int(
                    application.get(
                        "user_id",
                        0
                    )
                )
                !=
                int(user["id"])
            ):
                continue

        except (
            ValueError,
            TypeError
        ):
            continue


        job = get_application_job(
            application,
            data
        )


        resume = get_resume_by_id(
            application.get(
                "resume_id"
            ),
            data
        )


        item = dict(
            application
        )

        item["job"] = job

        item["resume"] = resume


        results.append(
            item
        )


    return jsonify({

        "success": True,

        "applications": results
    })


# =========================================================
# APPLICATION STATUS
# =========================================================

@app.route(
    "/api/application-status",
    methods=["GET"]
)
@role_required("job_seeker")
def application_status():

    data = load_data()

    user = get_current_user(data)  # FIX: pass shared data

    applications = []


    # =====================================================
    # ONLY CURRENT SEEKER'S APPLICATIONS
    # =====================================================

    for application in data["applications"]:

        try:

            if (
                int(
                    application.get(
                        "user_id",
                        0
                    )
                )
                !=
                int(user["id"])
            ):
                continue

        except (
            ValueError,
            TypeError
        ):
            continue


        job = get_application_job(
            application,
            data
        )


        if not job:

            job = {

                "id": application.get(
                    "job_id"
                ),

                "title": application.get(
                    "job_title",
                    "Deleted Job"
                ),

                "company": application.get(
                    "company",
                    "Company not provided"
                ),

                "category": application.get(
                    "category",
                    "JOB"
                ),

                "location": application.get(
                    "location",
                    "Not provided"
                ),

                "salary": "",

                "description": "",

                "deleted": True
            }


        item = dict(
            application
        )

        item["job"] = job


        applications.append(
            item
        )


    counts = {

        "total": len(
            applications
        ),

        "hired": 0,

        "shortlisted": 0,

        "under_review": 0,

        "rejected": 0,

        "applied": 0
    }


    for application in applications:

        status = str(
            application.get(
                "status",
                "Applied"
            )
        ).strip().lower()


        if status == "hired":

            counts["hired"] += 1

        elif status == "shortlisted":

            counts["shortlisted"] += 1

        elif status in [
            "under review",
            "under_review"
        ]:

            counts["under_review"] += 1

        elif status == "rejected":

            counts["rejected"] += 1

        else:

            counts["applied"] += 1


    return jsonify({

        "success": True,

        "counts": counts,

        "applications": applications
    })


# =========================================================
# POSTER APPLICATIONS
# =========================================================

@app.route(
    "/api/my-applicants",
    methods=["GET"]
)
@app.route(
    "/api/applicants",
    methods=["GET"]
)
@app.route(
    "/my-applicants",
    methods=["GET"]
)
@role_required("job_poster")
def my_applicants():

    data = load_data()

    poster = get_current_user(data)  # FIX: pass shared data

    results = []


    # =====================================================
    # IMPORTANT:
    # A poster can ONLY see applications belonging to jobs
    # posted by that poster.
    # =====================================================

    for application in data["applications"]:

        job = get_application_job(
            application,
            data
        )


        if not job:
            continue


        try:

            job_poster_id = int(
                job.get(
                    "poster_id",
                    0
                )
            )

        except (
            ValueError,
            TypeError
        ):

            continue


        if (
            job_poster_id
            !=
            int(poster["id"])
        ):

            continue


        applicant = get_user_by_id(
            application.get(
                "user_id"
            ),
            data
        )


        if not applicant:
            continue


        resume = get_resume_by_id(
            application.get(
                "resume_id"
            ),
            data
        )


        results.append({

            "application_id":
                application.get("id"),

            "status":
                application.get(
                    "status",
                    "Applied"
                ),

            "job": job,

            "applicant": {

                "id":
                    applicant.get("id"),

                "name":
                    application.get(
                        "applicant_name",
                        applicant.get(
                            "name",
                            ""
                        )
                    ),

                "email":
                    application.get(
                        "applicant_email",
                        applicant.get(
                            "email",
                            ""
                        )
                    ),

                "contact":
                    application.get(
                        "contact",
                        ""
                    ),

                "introduction":
                    application.get(
                        "introduction",
                        ""
                    )
            },

            "resume": resume,

            "resume_filename":
                resume.get(
                    "filename"
                )
                if resume
                else "",

            "resume_url":
                (
                    "/resumes/"
                    +
                    resume.get(
                        "filename"
                    )
                )
                if resume
                and resume.get(
                    "filename"
                )
                else "",

            "salary":
                application.get(
                    "salary",
                    ""
                ),

            "interview_date":
                application.get(
                    "interview_date",
                    ""
                ),

            "interview_time":
                application.get(
                    "interview_time",
                    ""
                ),

            "remarks":
                application.get(
                    "remarks",
                    ""
                ),

            "introduction":
                application.get(
                    "introduction",
                    ""
                )
        })


    return jsonify({

        "success": True,

        "applicants": results
    })


# =========================================================
# ONE JOB'S APPLICANTS
# =========================================================

@app.route(
    "/api/jobs/<int:job_id>/applicants",
    methods=["GET"]
)
@role_required("job_poster")
def job_applicants(job_id):

    data = load_data()

    poster = get_current_user(data)  # FIX: pass shared data

    job = get_job_by_id(
        job_id,
        data
    )


    if not job:

        return jsonify({
            "success": False,
            "message": "Job not found."
        }), 404


    try:

        if (
            int(
                job.get(
                    "poster_id",
                    0
                )
            )
            !=
            int(poster["id"])
        ):

            return jsonify({
                "success": False,
                "message": "You do not own this job."
            }), 403

    except (
        ValueError,
        TypeError
    ):

        return jsonify({
            "success": False,
            "message": "You do not own this job."
        }), 403


    applicants = []


    for application in data["applications"]:

        try:

            if (
                int(
                    application.get(
                        "job_id",
                        0
                    )
                )
                !=
                int(job_id)
            ):
                continue

        except (
            ValueError,
            TypeError
        ):
            continue


        applicant = get_user_by_id(
            application.get(
                "user_id"
            ),
            data
        )


        if not applicant:
            continue


        resume = get_resume_by_id(
            application.get(
                "resume_id"
            ),
            data
        )


        item = dict(
            application
        )

        item["job"] = job

        item["applicant"] = {

            "id":
                applicant.get(
                    "id"
                ),

            "name":
                application.get(
                    "applicant_name",
                    applicant.get(
                        "name",
                        ""
                    )
                ),

            "email":
                application.get(
                    "applicant_email",
                    applicant.get(
                        "email",
                        ""
                    )
                ),

            "contact":
                application.get(
                    "contact",
                    ""
                ),

            "introduction":
                application.get(
                    "introduction",
                    ""
                )
        }

        item["resume"] = resume

        applicants.append(
            item
        )


    return jsonify({

        "success": True,

        "job": job,

        "applicants": applicants
    })


# =========================================================
# RESUME UPLOAD
# =========================================================

@app.route(
    "/api/resumes/upload",
    methods=["POST"]
)
@app.route(
    "/api/resume/upload",
    methods=["POST"]
)
@role_required("job_seeker")
def upload_resume():

    data = load_data()

    user = get_current_user(data)  # FIX: pass shared data


    file = request.files.get(
        "resume"
    )

    skills = request.form.get(
        "skills",
        ""
    ).strip()

    introduction = request.form.get(
        "introduction",
        ""
    ).strip()


    if file is None:

        return jsonify({
            "success": False,
            "field": "resume",
            "message": "Please select your resume file."
        }), 400


    if not file.filename:

        return jsonify({
            "success": False,
            "field": "resume",
            "message": "Please select your resume file."
        }), 400


    if not allowed_file(
        file.filename
    ):

        return jsonify({
            "success": False,
            "field": "resume",
            "message": "Only PDF, DOC, and DOCX files are allowed."
        }), 400


    if not skills:

        return jsonify({
            "success": False,
            "field": "skills",
            "message": "Please enter your skills."
        }), 400


    if not introduction:

        return jsonify({
            "success": False,
            "field": "introduction",
            "message": "Please enter your professional introduction."
        }), 400


    extension = (
        file.filename
        .rsplit(".", 1)[1]
        .lower()
    )


    # -----------------------------------------------------
    # Each user's professional resume gets its own filename.
    # -----------------------------------------------------

    resume_id = next_id(
        data["resumes"]
    )


    filename = secure_filename(
        f"resume_{user['id']}_{resume_id}.{extension}"
    )


    filepath = os.path.join(
        RESUME_FOLDER,
        filename
    )


    try:

        file.save(
            filepath
        )

    except OSError:

        return jsonify({
            "success": False,
            "message": "Unable to save resume file."
        }), 500


    # -----------------------------------------------------
    # Remove/replace only THIS USER'S previous profile
    # resume records.
    #
    # Application resumes are kept because applications
    # must retain their original resume.
    # -----------------------------------------------------

    resume = {

        "id": resume_id,

        "user_id": user["id"],

        "filename": filename,

        "original_filename":
            secure_filename(
                file.filename
            ),

        "skills": skills,

        "introduction": introduction,

        "created_at":
            datetime.now().isoformat(),

        "profile_resume": True
    }


    data["resumes"].append(
        resume
    )

    save_data(data)


    return jsonify({

        "success": True,

        "message": "Resume uploaded successfully.",

        "resume": resume
    })


# =========================================================
# CANDIDATE RESUMES
# =========================================================

@app.route(
    "/api/resumes",
    methods=["GET"]
)
@app.route(
    "/api/candidates",
    methods=["GET"]
)
@app.route(
    "/candidates",
    methods=["GET"]
)
@role_required("job_poster")
def get_candidates():

    data = load_data()

    search = request.args.get(
        "search",
        ""
    ).strip().lower()


    results = []


    for resume in data["resumes"]:

        # -------------------------------------------------
        # Only profile resumes should appear in candidate
        # search. Application-specific resumes are private
        # to the related application.
        # -------------------------------------------------

        if (
            resume.get(
                "profile_resume",
                False
            )
            is not True
        ):
            continue


        skills = str(
            resume.get(
                "skills",
                ""
            )
        ).lower()

        introduction = str(
            resume.get(
                "introduction",
                ""
            )
        ).lower()


        candidate = get_user_by_id(
            resume.get(
                "user_id"
            ),
            data
        )


        if not candidate:
            continue


        name = str(
            candidate.get(
                "name",
                ""
            )
        ).lower()

        email = str(
            candidate.get(
                "email",
                ""
            )
        ).lower()


        if search:

            searchable = " ".join([
                skills,
                introduction,
                name,
                email
            ])

            if search not in searchable:
                continue


        results.append({

            "resume": resume,

            "user": {

                "id":
                    candidate.get(
                        "id"
                    ),

                "name":
                    candidate.get(
                        "name",
                        ""
                    ),

                "email":
                    candidate.get(
                        "email",
                        ""
                    )
            }
        })


    return jsonify({

        "success": True,

        "resumes": results,

        "candidates": results
    })


# =========================================================
# RESUME FILE
# =========================================================

@app.route(
    "/resumes/<path:filename>",
    methods=["GET"]
)
def serve_resume(filename):

    return send_from_directory(
        RESUME_FOLDER,
        filename,
        as_attachment=False
    )


# =========================================================
# NOTIFICATIONS
# =========================================================

@app.route(
    "/api/notifications",
    methods=["GET"]
)
@app.route(
    "/notifications",
    methods=["GET"]
)
@login_required
def get_notifications():

    user = get_current_user()

    # -----------------------------------------------------
    # CRITICAL:
    #
    # Notifications are read ONLY from the logged-in user's
    # own notifications list.
    #
    # No global notification list is used.
    # -----------------------------------------------------

    notifications = user.get(
        "notifications",
        []
    )


    if not isinstance(
        notifications,
        list
    ):
        notifications = []


    unread_count = 0


    for notification in notifications:

        if not notification.get(
            "read",
            False
        ):

            unread_count += 1


    return jsonify({

        "success": True,

        "notifications": notifications,

        "count": unread_count
    })


# =========================================================
# MARK NOTIFICATIONS READ
# =========================================================

@app.route(
    "/api/notifications/read",
    methods=["POST"]
)
@login_required
def mark_notifications_read():

    data = load_data()

    # FIX (critical): same class of bug as favorites — must
    # pass `data` so the notification dicts we mutate below
    # are literally the ones inside `data`, otherwise
    # save_data(data) writes back the old "unread" state.
    user = get_current_user(data)


    notifications = user.get(
        "notifications",
        []
    )


    if not isinstance(
        notifications,
        list
    ):

        user["notifications"] = []

    else:

        for notification in notifications:

            notification["read"] = True


    save_data(data)


    return jsonify({

        "success": True,

        "message": "Notifications marked as read."
    })


# =========================================================
# UPDATE APPLICATION STATUS
# =========================================================

@app.route(
    "/api/applications/<int:application_id>/status",
    methods=["POST"]
)
@role_required("job_poster")
def update_application_status(
    application_id
):

    data = load_data()

    poster = get_current_user(data)  # FIX: pass shared data

    incoming = request.get_json(
        silent=True
    )

    if incoming is None:
        incoming = request.form.to_dict()


    status = str(
        incoming.get(
            "status",
            ""
        )
    ).strip()

    salary = str(
        incoming.get(
            "salary",
            ""
        )
    ).strip()

    interview_date = str(
        incoming.get(
            "interview_date",
            ""
        )
    ).strip()

    interview_time = str(
        incoming.get(
            "interview_time",
            ""
        )
    ).strip()

    remarks = str(
        incoming.get(
            "remarks",
            ""
        )
    ).strip()


    allowed_statuses = [
        "Applied",
        "Under Review",
        "Shortlisted",
        "Rejected",
        "Hired"
    ]


    if status not in allowed_statuses:

        return jsonify({
            "success": False,
            "message": "Invalid application status."
        }), 400


    application = get_application_by_id(
        application_id,
        data
    )


    if not application:

        return jsonify({
            "success": False,
            "message": "Application not found."
        }), 404


    # -----------------------------------------------------
    # IMPORTANT:
    #
    # Find the job from active jobs first, then snapshot.
    # -----------------------------------------------------

    job = get_application_job(
        application,
        data
    )


    if not job:

        return jsonify({
            "success": False,
            "message": "The job connected to this application was not found."
        }), 404


    # -----------------------------------------------------
    # SECURITY:
    #
    # Only the poster who owns THIS job may update THIS
    # application.
    # -----------------------------------------------------

    try:

        job_poster_id = int(
            job.get(
                "poster_id",
                0
            )
        )

    except (
        ValueError,
        TypeError
    ):

        job_poster_id = 0


    if (
        job_poster_id
        !=
        int(poster["id"])
    ):

        return jsonify({
            "success": False,
            "message": "You cannot update this application."
        }), 403


    # =====================================================
    # VALIDATION
    # =====================================================

    if status == "Hired":

        if not salary:

            return jsonify({
                "success": False,
                "field": "salary",
                "message": "Salary is required when hiring a candidate."
            }), 400


    if status == "Shortlisted":

        if not interview_date:

            return jsonify({
                "success": False,
                "field": "interview_date",
                "message": "Interview date is required."
            }), 400


        if not interview_time:

            return jsonify({
                "success": False,
                "field": "interview_time",
                "message": "Interview time is required."
            }), 400


    if status == "Rejected":

        if not remarks:

            return jsonify({
                "success": False,
                "field": "remarks",
                "message": "Remarks are required when rejecting a candidate."
            }), 400


    if status == "Under Review":

        if not remarks:

            return jsonify({
                "success": False,
                "field": "remarks",
                "message": "Remarks are required."
            }), 400


    # =====================================================
    # UPDATE APPLICATION
    # =====================================================

    application["status"] = status

    application["salary"] = ""

    application["interview_date"] = ""

    application["interview_time"] = ""

    application["remarks"] = ""


    if status == "Hired":

        application["salary"] = salary

        application["remarks"] = remarks


    elif status == "Shortlisted":

        application["interview_date"] = (
            interview_date
        )

        application["interview_time"] = (
            interview_time
        )

        application["remarks"] = remarks


    elif status == "Rejected":

        application["remarks"] = remarks


    elif status == "Under Review":

        application["remarks"] = remarks


    # =====================================================
    # NOTIFY ONLY THE APPLICANT
    # =====================================================

    applicant = get_user_by_id(
        application.get(
            "user_id"
        ),
        data
    )


    if applicant:

        if not isinstance(
            applicant.get(
                "notifications"
            ),
            list
        ):

            applicant["notifications"] = []


        job_title = job.get(
            "title",
            "Job"
        )


        if status == "Hired":

            message = (
                f"Congratulations! You have been hired "
                f"for '{job_title}'. "
                f"Salary: {salary}."
            )


        elif status == "Shortlisted":

            message = (
                f"You have been shortlisted for "
                f"'{job_title}'. "
                f"Interview: {interview_date} "
                f"at {interview_time}."
            )


        elif status == "Rejected":

            message = (
                f"Your application for "
                f"'{job_title}' has been rejected. "
                f"Remarks: {remarks}"
            )


        elif status == "Under Review":

            message = (
                f"Your application for "
                f"'{job_title}' is now under review. "
                f"Remarks: {remarks}"
            )


        else:

            message = (
                f"Your application for "
                f"'{job_title}' has been updated."
            )


        applicant["notifications"].append({

            "id":
                next_id(
                    applicant["notifications"]
                ),

            "type":
                "application_status",

            "status":
                status,

            "message":
                message,

            "job_id":
                application.get(
                    "job_id"
                ),

            "application_id":
                application.get(
                    "id"
                ),

            "read":
                False,

            "created_at":
                datetime.now().isoformat()
        })


    save_data(data)


    return jsonify({

        "success": True,

        "message":
            f"Application marked as {status}.",

        "application":
            application
    })


# =========================================================
# DELETE JOB
# =========================================================

@app.route(
    "/api/jobs/<int:job_id>",
    methods=["DELETE"]
)
@role_required("job_poster")
def delete_job(job_id):

    data = load_data()

    poster = get_current_user(data)  # FIX: pass shared data

    job = get_job_by_id(
        job_id,
        data
    )


    if not job:

        return jsonify({
            "success": False,
            "message": "Job not found."
        }), 404


    try:

        if (
            int(
                job.get(
                    "poster_id",
                    0
                )
            )
            !=
            int(poster["id"])
        ):

            return jsonify({
                "success": False,
                "message": "You can only delete your own jobs."
            }), 403

    except (
        ValueError,
        TypeError
    ):

        return jsonify({
            "success": False,
            "message": "You can only delete your own jobs."
        }), 403


    # -----------------------------------------------------
    # NEVER delete applications.
    #
    # Save job snapshot first so application history
    # continues to work after job deletion.
    # -----------------------------------------------------

    for application in data["applications"]:

        try:

            if (
                int(
                    application.get(
                        "job_id",
                        0
                    )
                )
                ==
                int(job_id)
            ):

                application["job_snapshot"] = (
                    dict(job)
                )

        except (
            ValueError,
            TypeError
        ):
            continue


    # Remove only active job posting.

    data["jobs"] = [

        item

        for item in data["jobs"]

        if int(
            item.get(
                "id",
                0
            )
        )
        !=
        int(job_id)
    ]


    # -----------------------------------------------------
    # Remove deleted job from favorites.
    # -----------------------------------------------------

    for user in data["users"]:

        favorites = user.get(
            "favorites",
            []
        )

        cleaned = []


        for favorite in favorites:

            try:

                if (
                    int(favorite)
                    !=
                    int(job_id)
                ):

                    cleaned.append(
                        int(favorite)
                    )

            except (
                ValueError,
                TypeError
            ):
                continue


        user["favorites"] = cleaned


    save_data(data)


    return jsonify({

        "success": True,

        "message": "Job deleted successfully.",

        "deleted_job_id":
            int(job_id)
    })


# =========================================================
# ERROR HANDLERS
# =========================================================

@app.errorhandler(413)
def file_too_large(error):

    return jsonify({

        "success": False,

        "message":
            "File is too large. Maximum size is 10 MB."
    }), 413


@app.errorhandler(404)
def page_not_found(error):

    if request.path.startswith(
        "/api/"
    ):

        return jsonify({

            "success": False,

            "message":
                "API route not found.",

            "path":
                request.path
        }), 404


    return render_template(
        "index.html"
    )


@app.errorhandler(500)
def internal_error(error):

    return jsonify({

        "success": False,

        "message":
            "Internal server error."
    }), 500


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    print("")
    print(
        "=========================================="
    )
    print(
        "        JOBSPHERE JOB PORTAL"
    )
    print(
        "=========================================="
    )
    print(
        "Server starting..."
    )
    print(
        "Open: http://127.0.0.1:5000/"
    )
    print(
        "=========================================="
    )
    print("")


    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )