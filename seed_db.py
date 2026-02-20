from datetime import datetime, timedelta
import random
import re
from app import app
from extensions import db
from models import User, Lobby, Team, Submission, Rating
from werkzeug.security import generate_password_hash


def reset_db():
    db.drop_all()
    db.create_all()


def seed_users():
    users = [
        User(
            name="Alice Zhang",
            major="CS",
            year="2027",
            bio="Backend-focused. Flask + SQLAlchemy + SQLite. Strong with API design and data modeling.",
            contact="GitHub: github.com/alicezhang | Discord: alice#1024 | LinkedIn: linkedin.com/in/alicezhang",
            phone="919-555-0101",
            email="alice.zhang@example.com",
        ),
        User(
            name="Bob Lin",
            major="Math",
            year="2026",
            bio="Algorithms & systems. Strong in C++/Python, optimization, and debugging edge cases.",
            contact="GitHub: github.com/boblin | Discord: bob#2048 | WeChat: boblin_math",
            phone="919-555-0102",
            email="bob.lin@example.com",
        ),
        User(
            name="Cathy Wu",
            major="Data Science",
            year="2027",
            bio="ML & data. Pandas/Numpy, evaluation metrics, feature engineering, baseline modeling.",
            contact="GitHub: github.com/cathywu | LinkedIn: linkedin.com/in/cathywu | Discord: cathy#7788",
            phone="919-555-0103",
            email="cathy.wu@example.com",
        ),
        User(
            name="David Chen",
            major="ECE",
            year="2026",
            bio="Frontend + integration. JavaScript/HTML/CSS, Bootstrap, and wiring UI to REST APIs.",
            contact="GitHub: github.com/davidchen | Discord: david#3344 | Portfolio: davidchen.dev",
            phone="919-555-0104",
            email="david.chen@example.com",
        ),
        User(
            name="Evan Li",
            major="Business",
            year="2028",
            bio="Product & pitching. Milestones, demos, writing clear requirements, and presenting.",
            contact="LinkedIn: linkedin.com/in/evanli | Discord: evan#5566 | Email preferred",
            phone="919-555-0105",
            email="evan.li@example.com",
        ),
        User(
            name="Fiona Wang",
            major="CS",
            year="2028",
            bio="UI/UX. Bootstrap layouts, usability-focused flows, quick iteration with clean styling.",
            contact="GitHub: github.com/fionawang | Behance: behance.net/fionawang | Discord: fiona#1212",
            phone="919-555-0106",
            email="fiona.wang@example.com",
        ),
        User(
            name="Grace Zhao",
            major="Statistics",
            year="2027",
            bio="Experimentation & analytics. A/B tests, scoring robustness, and communicating results.",
            contact="LinkedIn: linkedin.com/in/gracezhao | Discord: grace#9090 | WeChat: grace_stats",
            phone="919-555-0107",
            email="grace.zhao@example.com",
        ),
        User(
            name="Henry Sun",
            major="Physics",
            year="2026",
            bio="Systems + performance. Profiling, reliability, and making code stable under constraints.",
            contact="GitHub: github.com/henrysun | Discord: henry#7878 | Email preferred",
            phone="919-555-0108",
            email="henry.sun@example.com",
        ),
        User(
            name="Ivy Gao",
            major="CS",
            year="2027",
            bio="Backend engineer. CRUD APIs, schema design, and clean service boundaries.",
            contact="GitHub: github.com/ivygao | Discord: ivy#2323 | LinkedIn: linkedin.com/in/ivygao",
            phone="919-555-0109",
            email="ivy.gao@example.com",
        ),
        User(
            name="Jack He",
            major="Math",
            year="2027",
            bio="Logic + algorithms. Correctness, tests, and writing clean maintainable code.",
            contact="GitHub: github.com/jackhe | Discord: jack#1717 | WeChat: jack_logic",
            phone="919-555-0110",
            email="jack.he@example.com",
        ),
        User(
            name="Kelly Huang",
            major="Economics",
            year="2028",
            bio="Research & narrative. Surveys, validating assumptions, and polishing documentation.",
            contact="LinkedIn: linkedin.com/in/kellyhuang | Discord: kelly#4848 | Email preferred",
            phone="919-555-0111",
            email="kelly.huang@example.com",
        ),
        User(
            name="Leo Xu",
            major="CS",
            year="2026",
            bio="DevOps mindset. Git workflows, CI basics, and keeping repos organized for teamwork.",
            contact="GitHub: github.com/leoxu | Discord: leo#6060 | Email preferred",
            phone="919-555-0112",
            email="leo.xu@example.com",
        ),
        User(
            name="Mia Yang",
            major="Data Science",
            year="2026",
            bio="Visualization & dashboards. Clear charts, summary pages, and interpreting patterns.",
            contact="GitHub: github.com/miayang | Discord: mia#3131 | Portfolio: miayang.dev",
            phone="919-555-0113",
            email="mia.yang@example.com",
        ),
        User(
            name="Noah Liu",
            major="ECE",
            year="2028",
            bio="Hardware-software bridge. Careful debugging and reliable implementation habits.",
            contact="GitHub: github.com/noahliu | Discord: noah#1414 | WeChat: noah_ece",
            phone="919-555-0114",
            email="noah.liu@example.com",
        ),
        User(
            name="Olivia Qian",
            major="CS",
            year="2027",
            bio="Frontend specialist. Strong HTML/CSS, solid UX intuition, quick UI iteration.",
            contact="GitHub: github.com/oliviaqian | Discord: olivia#8888 | Portfolio: oliviaqian.dev",
            phone="919-555-0115",
            email="olivia.qian@example.com",
        ),
        User(
            name="Peter Ren",
            major="Statistics",
            year="2026",
            bio="Metrics & evaluation. Reputation aggregation, robustness, and reducing noisy ratings.",
            contact="LinkedIn: linkedin.com/in/peterren | Discord: peter#2525 | WeChat: peter_stats",
            phone="919-555-0116",
            email="peter.ren@example.com",
        ),
        User(
            name="Quinn Zhou",
            major="Business",
            year="2027",
            bio="Operations. Standups, task tracking, and keeping teams on schedule.",
            contact="LinkedIn: linkedin.com/in/quinnzhou | Discord: quinn#3636 | Email preferred",
            phone="919-555-0117",
            email="quinn.zhou@example.com",
        ),
        User(
            name="Ruby Tang",
            major="Physics",
            year="2028",
            bio="Simulation & problem solving. Turns vague specs into testable steps and clean logic.",
            contact="GitHub: github.com/rubytang | Discord: ruby#4545 | Email preferred",
            phone="919-555-0118",
            email="ruby.tang@example.com",
        ),
        User(
            name="Sam Gu",
            major="CS",
            year="2026",
            bio="Full-stack generalist. Flask + templates, basic JS, and connecting forms to routes.",
            contact="GitHub: github.com/samgu | Discord: sam#5656 | LinkedIn: linkedin.com/in/samgu",
            phone="919-555-0119",
            email="sam.gu@example.com",
        ),
        User(
            name="Tina Fan",
            major="Data Science",
            year="2028",
            bio="Data cleaning & ML basics. Prepares datasets, runs baselines, writes experiment notes.",
            contact="GitHub: github.com/tinafan | Discord: tina#6767 | Email preferred",
            phone="919-555-0120",
            email="tina.fan@example.com",
        ),
        User(
            name="Uma Shen",
            major="Economics",
            year="2027",
            bio="Research & writing. Strong documentation, proposals, and summarizing decisions.",
            contact="LinkedIn: linkedin.com/in/umashen | Discord: uma#7870 | Email preferred",
            phone="919-555-0121",
            email="uma.shen@example.com",
        ),
        User(
            name="Victor Ma",
            major="CS",
            year="2028",
            bio="Competitive programming. Fast implementation, strong debugging, and constraints handling.",
            contact="GitHub: github.com/victorma | Discord: victor#8989 | WeChat: victor_cp",
            phone="919-555-0122",
            email="victor.ma@example.com",
        ),
        User(
            name="Wendy Luo",
            major="ECE",
            year="2027",
            bio="UI + integration. Polishing flows, form validation, and improving user experience.",
            contact="GitHub: github.com/wendyluo | Discord: wendy#9091 | Portfolio: wendyluo.dev",
            phone="919-555-0123",
            email="wendy.luo@example.com",
        ),
        User(
            name="Xavier Deng",
            major="Statistics",
            year="2028",
            bio="Scoring systems. Interested in robust aggregation and reducing gaming of ratings.",
            contact="LinkedIn: linkedin.com/in/xavierdeng | Discord: xavier#1010 | Email preferred",
            phone="919-555-0124",
            email="xavier.deng@example.com",
        ),
    ]
    # regenerate emails to firstname + 3 random digits @duke.com (lowercase, unique)
    used = set()
    for u in users:
        # derive base from first token of name
        first = (u.name or 'user').split()[0].lower()
        base = re.sub('[^a-z0-9]', '', first)
        if not base:
            base = 'user'
        # pick unique 3-digit suffix
        for _ in range(1000):
            suffix = random.randint(100, 999)
            email = f"{base}{suffix}@duke.com"
            if email not in used:
                used.add(email)
                u.email = email
                # set default password for seeded users
                u.password_hash = generate_password_hash('123456')
                break

    db.session.add_all(users)
    db.session.commit()
    return users


def create_lobby(title, link, leader_id, finished=False, finished_at=None):
    lobby = Lobby(
        title=title,
        contest_link=link,
        leader_id=leader_id,
        finished=finished,
        finished_at=finished_at,
    )
    db.session.add(lobby)
    db.session.commit()
    return lobby


def create_team(lobby_id, locked=False):
    team = Team(lobby_id=lobby_id, locked=locked)
    db.session.add(team)
    db.session.commit()
    return team


def add_members(team, user_ids):
    for uid in user_ids:
        team.add_member(uid)
    db.session.commit()


def seed_submission(team_id, submitter_id, proof_link):
    s = Submission(team_id=team_id, submitter_id=submitter_id, proof_link=proof_link)
    db.session.add(s)
    db.session.commit()
    return s


def seed_ratings_full_matrix(team_id, member_ids, salt=0):
    ratings = []
    for i, rater in enumerate(member_ids):
        for j, target in enumerate(member_ids):
            if rater == target:
                continue
            contribution = 6 + ((i + 2 * j + salt) % 5)
            communication = 6 + ((2 * i + j + salt) % 5)
            would_work_again = ((i + j + salt) % 2 == 0)
            ratings.append(
                Rating(
                    team_id=team_id,
                    rater_id=rater,
                    target_user_id=target,
                    contribution=contribution,
                    communication=communication,
                    would_work_again=would_work_again,
                    comment=f"demo rating {rater}->{target}",
                )
            )
    db.session.add_all(ratings)
    db.session.commit()


def group_for_lobby(user_ids, lobby_index, group_size=4):
    n = len(user_ids)
    start = (lobby_index * group_size) % n
    group = []
    for k in range(group_size):
        group.append(user_ids[(start + k) % n])
    if len(set(group)) < 2:
        group = [user_ids[start], user_ids[(start + 1) % n]]
    return group


def seed_finished_lobby(users, lobby_index, title, link, days_ago):
    user_ids = [u.id for u in users]
    members = group_for_lobby(user_ids, lobby_index, group_size=4)
    leader_id = members[0]

    lobby = create_lobby(
        title=title,
        link=link,
        leader_id=leader_id,
        finished=True,
        finished_at=datetime.now() - timedelta(days=days_ago),
    )

    team = create_team(lobby.id, locked=True)
    add_members(team, members)

    seed_submission(team.id, submitter_id=leader_id, proof_link=f"https://devpost.com/software/{lobby.id}-{team.id}")
    seed_ratings_full_matrix(team.id, members, salt=(lobby.id + lobby_index))
    return lobby


def seed_open_lobby(users, lobby_index, title, link, locked=False):
    user_ids = [u.id for u in users]
    members = group_for_lobby(user_ids, lobby_index, group_size=4)
    leader_id = members[0]

    lobby = create_lobby(
        title=title,
        link=link,
        leader_id=leader_id,
        finished=False,
        finished_at=None,
    )

    team = create_team(lobby.id, locked=locked)
    add_members(team, members)
    return lobby


def main():
    with app.app_context():
        reset_db()
        users = seed_users()

        seed_finished_lobby(users, 0, "Hackathon A", "https://example.com/hackathon-a", 1)
        seed_finished_lobby(users, 1, "Hackathon B", "https://example.com/hackathon-b", 3)
        seed_finished_lobby(users, 2, "Hackathon C", "https://example.com/hackathon-c", 7)
        seed_finished_lobby(users, 3, "Hackathon D", "https://example.com/hackathon-d", 10)

        seed_open_lobby(users, 4, "Contest E", "https://example.com/contest-e", locked=False)
        seed_open_lobby(users, 5, "Contest F", "https://example.com/contest-f", locked=False)
        seed_open_lobby(users, 6, "Contest G", "https://example.com/contest-g", locked=True)
        seed_open_lobby(users, 7, "Contest H", "https://example.com/contest-h", locked=False)
        seed_open_lobby(users, 8, "Contest I", "https://example.com/contest-i", locked=True)
        seed_open_lobby(users, 9, "Contest J", "https://example.com/contest-j", locked=False)

        print("Seed complete.")


if __name__ == "__main__":
    main()
