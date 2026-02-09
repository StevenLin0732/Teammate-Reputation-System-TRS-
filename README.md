# TeamRank Prototype

This is a minimal runnable prototype (Flask + SQLite) demonstrating the core flow: create users, open lobbies, join teams, submit proof, and provide peer ratings (ratings require a prior submission).

## Setup

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

## TODO (MVP Demo Checklist)

Goal: ship a bare-minimum demo that shows the full loop — **Profile → Lobby → Handshake/Team → Proof → Rate → Reputation updates**.

### Backend / Data (Person A)

- [ ] Add user “Teammate CV” fields (minimal): `github_url`, `linkedin_url`, `skills` (simple string/JSON is fine for demo)
- [ ] Add lobby fields: `status` ("looking_for_members" | "looking_to_join") and `deadline` (datetime/date)
- [ ] Implement a simple “handshake” join flow:
	- [ ] User requests to join a lobby/team
	- [ ] Leader lists pending requests
	- [ ] Leader accepts/rejects (accept adds member)
- [ ] Enforce contest-timeline rule: ratings only allowed after `deadline` (keep existing proof-of-submission gate)
- [ ] Make `/api/users/<id>/reputation` return demo-friendly labels (e.g., Reliability + Skill; can map from communication + contribution)
- [ ] Quick sanity test via curl/Postman (happy path end-to-end)

### Frontend Demo UI (Person B)

- [ ] Replace the placeholder homepage with a simple single-page demo UI:
	- [ ] Create/select user
	- [ ] Create/list lobbies (show contest link, status, deadline)
	- [ ] Lobby detail: participants + pending requests (leader view)
	- [ ] “Request to join” button (non-leader view)
	- [ ] Lock team button
	- [ ] Submit proof link form
	- [ ] Rate teammates form (unlocked after deadline + proof)
	- [ ] Reputation widget on user profile (shows updated values)
- [ ] Minimal styling in `static/main.css` for presentation readability

### Seed + Demo Script (Person C)

- [ ] Expand `seed_db.py` to generate:
	- [ ] 6–10 users with varied majors/skills
	- [ ] 2–3 lobbies with different statuses/deadlines
	- [ ] At least one lobby with a locked team + proof + a few ratings (so the UI looks “alive” immediately)
- [ ] Write a short click-through demo script (60–90 seconds): show loop + proof gate + reputation change
- [ ] Add README “Demo steps” bullets (exact buttons/sequence to click)