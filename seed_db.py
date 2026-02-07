from app import app
from extensions import db
from models import User, Lobby, Team

def seed():
    with app.app_context():
        db.drop_all()
        db.create_all()
        u1 = User(name='Alice', major='CS', year='Senior', bio='Full-stack developer, likes algorithms and mentoring. Experienced in Python and Flask.', contact='alice@example.com', phone='555-0101', email='alice@example.com')
        u2 = User(name='Bob', major='Design', year='Junior', bio='UI/UX designer who focuses on clean interfaces and prototyping.', contact='https://dribbble.com/bob', phone='555-0202', email='bob@example.com')
        u3 = User(name='Carol', major='Business', year='Senior', bio='Business analyst and project manager—good at planning and coordination.', contact='carol@example.com', phone='555-0303', email='carol@example.com')
        db.session.add_all([u1, u2, u3])
        db.session.commit()
        l1 = Lobby(title='ICPC Regional 2026 Team', contest_link='https://icpc.example', leader_id=u1.id)
        l2 = Lobby(title='Challenge Cup Team', contest_link='https://www.ChallengeCup.com', leader_id=None)
        db.session.add(l1)
        db.session.commit()
        t1 = Team(lobby_id=l1.id)
        t2 = Team(lobby_id=l2.id)
        db.session.add_all([t1, t2])
        db.session.commit()
        # add members: Alice+Bob in t1, Carol in t2
        t1.add_member(u1.id)
        t1.add_member(u2.id)
        t2.add_member(u3.id)
        db.session.commit()
        print('Seeded sample users and lobby')

if __name__ == '__main__':
    seed()
