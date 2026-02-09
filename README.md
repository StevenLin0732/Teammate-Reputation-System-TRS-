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

## API Overview (JSON)

The UI pages use server-rendered HTML, but the app also exposes JSON endpoints you can call with curl/Postman.

### Users

- `GET /api/users` — list users
- `POST /api/users` — create a user
	- Body: `{ "name": "...", "major": "...", "year": "...", "lobby_id"?: 1 }`
- `GET /api/users/<id>` — get one user (includes list of participated lobbies)
- `GET /api/users/<id>/reputation` — aggregate reputation for the user

### Lobbies / Teams

- `GET /api/lobbies` — list lobbies
- `POST /api/lobbies` — create a lobby (also creates an initial team)
	- Body: `{ "title": "...", "contest_link": "...", "leader_id": 1 }`
- `GET /api/lobbies/<id>` — get lobby details (includes participants)
- `POST /api/lobbies/<id>/join` — join the lobby’s team (disabled if contest finished or team locked)
	- Body: `{ "user_id": 1 }`
- `POST /api/teams/<id>/lock` — lock a team

### Proof + Ratings (post-contest)

- `POST /api/teams/<id>/submit` — submit proof of submission
	- Requires: the lobby is marked finished
	- Requires: submitter is a team member
	- Body: `{ "proof": "url or text", "submitter_id": 1 }`
- `POST /api/teams/<id>/ratings` — submit a rating
	- Requires: the lobby is marked finished
	- Requires: rater and target are team members; cannot rate yourself
	- Body: `{ "rater_id": 1, "target_user_id": 2, "contribution": 8, "communication": 9, "would_work_again": true, "comment": "..." }`

## Demo Pages (HTML)

Main pages in the demo UI:

- `/login` — choose a user
- `/users` — user list
- `/users/<id>` — profile
- `/lobbies` — lobby feed
- `/lobbies/new` — create lobby
- `/lobbies/<id>` — lobby detail (leader actions, proof, ratings)

## TODO (MVP Demo Checklist)

Goal: ship a bare-minimum demo that shows the full loop — **Profile → Lobby → Handshake/Team → Proof → Rate → Reputation updates**.

### Backend / Data (Person A)

- [x] Add demo login (choose a seeded user; no passwords)
- [x] Add contest lifecycle flag (`finished`, `finished_at`) and gate proof/ratings behind “contest finished”
- [x] Allow members to submit/delete proof entries (tracks submitter)
- [x] Allow members to create/update/delete ratings; render ratings matrix in lobby detail
- [ ] Enforce **Proof-of-Work gate** for ratings: require at least 1 proof submission before any ratings are accepted (both UI route + API route)
- [ ] Implement the “handshake” join flow (replace instant join): request → leader review → accept/reject
- [ ] Add lobby `status` ("looking_for_members" | "looking_to_join") to support recruitment intent + feed filters
- [ ] Add minimal “Teammate CV” fields: GitHub/LinkedIn links + skills/tags (can be a simple text field for demo)
- [ ] Align reputation wording with pitch (Reliability + Skill) in the reputation endpoint and templates
- [ ] Quick happy-path sanity test (login as 2 users → request/join → finish → proof → rate → see reputation change)

### Frontend Demo UI (Person B)

- [x] Implement multi-page Bootstrap UI (home, login, users, profile, lobbies, lobby detail, create lobby)
- [x] Profile page supports inline edits for the current user (bio/contact/email/phone/etc.)
- [x] Lobby detail supports leader-only actions (edit lobby, lock team, mark finished)
- [x] Proof submission + teammate rating UI exists on finished contests
- [ ] Update lobby UI to show/apply `status` once backend adds it (badges + filters)
- [ ] Add join-request UI once handshake is implemented (pending requests list + accept/reject)
- [ ] Make ratings clearly gated in the UI (show an alert if contest finished but no proof exists yet)
- [ ] (Optional) Add “create user” form for faster demo setup (otherwise seeded users are fine)

### Seed + Demo Script (Person C)

- [x] Seed script creates a finished lobby with proof + ratings (so the app is not empty)
- [ ] Expand `seed_db.py` to generate 6–10 users with varied majors/skills + 2–3 lobbies with different `status` values
- [ ] Seed a handshake scenario (pending join requests) so the leader view looks populated
- [ ] Write a short click-through demo script (60–90 seconds): handshake → finish → proof gate → rate → reputation updates
- [ ] Add README “Demo steps” bullets (exact buttons/sequence to click)