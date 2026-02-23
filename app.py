import os
import secrets
import smtplib
from datetime import datetime
from email.message import EmailMessage
from typing import Optional, Dict, Any

from flask import (
    Flask,
    request,
    jsonify,
    session,
)
from flask_cors import CORS
from sqlalchemy import text
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db

app = Flask(__name__)
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
    # import models so tables are registered. Ignore imported but unused errors
    from models import (
        User,
        Lobby,
        Team,
        Submission,
        Rating,
        JoinRequest,
        Invitation,
        TeamMember,
    )

    db.create_all()

    # Minimal schema evolution for SQLite (no migration tool in this demo)
    _sqlite_add_column_if_missing("lobby", "finished", "finished BOOLEAN DEFAULT 0")
    _sqlite_add_column_if_missing("lobby", "finished_at", "finished_at DATETIME")
    _sqlite_add_column_if_missing("submission", "submitter_id", "submitter_id INTEGER")
    _sqlite_add_column_if_missing("user", "password_hash", "password_hash TEXT")

    if User.query.first() is None:
        from seed_db import seed_users

        seed_users()


def get_current_user() -> Optional["User"]:
    from models import User as UserModel

    user_id = session.get("user_id")
    if not user_id:
        return None
    return UserModel.query.get(user_id)


def _send_email(subject: str, to_email: str, body: str) -> None:
    """SMTP helper; falls back to stdout in local/classroom environments."""
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


def json_error(message: str, status: int = 400, extra: Optional[Dict[str, Any]] = None):
    payload: Dict[str, Any] = {"error": message}
    if extra:
        payload.update(extra)
    return jsonify(payload), status


@app.post("/api/auth/register")
def api_register():
    from models import User

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip() or "Anonymous"
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""
    major = (data.get("major") or "").strip() or None
    year = (data.get("year") or "").strip() or None
    bio = (data.get("bio") or "").strip() or None
    contact = (data.get("contact") or "").strip() or None
    phone = (data.get("phone") or "").strip() or None

    if not email or not email.lower().endswith("@duke.edu"):
        return json_error("email must end with @duke.edu")

    if not password or len(password) < 6:
        return json_error("password must be at least 6 characters")

    existing = User.query.filter_by(email=email).first()
    if existing:
        return json_error("email already exists")

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

    return jsonify({"user": user.to_dict()}), 201


@app.post("/api/auth/login")
def api_login():
    from models import User

    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""

    if not email or not password:
        return json_error("email and password are required")

    user = User.query.filter_by(email=email).first()
    if not user or not getattr(user, "password_hash", None):
        return json_error("invalid credentials", 401)

    if not check_password_hash(user.password_hash, password):
        return json_error("invalid credentials", 401)

    session["user_id"] = user.id
    return jsonify({"user": user.to_dict()}), 200


@app.post("/api/auth/logout")
def api_logout():
    session.pop("user_id", None)
    return jsonify({"success": True}), 200


@app.get("/api/auth/me")
def api_me():
    user = get_current_user()
    if not user:
        return jsonify({"user": None}), 200
    return jsonify({"user": user.to_dict()}), 200


@app.route("/api/users", methods=["GET", "POST"])
def api_users():
    from models import User, Team

    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        name = data.get("name", "Anonymous")
        email = (data.get("email") or "").strip()
        password = data.get("password")
        major = data.get("major")
        year = data.get("year")

        if not email or not email.lower().endswith("@duke.edu"):
            return json_error("email must end with @duke.edu")

        if not password:
            return json_error("password required")

        if User.query.filter_by(email=email).first():
            return json_error("email already exists")

        user = User(
            name=name,
            major=major,
            year=year,
            email=email,
            password_hash=generate_password_hash(password),
        )
        db.session.add(user)
        db.session.commit()

        # auto-join a lobby if lobby_id has been provided
        lobby_id = data.get("lobby_id")
        if lobby_id:
            try:
                lobby_id = int(lobby_id)
            except Exception:
                lobby_id = None
            if lobby_id:
                team = Team.query.filter_by(lobby_id=lobby_id).first()
                if team and not team.locked:
                    team.add_member(user.id)
                    db.session.commit()

        return jsonify(user.to_dict()), 201

    # GET
    users = User.query.order_by(User.name.asc()).all()
    return jsonify([u.to_dict() for u in users]), 200


@app.get("/api/users/<int:user_id>")
def api_get_user(user_id: int):
    from models import User

    user = User.query.get_or_404(user_id)
    data = user.to_dict()
    # assumes User.participated_lobbies returns JSON-serializable data
    data["lobbies"] = user.participated_lobbies()
    return jsonify(data), 200


@app.get("/api/users/<int:user_id>/reputation")
def api_user_reputation(user_id: int):
    from models import User

    user = User.query.get_or_404(user_id)
    return jsonify({"reputation": user.reputation()}), 200


@app.get("/api/lobbies")
def api_list_lobbies():
    from models import Lobby, Team

    qs = Lobby.query.order_by(Lobby.created_at.desc()).all()
    out = []
    for q in qs:
        teams = Team.query.filter_by(lobby_id=q.id).all()
        count = sum(len(t.members) for t in teams)
        d = q.to_dict()
        d["participant_count"] = count
        out.append(d)
    return jsonify(out), 200


@app.post("/api/lobbies")
def api_create_lobby():
    from models import Lobby, Team

    user = get_current_user()
    if not user:
        return json_error("not_logged_in", 401)

    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    contest_link = (data.get("contest_link") or "").strip() or None

    if not title:
        return json_error("title is required")

    lobby = Lobby(title=title, contest_link=contest_link, leader_id=user.id)
    db.session.add(lobby)
    db.session.commit()

    team = Team(lobby_id=lobby.id, locked=False)
    db.session.add(team)
    db.session.commit()

    # creator joins team by default
    team.add_member(user.id)
    db.session.commit()

    return jsonify(lobby.to_dict()), 201


@app.get("/api/lobbies/<int:lobby_id>")
def api_get_lobby(lobby_id: int):
    from models import Lobby, Team, User

    lobby = Lobby.query.get_or_404(lobby_id)

    teams = Team.query.filter_by(lobby_id=lobby.id).all()
    participants = []
    for t in teams:
        for tm in t.members:
            u = User.query.get(tm.user_id)
            if u:
                participants.append(u.to_dict())

    out = lobby.to_dict()
    out["participants"] = participants
    return jsonify(out), 200


@app.post("/api/lobbies/<int:lobby_id>/join")
def api_join_lobby(lobby_id: int):
    from models import Lobby, Team

    user = get_current_user()
    if not user:
        return json_error("not_logged_in", 401)

    lobby = Lobby.query.get_or_404(lobby_id)
    if lobby.finished:
        return json_error("contest finished")

    team = Team.query.filter_by(lobby_id=lobby.id).first()
    if not team:
        return json_error("team not found", 404)
    if team.locked:
        return json_error("team locked")

    if any(tm.user_id == user.id for tm in team.members):
        return json_error("already_member")

    team.add_member(user.id)
    db.session.commit()

    return jsonify(team.to_dict()), 200


@app.post("/api/lobbies/<int:lobby_id>/finish")
def api_finish_lobby(lobby_id: int):
    from models import Lobby

    user = get_current_user()
    if not user:
        return json_error("not_logged_in", 401)

    lobby = Lobby.query.get_or_404(lobby_id)
    if lobby.leader_id != user.id:
        return json_error("leader_only", 403)

    lobby.finished = True
    lobby.finished_at = datetime.utcnow()
    db.session.commit()

    return jsonify(lobby.to_dict()), 200


@app.post("/api/teams/<int:team_id>/lock")
def api_lock_team(team_id: int):
    from models import Team, Lobby

    user = get_current_user()
    if not user:
        return json_error("not_logged_in", 401)

    team = Team.query.get_or_404(team_id)
    lobby = Lobby.query.get(team.lobby_id)

    if lobby.leader_id != user.id:
        return json_error("leader_only", 403)

    team.locked = True
    db.session.commit()
    return jsonify(team.to_dict()), 200


@app.post("/api/teams/<int:team_id>/submit")
def api_submit_team(team_id: int):
    from models import Team, Submission, Lobby

    user = get_current_user()
    if not user:
        return json_error("not_logged_in", 401)

    team = Team.query.get_or_404(team_id)
    data = request.get_json(silent=True) or {}
    proof = data.get("proof")

    if not proof:
        return json_error("proof required")

    lobby = Lobby.query.get(team.lobby_id)
    if not lobby or not lobby.finished:
        return json_error("contest must be finished before submitting proof")

    submitter_id = data.get("submitter_id") or user.id
    member_ids = {tm.user_id for tm in team.members}
    if int(submitter_id) not in member_ids:
        return json_error("submitter must be a team member")

    submission = Submission(
        team_id=team.id, submitter_id=int(submitter_id), proof_link=proof
    )
    db.session.add(submission)
    db.session.commit()

    return jsonify(submission.to_dict()), 201


@app.post("/api/teams/<int:team_id>/ratings")
def api_rate_member(team_id: int):
    from models import Team, Rating, Lobby

    user = get_current_user()
    if not user:
        return json_error("not_logged_in", 401)

    team = Team.query.get_or_404(team_id)
    lobby = Lobby.query.get(team.lobby_id)
    if not lobby or not lobby.finished:
        return json_error("contest must be finished before ratings")

    data = request.get_json(silent=True) or {}
    member_ids = {tm.user_id for tm in team.members}

    rater_id = data.get("rater_id") or user.id
    target_user_id = data.get("target_user_id")

    if rater_id is None or target_user_id is None:
        return json_error("rater_id and target_user_id required")

    rater_id = int(rater_id)
    target_user_id = int(target_user_id)

    if rater_id not in member_ids or target_user_id not in member_ids:
        return json_error("rater and target must be team members")

    if rater_id == target_user_id:
        return json_error("cannot rate yourself")

    contribution = int(data.get("contribution", 0))
    communication = int(data.get("communication", 0))
    would_work_again = bool(data.get("would_work_again", False))
    comment = data.get("comment")

    existing = Rating.query.filter_by(
        team_id=team.id, rater_id=rater_id, target_user_id=target_user_id
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
        return jsonify(keep.to_dict()), 200

    r = Rating(
        team_id=team.id,
        rater_id=rater_id,
        target_user_id=target_user_id,
        contribution=contribution,
        communication=communication,
        would_work_again=would_work_again,
        comment=comment,
    )
    db.session.add(r)
    db.session.commit()

    return jsonify(r.to_dict()), 201


@app.post("/api/lobbies/<int:lobby_id>/join-requests")
def api_create_join_request(lobby_id: int):
    from models import Lobby, Team, JoinRequest

    user = get_current_user()
    if not user:
        return json_error("not_logged_in", 401)

    lobby = Lobby.query.get_or_404(lobby_id)
    team = Team.query.filter_by(lobby_id=lobby.id).first()
    if not team:
        return json_error("team_not_found", 404)

    if lobby.finished:
        return json_error("lobby_finished")
    if team.locked:
        return json_error("team_locked")
    if any(tm.user_id == user.id for tm in team.members):
        return json_error("already_member")

    existing = JoinRequest.query.filter_by(
        lobby_id=lobby.id,
        team_id=team.id,
        requester_id=user.id,
        status="pending",
    ).first()
    if existing:
        return json_error("already_pending", extra={"request": existing.to_dict()})

    jr = JoinRequest(
        lobby_id=lobby.id, team_id=team.id, requester_id=user.id, status="pending"
    )
    db.session.add(jr)
    db.session.commit()

    return jsonify(jr.to_dict()), 201


@app.get("/api/lobbies/<int:lobby_id>/join-requests")
def api_list_join_requests(lobby_id: int):
    from models import Lobby, Team, JoinRequest

    user = get_current_user()
    if not user:
        return json_error("not_logged_in", 401)

    lobby = Lobby.query.get_or_404(lobby_id)
    if lobby.leader_id != user.id:
        return json_error("leader_only", 403)

    team = Team.query.filter_by(lobby_id=lobby.id).first()
    if not team:
        return json_error("team_not_found", 404)

    status = (request.args.get("status") or "pending").strip().lower()

    q = JoinRequest.query.filter_by(lobby_id=lobby.id, team_id=team.id)
    if status in {"pending", "accepted", "rejected", "canceled"}:
        q = q.filter_by(status=status)

    reqs = q.order_by(JoinRequest.created_at.asc()).all()
    return jsonify([r.to_dict() for r in reqs]), 200


@app.post("/api/lobbies/<int:lobby_id>/join-requests/<int:request_id>/decision")
def api_decide_join_request(lobby_id: int, request_id: int):
    from models import Lobby, Team, JoinRequest

    user = get_current_user()
    if not user:
        return json_error("not_logged_in", 401)

    lobby = Lobby.query.get_or_404(lobby_id)
    if lobby.leader_id != user.id:
        return json_error("leader_only", 403)

    team = Team.query.filter_by(lobby_id=lobby.id).first()
    if not team:
        return json_error("team_not_found", 404)

    jr = JoinRequest.query.get_or_404(request_id)
    if jr.lobby_id != lobby.id or jr.team_id != team.id:
        return json_error("invalid_request")

    if jr.status != "pending":
        return json_error("not_pending", extra={"request": jr.to_dict()})

    data = request.get_json(silent=True) or {}
    decision = (data.get("decision") or "").strip().lower()
    if decision not in {"accept", "reject"}:
        return json_error("invalid_decision")

    if lobby.finished:
        return json_error("lobby_finished")
    if team.locked:
        return json_error("team_locked")

    if decision == "reject":
        jr.status = "rejected"
        db.session.commit()
        return jsonify(jr.to_dict()), 200

    # accept
    if any(tm.user_id == jr.requester_id for tm in team.members):
        jr.status = "accepted"
        db.session.commit()
        return jsonify(jr.to_dict()), 200

    team.add_member(jr.requester_id)
    jr.status = "accepted"
    db.session.commit()
    return jsonify(jr.to_dict()), 200


@app.post("/api/lobbies/<int:lobby_id>/invite")
def api_invite_to_lobby(lobby_id: int):
    from models import Lobby, Team, User, Invitation

    user = get_current_user()
    if not user:
        return json_error("not_logged_in", 401)

    lobby = Lobby.query.get_or_404(lobby_id)
    team = Team.query.filter_by(lobby_id=lobby.id).first()
    if not team:
        return json_error("team_not_found", 404)

    if lobby.finished:
        return json_error("lobby_finished")
    if team.locked:
        return json_error("team_locked")

    data = request.get_json(silent=True) or {}
    email = (data.get("target_email") or "").strip()
    if not email:
        return json_error("target_email required")

    target = User.query.filter_by(email=email).first()
    if not target:
        return json_error("user_not_found")

    if any(tm.user_id == target.id for tm in team.members):
        return json_error("already_member")

    existing = Invitation.query.filter_by(
        team_id=team.id, target_user_id=target.id, status="pending"
    ).first()
    if existing:
        return json_error("already_invited")

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

    accept_url = (
        f"{request.host_url.rstrip('/')}/api/invites/respond/{token}?action=accept"
    )
    reject_url = (
        f"{request.host_url.rstrip('/')}/api/invites/respond/{token}?action=reject"
    )

    subject = f"Team invite for '{lobby.title}' from {user.name}"
    body = (
        f"{user.name} has requested you join their team for lobby '{lobby.title}'.\n\n"
        f"Accept: {accept_url}\n"
        f"Reject: {reject_url}\n\n"
        f"If you didn't expect this, ignore this email."
    )
    _send_email(subject, target.email, body)

    return jsonify({"invitation": inv.to_dict(), "accept_url": accept_url}), 201


@app.get("/api/invites/respond/<token>")
def api_respond_invite(token: str):
    from models import Invitation, Team

    action = (request.args.get("action") or "").lower()
    inv = Invitation.query.filter_by(token=token).first()
    if not inv:
        return json_error("invalid_token", 404)

    if inv.status != "pending":
        return jsonify(
            {"message": "already_responded", "invitation": inv.to_dict()}
        ), 200

    if action == "accept":
        team = Team.query.get(inv.team_id)
        if team and not team.locked:
            team.add_member(inv.target_user_id)
            inv.status = "accepted"
            inv.responded_at = datetime.utcnow()
            db.session.commit()
            return jsonify({"message": "accepted", "invitation": inv.to_dict()}), 200
        return json_error("team_not_found_or_locked")

    if action == "reject":
        inv.status = "rejected"
        inv.responded_at = datetime.utcnow()
        db.session.commit()
        return jsonify({"message": "rejected", "invitation": inv.to_dict()}), 200

    return json_error("invalid_action")


if __name__ == "__main__":
    # debug=False to keep it simple in some environments
    app.run(host="127.0.0.1", port=5000, debug=True)
