from datetime import datetime
from extensions import db


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    major = db.Column(db.String(120))
    year = db.Column(db.String(50))
    bio = db.Column(db.String(1000))
    contact = db.Column(db.String(500))
    phone = db.Column(db.String(80))
    email = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'major': self.major,
            'year': self.year,
            'bio': self.bio,
            'contact': self.contact,
            'phone': self.phone,
            'email': self.email,
        }

    def participated_lobbies(self):
        # return list of lobbies this user is part of
        from models import Lobby, TeamMember, Team
        # query lobbies by joining TeamMember->Team->Lobby
        lobbies = db.session.query(Lobby).join(Team).join(TeamMember, Team.id == TeamMember.team_id).filter(TeamMember.user_id == self.id).all()
        return [l.to_dict() for l in lobbies]

    def reputation(self):
        # compute averages of ratings where target_user_id == self.id
        from sqlalchemy import case, func
        avg_contrib = db.session.query(func.avg(Rating.contribution)).filter(Rating.target_user_id == self.id).scalar() or 0
        avg_comm = db.session.query(func.avg(Rating.communication)).filter(Rating.target_user_id == self.id).scalar() or 0
        would_work_again_count = (
            db.session.query(
                func.sum(
                    case(
                        (Rating.would_work_again.is_(True), 1),
                        else_=0,
                    )
                )
            )
            .filter(Rating.target_user_id == self.id)
            .scalar()
            or 0
        )
        total = db.session.query(func.count(Rating.id)).filter(Rating.target_user_id == self.id).scalar() or 0
        return {
            'contribution_avg': round(float(avg_contrib), 2),
            'communication_avg': round(float(avg_comm), 2),
            'would_work_again_ratio': float(would_work_again_count) / total if total else None,
            'rating_count': total
        }


class Lobby(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    contest_link = db.Column(db.String(500))
    leader_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    finished = db.Column(db.Boolean, default=False)
    finished_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'contest_link': self.contest_link,
            'leader_id': self.leader_id,
            'finished': self.finished,
            'finished_at': self.finished_at.isoformat() if self.finished_at else None,
        }

    teams = db.relationship('Team', backref='lobby', cascade='all, delete-orphan')


class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lobby_id = db.Column(db.Integer, db.ForeignKey('lobby.id'))
    locked = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    members = db.relationship('TeamMember', backref='team', cascade='all, delete-orphan')
    submissions = db.relationship('Submission', backref='team', cascade='all, delete-orphan')

    def add_member(self, user_id):
        if any(tm.user_id == user_id for tm in self.members):
            return
        tm = TeamMember(team_id=self.id, user_id=user_id)
        db.session.add(tm)

    def to_dict(self):
        return {
            'id': self.id,
            'lobby_id': self.lobby_id,
            'locked': self.locked,
            'members': [m.user_id for m in self.members],
            'submissions': [s.to_dict() for s in self.submissions]
        }


class TeamMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))


class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'))
    submitter_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    proof_link = db.Column(db.String(1000))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'team_id': self.team_id,
            'submitter_id': self.submitter_id,
            'proof_link': self.proof_link,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Rating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'))
    rater_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    target_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    contribution = db.Column(db.Integer)
    communication = db.Column(db.Integer)
    would_work_again = db.Column(db.Boolean, default=False)
    comment = db.Column(db.String(1000))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'team_id': self.team_id,
            'rater_id': self.rater_id,
            'target_user_id': self.target_user_id,
            'contribution': self.contribution,
            'communication': self.communication,
            'would_work_again': self.would_work_again,
            'comment': self.comment,
        }
