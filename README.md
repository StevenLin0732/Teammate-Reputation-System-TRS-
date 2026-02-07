# TeamRank Prototype

This is a minimal runnable prototype (Flask + SQLite) demonstrating the core flow: create users, open lobbies, join teams, submit proof, and provide peer ratings (ratings require a prior submission).

Getting started:

1. Create and activate a Python virtual environment (optional but recommended)

```bash
python -m venv venv
venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Populate sample data:

```bash
python seed_db.py
```

4. Start the app:

```bash
python app.py
```

5. Open your browser at http://127.0.0.1:5000/ to view the simple frontend demo.

API overview:
- `GET /api/users`  — list users
- `POST /api/users` — create a user, JSON {name, major, year, lobby_id?}
- `GET /api/lobbies` — list lobbies
- `POST /api/lobbies` — create a lobby, JSON {title, contest_link, leader_id}
- `GET /api/lobbies/<id>` — get lobby details (includes participants)
- `POST /api/lobbies/<id>/join` — join a lobby, JSON {user_id}
- `POST /api/teams/<id>/submit` — submit proof, JSON {proof: 'url or text'}
- `POST /api/teams/<id>/ratings` — submit a rating (requires submission) JSON {rater_id, target_user_id, contribution, communication, would_work_again, comment}
