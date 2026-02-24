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


with app.app_context():
    # Auto-seed only when running the web app; avoid doing this during `seed_db.py`
    if os.environ.get("TRS_DISABLE_AUTOSEED") != "1":
        has_user = db.session.execute(text("SELECT 1 FROM user LIMIT 1")).first()
        if has_user is None:
            from seed_db import seed_users

            seed_users()


def get_current_user():
    from models import User

    user_id = session.get("user_id")
    if not user_id:
        return None
    return User.query.get(user_id)


def _rep_overall_score_0_to_10(rep: dict | None) -> float:
    """Scalar reputation score in [0, 10] derived from the existing rep dict.

    We keep this consistent with the graph API's normalization: contribution and
    communication are treated as 0..10 inputs, normalized to 0..1, then averaged
    with the would_work_again ratio (0..1).
    """

    if not rep:
        return 0.0

    from models import _normalize_0_to_10

    contrib = _normalize_0_to_10(rep.get("contribution_avg"))
    comm = _normalize_0_to_10(rep.get("communication_avg"))

    wwa_raw = rep.get("would_work_again_ratio")
    try:
        wwa = float(wwa_raw) if wwa_raw is not None else 0.0
    except (TypeError, ValueError):
        wwa = 0.0
    if wwa < 0.0:
        wwa = 0.0
    if wwa > 1.0:
        wwa = 1.0

    score = 10.0 * ((contrib + comm + wwa) / 3.0)
    return round(float(score), 2)


def _aggregate_team_rep_0_to_10(member_ids: list[int], rep_score_by_id: dict[int, float]) -> float:
    if not member_ids:
        return 0.0
    scores = [float(rep_score_by_id.get(uid, 0.0)) for uid in member_ids]
    if not scores:
        return 0.0
    return round(sum(scores) / float(len(scores)), 2)


def _compute_rep_scores_for_user_ids(user_ids: set[int]) -> dict[int, float]:
    """Compute scalar rep scores for a set of user ids (best effort)."""

    if not user_ids:
        return {}

    from models import User

    trust_scores = User.compute_transitive_trust_scores()
    users = User.query.filter(User.id.in_(user_ids)).all()
    rep_score_by_id: dict[int, float] = {}
    for u in users:
        rep_score_by_id[u.id] = _rep_overall_score_0_to_10(
            u.reputation(trust_scores=trust_scores)
        )
    return rep_score_by_id


def _send_email(subject: str, to_email: str, body: str):
    # Use SMTP settings if configured; otherwise log to console
    smtp_host = app.config.get("SMTP_HOST")
    smtp_port = app.config.get("SMTP_PORT") or 25
    smtp_user = app.config.get("SMTP_USER")
    smtp_pass = app.config.get("SMTP_PASS")
    mail_from = app.config.get("MAIL_FROM") or "noreply@teammate-reputation-system.com"

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


def _serialize_user(user):
    # prefer model-provided to_dict when available, otherwise build a minimal dict
    try:
        if hasattr(user, "to_dict"):
            d = user.to_dict()
        else:
            keys = ["id", "name", "email", "major", "year", "bio", "contact", "phone"]
            d = {k: getattr(user, k, None) for k in keys}
        try:
            d["reputation"] = user.reputation()
        except Exception:
            pass
        return d
    except Exception:
        return {"id": getattr(user, "id", None), "name": getattr(user, "name", None)}


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

        accept = request.headers.get("Accept", "")
        accept_json = (
            "application/json" in accept
            or request.is_json
            or request.headers.get("X-Requested-With") == "XMLHttpRequest"
        )
        # support JSON or form-encoded POST bodies for API clients (Next.js)
        json_data = request.get_json(silent=True) or {}
        if json_data:
            email = (json_data.get("email") or "").strip()
            password = json_data.get("password") or ""

        if not email or not password:
            if accept_json:
                return jsonify({"error": "email_password_required"}), 400
            flash("Email and password are required.", "warning")
            return render_template("login.html", users=users)

        user = User.query.filter_by(email=email).first()
        if not user or not getattr(user, "password_hash", None):
            if accept_json:
                return jsonify({"error": "invalid_credentials"}), 401
            flash("Invalid credentials.", "danger")
            return render_template("login.html", users=users)

        if not check_password_hash(user.password_hash, password):
            if accept_json:
                return jsonify({"error": "invalid_credentials"}), 401
            flash("Invalid credentials.", "danger")
            return render_template("login.html", users=users)

        session["user_id"] = user.id
        # ensure session cookie is sent; API clients will receive Set-Cookie
        if accept_json:
            return jsonify(_serialize_user(user)), 200

        flash(f"Logged in as {user.name}.", "success")
        next_url = request.args.get("next")
        return redirect(next_url or url_for("me"))


@app.route("/logout", methods=["POST"])
def logout():
    session.pop("user_id", None)
    accept = request.headers.get("Accept", "")
    accept_json = ("application/json" in accept) or (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
    )
    if accept_json:
        return jsonify({"status": "ok"}), 204
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
            bio=bio or "",
            contact=contact or "",
            phone=phone or "0",
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
    accept = request.headers.get("Accept", "")
    accept_json = ("application/json" in accept) or (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
    )

    if not user:
        if accept_json:
            return jsonify({"error": "not_logged_in"}), 401
        return redirect(url_for("login", next=url_for("me")))

    if accept_json:
        return jsonify(_serialize_user(user))
    return redirect(url_for("user_profile", user_id=user.id))


@app.route("/users")
def users_page():
    from models import User

    users = User.query.order_by(User.name.asc()).all()
    trust_scores = User.compute_transitive_trust_scores()
    rep_by_id = {u.id: u.reputation(trust_scores=trust_scores) for u in users}
    return render_template("users.html", users=users, rep_by_id=rep_by_id)


@app.route("/graph")
def graph_page():
    return render_template("graph.html")


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

    trust_scores = User.compute_transitive_trust_scores()
    overall_rep = user.reputation(trust_scores=trust_scores)
    return render_template(
        "profile.html",
        user=user,
        can_edit=can_edit,
        history=history,
        overall_rep=overall_rep,
    )


@app.route("/lobbies")
def lobbies_page():
    from models import Lobby, Team, JoinRequest

    qs = Lobby.query.order_by(Lobby.created_at.desc()).all()
    lobbies = []
    viewer = get_current_user()

    pending_by_lobby_id = {}
    if viewer:
        pending = JoinRequest.query.filter_by(
            requester_id=viewer.id, status="pending"
        ).all()
        pending_by_lobby_id = {r.lobby_id: r for r in pending}

    # Pre-compute rep scores for users participating in these lobbies (+ viewer).
    member_ids_by_lobby_id: dict[int, list[int]] = {}
    all_user_ids: set[int] = set()

    for q in qs:
        team = Team.query.filter_by(lobby_id=q.id).first()
        member_ids = [tm.user_id for tm in team.members] if team else []
        member_ids_by_lobby_id[q.id] = member_ids
        all_user_ids.update(member_ids)

    if viewer:
        all_user_ids.add(viewer.id)

    rep_score_by_id = _compute_rep_scores_for_user_ids(all_user_ids)
    viewer_rep = float(rep_score_by_id.get(viewer.id, 0.0)) if viewer else None

    for idx, q in enumerate(qs):
        team = Team.query.filter_by(lobby_id=q.id).first()
        member_ids = member_ids_by_lobby_id.get(q.id, [])
        participant_count = len(member_ids)
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

        req = pending_by_lobby_id.get(q.id)
        d["join_request_status"] = req.status if req else None

        team_rep = _aggregate_team_rep_0_to_10(member_ids, rep_score_by_id)
        d["team_reputation"] = team_rep
        if viewer_rep is not None:
            d["rep_distance"] = round(abs(team_rep - viewer_rep), 2)
        else:
            d["rep_distance"] = None

        # preserve original ordering (created_at desc) as a stable tiebreaker
        d["_order"] = idx
        lobbies.append(d)

    if viewer:
        def _is_joinable(l: dict) -> bool:
            return (
                l.get("role") is None
                and (not bool(l.get("finished")))
                and (not bool(l.get("team_locked")))
            )

        def _sort_key(l: dict):
            joinable_bucket = 0 if _is_joinable(l) else 1
            dist = l.get("rep_distance")
            dist_val = float(dist) if dist is not None else 1e9
            return (joinable_bucket, dist_val, l.get("_order", 0))

        lobbies.sort(key=_sort_key)

    for l in lobbies:
        l.pop("_order", None)

    return render_template("lobbies.html", lobbies=lobbies)


@app.route("/lobbies/<int:lobby_id>", methods=["GET", "POST"])
def lobby_detail(lobby_id):
    from models import Lobby, Team, User, Rating, JoinRequest
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

    viewer_join_request = None
    if viewer and team and (not is_member):
        viewer_join_request = JoinRequest.query.filter_by(
            lobby_id=lobby.id, team_id=team.id, requester_id=viewer.id
        ).order_by(JoinRequest.created_at.desc()).first()

    join_requests = []
    if is_leader and team:
        reqs = (
            JoinRequest.query.filter_by(lobby_id=lobby.id, team_id=team.id)
            .order_by(JoinRequest.created_at.asc())
            .all()
        )
        for r in reqs:
            join_requests.append({"request": r, "requester": User.query.get(r.requester_id)})

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

    invite_recommendations = []
    if viewer and is_leader and team and (not team.locked) and (not lobby.finished):
        pending_invites = Invitation.query.filter_by(team_id=team.id, status="pending").all()
        excluded_ids = {tm.user_id for tm in team.members} | {viewer.id}
        excluded_ids |= {inv.target_user_id for inv in pending_invites if inv.target_user_id is not None}

        candidates = (
            User.query.filter(~User.id.in_(excluded_ids)).order_by(User.name.asc()).all()
            if excluded_ids
            else User.query.order_by(User.name.asc()).all()
        )

        rep_user_ids: set[int] = {viewer.id} | {u.id for u in candidates}
        rep_score_by_id = _compute_rep_scores_for_user_ids(rep_user_ids)
        viewer_rep = float(rep_score_by_id.get(viewer.id, 0.0))

        scored = []
        for u in candidates:
            score = float(rep_score_by_id.get(u.id, 0.0))
            scored.append(
                {
                    "user": u,
                    "reputation": score,
                    "distance": round(abs(score - viewer_rep), 2),
                }
            )

        scored.sort(key=lambda x: (x["distance"], x["user"].name.lower()))
        invite_recommendations = scored[:5]

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
        viewer_join_request=viewer_join_request,
        join_requests=join_requests,
        submissions=submissions,
        teammates=teammates,
        ratings=ratings,
        rating_by_pair=rating_by_pair,
        viewer_ratings_by_target=viewer_ratings_by_target,
        avg_by_target=avg_by_target,
        invites=Invitation.query.filter_by(team_id=team.id).all() if team else [],
        invite_recommendations=invite_recommendations,
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


@app.route("/lobbies/<int:lobby_id>/join-requests", methods=["POST"])
def create_join_request_page(lobby_id):
    from models import Lobby, Team, JoinRequest

    user = get_current_user()
    if not user:
        return redirect(url_for("login", next=url_for("lobby_detail", lobby_id=lobby_id)))

    lobby = Lobby.query.get_or_404(lobby_id)
    team = Team.query.filter_by(lobby_id=lobby.id).first()
    if not team:
        flash("Team not found for this lobby.", "danger")
        return redirect(url_for("lobby_detail", lobby_id=lobby.id))

    if lobby.finished:
        flash("This contest is finished; joining is disabled.", "warning")
        return redirect(url_for("lobby_detail", lobby_id=lobby.id))
    if team.locked:
        flash("Team is locked; cannot request to join.", "warning")
        return redirect(url_for("lobby_detail", lobby_id=lobby.id))

    if any(tm.user_id == user.id for tm in team.members):
        flash("You are already a team member.", "info")
        return redirect(url_for("lobby_detail", lobby_id=lobby.id))

    existing = JoinRequest.query.filter_by(
        lobby_id=lobby.id,
        team_id=team.id,
        requester_id=user.id,
        status="pending",
    ).first()
    if existing:
        flash("Join request already pending.", "info")
        return redirect(url_for("lobby_detail", lobby_id=lobby.id))

    jr = JoinRequest(lobby_id=lobby.id, team_id=team.id, requester_id=user.id, status="pending")
    db.session.add(jr)
    db.session.commit()
    flash("Join request submitted.", "success")
    return redirect(url_for("lobby_detail", lobby_id=lobby.id))


@app.route(
    "/lobbies/<int:lobby_id>/join-requests/<int:request_id>/decision",
    methods=["POST"],
)
def decide_join_request_page(lobby_id, request_id):
    from models import Lobby, Team, JoinRequest

    user = get_current_user()
    if not user:
        return redirect(url_for("login", next=url_for("lobby_detail", lobby_id=lobby_id)))

    lobby = Lobby.query.get_or_404(lobby_id)
    if lobby.leader_id != user.id:
        flash("Only the lobby leader can decide join requests.", "danger")
        return redirect(url_for("lobby_detail", lobby_id=lobby.id))

    team = Team.query.filter_by(lobby_id=lobby.id).first()
    if not team:
        flash("Team not found for this lobby.", "danger")
        return redirect(url_for("lobby_detail", lobby_id=lobby.id))

    jr = JoinRequest.query.get_or_404(request_id)
    if jr.lobby_id != lobby.id or jr.team_id != team.id:
        flash("Invalid join request.", "danger")
        return redirect(url_for("lobby_detail", lobby_id=lobby.id))

    if jr.status != "pending":
        flash("This join request is no longer pending.", "info")
        return redirect(url_for("lobby_detail", lobby_id=lobby.id))

    decision = (request.form.get("decision") or "").strip().lower()
    if decision not in {"accept", "reject"}:
        flash("Invalid decision.", "danger")
        return redirect(url_for("lobby_detail", lobby_id=lobby.id))

    if lobby.finished or team.locked:
        flash("Team is not accepting new members.", "warning")
        return redirect(url_for("lobby_detail", lobby_id=lobby.id))

    if decision == "reject":
        jr.status = "rejected"
        db.session.commit()
        flash("Join request rejected.", "secondary")
        return redirect(url_for("lobby_detail", lobby_id=lobby.id))

    if any(tm.user_id == jr.requester_id for tm in team.members):
        jr.status = "accepted"
        db.session.commit()
        flash("Requester is already a member.", "info")
        return redirect(url_for("lobby_detail", lobby_id=lobby.id))

    team.add_member(jr.requester_id)
    jr.status = "accepted"
    db.session.commit()
    flash("Join request accepted; member added.", "success")
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
    if lobby.leader_id != user.id:
        flash("Only the lobby leader can invite teammates.", "danger")
        return redirect(url_for("lobby_detail", lobby_id=lobby.id))
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


@app.route("/invites")
def invites_page():
    from models import Invitation, Lobby, User

    user = get_current_user()
    if not user:
        return redirect(url_for("login", next=url_for("invites_page")))

    received = (
        Invitation.query.filter_by(target_user_id=user.id)
        .order_by(Invitation.created_at.desc())
        .all()
    )
    sent = (
        Invitation.query.filter_by(applicant_id=user.id)
        .order_by(Invitation.created_at.desc())
        .all()
    )

    lobby_by_id = {l.id: l for l in Lobby.query.filter(Lobby.id.in_({i.lobby_id for i in received + sent})).all()} if (received or sent) else {}
    user_ids = {i.applicant_id for i in received + sent} | {i.target_user_id for i in received + sent}
    users_by_id = {u.id: u for u in User.query.filter(User.id.in_(user_ids)).all()} if user_ids else {}

    return render_template(
        "invites.html",
        received=received,
        sent=sent,
        lobby_by_id=lobby_by_id,
        users_by_id=users_by_id,
    )


@app.route("/join-requests")
def join_requests_page():
    from models import JoinRequest, Lobby, User

    user = get_current_user()
    if not user:
        return redirect(url_for("login", next=url_for("join_requests_page")))

    made = (
        JoinRequest.query.filter_by(requester_id=user.id)
        .order_by(JoinRequest.created_at.desc())
        .all()
    )

    leader_lobbies = Lobby.query.filter_by(leader_id=user.id).all()
    leader_lobby_ids = {l.id for l in leader_lobbies}
    received = (
        JoinRequest.query.filter(JoinRequest.lobby_id.in_(leader_lobby_ids)).order_by(JoinRequest.created_at.desc()).all()
        if leader_lobby_ids
        else []
    )

    lobby_ids = {r.lobby_id for r in made + received}
    lobby_by_id = {l.id: l for l in Lobby.query.filter(Lobby.id.in_(lobby_ids)).all()} if lobby_ids else {}

    requester_ids = {r.requester_id for r in made + received}
    users_by_id = {u.id: u for u in User.query.filter(User.id.in_(requester_ids)).all()} if requester_ids else {}

    return render_template(
        "join_requests.html",
        made=made,
        received=received,
        lobby_by_id=lobby_by_id,
        users_by_id=users_by_id,
    )


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
    out["participant_count"] = len(participants)
    # This app's UI assumes a single team per lobby; expose a simple lock flag.
    primary_team = Team.query.filter_by(lobby_id=lobby.id).first()
    out["team_locked"] = bool(primary_team.locked) if primary_team else False
    return jsonify(out)


@app.route("/api/lobbies", methods=["GET", "POST"])
def lobbies():
    from models import Lobby, Team, JoinRequest

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
    viewer = get_current_user()

    # Keep newest-first as the baseline order.
    qs = Lobby.query.order_by(Lobby.created_at.desc()).all()

    member_ids_by_lobby_id: dict[int, list[int]] = {}
    all_user_ids: set[int] = set()

    for q in qs:
        team = Team.query.filter_by(lobby_id=q.id).first()
        member_ids = [tm.user_id for tm in team.members] if team else []
        member_ids_by_lobby_id[q.id] = member_ids
        all_user_ids.update(member_ids)

    if viewer:
        all_user_ids.add(viewer.id)

    rep_score_by_id = _compute_rep_scores_for_user_ids(all_user_ids)
    viewer_rep = float(rep_score_by_id.get(viewer.id, 0.0)) if viewer else None

    pending_by_lobby_id = {}
    if viewer:
        pending = JoinRequest.query.filter_by(requester_id=viewer.id, status="pending").all()
        pending_by_lobby_id = {r.lobby_id: r for r in pending}

    out = []
    for idx, q in enumerate(qs):
        team = Team.query.filter_by(lobby_id=q.id).first()
        member_ids = member_ids_by_lobby_id.get(q.id, [])

        d = q.to_dict()
        d["participant_count"] = len(member_ids)
        d["team_locked"] = bool(team.locked) if team else False

        role = None
        if viewer:
            if q.leader_id and viewer.id == q.leader_id:
                role = "Leader"
            elif team and any(tm.user_id == viewer.id for tm in team.members):
                role = "Member"
        d["role"] = role

        req = pending_by_lobby_id.get(q.id)
        d["join_request_status"] = req.status if req else None

        team_rep = _aggregate_team_rep_0_to_10(member_ids, rep_score_by_id)
        d["team_reputation"] = team_rep
        if viewer_rep is not None:
            d["rep_distance"] = round(abs(team_rep - viewer_rep), 2)
        else:
            d["rep_distance"] = None

        d["_order"] = idx
        out.append(d)

    if viewer:
        def _is_joinable(l: dict) -> bool:
            return (
                l.get("role") is None
                and (not bool(l.get("finished")))
                and (not bool(l.get("team_locked")))
            )

        def _sort_key(l: dict):
            joinable_bucket = 0 if _is_joinable(l) else 1
            dist = l.get("rep_distance")
            dist_val = float(dist) if dist is not None else 1e9
            return (joinable_bucket, dist_val, l.get("_order", 0))

        out.sort(key=_sort_key)

    for l in out:
        l.pop("_order", None)

    return jsonify(out)


@app.route("/api/lobbies/<int:lobby_id>/invite-suggestions", methods=["GET"])
def api_invite_suggestions(lobby_id: int):
    """Return a few users whose reputation is closest to the leader's.

    Leader-only, excludes current team members and pending invites.
    """

    from models import Lobby, Team, User, Invitation

    viewer = get_current_user()
    if not viewer:
        return jsonify({"error": "not_logged_in"}), 401

    lobby = Lobby.query.get_or_404(lobby_id)
    if lobby.leader_id != viewer.id:
        return jsonify({"error": "leader_only"}), 403

    team = Team.query.filter_by(lobby_id=lobby.id).first()
    if not team:
        return jsonify({"error": "team_not_found"}), 404

    if lobby.finished or team.locked:
        return jsonify([]), 200

    pending_invites = Invitation.query.filter_by(team_id=team.id, status="pending").all()
    excluded_ids = {tm.user_id for tm in team.members} | {viewer.id}
    excluded_ids |= {inv.target_user_id for inv in pending_invites if inv.target_user_id is not None}

    candidates = (
        User.query.filter(~User.id.in_(excluded_ids)).order_by(User.name.asc()).all()
        if excluded_ids
        else User.query.order_by(User.name.asc()).all()
    )

    rep_user_ids: set[int] = {viewer.id} | {u.id for u in candidates}
    rep_score_by_id = _compute_rep_scores_for_user_ids(rep_user_ids)
    viewer_rep = float(rep_score_by_id.get(viewer.id, 0.0))

    scored = []
    for u in candidates:
        score = float(rep_score_by_id.get(u.id, 0.0))
        scored.append(
            {
                "id": u.id,
                "name": u.name,
                "email": u.email,
                "reputation": score,
                "distance": round(abs(score - viewer_rep), 2),
            }
        )

    scored.sort(key=lambda x: (x["distance"], (x["name"] or "").lower()))
    return jsonify(scored[:5]), 200
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
    trust_scores = User.compute_transitive_trust_scores()
    return jsonify(user.reputation(trust_scores=trust_scores))


@app.route("/api/graph")
def api_graph():
    """Return a deduped rating graph for demo visualization.

    Nodes are users with a global trust score.
    Edges are rater -> target with an averaged local weight in [0, 1].
    """

    from models import User, Rating, _normalize_0_to_10

    trust_scores = User.compute_transitive_trust_scores()
    users = User.query.order_by(User.id.asc()).all()

    rep_by_id = {u.id: u.reputation(trust_scores=trust_scores) for u in users}

    # Collapse multiple ratings between the same (rater, target)
    pair_local_sum: dict[tuple[int, int], float] = {}
    pair_local_count: dict[tuple[int, int], int] = {}
    pair_contrib_sum: dict[tuple[int, int], float] = {}
    pair_contrib_n: dict[tuple[int, int], int] = {}
    pair_comm_sum: dict[tuple[int, int], float] = {}
    pair_comm_n: dict[tuple[int, int], int] = {}
    pair_wwa_sum: dict[tuple[int, int], float] = {}
    pair_wwa_n: dict[tuple[int, int], int] = {}

    rows = db.session.query(
        Rating.rater_id,
        Rating.target_user_id,
        Rating.contribution,
        Rating.communication,
        Rating.would_work_again,
    ).all()

    for rater_id, target_user_id, contribution, communication, would_work_again in rows:
        if rater_id is None or target_user_id is None:
            continue
        if rater_id == target_user_id:
            continue

        contrib_n = _normalize_0_to_10(contribution)
        comm_n = _normalize_0_to_10(communication)
        wwa_n = 1.0 if bool(would_work_again) else 0.0

        local = (contrib_n + comm_n + wwa_n) / 3.0
        if local <= 0.0:
            continue

        key = (int(rater_id), int(target_user_id))
        pair_local_sum[key] = pair_local_sum.get(key, 0.0) + float(local)
        pair_local_count[key] = pair_local_count.get(key, 0) + 1

        if contribution is not None:
            pair_contrib_sum[key] = pair_contrib_sum.get(key, 0.0) + float(contribution)
            pair_contrib_n[key] = pair_contrib_n.get(key, 0) + 1
        if communication is not None:
            pair_comm_sum[key] = pair_comm_sum.get(key, 0.0) + float(communication)
            pair_comm_n[key] = pair_comm_n.get(key, 0) + 1

        pair_wwa_sum[key] = pair_wwa_sum.get(key, 0.0) + (1.0 if bool(would_work_again) else 0.0)
        pair_wwa_n[key] = pair_wwa_n.get(key, 0) + 1

    nodes = [
        {
            "id": u.id,
            "name": u.name,
            "trust": float(trust_scores.get(u.id, 0.0)),
            "reputation": rep_by_id.get(u.id),
            "reputation_overall": (
                (
                    (_normalize_0_to_10((rep_by_id.get(u.id) or {}).get("contribution_avg"))
                    + _normalize_0_to_10((rep_by_id.get(u.id) or {}).get("communication_avg"))
                    + float((rep_by_id.get(u.id) or {}).get("would_work_again_ratio") or 0.0))
                    / 3.0
                )
                if rep_by_id.get(u.id) is not None
                else 0.0
            ),
        }
        for u in users
    ]

    edges = []
    for (rater_id, target_user_id), s in pair_local_sum.items():
        n = pair_local_count[(rater_id, target_user_id)]
        contrib_avg = None
        comm_avg = None
        if pair_contrib_n.get((rater_id, target_user_id), 0):
            contrib_avg = pair_contrib_sum[(rater_id, target_user_id)] / float(pair_contrib_n[(rater_id, target_user_id)])
        if pair_comm_n.get((rater_id, target_user_id), 0):
            comm_avg = pair_comm_sum[(rater_id, target_user_id)] / float(pair_comm_n[(rater_id, target_user_id)])
        wwa_ratio = (
            pair_wwa_sum.get((rater_id, target_user_id), 0.0) / float(pair_wwa_n.get((rater_id, target_user_id), 1))
        )
        edges.append(
            {
                "source": rater_id,
                "target": target_user_id,
                "weight": float(s / float(n)),
                "count": int(n),
                "contribution_avg": contrib_avg,
                "communication_avg": comm_avg,
                "would_work_again_ratio": float(wwa_ratio),
            }
        )

    return jsonify({"nodes": nodes, "edges": edges})


@app.route("/api/lobbies/<int:lobby_id>/join-requests", methods=["POST"])
def api_create_join_request(lobby_id):
    from models import Lobby, Team, JoinRequest

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

    jr = JoinRequest(
        lobby_id=lobby.id,
        team_id=team.id,
        requester_id=user.id,
        status="pending",
    )
    db.session.add(jr)
    db.session.commit()
    return jsonify(jr.to_dict()), 201

@app.route("/api/lobbies/<int:lobby_id>/join-requests", methods=["GET"])
def api_list_join_requests(lobby_id):
    from models import Lobby, Team, JoinRequest

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
    from models import Lobby, Team, JoinRequest

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


if __name__ == "__main__":
    # run without the reloader to avoid external shell tool dependencies in some terminals
    app.run(debug=False)