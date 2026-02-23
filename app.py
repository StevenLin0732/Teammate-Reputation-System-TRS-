from flask import (
    Flask,
    request,
    jsonify,
    render_template,
    redirect,
    url_for,
    session,
    flash,
)
from flask_cors import CORS
import os
import secrets
from datetime import datetime
from sqlalchemy import text
from werkzeug.security import generate_password_hash, check_password_hash
import smtplib
from email.message import EmailMessage

from extensions import db

app = Flask(__name__, template_folder="templates")
CORS(
    app,
    supports_credentials=True,
    origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(
    basedir, "teamrank.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or secrets.token_hex(16)

db.init_app(app)

with app.app_context():
    # import models so tables are registered
    from models import User, Lobby, Team, Submission, Rating, JoinRequest

    db.create_all()

    if User.query.first() is None:
        from seed_db import seed_users

        seed_users()


def _sqlite_column_exists(table_name: str, column_name: str) -> bool:
    rows = db.session.execute(text(f"PRAGMA table_info({table_name})")).all()
    return any(r[1] == column_name for r in rows)


def _sqlite_add_column_if_missing(
    table_name: str, column_name: str, column_def_sql: str
) -> None:
    if _sqlite_column_exists(table_name, column_name):
        return
    db.session.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_def_sql}"))
    db.session.commit()


with app.app_context():
    # Minimal schema evolution for SQLite (no migration tool in this demo)
    _sqlite_add_column_if_missing("lobby", "finished", "finished BOOLEAN DEFAULT 0")
    _sqlite_add_column_if_missing("lobby", "finished_at", "finished_at DATETIME")
    _sqlite_add_column_if_missing("submission", "submitter_id", "submitter_id INTEGER")
    _sqlite_add_column_if_missing("user", "password_hash", "password_hash TEXT")


def get_current_user():
    from models import User

    user_id = session.get("user_id")
    if not user_id:
        return None
    return User.query.get(user_id)


def _send_email(subject: str, to_email: str, body: str):
    # Use SMTP settings if configured; otherwise log to console
    smtp_host = app.config.get("SMTP_HOST")
    smtp_port = app.config.get("SMTP_PORT") or 25
    smtp_user = app.config.get("SMTP_USER")
    smtp_pass = app.config.get("SMTP_PASS")
    mail_from = app.config.get("MAIL_FROM") or "noreply@example.com"

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = mail_from
    msg["To"] = to_email
    msg.set_content(body)

    if not smtp_host:
        # fallback: print to console
        print("--- EMAIL (fallback) ---")
        print("To:", to_email)
        print("Subject:", subject)
        print(body)
        print("--- END EMAIL ---")
        return

    try:
        s = smtplib.SMTP(smtp_host, int(smtp_port))
        s.ehlo()
        if smtp_user and smtp_pass:
            s.starttls()
            s.login(smtp_user, smtp_pass)
        s.send_message(msg)
        s.quit()
    except Exception as e:
        print("Failed to send email:", e)


@app.context_processor
def inject_current_user():
    return {"current_user": get_current_user()}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    from models import User

    if request.method == "GET":
        users = User.query.order_by(User.name.asc()).all()
        return render_template("login.html", users=users)

    if request.method == "POST":
        # Email/password authentication
        email = (request.form.get("email") or "").strip()
        password = request.form.get("password") or ""
        users = User.query.order_by(User.name.asc()).all()

        if not email or not password:
            flash("Email and password are required.", "warning")
            return render_template("login.html", users=users)

        user = User.query.filter_by(email=email).first()
        if not user or not getattr(user, "password_hash", None):
            flash("Invalid credentials.", "danger")
            return render_template("login.html", users=users)

        if not check_password_hash(user.password_hash, password):
            flash("Invalid credentials.", "danger")
            return render_template("login.html", users=users)

        session["user_id"] = user.id
        flash(f"Logged in as {user.name}.", "success")
        next_url = request.args.get("next")
        return redirect(next_url or url_for("me"))


@app.route("/logout", methods=["POST"])
def logout():
    session.pop("user_id", None)
    flash("Logged out.", "secondary")
    return redirect(url_for("index"))


@app.route("/register", methods=["GET", "POST"])
def register():
    from models import User

    if request.method == "POST":
        name = (request.form.get("name") or "").strip() or "Anonymous"
        email = (request.form.get("email") or "").strip()
        password = request.form.get("password") or ""
        major = (request.form.get("major") or "").strip() or None
        year = (request.form.get("year") or "").strip() or None
        bio = (request.form.get("bio") or "").strip() or None
        contact = (request.form.get("contact") or "").strip() or None
        phone = (request.form.get("phone") or "").strip() or None

        if not email or not email.lower().endswith("@duke.edu"):
            flash("Email must end with @duke.edu", "danger")
            return redirect(url_for("register"))
        if not password or len(password) < 6:
            flash("Password is required (min 6 characters).", "warning")
            return redirect(url_for("register"))

        existing = User.query.filter_by(email=email).first()
        if existing:
            flash("An account with that email already exists. Please login.", "warning")
            return redirect(url_for("login"))

        user = User(
            name=name,
            email=email,
            major=major,
            year=year,
            bio=bio,
            contact=contact,
            phone=phone,
            password_hash=generate_password_hash(password),
        )
        db.session.add(user)
        db.session.commit()
        session["user_id"] = user.id
        flash("Account created and logged in.", "success")
        return redirect(url_for("me"))

    return render_template("register.html")


@app.route("/me")
def me():
    user = get_current_user()
    if not user:
        return redirect(url_for("login", next=url_for("me")))
    return redirect(url_for("user_profile", user_id=user.id))


@app.route("/users")
def users_page():
    from models import User

    users = User.query.order_by(User.name.asc()).all()
    rep_by_id = {u.id: u.reputation() for u in users}
    return render_template("users.html", users=users, rep_by_id=rep_by_id)


@app.route("/users/<int:user_id>", methods=["GET", "POST"])
def user_profile(user_id):
    from models import User, Lobby, Team, TeamMember, Rating

    user = User.query.get_or_404(user_id)
    viewer = get_current_user()
    can_edit = viewer is not None and viewer.id == user.id

    if request.method == "POST":
        if not can_edit:
            flash("You can only edit your own profile.", "danger")
            return redirect(url_for("user_profile", user_id=user.id))

        # Single-field update (used by inline-edit modal)
        field = (request.form.get("field") or "").strip()
        if field:
            value = (request.form.get("value") or "").strip()
            allowed = {"name", "major", "year", "bio", "contact", "phone", "email"}
            if field not in allowed:
                flash("Invalid field.", "danger")
                return redirect(url_for("user_profile", user_id=user.id))
            if field == "name":
                if not value:
                    flash("Name cannot be empty.", "warning")
                    return redirect(url_for("user_profile", user_id=user.id))
                user.name = value
            else:
                setattr(user, field, value or None)
        else:
            # Full-form update (legacy)
            if "name" in request.form:
                user.name = (request.form.get("name") or user.name).strip() or user.name
            if "major" in request.form:
                user.major = (request.form.get("major") or "").strip() or None
            if "year" in request.form:
                user.year = (request.form.get("year") or "").strip() or None
            if "bio" in request.form:
                user.bio = (request.form.get("bio") or "").strip() or None
            if "contact" in request.form:
                user.contact = (request.form.get("contact") or "").strip() or None
            if "phone" in request.form:
                user.phone = (request.form.get("phone") or "").strip() or None
            if "email" in request.form:
                user.email = (request.form.get("email") or "").strip() or None

        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("user_profile", user_id=user.id))

    history = []
    lobby_ids = (
        db.session.query(Team.lobby_id)
        .join(TeamMember, TeamMember.team_id == Team.id)
        .filter(TeamMember.user_id == user.id)
        .distinct()
        .all()
    )
    ids = [x[0] for x in lobby_ids]
    history_lobbies = (
        (
            Lobby.query.filter(Lobby.id.in_(ids), Lobby.finished == True)
            .order_by(Lobby.finished_at.desc().nullslast(), Lobby.created_at.desc())
            .all()
        )
        if ids
        else []
    )

    for lobby in history_lobbies:
        # ratings received by this user for this lobby
        ratings = (
            db.session.query(Rating)
            .join(Team, Rating.team_id == Team.id)
            .filter(Team.lobby_id == lobby.id)
            .filter(Rating.target_user_id == user.id)
            .all()
        )
        if ratings:
            contribution_avg = round(
                sum(r.contribution or 0 for r in ratings) / len(ratings), 2
            )
            communication_avg = round(
                sum(r.communication or 0 for r in ratings) / len(ratings), 2
            )
            would_work_again_ratio = sum(
                1 for r in ratings if r.would_work_again
            ) / len(ratings)
        else:
            contribution_avg = 0
            communication_avg = 0
            would_work_again_ratio = None
        history.append(
            {
                "lobby": lobby,
                "rating_count": len(ratings),
                "contribution_avg": contribution_avg,
                "communication_avg": communication_avg,
                "would_work_again_ratio": would_work_again_ratio,
            }
        )

    overall_rep = user.reputation()
    return render_template(
        "profile.html",
        user=user,
        can_edit=can_edit,
        history=history,
        overall_rep=overall_rep,
    )


@app.route("/lobbies")
def lobbies_page():
    from models import Lobby, Team

    qs = Lobby.query.order_by(Lobby.created_at.desc()).all()
    lobbies = []
    viewer = get_current_user()
    for q in qs:
        team = Team.query.filter_by(lobby_id=q.id).first()
        participant_count = len(team.members) if team else 0
        d = q.to_dict()
        d["participant_count"] = participant_count
        d["team_locked"] = bool(team.locked) if team else False

        role = None
        if viewer:
            if q.leader_id and viewer.id == q.leader_id:
                role = "Leader"
            elif team and any(tm.user_id == viewer.id for tm in team.members):
                role = "Member"
        d["role"] = role
        lobbies.append(d)
    return render_template("lobbies.html", lobbies=lobbies)


@app.route("/lobbies/<int:lobby_id>", methods=["GET", "POST"])
def lobby_detail(lobby_id):
    from models import Lobby, Team, User, Rating
    from models import Invitation

    lobby = Lobby.query.get_or_404(lobby_id)
    team = Team.query.filter_by(lobby_id=lobby.id).first()
    leader = User.query.get(lobby.leader_id) if lobby.leader_id else None

    viewer = get_current_user()
    is_leader = (
        viewer is not None
        and lobby.leader_id is not None
        and viewer.id == lobby.leader_id
    )

    members = []
    if team:
        for tm in team.members:
            u = User.query.get(tm.user_id)
            if u:
                members.append(u)

    is_member = False
    if viewer and team:
        is_member = any(tm.user_id == viewer.id for tm in team.members)

    submissions = []
    if team:
        from models import Submission

        for s in team.submissions:
            submitter = (
                User.query.get(s.submitter_id)
                if getattr(s, "submitter_id", None)
                else None
            )
            submissions.append({"submission": s, "submitter": submitter})
        submissions.sort(
            key=lambda x: (x["submission"].created_at or datetime.min), reverse=True
        )

    teammates = []
    if viewer:
        teammates = [m for m in members if m.id != viewer.id]

    ratings = []
    rating_by_pair = {}
    viewer_ratings_by_target = {}
    avg_by_target = {}
    if team:
        ratings = Rating.query.filter_by(team_id=team.id).all()
        for r in ratings:
            rating_by_pair[(r.target_user_id, r.rater_id)] = r
            if viewer and r.rater_id == viewer.id:
                viewer_ratings_by_target[r.target_user_id] = r
        for m in members:
            rs = [r for r in ratings if r.target_user_id == m.id]
            if rs:
                avg_by_target[m.id] = {
                    "contribution": round(
                        sum(r.contribution or 0 for r in rs) / len(rs), 2
                    ),
                    "communication": round(
                        sum(r.communication or 0 for r in rs) / len(rs), 2
                    ),
                    "count": len(rs),
                }
            else:
                avg_by_target[m.id] = {
                    "contribution": 0,
                    "communication": 0,
                    "count": 0,
                }

    if request.method == "POST":
        if not is_leader:
            flash("Only the lobby leader can modify lobby details.", "danger")
            return redirect(url_for("lobby_detail", lobby_id=lobby.id))

        action = (request.form.get("action") or "save").strip()
        if action == "lock_team":
            if not team:
                flash("No team exists for this lobby.", "danger")
                return redirect(url_for("lobby_detail", lobby_id=lobby.id))
            team.locked = True
            db.session.commit()
            flash("Team locked.", "success")
            return redirect(url_for("lobby_detail", lobby_id=lobby.id))

        if action == "finish_contest":
            lobby.finished = True
            lobby.finished_at = datetime.utcnow()
            db.session.commit()
            flash(
                "Contest marked as finished. Team members can now submit proof and ratings.",
                "success",
            )
            return redirect(url_for("lobby_detail", lobby_id=lobby.id))

        # default: save lobby fields
        title = (request.form.get("title") or "").strip()
        contest_link = (request.form.get("contest_link") or "").strip() or None

        if not title:
            flash("Title is required.", "warning")
            return redirect(url_for("lobby_detail", lobby_id=lobby.id))

        lobby.title = title
        lobby.contest_link = contest_link
        db.session.commit()
        flash("Lobby updated.", "success")
        return redirect(url_for("lobby_detail", lobby_id=lobby.id))

    return render_template(
        "lobby_detail.html",
        lobby=lobby,
        team=team,
        leader=leader,
        members=members,
        is_leader=is_leader,
        is_member=is_member,
        submissions=submissions,
        teammates=teammates,
        ratings=ratings,
        rating_by_pair=rating_by_pair,
        viewer_ratings_by_target=viewer_ratings_by_target,
        avg_by_target=avg_by_target,
        invites=Invitation.query.filter_by(team_id=team.id).all() if team else [],
    )


@app.route(
    "/lobbies/<int:lobby_id>/submissions/<int:submission_id>/delete", methods=["POST"]
)
def delete_proof_page(lobby_id, submission_id):
    from models import Lobby, Team, Submission

    user = get_current_user()
    if not user:
        return redirect(
            url_for("login", next=url_for("lobby_detail", lobby_id=lobby_id))
        )

    lobby = Lobby.query.get_or_404(lobby_id)
    team = Team.query.filter_by(lobby_id=lobby.id).first()
    if not team:
        flash("Team not found for this lobby.", "danger")
        return redirect(url_for("lobby_detail", lobby_id=lobby.id))

    submission = Submission.query.get_or_404(submission_id)
    if submission.team_id != team.id:
        flash("Invalid submission.", "danger")
        return redirect(url_for("lobby_detail", lobby_id=lobby.id))
    if submission.submitter_id != user.id:
        flash("You can only delete your own proof.", "danger")
        return redirect(url_for("lobby_detail", lobby_id=lobby.id))

    db.session.delete(submission)
    db.session.commit()
    flash("Proof deleted.", "secondary")
    return redirect(url_for("lobby_detail", lobby_id=lobby.id))


@app.route("/lobbies/<int:lobby_id>/submit", methods=["POST"])
def submit_proof_page(lobby_id):
    from models import Lobby, Team, Submission

    user = get_current_user()
    if not user:
        return redirect(
            url_for("login", next=url_for("lobby_detail", lobby_id=lobby_id))
        )

    lobby = Lobby.query.get_or_404(lobby_id)
    team = Team.query.filter_by(lobby_id=lobby.id).first()
    if not team:
        flash("Team not found for this lobby.", "danger")
        return redirect(url_for("lobby_detail", lobby_id=lobby.id))

    if not lobby.finished:
        flash(
            "Proof submission is only available after the contest is finished.",
            "warning",
        )
        return redirect(url_for("lobby_detail", lobby_id=lobby.id))

    if not any(tm.user_id == user.id for tm in team.members):
        flash("Only team members can submit proof.", "danger")
        return redirect(url_for("lobby_detail", lobby_id=lobby.id))

    proof = (request.form.get("proof") or "").strip()
    if not proof:
        flash("Proof link/text is required.", "warning")
        return redirect(url_for("lobby_detail", lobby_id=lobby.id))

    submission = Submission(team_id=team.id, submitter_id=user.id, proof_link=proof)
    db.session.add(submission)
    db.session.commit()
    flash("Proof submitted.", "success")
    return redirect(url_for("lobby_detail", lobby_id=lobby.id))


@app.route("/lobbies/<int:lobby_id>/rate", methods=["POST"])
def rate_member_page(lobby_id):
    from models import Lobby, Team, Rating

    user = get_current_user()
    if not user:
        return redirect(
            url_for("login", next=url_for("lobby_detail", lobby_id=lobby_id))
        )

    lobby = Lobby.query.get_or_404(lobby_id)
    team = Team.query.filter_by(lobby_id=lobby.id).first()
    if not team:
        flash("Team not found for this lobby.", "danger")
        return redirect(url_for("lobby_detail", lobby_id=lobby.id))

    if not lobby.finished:
        flash("Ratings are only available after the contest is finished.", "warning")
        return redirect(url_for("lobby_detail", lobby_id=lobby.id))

    member_ids = {tm.user_id for tm in team.members}
    if user.id not in member_ids:
        flash("Only team members can submit ratings.", "danger")
        return redirect(url_for("lobby_detail", lobby_id=lobby.id))

    try:
        target_user_id = int(request.form.get("target_user_id") or 0)
    except Exception:
        target_user_id = 0
    if target_user_id not in member_ids or target_user_id == user.id:
        flash("Choose a valid teammate to rate.", "warning")
        return redirect(url_for("lobby_detail", lobby_id=lobby.id))

    try:
        contribution = int(request.form.get("contribution") or 0)
        communication = int(request.form.get("communication") or 0)
    except Exception:
        flash("Contribution and communication must be numbers.", "warning")
        return redirect(url_for("lobby_detail", lobby_id=lobby.id))

    would_work_again = request.form.get("would_work_again") == "on"
    comment = (request.form.get("comment") or "").strip() or None

    existing = Rating.query.filter_by(
        team_id=team.id, rater_id=user.id, target_user_id=target_user_id
    ).all()
    if existing:
        keep = existing[0]
        keep.contribution = contribution
        keep.communication = communication
        keep.would_work_again = would_work_again
        keep.comment = comment
        for extra in existing[1:]:
            db.session.delete(extra)
        db.session.commit()
        flash("Rating updated.", "success")
    else:
        r = Rating(
            team_id=team.id,
            rater_id=user.id,
            target_user_id=target_user_id,
            contribution=contribution,
            communication=communication,
            would_work_again=would_work_again,
            comment=comment,
        )
        db.session.add(r)
        db.session.commit()
        flash("Rating submitted.", "success")
    return redirect(url_for("lobby_detail", lobby_id=lobby.id))


@app.route("/lobbies/<int:lobby_id>/ratings/<int:rating_id>/delete", methods=["POST"])
def delete_rating_page(lobby_id, rating_id):
    from models import Lobby, Team, Rating

    user = get_current_user()
    if not user:
        return redirect(
            url_for("login", next=url_for("lobby_detail", lobby_id=lobby_id))
        )

    lobby = Lobby.query.get_or_404(lobby_id)
    team = Team.query.filter_by(lobby_id=lobby.id).first()
    if not team:
        flash("Team not found for this lobby.", "danger")
        return redirect(url_for("lobby_detail", lobby_id=lobby.id))

    rating = Rating.query.get_or_404(rating_id)
    if rating.team_id != team.id:
        flash("Invalid rating.", "danger")
        return redirect(url_for("lobby_detail", lobby_id=lobby.id))
    if rating.rater_id != user.id:
        flash("You can only delete ratings you posted.", "danger")
        return redirect(url_for("lobby_detail", lobby_id=lobby.id))

    db.session.delete(rating)
    db.session.commit()
    flash("Rating deleted.", "secondary")
    return redirect(url_for("lobby_detail", lobby_id=lobby.id))


@app.route("/lobbies/new", methods=["GET", "POST"])
def create_lobby_page():
    user = get_current_user()
    if not user:
        return redirect(url_for("login", next=url_for("create_lobby_page")))

    if request.method == "POST":
        from models import Lobby, Team

        title = (request.form.get("title") or "").strip()
        contest_link = (request.form.get("contest_link") or "").strip() or None

        if not title:
            flash("Title is required.", "warning")
            return redirect(url_for("create_lobby_page"))

        lobby = Lobby(title=title, contest_link=contest_link, leader_id=user.id)
        db.session.add(lobby)
        db.session.commit()

        team = Team(lobby_id=lobby.id, locked=False)
        db.session.add(team)
        db.session.commit()

        # creator joins by default
        team.add_member(user.id)
        db.session.commit()

        flash("Lobby created.", "success")
        return redirect(url_for("lobbies_page"))

    return render_template("lobby_new.html")


@app.route("/lobbies/<int:lobby_id>/join", methods=["POST"])
def join_lobby_page(lobby_id):
    user = get_current_user()
    if not user:
        return redirect(
            url_for("login", next=url_for("lobby_detail", lobby_id=lobby_id))
        )

    from models import Lobby, Team

    lobby = Lobby.query.get_or_404(lobby_id)
    team = Team.query.filter_by(lobby_id=lobby.id).first()
    if not team:
        flash("Team not found for this lobby.", "danger")
        return redirect(url_for("lobbies_page"))
    if lobby.finished:
        flash("This contest is finished; joining is disabled.", "warning")
        return redirect(url_for("lobby_detail", lobby_id=lobby.id))
    if team.locked:
        return redirect(url_for("lobby_detail", lobby_id=lobby.id))

    team.add_member(user.id)
    db.session.commit()
    flash("Joined lobby.", "success")
    return redirect(url_for("lobby_detail", lobby_id=lobby.id))


@app.route("/lobbies/<int:lobby_id>/invite", methods=["POST"])
def invite_to_lobby(lobby_id):
    from models import Lobby, Team, User, Invitation

    user = get_current_user()
    if not user:
        return redirect(
            url_for("login", next=url_for("lobby_detail", lobby_id=lobby_id))
        )

    lobby = Lobby.query.get_or_404(lobby_id)
    team = Team.query.filter_by(lobby_id=lobby.id).first()
    if not team:
        flash("Team not found for this lobby.", "danger")
        return redirect(url_for("lobby_detail", lobby_id=lobby.id))
    if lobby.finished:
        flash("This contest is finished; inviting is disabled.", "warning")
        return redirect(url_for("lobby_detail", lobby_id=lobby.id))
    if team.locked:
        flash("Team is locked; cannot invite new members.", "warning")
        return redirect(url_for("lobby_detail", lobby_id=lobby.id))

    email = (request.form.get("target_email") or "").strip()
    if not email:
        flash("Target email is required.", "warning")
        return redirect(url_for("lobby_detail", lobby_id=lobby.id))

    target = User.query.filter_by(email=email).first()
    if not target:
        flash("No user with that email found. The user must register first.", "warning")
        return redirect(url_for("lobby_detail", lobby_id=lobby.id))

    # prevent duplicate invite or if already member
    if any(tm.user_id == target.id for tm in team.members):
        flash("User is already a member of this team.", "info")
        return redirect(url_for("lobby_detail", lobby_id=lobby.id))

    existing = Invitation.query.filter_by(
        team_id=team.id, target_user_id=target.id, status="pending"
    ).first()
    if existing:
        flash("A pending invitation already exists for that user.", "info")
        return redirect(url_for("lobby_detail", lobby_id=lobby.id))

    token = secrets.token_urlsafe(24)
    inv = Invitation(
        lobby_id=lobby.id,
        team_id=team.id,
        applicant_id=user.id,
        target_user_id=target.id,
        token=token,
        status="pending",
    )
    db.session.add(inv)
    db.session.commit()

    # send email with accept/reject links
    accept_url = url_for("respond_invite", token=token, action="accept", _external=True)
    reject_url = url_for("respond_invite", token=token, action="reject", _external=True)
    subject = f"Team invite for '{lobby.title}' from {user.name}"
    body = f"{user.name} has requested you join their team for lobby '{lobby.title}'.\n\nAccept: {accept_url}\nReject: {reject_url}\n\nIf you didn't expect this, ignore this email."
    _send_email(subject, target.email, body)
    flash("Invitation sent (or logged).", "success")
    return redirect(url_for("lobby_detail", lobby_id=lobby.id))


@app.route("/invites/respond/<token>")
def respond_invite(token):
    from models import Invitation, Team, User

    action = (request.args.get("action") or "").lower()
    inv = Invitation.query.filter_by(token=token).first()
    if not inv:
        flash("Invalid invitation token.", "danger")
        return redirect(url_for("index"))

    if inv.status != "pending":
        flash("This invitation has already been responded to.", "info")
        return redirect(url_for("lobby_detail", lobby_id=inv.lobby_id))

    if action == "accept":
        # add target to team
        team = Team.query.get(inv.team_id)
        if team and not team.locked:
            team.add_member(inv.target_user_id)
            inv.status = "accepted"
            inv.responded_at = datetime.utcnow()
            db.session.commit()
            flash("You have accepted the invitation and joined the team.", "success")
        else:
            flash("Team not found or locked.", "danger")
    elif action == "reject":
        inv.status = "rejected"
        inv.responded_at = datetime.utcnow()
        db.session.commit()
        flash("You have rejected the invitation.", "secondary")
    else:
        # show simple page with accept/reject links
        accept_url = url_for(
            "respond_invite", token=token, action="accept", _external=True
        )
        reject_url = url_for(
            "respond_invite", token=token, action="reject", _external=True
        )
        return render_template(
            "invite_confirm.html", accept_url=accept_url, reject_url=reject_url
        )

    return redirect(url_for("lobby_detail", lobby_id=inv.lobby_id))


@app.route("/api/users", methods=["GET", "POST"])
def users():
    from models import User

    if request.method == "POST":
        data = request.json or {}
        name = data.get("name", "Anonymous")
        email = (data.get("email") or "").strip()
        password = data.get("password")
        major = data.get("major")
        year = data.get("year")

        if not email or not email.lower().endswith("@duke.edu"):
            return jsonify({"error": "email must end with @duke.edu"}), 400
        if not password:
            return jsonify({"error": "password required"}), 400
        # prevent duplicate emails
        if User.query.filter_by(email=email).first():
            return jsonify({"error": "email already exists"}), 400

        user = User(
            name=name,
            major=major,
            year=year,
            email=email,
            password_hash=generate_password_hash(password),
        )
        db.session.add(user)
        db.session.commit()
        # optional: auto-join a lobby if lobby_id provided
        lobby_id = data.get("lobby_id")
        if lobby_id:
            try:
                lobby_id = int(lobby_id)
            except Exception:
                lobby_id = None
        if lobby_id:
            from models import Team

            team = Team.query.filter_by(lobby_id=lobby_id).first()
            if team and not team.locked:
                team.add_member(user.id)
                db.session.commit()
        return jsonify(user.to_dict()), 201
    users = User.query.all()
    return jsonify([u.to_dict() for u in users])


@app.route("/api/users/<int:user_id>", methods=["GET"])
def get_user(user_id):
    from models import User

    user = User.query.get_or_404(user_id)
    data = user.to_dict()
    data["lobbies"] = user.participated_lobbies()
    return jsonify(data)


@app.route("/api/lobbies/<int:lobby_id>", methods=["GET"])
def get_lobby(lobby_id):
    from models import Lobby, Team, TeamMember, User

    lobby = Lobby.query.get_or_404(lobby_id)
    # gather participants across teams for this lobby
    teams = Team.query.filter_by(lobby_id=lobby.id).all()
    participants = []
    for t in teams:
        for tm in t.members:
            u = User.query.get(tm.user_id)
            if u:
                participants.append(u.to_dict())
    out = lobby.to_dict()
    out["participants"] = participants
    return jsonify(out)


@app.route("/api/lobbies", methods=["GET", "POST"])
def lobbies():
    from models import Lobby, Team

    if request.method == "POST":
        data = request.json or {}
        lobby = Lobby(
            title=data.get("title", "Untitled"),
            contest_link=data.get("contest_link"),
            leader_id=data.get("leader_id"),
        )
        db.session.add(lobby)
        db.session.commit()
        team = Team(lobby_id=lobby.id, locked=False)
        db.session.add(team)
        db.session.commit()
        return jsonify(lobby.to_dict()), 201
    qs = Lobby.query.all()
    out = []
    for q in qs:
        # compute participant count across teams
        teams = Team.query.filter_by(lobby_id=q.id).all()
        count = 0
        for t in teams:
            count += len(t.members)
        d = q.to_dict()
        d["participant_count"] = count
        out.append(d)
    return jsonify(out)


@app.route("/api/lobbies/<int:lobby_id>/join", methods=["POST"])
def join_lobby(lobby_id):
    from models import Lobby, Team

    data = request.json or {}
    user_id = data.get("user_id")
    lobby = Lobby.query.get_or_404(lobby_id)
    if lobby.finished:
        return jsonify({"error": "contest finished"}), 400
    team = Team.query.filter_by(lobby_id=lobby.id).first()
    if not team:
        return jsonify({"error": "team not found"}), 404
    if team.locked:
        return jsonify({"error": "team locked"}), 400
    team.add_member(user_id)
    db.session.commit()
    return jsonify(team.to_dict())


@app.route("/api/teams/<int:team_id>/lock", methods=["POST"])
def lock_team(team_id):
    from models import Team

    team = Team.query.get_or_404(team_id)
    team.locked = True
    db.session.commit()
    return jsonify(team.to_dict())


@app.route("/api/teams/<int:team_id>/submit", methods=["POST"])
def submit_team(team_id):
    from models import Team, Submission, Lobby

    team = Team.query.get_or_404(team_id)
    data = request.json or {}
    proof = data.get("proof")
    if not proof:
        return jsonify({"error": "proof required"}), 400
    lobby = Lobby.query.get(team.lobby_id)
    if not lobby or not lobby.finished:
        return jsonify(
            {"error": "contest must be finished before submitting proof"}
        ), 400
    submitter_id = data.get("submitter_id")
    if submitter_id is None:
        return jsonify({"error": "submitter_id required"}), 400
    member_ids = {tm.user_id for tm in team.members}
    if int(submitter_id) not in member_ids:
        return jsonify({"error": "submitter must be a team member"}), 400
    submission = Submission(
        team_id=team.id, submitter_id=int(submitter_id), proof_link=proof
    )
    db.session.add(submission)
    db.session.commit()
    return jsonify(submission.to_dict()), 201


@app.route("/api/teams/<int:team_id>/ratings", methods=["POST"])
def rate_member(team_id):
    from models import Team, Rating, Lobby

    team = Team.query.get_or_404(team_id)
    lobby = Lobby.query.get(team.lobby_id)
    if not lobby or not lobby.finished:
        return jsonify({"error": "contest must be finished before ratings"}), 400
    data = request.json or {}
    member_ids = {tm.user_id for tm in team.members}
    rater_id = data.get("rater_id")
    target_user_id = data.get("target_user_id")
    if rater_id is None or target_user_id is None:
        return jsonify({"error": "rater_id and target_user_id required"}), 400
    if int(rater_id) not in member_ids or int(target_user_id) not in member_ids:
        return jsonify({"error": "rater and target must be team members"}), 400
    if int(rater_id) == int(target_user_id):
        return jsonify({"error": "cannot rate yourself"}), 400
    r = Rating(
        team_id=team.id,
        rater_id=int(rater_id),
        target_user_id=int(target_user_id),
        contribution=int(data.get("contribution", 0)),
        communication=int(data.get("communication", 0)),
        would_work_again=bool(data.get("would_work_again", False)),
        comment=data.get("comment"),
    )
    db.session.add(r)
    db.session.commit()
    return jsonify(r.to_dict()), 201


@app.route("/api/users/<int:user_id>/reputation")
def user_reputation(user_id):
    from models import User

    user = User.query.get_or_404(user_id)
    return jsonify(user.reputation())


if __name__ == "__main__":
    # run without the reloader to avoid external shell tool dependencies in some terminals
    app.run(debug=False)

@app.route("/api/lobbies/<int:lobby_id>/join-requests", methods=["POST"])
def api_create_join_request(lobby_id):
    user = get_current_user()
    if not user:
        return jsonify({"error": "not_logged_in"}), 401

    lobby = Lobby.query.get_or_404(lobby_id)
    team = Team.query.filter_by(lobby_id=lobby.id).first()
    if not team:
        return jsonify({"error": "team_not_found"}), 404

    if lobby.finished:
        return jsonify({"error": "lobby_finished"}), 400
    if team.locked:
        return jsonify({"error": "team_locked"}), 400

    if any(tm.user_id == user.id for tm in team.members):
        return jsonify({"error": "already_member"}), 400

    existing = JoinRequest.query.filter_by(
        lobby_id=lobby.id,
        team_id=team.id,
        requester_id=user.id,
        status="pending",
    ).first()
    if existing:
        return jsonify({"error": "already_pending", "request": existing.to_dict()}), 400

    jr = JoinRequest(lobby_id=lobby.id, team_id=team.id, requester_id=user.id, status="pending")
    db.session.add(jr)
    db.session.commit()
    return jsonify(jr.to_dict()), 201

@app.route("/api/lobbies/<int:lobby_id>/join-requests", methods=["GET"])
def api_list_join_requests(lobby_id):
    user = get_current_user()
    if not user:
        return jsonify({"error": "not_logged_in"}), 401

    lobby = Lobby.query.get_or_404(lobby_id)
    if lobby.leader_id != user.id:
        return jsonify({"error": "leader_only"}), 403

    team = Team.query.filter_by(lobby_id=lobby.id).first()
    if not team:
        return jsonify({"error": "team_not_found"}), 404

    status = (request.args.get("status") or "pending").strip().lower()
    q = JoinRequest.query.filter_by(lobby_id=lobby.id, team_id=team.id)
    if status in {"pending", "accepted", "rejected", "canceled"}:
        q = q.filter_by(status=status)

    reqs = q.order_by(JoinRequest.created_at.asc()).all()
    return jsonify([r.to_dict() for r in reqs]), 200

@app.route("/api/lobbies/<int:lobby_id>/join-requests/<int:request_id>/decision", methods=["POST"])
def api_decide_join_request(lobby_id, request_id):
    user = get_current_user()
    if not user:
        return jsonify({"error": "not_logged_in"}), 401

    lobby = Lobby.query.get_or_404(lobby_id)
    if lobby.leader_id != user.id:
        return jsonify({"error": "leader_only"}), 403

    team = Team.query.filter_by(lobby_id=lobby.id).first()
    if not team:
        return jsonify({"error": "team_not_found"}), 404

    jr = JoinRequest.query.get_or_404(request_id)
    if jr.lobby_id != lobby.id or jr.team_id != team.id:
        return jsonify({"error": "invalid_request"}), 400

    if jr.status != "pending":
        return jsonify({"error": "not_pending", "request": jr.to_dict()}), 400

    data = request.get_json(silent=True) or {}
    decision = (data.get("decision") or "").strip().lower()
    if decision not in {"accept", "reject"}:
        return jsonify({"error": "invalid_decision"}), 400

    if lobby.finished:
        return jsonify({"error": "lobby_finished"}), 400
    if team.locked:
        return jsonify({"error": "team_locked"}), 400

    if decision == "reject":
        jr.status = "rejected"
        db.session.commit()
        return jsonify(jr.to_dict()), 200

    if any(tm.user_id == jr.requester_id for tm in team.members):
        jr.status = "accepted"
        db.session.commit()
        return jsonify(jr.to_dict()), 200

    team.add_member(jr.requester_id)
    jr.status = "accepted"
    db.session.commit()
    return jsonify(jr.to_dict()), 200