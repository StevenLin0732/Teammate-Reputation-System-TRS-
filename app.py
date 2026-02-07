from flask import Flask, request, jsonify, render_template
import os

from extensions import db

app = Flask(__name__, template_folder='templates')
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'teamrank.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

with app.app_context():
    # import models so tables are registered
    from models import User, Lobby, Team, Submission, Rating
    db.create_all()


@app.route('/')
def index():
    return render_template('index.html')


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
    from models import Team, Submission
    team = Team.query.get_or_404(team_id)
    data = request.json or {}
    proof = data.get('proof')
    if not proof:
        return jsonify({'error': 'proof required'}), 400
    submission = Submission(team_id=team.id, proof_link=proof)
    db.session.add(submission)
    db.session.commit()
    return jsonify(submission.to_dict()), 201


@app.route('/api/teams/<int:team_id>/ratings', methods=['POST'])
def rate_member(team_id):
    from models import Team, Rating
    team = Team.query.get_or_404(team_id)
    if not team.submissions:
        return jsonify({'error': 'proof of submission required before ratings'}), 400
    data = request.json or {}
    r = Rating(
        team_id=team.id,
        rater_id=data.get('rater_id'),
        target_user_id=data.get('target_user_id'),
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
