from datetime import datetime
from extensions import db


def _clamp01(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def _normalize_0_to_10(value) -> float:
    if value is None:
        return 0.0
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.0
    # App UI/API uses 0..10 inputs.
    return _clamp01(v / 10.0)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    major = db.Column(db.String(120))
    year = db.Column(db.String(50))
    bio = db.Column(db.String(1000))
    contact = db.Column(db.String(500))
    phone = db.Column(db.String(80))
    email = db.Column(db.String(200))
    password_hash = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __init__(self, name, major, year, email, bio="", contact="", phone="0", password_hash=""):
        self.name = name
        self.major = major 
        self.year = year
        self.bio = bio
        self.contact = contact
        self.phone = phone
        self.email = email
        self.password_hash= password_hash

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

    @staticmethod
    def compute_transitive_trust_scores(
        *,
        damping: float = 0.85,
        max_iter: int = 50,
        tol: float = 1e-10,
    ) -> dict:
        """Compute a global trust/weight per user from the rating graph.

        This is a PageRank/EigenTrust-style power iteration over a normalized
        rater->target edge matrix derived from `Rating` rows.
        """

        user_ids = [row[0] for row in db.session.query(User.id).all()]
        n = len(user_ids)
        if n == 0:
            return {}

        idx_by_user_id = {user_id: i for i, user_id in enumerate(user_ids)}

        # NOTE: we collapse multiple ratings between the same (rater, target)
        # into a single averaged edge weight. This prevents simple “spam the
        # same person repeatedly” manipulation from increasing influence.
        outgoing_by_idx: list[dict[int, float]] = [dict() for _ in range(n)]
        outgoing_sum: list[float] = [0.0 for _ in range(n)]

        rows = db.session.query(
            Rating.rater_id,
            Rating.target_user_id,
            Rating.contribution,
            Rating.communication,
            Rating.would_work_again,
        ).all()

        pair_sum: dict[tuple[int, int], float] = {}
        pair_count: dict[tuple[int, int], int] = {}

        for rater_id, target_user_id, contribution, communication, would_work_again in rows:
            if rater_id is None or target_user_id is None:
                continue
            if rater_id == target_user_id:
                continue
            i = idx_by_user_id.get(rater_id)
            j = idx_by_user_id.get(target_user_id)
            if i is None or j is None:
                continue

            contrib_n = _normalize_0_to_10(contribution)
            comm_n = _normalize_0_to_10(communication)
            wwa_n = 1.0 if bool(would_work_again) else 0.0

            # Local trust in [0, 1]. Keep it non-negative so it can be normalized.
            local = (contrib_n + comm_n + wwa_n) / 3.0
            if local <= 0.0:
                continue

            key = (i, j)
            pair_sum[key] = pair_sum.get(key, 0.0) + local
            pair_count[key] = pair_count.get(key, 0) + 1

        for (i, j), s in pair_sum.items():
            c_ij = s / float(pair_count[(i, j)])
            outgoing_by_idx[i][j] = c_ij
            outgoing_sum[i] += c_ij

        # Personalization / pre-trust vector: uniform.
        base = 1.0 / n
        p = [base for _ in range(n)]

        # Initialize uniformly.
        t = [base for _ in range(n)]

        for _ in range(max_iter):
            new_t = [(1.0 - damping) * p_j for p_j in p]

            dangling_mass = 0.0
            for i in range(n):
                if outgoing_sum[i] <= 0.0:
                    dangling_mass += t[i]

            if dangling_mass:
                share = damping * (dangling_mass / n)
                for j in range(n):
                    new_t[j] += share

            for i in range(n):
                s = outgoing_sum[i]
                if s <= 0.0:
                    continue
                ti = t[i]
                if ti == 0.0:
                    continue
                for j, weight in outgoing_by_idx[i].items():
                    new_t[j] += damping * (weight / s) * ti

            diff = sum(abs(new_t[i] - t[i]) for i in range(n))
            t = new_t
            if diff < tol:
                break

        total = sum(t)
        if total > 0.0:
            t = [x / total for x in t]

        return {user_ids[i]: float(t[i]) for i in range(n)}

    def reputation(self, *, trust_scores=None):
        """Compute this user's (weighted) reputation.

        When `trust_scores` is provided, each incoming rating is weighted by the
        trust score of the rater. If not provided, trust scores are computed on
        demand from the whole rating graph.
        """

        from sqlalchemy import case, func

        if trust_scores is None:
            trust_scores = User.compute_transitive_trust_scores()

        # Collapse multiple ratings from the same rater into a single
        # per-rater summary (averages). This prevents repeated ratings from the
        # same account from having outsized impact.
        ratings = (
            db.session.query(
                Rating.rater_id,
                Rating.contribution,
                Rating.communication,
                Rating.would_work_again,
            )
            .filter(Rating.target_user_id == self.id)
            .all()
        )

        by_rater: dict[int, dict[str, float]] = {}
        for rater_id, contribution, communication, would_work_again in ratings:
            if rater_id is None:
                continue
            bucket = by_rater.get(rater_id)
            if bucket is None:
                bucket = {
                    "contrib_sum": 0.0,
                    "contrib_n": 0.0,
                    "comm_sum": 0.0,
                    "comm_n": 0.0,
                    "wwa_sum": 0.0,
                    "wwa_n": 0.0,
                }
                by_rater[rater_id] = bucket

            if contribution is not None:
                bucket["contrib_sum"] += float(contribution)
                bucket["contrib_n"] += 1.0
            if communication is not None:
                bucket["comm_sum"] += float(communication)
                bucket["comm_n"] += 1.0
            bucket["wwa_sum"] += 1.0 if bool(would_work_again) else 0.0
            bucket["wwa_n"] += 1.0

        contrib_num = 0.0
        contrib_den = 0.0
        comm_num = 0.0
        comm_den = 0.0
        wwa_num = 0.0
        wwa_den = 0.0

        for rater_id, bucket in by_rater.items():
            w = float(trust_scores.get(rater_id, 0.0))
            if w <= 0.0:
                continue

            contrib_avg_r = (
                (bucket["contrib_sum"] / bucket["contrib_n"]) if bucket["contrib_n"] else None
            )
            comm_avg_r = (
                (bucket["comm_sum"] / bucket["comm_n"]) if bucket["comm_n"] else None
            )
            wwa_ratio_r = (
                (bucket["wwa_sum"] / bucket["wwa_n"]) if bucket["wwa_n"] else 0.0
            )

            if contrib_avg_r is not None:
                contrib_num += w * float(contrib_avg_r)
                contrib_den += w
            if comm_avg_r is not None:
                comm_num += w * float(comm_avg_r)
                comm_den += w

            wwa_num += w * float(wwa_ratio_r)
            wwa_den += w

        avg_contrib = (contrib_num / contrib_den) if contrib_den else 0.0
        avg_comm = (comm_num / comm_den) if comm_den else 0.0

        total = (
            db.session.query(func.count(Rating.id))
            .filter(Rating.target_user_id == self.id)
            .scalar()
            or 0
        )

        return {
            "contribution_avg": round(float(avg_contrib), 2),
            "communication_avg": round(float(avg_comm), 2),
            "would_work_again_ratio": (wwa_num / wwa_den) if wwa_den else None,
            "rating_count": total,
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


class Invitation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lobby_id = db.Column(db.Integer, db.ForeignKey('lobby.id'))
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'))
    applicant_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    target_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    token = db.Column(db.String(200), unique=True, index=True)
    status = db.Column(db.String(50), default='pending')  # pending, accepted, rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    responded_at = db.Column(db.DateTime)

    def to_dict(self):
        return {
            'id': self.id,
            'lobby_id': self.lobby_id,
            'team_id': self.team_id,
            'applicant_id': self.applicant_id,
            'target_user_id': self.target_user_id,
            'token': self.token,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'responded_at': self.responded_at.isoformat() if self.responded_at else None,
        }

from datetime import datetime
from extensions import db

class JoinRequest(db.Model):
    __tablename__ = "join_request"

    id = db.Column(db.Integer, primary_key=True)
    lobby_id = db.Column(db.Integer, db.ForeignKey("lobby.id"), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey("team.id"), nullable=False)
    requester_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    status = db.Column(db.String(20), nullable=False, default="pending")  # pending/accepted/rejected/canceled
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "lobby_id": self.lobby_id,
            "team_id": self.team_id,
            "requester_id": self.requester_id,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }