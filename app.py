from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash
import os
import secrets
from datetime import datetime
from sqlalchemy import text

from extensions import db

app = Flask(__name__, template_folder='templates')
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'teamrank.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or secrets.token_hex(16)

db.init_app(app)

with app.app_context():
    # import models so tables are registered
    from models import User, Lobby, Team, Submission, Rating
    db.create_all()


def _sqlite_column_exists(table_name: str, column_name: str) -> bool:
    rows = db.session.execute(text(f"PRAGMA table_info({table_name})")).all()
    return any(r[1] == column_name for r in rows)


def _sqlite_add_column_if_missing(table_name: str, column_name: str, column_def_sql: str) -> None:
    if _sqlite_column_exists(table_name, column_name):
        return
    db.session.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_def_sql}"))
    db.session.commit()


with app.app_context():
    # Minimal schema evolution for SQLite (no migration tool in this demo)
    _sqlite_add_column_if_missing('lobby', 'finished', 'finished BOOLEAN DEFAULT 0')
    _sqlite_add_column_if_missing('lobby', 'finished_at', 'finished_at DATETIME')
    _sqlite_add_column_if_missing('submission', 'submitter_id', 'submitter_id INTEGER')


def get_current_user():
    from models import User
    user_id = session.get('user_id')
    if not user_id:
        return None
    return User.query.get(user_id)


@app.context_processor
def inject_current_user():
    return {'current_user': get_current_user()}


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    from models import User
    if request.method == 'POST':
        selected = request.form.get('user_id')
        try:
            selected_id = int(selected)
        except Exception:
            selected_id = None

        if not selected_id:
            flash('Please choose a user to continue.', 'warning')
            return redirect(url_for('login'))

        user = User.query.get(selected_id)
        if not user:
            flash('That user does not exist.', 'danger')
            return redirect(url_for('login'))

        session['user_id'] = user.id
        flash(f'Logged in as {user.name}.', 'success')
        next_url = request.args.get('next')
        return redirect(next_url or url_for('me'))

    users = User.query.order_by(User.name.asc()).all()
    return render_template('login.html', users=users)


@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    flash('Logged out.', 'secondary')
    return redirect(url_for('index'))


@app.route('/me')
def me():
    user = get_current_user()
    if not user:
        return redirect(url_for('login', next=url_for('me')))
    return redirect(url_for('user_profile', user_id=user.id))


@app.route('/users')
def users_page():
    from models import User
    users = User.query.order_by(User.name.asc()).all()
    rep_by_id = {u.id: u.reputation() for u in users}
    return render_template('users.html', users=users, rep_by_id=rep_by_id)


@app.route('/users/<int:user_id>', methods=['GET', 'POST'])
def user_profile(user_id):
    from models import User, Lobby, Team, TeamMember, Rating
    user = User.query.get_or_404(user_id)
    viewer = get_current_user()
    can_edit = viewer is not None and viewer.id == user.id

    if request.method == 'POST':
        if not can_edit:
            flash('You can only edit your own profile.', 'danger')
            return redirect(url_for('user_profile', user_id=user.id))

        # Single-field update (used by inline-edit modal)
        field = (request.form.get('field') or '').strip()
        if field:
            value = (request.form.get('value') or '').strip()
            allowed = {'name', 'major', 'year', 'bio', 'contact', 'phone', 'email'}
            if field not in allowed:
                flash('Invalid field.', 'danger')
                return redirect(url_for('user_profile', user_id=user.id))
            if field == 'name':
                if not value:
                    flash('Name cannot be empty.', 'warning')
                    return redirect(url_for('user_profile', user_id=user.id))
                user.name = value
            else:
                setattr(user, field, value or None)
        else:
            # Full-form update (legacy)
            if 'name' in request.form:
                user.name = (request.form.get('name') or user.name).strip() or user.name
            if 'major' in request.form:
                user.major = (request.form.get('major') or '').strip() or None
            if 'year' in request.form:
                user.year = (request.form.get('year') or '').strip() or None
            if 'bio' in request.form:
                user.bio = (request.form.get('bio') or '').strip() or None
            if 'contact' in request.form:
                user.contact = (request.form.get('contact') or '').strip() or None
            if 'phone' in request.form:
                user.phone = (request.form.get('phone') or '').strip() or None
            if 'email' in request.form:
                user.email = (request.form.get('email') or '').strip() or None

        db.session.commit()
        flash('Profile updated.', 'success')
        return redirect(url_for('user_profile', user_id=user.id))

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
        Lobby.query.filter(Lobby.id.in_(ids), Lobby.finished == True)
        .order_by(Lobby.finished_at.desc().nullslast(), Lobby.created_at.desc())
        .all()
    ) if ids else []

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
            contribution_avg = round(sum(r.contribution or 0 for r in ratings) / len(ratings), 2)
            communication_avg = round(sum(r.communication or 0 for r in ratings) / len(ratings), 2)
            would_work_again_ratio = sum(1 for r in ratings if r.would_work_again) / len(ratings)
        else:
            contribution_avg = 0
            communication_avg = 0
            would_work_again_ratio = None
        history.append(
            {
                'lobby': lobby,
                'rating_count': len(ratings),
                'contribution_avg': contribution_avg,
                'communication_avg': communication_avg,
                'would_work_again_ratio': would_work_again_ratio,
            }
        )

    overall_rep = user.reputation()
    return render_template('profile.html', user=user, can_edit=can_edit, history=history, overall_rep=overall_rep)


@app.route('/lobbies')
def lobbies_page():
    from models import Lobby, Team
    qs = Lobby.query.order_by(Lobby.created_at.desc()).all()
    lobbies = []
    viewer = get_current_user()
    for q in qs:
        team = Team.query.filter_by(lobby_id=q.id).first()
        participant_count = len(team.members) if team else 0
        d = q.to_dict()
        d['participant_count'] = participant_count
        d['team_locked'] = bool(team.locked) if team else False

        role = None
        if viewer:
            if q.leader_id and viewer.id == q.leader_id:
                role = 'Leader'
            elif team and any(tm.user_id == viewer.id for tm in team.members):
                role = 'Member'
        d['role'] = role
        lobbies.append(d)
    return render_template('lobbies.html', lobbies=lobbies)


@app.route('/lobbies/<int:lobby_id>', methods=['GET', 'POST'])
def lobby_detail(lobby_id):
    from models import Lobby, Team, User, Rating
    lobby = Lobby.query.get_or_404(lobby_id)
    team = Team.query.filter_by(lobby_id=lobby.id).first()
    leader = User.query.get(lobby.leader_id) if lobby.leader_id else None

    viewer = get_current_user()
    is_leader = viewer is not None and lobby.leader_id is not None and viewer.id == lobby.leader_id

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
            submitter = User.query.get(s.submitter_id) if getattr(s, 'submitter_id', None) else None
            submissions.append({'submission': s, 'submitter': submitter})
        submissions.sort(key=lambda x: (x['submission'].created_at or datetime.min), reverse=True)

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
                    'contribution': round(sum(r.contribution or 0 for r in rs) / len(rs), 2),
                    'communication': round(sum(r.communication or 0 for r in rs) / len(rs), 2),
                    'count': len(rs),
                }
            else:
                avg_by_target[m.id] = {'contribution': 0, 'communication': 0, 'count': 0}

    if request.method == 'POST':
        if not is_leader:
            flash('Only the lobby leader can modify lobby details.', 'danger')
            return redirect(url_for('lobby_detail', lobby_id=lobby.id))

        action = (request.form.get('action') or 'save').strip()
        if action == 'lock_team':
            if not team:
                flash('No team exists for this lobby.', 'danger')
                return redirect(url_for('lobby_detail', lobby_id=lobby.id))
            team.locked = True
            db.session.commit()
            flash('Team locked.', 'success')
            return redirect(url_for('lobby_detail', lobby_id=lobby.id))

        if action == 'finish_contest':
            lobby.finished = True
            lobby.finished_at = datetime.utcnow()
            db.session.commit()
            flash('Contest marked as finished. Team members can now submit proof and ratings.', 'success')
            return redirect(url_for('lobby_detail', lobby_id=lobby.id))

        # default: save lobby fields
        title = (request.form.get('title') or '').strip()
        contest_link = (request.form.get('contest_link') or '').strip() or None

        if not title:
            flash('Title is required.', 'warning')
            return redirect(url_for('lobby_detail', lobby_id=lobby.id))

        lobby.title = title
        lobby.contest_link = contest_link
        db.session.commit()
        flash('Lobby updated.', 'success')
        return redirect(url_for('lobby_detail', lobby_id=lobby.id))

    return render_template(
        'lobby_detail.html',
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
    )


@app.route('/lobbies/<int:lobby_id>/submissions/<int:submission_id>/delete', methods=['POST'])
def delete_proof_page(lobby_id, submission_id):
    from models import Lobby, Team, Submission
    user = get_current_user()
    if not user:
        return redirect(url_for('login', next=url_for('lobby_detail', lobby_id=lobby_id)))

    lobby = Lobby.query.get_or_404(lobby_id)
    team = Team.query.filter_by(lobby_id=lobby.id).first()
    if not team:
        flash('Team not found for this lobby.', 'danger')
        return redirect(url_for('lobby_detail', lobby_id=lobby.id))

    submission = Submission.query.get_or_404(submission_id)
    if submission.team_id != team.id:
        flash('Invalid submission.', 'danger')
        return redirect(url_for('lobby_detail', lobby_id=lobby.id))
    if submission.submitter_id != user.id:
        flash('You can only delete your own proof.', 'danger')
        return redirect(url_for('lobby_detail', lobby_id=lobby.id))

    db.session.delete(submission)
    db.session.commit()
    flash('Proof deleted.', 'secondary')
    return redirect(url_for('lobby_detail', lobby_id=lobby.id))


@app.route('/lobbies/<int:lobby_id>/submit', methods=['POST'])
def submit_proof_page(lobby_id):
    from models import Lobby, Team, Submission
    user = get_current_user()
    if not user:
        return redirect(url_for('login', next=url_for('lobby_detail', lobby_id=lobby_id)))

    lobby = Lobby.query.get_or_404(lobby_id)
    team = Team.query.filter_by(lobby_id=lobby.id).first()
    if not team:
        flash('Team not found for this lobby.', 'danger')
        return redirect(url_for('lobby_detail', lobby_id=lobby.id))

    if not lobby.finished:
        flash('Proof submission is only available after the contest is finished.', 'warning')
        return redirect(url_for('lobby_detail', lobby_id=lobby.id))

    if not any(tm.user_id == user.id for tm in team.members):
        flash('Only team members can submit proof.', 'danger')
        return redirect(url_for('lobby_detail', lobby_id=lobby.id))

    proof = (request.form.get('proof') or '').strip()
    if not proof:
        flash('Proof link/text is required.', 'warning')
        return redirect(url_for('lobby_detail', lobby_id=lobby.id))

    submission = Submission(team_id=team.id, submitter_id=user.id, proof_link=proof)
    db.session.add(submission)
    db.session.commit()
    flash('Proof submitted.', 'success')
    return redirect(url_for('lobby_detail', lobby_id=lobby.id))


@app.route('/lobbies/<int:lobby_id>/rate', methods=['POST'])
def rate_member_page(lobby_id):
    from models import Lobby, Team, Rating
    user = get_current_user()
    if not user:
        return redirect(url_for('login', next=url_for('lobby_detail', lobby_id=lobby_id)))

    lobby = Lobby.query.get_or_404(lobby_id)
    team = Team.query.filter_by(lobby_id=lobby.id).first()
    if not team:
        flash('Team not found for this lobby.', 'danger')
        return redirect(url_for('lobby_detail', lobby_id=lobby.id))

    if not lobby.finished:
        flash('Ratings are only available after the contest is finished.', 'warning')
        return redirect(url_for('lobby_detail', lobby_id=lobby.id))

    member_ids = {tm.user_id for tm in team.members}
    if user.id not in member_ids:
        flash('Only team members can submit ratings.', 'danger')
        return redirect(url_for('lobby_detail', lobby_id=lobby.id))

    try:
        target_user_id = int(request.form.get('target_user_id') or 0)
    except Exception:
        target_user_id = 0
    if target_user_id not in member_ids or target_user_id == user.id:
        flash('Choose a valid teammate to rate.', 'warning')
        return redirect(url_for('lobby_detail', lobby_id=lobby.id))

    try:
        contribution = int(request.form.get('contribution') or 0)
        communication = int(request.form.get('communication') or 0)
    except Exception:
        flash('Contribution and communication must be numbers.', 'warning')
        return redirect(url_for('lobby_detail', lobby_id=lobby.id))

    would_work_again = request.form.get('would_work_again') == 'on'
    comment = (request.form.get('comment') or '').strip() or None

    existing = Rating.query.filter_by(team_id=team.id, rater_id=user.id, target_user_id=target_user_id).all()
    if existing:
        keep = existing[0]
        keep.contribution = contribution
        keep.communication = communication
        keep.would_work_again = would_work_again
        keep.comment = comment
        for extra in existing[1:]:
            db.session.delete(extra)
        db.session.commit()
        flash('Rating updated.', 'success')
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
        flash('Rating submitted.', 'success')
    return redirect(url_for('lobby_detail', lobby_id=lobby.id))


@app.route('/lobbies/<int:lobby_id>/ratings/<int:rating_id>/delete', methods=['POST'])
def delete_rating_page(lobby_id, rating_id):
    from models import Lobby, Team, Rating
    user = get_current_user()
    if not user:
        return redirect(url_for('login', next=url_for('lobby_detail', lobby_id=lobby_id)))

    lobby = Lobby.query.get_or_404(lobby_id)
    team = Team.query.filter_by(lobby_id=lobby.id).first()
    if not team:
        flash('Team not found for this lobby.', 'danger')
        return redirect(url_for('lobby_detail', lobby_id=lobby.id))

    rating = Rating.query.get_or_404(rating_id)
    if rating.team_id != team.id:
        flash('Invalid rating.', 'danger')
        return redirect(url_for('lobby_detail', lobby_id=lobby.id))
    if rating.rater_id != user.id:
        flash('You can only delete ratings you posted.', 'danger')
        return redirect(url_for('lobby_detail', lobby_id=lobby.id))

    db.session.delete(rating)
    db.session.commit()
    flash('Rating deleted.', 'secondary')
    return redirect(url_for('lobby_detail', lobby_id=lobby.id))


@app.route('/lobbies/new', methods=['GET', 'POST'])
def create_lobby_page():
    user = get_current_user()
    if not user:
        return redirect(url_for('login', next=url_for('create_lobby_page')))

    if request.method == 'POST':
        from models import Lobby, Team
        title = (request.form.get('title') or '').strip()
        contest_link = (request.form.get('contest_link') or '').strip() or None

        if not title:
            flash('Title is required.', 'warning')
            return redirect(url_for('create_lobby_page'))

        lobby = Lobby(title=title, contest_link=contest_link, leader_id=user.id)
        db.session.add(lobby)
        db.session.commit()

        team = Team(lobby_id=lobby.id, locked=False)
        db.session.add(team)
        db.session.commit()

        # creator joins by default
        team.add_member(user.id)
        db.session.commit()

        flash('Lobby created.', 'success')
        return redirect(url_for('lobbies_page'))

    return render_template('lobby_new.html')


@app.route('/lobbies/<int:lobby_id>/join', methods=['POST'])
def join_lobby_page(lobby_id):
    user = get_current_user()
    if not user:
        return redirect(url_for('login', next=url_for('lobby_detail', lobby_id=lobby_id)))

    from models import Lobby, Team
    lobby = Lobby.query.get_or_404(lobby_id)
    team = Team.query.filter_by(lobby_id=lobby.id).first()
    if not team:
        flash('Team not found for this lobby.', 'danger')
        return redirect(url_for('lobbies_page'))
    if lobby.finished:
        flash('This contest is finished; joining is disabled.', 'warning')
        return redirect(url_for('lobby_detail', lobby_id=lobby.id))
    if team.locked:
        return redirect(url_for('lobby_detail', lobby_id=lobby.id))

    team.add_member(user.id)
    db.session.commit()
    flash('Joined lobby.', 'success')
    return redirect(url_for('lobby_detail', lobby_id=lobby.id))


@app.route('/api/users', methods=['GET', 'POST'])
def users():
    from models import User
    if request.method == 'POST':
        data = request.json or {}
        user = User(name=data.get('name', 'Anonymous'), major=data.get('major'), year=data.get('year'))
        db.session.add(user)
        db.session.commit()
        # optional: auto-join a lobby if lobby_id provided
        lobby_id = data.get('lobby_id')
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


@app.route('/api/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    from models import User
    user = User.query.get_or_404(user_id)
    data = user.to_dict()
    data['lobbies'] = user.participated_lobbies()
    return jsonify(data)


@app.route('/api/lobbies/<int:lobby_id>', methods=['GET'])
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
    out['participants'] = participants
    return jsonify(out)


@app.route('/api/lobbies', methods=['GET', 'POST'])
def lobbies():
    from models import Lobby, Team
    if request.method == 'POST':
        data = request.json or {}
        lobby = Lobby(title=data.get('title', 'Untitled'), contest_link=data.get('contest_link'), leader_id=data.get('leader_id'))
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
        d['participant_count'] = count
        out.append(d)
    return jsonify(out)


@app.route('/api/lobbies/<int:lobby_id>/join', methods=['POST'])
def join_lobby(lobby_id):
    from models import Lobby, Team
    data = request.json or {}
    user_id = data.get('user_id')
    lobby = Lobby.query.get_or_404(lobby_id)
    if lobby.finished:
        return jsonify({'error': 'contest finished'}), 400
    team = Team.query.filter_by(lobby_id=lobby.id).first()
    if not team:
        return jsonify({'error': 'team not found'}), 404
    if team.locked:
        return jsonify({'error': 'team locked'}), 400
    team.add_member(user_id)
    db.session.commit()
    return jsonify(team.to_dict())


@app.route('/api/teams/<int:team_id>/lock', methods=['POST'])
def lock_team(team_id):
    from models import Team
    team = Team.query.get_or_404(team_id)
    team.locked = True
    db.session.commit()
    return jsonify(team.to_dict())


@app.route('/api/teams/<int:team_id>/submit', methods=['POST'])
def submit_team(team_id):
    from models import Team, Submission, Lobby
    team = Team.query.get_or_404(team_id)
    data = request.json or {}
    proof = data.get('proof')
    if not proof:
        return jsonify({'error': 'proof required'}), 400
    lobby = Lobby.query.get(team.lobby_id)
    if not lobby or not lobby.finished:
        return jsonify({'error': 'contest must be finished before submitting proof'}), 400
    submitter_id = data.get('submitter_id')
    if submitter_id is None:
        return jsonify({'error': 'submitter_id required'}), 400
    member_ids = {tm.user_id for tm in team.members}
    if int(submitter_id) not in member_ids:
        return jsonify({'error': 'submitter must be a team member'}), 400
    submission = Submission(team_id=team.id, submitter_id=int(submitter_id), proof_link=proof)
    db.session.add(submission)
    db.session.commit()
    return jsonify(submission.to_dict()), 201


@app.route('/api/teams/<int:team_id>/ratings', methods=['POST'])
def rate_member(team_id):
    from models import Team, Rating, Lobby
    team = Team.query.get_or_404(team_id)
    lobby = Lobby.query.get(team.lobby_id)
    if not lobby or not lobby.finished:
        return jsonify({'error': 'contest must be finished before ratings'}), 400
    data = request.json or {}
    member_ids = {tm.user_id for tm in team.members}
    rater_id = data.get('rater_id')
    target_user_id = data.get('target_user_id')
    if rater_id is None or target_user_id is None:
        return jsonify({'error': 'rater_id and target_user_id required'}), 400
    if int(rater_id) not in member_ids or int(target_user_id) not in member_ids:
        return jsonify({'error': 'rater and target must be team members'}), 400
    if int(rater_id) == int(target_user_id):
        return jsonify({'error': 'cannot rate yourself'}), 400
    r = Rating(
        team_id=team.id,
        rater_id=int(rater_id),
        target_user_id=int(target_user_id),
        contribution=int(data.get('contribution', 0)),
        communication=int(data.get('communication', 0)),
        would_work_again=bool(data.get('would_work_again', False)),
        comment=data.get('comment')
    )
    db.session.add(r)
    db.session.commit()
    return jsonify(r.to_dict()), 201


@app.route('/api/users/<int:user_id>/reputation')
def user_reputation(user_id):
    from models import User
    user = User.query.get_or_404(user_id)
    return jsonify(user.reputation())


if __name__ == '__main__':
    # run without the reloader to avoid external shell tool dependencies in some terminals
    app.run(debug=False)
