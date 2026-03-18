from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import MetaData
from datetime import datetime, date
from random import choice
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from collections import defaultdict
import os
from sqlalchemy import func

# Alembic-safe naming
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
metadata = MetaData(naming_convention=convention)

# App & DB
app = Flask(__name__)
app.secret_key = "super-secret-key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///time_spread.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app, metadata=metadata)
migrate = Migrate(app, db)

ALLOWED_EXTENSIONS = {
    "pdf",
    "png",
    "jpg",
    "jpeg",
    "gif",
    "txt",
    "py",
    "js",
    "html",
    "css",
}

# ---------------- Models ----------------


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(200), nullable=False)


class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    color = db.Column(db.String(20), default="#f97316")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    projects = db.relationship("Project", backref="group", cascade="all, delete-orphan")
    tasks = db.relationship("Task", backref="group", cascade="all, delete-orphan")
    notes = db.relationship("Note", backref="group", cascade="all, delete-orphan")
    resources = db.relationship(
        "Resource", backref="group", cascade="all, delete-orphan"
    )
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    __table_args__ = (
        db.UniqueConstraint("user_id", "name", name="uq_user_group_name"),
    )


class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    due_date = db.Column(db.DateTime)
    tasks = db.relationship(
        "Task", backref="project", lazy=True, cascade="all, delete-orphan"
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    group_id = db.Column(db.Integer, db.ForeignKey("group.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"))
    energy_required = db.Column(db.Integer, default=2)
    due_date = db.Column(db.DateTime)
    subtasks = db.relationship(
        "SubTask", backref="task", lazy=True, cascade="all, delete-orphan"
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    group_id = db.Column(db.Integer, db.ForeignKey("group.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


class SubTask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    is_done = db.Column(db.Boolean, default=False)
    task_id = db.Column(db.Integer, db.ForeignKey("task.id"))
    group_id = db.Column(db.Integer, db.ForeignKey("group.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


class TaskLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200))
    description = db.Column(db.Text)
    energy_required = db.Column(db.Integer)
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)

    project_id = db.Column(db.Integer, db.ForeignKey("project.id"))
    project = db.relationship("Project")
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100))
    content = db.Column(db.Text, default="")
    group_id = db.Column(db.Integer, db.ForeignKey("group.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


class Resource(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    type = db.Column(db.String(20), nullable=False)
    url = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    group_id = db.Column(db.Integer, db.ForeignKey("group.id"), nullable=False)

    files = db.relationship("ResourceFile", backref="resource", lazy=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


class ResourceFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    resource_id = db.Column(db.Integer, db.ForeignKey("resource.id"), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_name = db.Column(db.String(255), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


class Quote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    author = db.Column(db.String(100))

@app.route("/")
def landing():
    return render_template("landing.html")

# ---------------- Auth ----------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        if password != confirm_password:
            return render_template(
                "signup.html", error="password not matching confirm passwprd"
            )

        if not username or not password:
            return render_template(
                "signup.html", error="Username and password required"
            )

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return render_template("signup.html", error="Username already taken")

        password_hash = generate_password_hash(password)
        new_user = User(username=username, email=email, password_hash=password_hash)
        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for("login"))
    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        # Look up the user in the database
        user = User.query.filter_by(username=username).first()
        if not user:
            return render_template("signup.html", error="Invalid username or password")

        # Verify password using the hashed password
        if not check_password_hash(user.password_hash, password):
            return render_template("index.html", error="Invalid username or password")

        # Successful login
        session["user_id"] = user.id
        session["username"] = user.username

        get_inbox_group_for_user(user.id)

        return redirect(url_for("dashboard"))

    # GET request
    return render_template("index.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------- Pages ----------------


@app.route("/task_manager")
def task_manager():
    if "user_id" not in session:
        return redirect(url_for("login"))

    tasks = Task.query.order_by(Task.id.desc()).all()
    projects = Project.query.all()
    return render_template("task_manager.html", tasks=tasks, projects=projects)


@app.route("/notes_manager")
def notes_manager():
    if "user_id" not in session:
        return redirect(url_for("login"))

    notes = Note.query.order_by(Note.id.desc()).all()
    return render_template("notes_manager.html", notes=notes)


@app.route("/projects")
def projects():
    if "user_id" not in session:
        return redirect(url_for("login"))

    projects = Project.query.order_by(Project.id.desc()).all()
    return render_template("project_manager.html", projects=projects)


@app.route("/groups", methods=["GET", "POST"])
def groups():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    # Get or create Inbox group for the user
    inbox_group = get_inbox_group_for_user(user_id)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        color = request.form.get("color", "#f97316")

        # Prevent creating another Inbox
        if not name or name.lower() == "inbox":
            return redirect(url_for("groups"))

        new_group = Group(
            name=name, description=description, color=color, user_id=user_id
        )
        db.session.add(new_group)
        db.session.commit()
        return redirect(url_for("groups"))

    # Get all user groups except Inbox
    groups = Group.query.filter_by(user_id=user_id).filter(Group.name != "Inbox").all()

    # Compute counts for Inbox
    inbox_counts = {
        "task_count": Task.query.filter_by(group_id=inbox_group.id).count(),
        "note_count": Note.query.filter_by(group_id=inbox_group.id).count(),
        "project_count": Project.query.filter_by(group_id=inbox_group.id).count(),
        "resource_count": Resource.query.filter_by(group_id=inbox_group.id).count(),
    }

    # Compute counts for all other groups
    for g in groups:
        g.task_count = Task.query.filter_by(group_id=g.id).count()
        g.note_count = Note.query.filter_by(group_id=g.id).count()
        g.project_count = Project.query.filter_by(group_id=g.id).count()
        g.resource_count = Resource.query.filter_by(group_id=g.id).count()

    return render_template(
        "group.html",
        inbox_group=inbox_group,
        groups=groups,
        **inbox_counts,  # task_count, note_count, project_count, resource_count for Inbox
    )


@app.route("/group/<int:group_id>", methods=["GET", "POST"])
def group_tasks(group_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    user_id = session.get("user_id")
    inbox_group = get_inbox_group_for_user(session["user_id"])
    group = Group.query.filter_by(
        id=group_id, user_id=session["user_id"]
    ).first_or_404()

    if request.method == "POST":
        name = request.form.get("title")
        description = request.form.get("description")
        energy_required = request.form.get("energy_required")
        due_date = request.form.get("due_date")

        if not name:
            return redirect(url_for("group_tasks", group_id=group_id))

        task = Task(
            name=name,
            description=description,
            energy_required=int(energy_required) if energy_required else 2,
            due_date=datetime.strptime(due_date, "%Y-%m-%d") if due_date else None,
            group_id=group_id,
            user_id=user_id,
        )

        db.session.add(task)
        db.session.commit()

        return redirect(url_for("group_tasks", group_id=group_id))

    tasks = Task.query.filter_by(group_id=group_id).all()
    groups = Group.query.filter_by(user_id=user_id).all()

    return render_template(
        "group_tasks.html",
        groups=groups,
        group=group,
        tasks=tasks,
        inbox_group=inbox_group,
        current="group_tasks",
        task_count=len(group.tasks),
        note_count=len(group.notes),
        project_count=len(group.projects),
        resource_count=len(group.resources),
    )


@app.route("/group/<int:group_id>/notes", methods=["GET", "POST"])
def group_notes(group_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    user_id = session.get("user_id")
    group = Group.query.filter_by(
        id=group_id, user_id=session["user_id"]
    ).first_or_404()

    if request.method == "POST":
        title = request.form.get("title")
        content = request.form.get("content")

        if not title:
            return redirect(url_for("group_tasks", group_id=group_id))

        note = Note(title=title, content=content, group_id=group_id, user_id=user_id)

        db.session.add(note)
        db.session.commit()

        return redirect(url_for("group_notes", group_id=group_id))

    notes = Note.query.filter_by(group_id=group_id).all()
    return render_template(
        "group_notes.html",
        group=group,
        notes=notes,
        current="group_notes",
        task_count=len(group.tasks),
        note_count=len(group.notes),
        project_count=len(group.projects),
        resource_count=len(group.resources),
    )


@app.route("/group/<int:group_id>/projects", methods=["GET", "POST"])
def group_projects(group_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    user_id = session.get("user_id")
    group = Group.query.filter_by(
        id=group_id, user_id=session["user_id"]
    ).first_or_404()

    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")
        deadline_str = request.form.get("deadline")
        deadline = datetime.strptime(deadline_str, "%Y-%m-%d") if deadline_str else None

        project = Project(
            title=title,
            description=description,
            due_date=deadline,
            group_id=group.id,
            user_id=user_id,
        )
        db.session.add(project)
        db.session.flush()

        task_titles = request.form.getlist("task_titles[]")
        task_energy = request.form.getlist("task_energy[]")

        for i, task_name in enumerate(task_titles):
            if not task_name.strip():
                continue
            energy = task_energy[i] if i < len(task_energy) else "MEDIUM"
            energy_value = {"LOW": 1, "MED": 2, "MEDIUM": 2, "HIGH": 3}.get(
                energy.upper(), 2
            )

            task = Task(
                name=task_name.strip(),
                energy_required=energy_value,
                project_id=project.id,
                group_id=group.id,
                user_id=user_id,
            )
            db.session.add(task)

        db.session.commit()
        return redirect(url_for("group_projects", group_id=group.id))

    projects = Project.query.filter_by(group_id=group.id).all()

    return render_template(
        "group_projects.html",
        group=group,
        projects=projects,
        current="group_projects",
        task_count=len(group.tasks),
        note_count=len(group.notes),
        project_count=len(group.projects),
        resource_count=len(group.resources),
    )


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/group_resources/<int:group_id>/resources", methods=["GET", "POST"])
def group_resources(group_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    user_id = session.get("user_id")

    group = Group.query.filter_by(
        id=group_id, user_id=session["user_id"]
    ).first_or_404()

    error = None

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        link = request.form.get("link", "").strip()
        files = request.files.getlist("files[]")

        if not title:
            error = "Title is required."
        elif not link and (not files or all(f.filename == "" for f in files)):
            error = "Provide a link or at least one file."
        else:
            # If there is a link, save as a link resource
            if link:
                resource = Resource(
                    title=title,
                    type="link",
                    url=link,
                    group_id=group.id,
                    user_id=user_id,
                )
                db.session.add(resource)

            # If there are files, save as a file resource
            upload_folder = os.path.join(
                "static", "uploads", "resources", str(group.id)
            )
            os.makedirs(upload_folder, exist_ok=True)

            for f in files:
                if f.filename == "" or not allowed_file(f.filename):
                    continue
                resource = Resource(title=title, type="file", group_id=group.id)
                db.session.add(resource)
                db.session.flush()  # to get resource.id

                filename = secure_filename(f.filename)
                unique_filename = f"{resource.id}_{filename}"
                save_path = os.path.join(upload_folder, unique_filename)
                f.save(save_path)

                resource_file = ResourceFile(
                    resource_id=resource.id,
                    filename=unique_filename,
                    original_name=f.filename,
                )
                db.session.add(resource_file)

            db.session.commit()
            return redirect(url_for("group_resources", group_id=group_id))

    # GET request or form error
    resources = Resource.query.filter_by(group_id=group.id).all()
    return render_template(
        "group_resources.html",
        group=group,
        resources=resources,
        error=error,
        current="group_resources",
        task_count=len(group.tasks),
        note_count=len(group.notes),
        project_count=len(group.projects),
        resource_count=len(group.resources),
    )


@app.route("/logs")
def logs():
    if "user_id" not in session:
        return redirect(url_for("login"))

    logs = TaskLog.query.order_by(TaskLog.completed_at.desc()).all()

    logs_by_day = defaultdict(list)

    for log in logs:
        day = log.completed_at.date()  # extract date only
        logs_by_day[day].append(log)

    sorted_days = sorted(logs_by_day.keys(), reverse=True)

    return render_template(
        "logs.html", logs_by_day=logs_by_day, sorted_days=sorted_days
    )


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    group_id = request.args.get("group_id", type=int)

    selected_energy = session.get("current_energy", 2)
    
    if group_id:
        tasks = Task.query.filter_by(user_id=user_id, group_id=group_id).all()
    else:
        tasks = Task.query.filter_by(user_id=user_id).all()

    # Sort tasks: energy match first, then due_date (None = far future), then created_at
    def task_sort_key(task):
        energy_priority = 0 if task.energy_required == selected_energy else 1
        due = task.due_date if task.due_date else datetime.max
        created = task.created_at if task.created_at else datetime.max
        return (energy_priority, due, created)

    tasks_sorted = sorted(tasks, key=task_sort_key)

    current_task = tasks_sorted[0] if tasks_sorted else None
    next_tasks = tasks_sorted[1:6] if len(tasks_sorted) > 1 else []

    # -------- ENERGY PROGRESS --------
    today = date.today()
    today_logs = TaskLog.query.filter(
        TaskLog.user_id == user_id, db.func.date(TaskLog.completed_at) == today
    ).all()
    energy_done = sum(t.energy_required or 0 for t in today_logs)

    GAMING_REQ, WATCHING_REQ, FREE_REQ = 6, 12, 18

    def progress(val, req):
        return min(100, int((val / req) * 100)) if req else 0

    leisure = {
        "gaming": {
            "current": energy_done,
            "required": GAMING_REQ,
            "percent": progress(energy_done, GAMING_REQ),
            "unlocked": energy_done >= GAMING_REQ,
        },
        "watching": {
            "current": energy_done,
            "required": WATCHING_REQ,
            "percent": progress(energy_done, WATCHING_REQ),
            "unlocked": energy_done >= WATCHING_REQ,
        },
        "free": {
            "current": energy_done,
            "required": FREE_REQ,
            "percent": progress(energy_done, FREE_REQ),
            "unlocked": energy_done >= FREE_REQ,
        },
    }

    # Recommendation logic
    if energy_done < GAMING_REQ:
        recommendation = "Start with small wins. Low-effort tasks will build momentum."
    elif energy_done < WATCHING_REQ:
        recommendation = "You are warmed up. Medium-focus tasks are ideal now."
    elif energy_done < FREE_REQ:
        recommendation = "Push through one more serious task to fully unlock your day."
    else:
        recommendation = "You’ve earned your freedom. Use it well, don’t waste it."

    # Random quote
    quotes = Quote.query.all()
    random_quote = choice(quotes) if quotes else None

    # Inbox for this user
    inbox_group = get_inbox_group_for_user(user_id)

    # All groups for this user (including Inbox)
    groups = Group.query.filter_by(user_id=user_id).all()

    return render_template(
        "dashboard.html",
        current_task=current_task,
        next_tasks=next_tasks,
        energy_done=energy_done,
        leisure=leisure,
        recommendation=recommendation,
        quote=random_quote,
        current_energy=selected_energy,
        inbox_group=inbox_group,
        groups=groups,
    )


def get_inbox_group_for_user(user_id):
    inbox = Group.query.filter_by(user_id=user_id, name="Inbox").first()

    if not inbox:
        inbox = Group(
            name="Inbox", description="Default inbox", color="#3b82f6", user_id=user_id
        )
        db.session.add(inbox)
        db.session.commit()

    return inbox


# ---------------- Tasks ----------------
@app.route("/tasks/save", methods=["POST"])
def save_task():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    task_id = request.form.get("task_id")
    name = request.form.get("task_name")
    desc = request.form.get("task_description")
    energy = int(request.form.get("energy_required", 2))
    due_date_str = request.form.get("due_date")
    group_id = request.form.get("group_id")  # <-- fix here

    due_date = (
        datetime.strptime(due_date_str, "%Y-%m-%d")
        if due_date_str
        else None
    )

    # ---------- resolve group ----------
    if group_id:
        group = Group.query.filter_by(
            id=int(group_id),
            user_id=user_id
        ).first()
        resolved_group_id = group.id if group else get_inbox_group_for_user(user_id).id
    else:
        resolved_group_id = get_inbox_group_for_user(user_id).id

    # ---------- create / edit ----------
    if task_id == "new":
        task = Task(
            name=name,
            description=desc,
            energy_required=energy,
            due_date=due_date,
            group_id=resolved_group_id,
            user_id=user_id,
        )
        db.session.add(task)
    else:
        task = Task.query.filter_by(
            id=int(task_id),
            user_id=user_id
        ).first_or_404()

        task.name = name
        task.description = desc
        task.energy_required = energy
        task.due_date = due_date
        task.group_id = resolved_group_id

    db.session.commit()
    return redirect(url_for("group_tasks", group_id=resolved_group_id))

@app.route("/tasks/mark_done/<int:task_id>", methods=["POST"])
def mark_task_done(task_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    task = Task.query.filter_by(id=task_id, user_id=user_id).first_or_404()

    log = TaskLog(
        name=task.name,
        description=task.description,
        energy_required=task.energy_required,
        project_id=task.project_id,
        user_id=user_id,
    )

    db.session.add(log)
    db.session.delete(task)
    db.session.commit()

    return redirect(url_for("dashboard"))


# ---------------- Notes ----------------


@app.route("/notes/save", methods=["POST"])
def save_note():
    if "user_id" not in session:
        return redirect(url_for("login"))
    user_id = session.get("user_id")

    note_id = request.form.get("note_id")
    title = request.form.get("title")
    content = request.form.get("content", "")

    inbox = get_inbox_group_for_user(session["user_id"])

    if note_id == "new" or not note_id:
        note = Note(title=title, content=content, group_id=inbox.id, user_id=user_id)
        db.session.add(note)
    else:
        note = Note.query.get_or_404(note_id)
        note.title = title
        note.content = content

    db.session.commit()
    return jsonify({"success": True})


# ---------------- Energy ----------------


@app.route("/set_energy/<int:level>", methods=["POST"])
def set_energy(level):
    if level not in [1, 2, 3]:
        return jsonify({"success": False}), 400
    session["current_energy"] = level
    return jsonify({"success": True})


# ---------------- Projects ----------------


@app.route("/projects/save", methods=["POST"])
def save_project():
    if "user_id" not in session:
        return redirect(url_for("login"))
    user_id = session.get("user_id")

    data = request.get_json()
    project_id = data.get("project_id")
    title = data.get("title")
    description = data.get("description")
    due_date_str = data.get("due_date")
    tasks_data = data.get("tasks", [])
    due_date = datetime.strptime(due_date_str, "%Y-%m-%d") if due_date_str else None

    inbox = get_inbox_group_for_user(session["user_id"])

    if project_id == "new":
        project = Project(
            title=title,
            description=description,
            due_date=due_date,
            group_id=inbox.id,
            user_id=user_id,
        )
        db.session.add(project)
        db.session.flush()
    else:
        project = Project.query.get_or_404(project_id)
        project.title = title
        project.description = description
        project.due_date = due_date

    for t in tasks_data:
        task_name = t.get("name")
        delete_flag = t.get("delete", False)

        existing_task = Task.query.filter_by(
            project_id=project.id, name=task_name
        ).first()

        if delete_flag:
            if existing_task:
                log = TaskLog(
                    name=existing_task.name,
                    description=existing_task.description,
                    energy_required=existing_task.energy_required,
                    user_id=user_id,
                )
                db.session.add(log)
                db.session.delete(existing_task)
        else:
            if not existing_task:
                new_task = Task(
                    name=task_name,
                    project_id=project.id,
                    group_id=inbox.id,
                    user_id=user_id,
                )
                db.session.add(new_task)

    db.session.commit()
    return jsonify({"success": True})


# ---------------- Delete ----------------
# ---------------- Tasks ----------------
@app.route("/tasks/delete/<int:task_id>", methods=["POST"])
def delete_task(task_id):
    if "user_id" not in session:
        return jsonify({"success": False, "error": "Not logged in"}), 401
    user_id = session["user_id"]

    task = Task.query.get_or_404(task_id)
    if task.user_id != user_id:
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    db.session.delete(task)
    db.session.commit()
    return jsonify({"success": True})


# ---------------- Notes ----------------
@app.route("/notes/delete/<int:note_id>", methods=["POST"])
def delete_note(note_id):
    if "user_id" not in session:
        return jsonify({"success": False, "error": "Not logged in"}), 401
    user_id = session["user_id"]

    note = Note.query.get_or_404(note_id)
    if note.user_id != user_id:
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    db.session.delete(note)
    db.session.commit()
    return jsonify({"success": True})


# ---------------- Projects ----------------
@app.route("/projects/delete/<int:project_id>", methods=["POST"])
def delete_project(project_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    user_id = session.get("user_id")

    project = Project.query.get_or_404(project_id)
    if project.user_id != user_id:
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    for task in project.tasks:
        log = TaskLog(
            name=task.name,
            description=task.description,
            energy_required=task.energy_required,
            project_id=project.id,
            user_id=user_id,
        )
        db.session.add(log)
    db.session.delete(project)
    db.session.commit()
    return jsonify({"success": True})


@app.route("/logs/repeat/<int:log_id>", methods=["POST"])
def repeat_task(log_id):
    if "user_id" not in session:
        return jsonify({"success": False}), 401
    user_id = session.get("user_id")

    log = TaskLog.query.get_or_404(log_id)

    new_task = Task(
        name=log.name,
        description=log.description,
        energy_required=log.energy_required,
        project_id=log.project_id,
        group_id=get_inbox_group_for_user(session["user_id"]).id,
        user_id=user_id,
    )

    db.session.add(new_task)
    db.session.commit()

    return redirect(url_for("logs"))


# ---------------- Run ----------------

if __name__ == "__main__":
    app.run(debug=True)
