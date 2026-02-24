# TeamRank Prototype

This is a runnable prototype (Flask + SQLite) demonstrating the core flow: create users, open lobbies, **request/invite into teams**, submit proof, and provide peer ratings.

There are two frontends:

- Flask server-rendered pages (Jinja templates) served from the backend at `http://127.0.0.1:5000/`
- A Next.js frontend in `trs-webapp/` (dev server at `http://localhost:3000/`) that talks to the same Flask backend

## Setup

### Backend (Flask) only

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

For a demo-friendly visualization of how reputations compose from the rating graph, open:

- http://127.0.0.1:5000/graph — interactive rater→ratee network (zoom/pan, threshold slider, click-to-focus)

(The underlying JSON is available at `GET /api/graph`.)

After seeding, the database includes many users with a default password of `123456`.

### Full stack (Next.js + Flask)

In one terminal, start the Flask backend:

```bash
python app.py
```

In a second terminal, start the Next.js frontend:

```bash
cd trs-webapp
npm install
npm run dev
```

Then open http://localhost:3000/.

Notes:

- The frontend uses `NEXT_PUBLIC_API_BASE` (defaults to `http://localhost:5000`).
- The backend enables CORS for `http://localhost:3000` and `http://127.0.0.1:3000`.

## API Overview (JSON)

The UI pages use server-rendered HTML, but the app also exposes JSON endpoints you can call with curl/Postman.

### Users

- `GET /api/users` — list users
- `POST /api/users` — create a user
	- Body: `{ "name": "...", "email": "netid@duke.edu", "password": "...", "major": "...", "year": "..." }`
- `GET /api/users/<id>` — get one user (includes list of participated lobbies)
- `GET /api/users/<id>/reputation` — aggregate reputation for the user

See [Reputation weighting (transitive)](#reputation-weighting-transitive).

### Lobbies / Teams

- `GET /api/lobbies` — list lobbies
- `POST /api/lobbies` — create a lobby (also creates an initial team)
	- Body: `{ "title": "...", "contest_link": "...", "leader_id": 1 }`
- `GET /api/lobbies/<id>` — get lobby details (includes participants)
- `POST /api/teams/<id>/lock` — lock a team

### Join Requests (handshake API)

These endpoints exist for a request → decision flow:

- `POST /api/lobbies/<id>/join-requests` — create a join request (uses the logged-in session user)
- `GET /api/lobbies/<id>/join-requests?status=pending` — list join requests (filter by status)
- `POST /api/lobbies/<id>/join-requests/<request_id>/decision` — accept/reject a request

### Proof + Ratings (post-contest)

- `POST /api/teams/<id>/submit` — submit proof of submission
	- Requires: the lobby is marked finished
	- Requires: submitter is a team member
	- Body: `{ "proof": "url or text", "submitter_id": 1 }`
- `POST /api/teams/<id>/ratings` — submit a rating
	- Requires: the lobby is marked finished
	- Requires: rater and target are team members; cannot rate yourself
	- Body: `{ "rater_id": 1, "target_user_id": 2, "contribution": 8, "communication": 9, "would_work_again": true, "comment": "..." }`

## Reputation weighting (transitive)

The reputation returned by `GET /api/users/<id>/reputation` is a **transitively weighted** aggregate:

- Each incoming rating is weighted by the *rater’s* global trust score.
- Global trust scores are computed from the full rater→target graph using a PageRank/EigenTrust-style power iteration with damping (default `0.85`).

Implementation: see `User.compute_transitive_trust_scores()` and `User.reputation()` in `models.py`.

### How it works

We treat ratings as a directed graph: each `Rating` row is an edge **rater → target**.

1. **Local trust (edge weight).** For each rating, we compute a non-negative “local trust” weight in `[0,1]`:
   - `contribution` and `communication` are normalized from the app’s 0–10 scale into `[0,1]`.
   - `would_work_again` is mapped to 1 (true) or 0 (false).
   - The current implementation averages those three values.

2. **Row-normalize outgoing trust.** For each rater `i`, we normalize their outgoing weights so that the total trust they distribute sums to 1:
   ```text
   W_ij = c_ij / sum_k(c_ik)
   ```
   where `c_ij >= 0` is the accumulated local trust from user `i` to user `j`.

  Implementation note (simple collusion/spam mitigation): if there are multiple `Rating` rows between the same rater `i` and target `j` (e.g., across multiple teams/lobbies), the backend collapses them into a single edge by averaging their local trust values, instead of summing them. This prevents repeated interactions from inflating trust purely by volume.

3. **Compute global trust via damping + power iteration.** We compute a global trust vector `t` that is the stationary distribution of a damped walk over the rating graph (PageRank-style):
   ```text
   t <- (1 - d) * p + d * (W^T * t)
   ```
   - `d` is the damping factor (default 0.85).
   - `p` is a “base”/personalization distribution. This prototype uses a **uniform** `p`.
   - Users with no outgoing trust (“dangling nodes”) have their probability mass redistributed uniformly.

4. **Use trust as weights when aggregating reputation.** When computing a user’s reputation, each incoming rating from rater `r` is weighted by `t[r]`:
   - `contribution_avg` and `communication_avg` become trust-weighted averages (still on the 0–10 scale).
   - `would_work_again_ratio` becomes a trust-weighted fraction.

Notes:

- Trust scores are **relative weights** (they are normalized to sum to 1 across all users), not a 0–10 “reputation” number.
- `rating_count` in the response is the raw count of received ratings; the averages/ratios are computed using trust weights.

### Why this is (reasonably) reliable

This approach is a standard pattern in reputation/trust systems: compute a *global* trust score from the whole graph, then use it to weight votes/ratings.

- **Transitivity.** If trustworthy users (high `t`) rate someone positively, that boosts the target’s trust, which then increases the influence of the target’s future ratings.
- **Damping stabilizes the computation.** The `(1 - d) * p` term prevents the system from getting “stuck” in disconnected components and makes the iteration converge to a unique fixed point under typical conditions.
- **No negative trust in this prototype.** Edge weights are clamped to `[0,1]` before normalization, so the algorithm can be interpreted as a probability flow on a graph.

That said: **this is not a Sybil-proof magic bullet**. It makes “new/unknown” accounts tend to have low influence *relative to accounts with lots of trusted inbound edges*, but if identities are cheap, attackers can still manipulate the graph.

### Parameters and performance

- Damping: `damping=0.85` (higher = more influence from the graph; lower = closer to uniform trust).
- Iteration: `max_iter=50`, `tol=1e-10`.
- Complexity: roughly `O(E * I)` per computation, where `E` is number of rating edges and `I` is number of iterations.
- Optimization already applied: for pages that show many users, the backend computes trust scores once per request and passes the map into `User.reputation()`.

### Threat model: potential attacks (and mitigations)

Common ways reputation systems like this get attacked:

- **Sybil / sockpuppet flooding.** Create many fake accounts that rate each other and then target a victim.
  - Mitigations: make identities costly (email/phone verification, rate limits), require participation/proof before rating, detect dense near-cliques of new accounts, cap per-period rating impact.

- **Collusion rings.** A small group of real accounts coordinate to inflate each other.
  - Mitigations: require diversity of raters (e.g., ratings must come from multiple independent teams/lobbies), down-weight repeated interactions between the same pairs, audit unusual reciprocation patterns.
  - Implemented in this prototype: repeated ratings from the same rater to the same target are collapsed (averaged) so they don’t gain extra influence just by being repeated.

- **Camouflage / “long con”.** Behave honestly until trusted, then attack.
  - Mitigations: time decay on trust edges, anomaly detection on sudden behavior changes, manual review flags for large jumps.

- **Whitewashing.** Abandon an account after bad ratings and re-register.
  - Mitigations: stronger identity binding and friction, keep some continuity signals (e.g., verified email), delay full influence for new accounts.

- **Retaliation / harassment ratings.** Use ratings to punish teammates.
  - Mitigations: require proof of collaboration, provide dispute/reporting flows, consider hiding individual ratings and only showing aggregates.

If you want this to be more attack-resistant, the next step is usually to add **identity friction** and/or choose a non-uniform “pre-trusted” personalization distribution `p` (a key idea in EigenTrust), rather than letting trust originate uniformly.

### References

- S. D. Kamvar, M. T. Schlosser, H. Garcia-Molina. *The EigenTrust Algorithm for Reputation Management in P2P Networks*. WWW 2003. https://nlp.stanford.edu/pubs/eigentrust.pdf
- L. Page, S. Brin, R. Motwani, T. Winograd. *The PageRank Citation Ranking: Bringing Order to the Web*. Stanford Tech Report, 1999. http://ilpubs.stanford.edu:8090/422/1/1999-66.pdf
- R. Levien. *Attack Resistant Trust Metrics*. PhD thesis, 2004. https://levien.com/thesis/compact.pdf
- J. R. Douceur. *The Sybil Attack*. In: *Peer-to-Peer Systems (IPTPS 2002)*. DOI: 10.1007/3-540-45748-8_24 ; accessible copy: https://archive.org/details/peertopeersystem0000iptp/page/251
- J. M. Kleinberg. *Authoritative Sources in a Hyperlinked Environment*. 1998 (journal version). See discussion of link-based ranking pitfalls and simple anti-collusion heuristics such as limiting multiple same-source links to a target. https://www.cs.cornell.edu/home/kleinber/auth.pdf

## Demo Pages (HTML)

Main pages in the demo UI:

- `/login` — login with email + password
- `/register` — create an account (enforces `@duke.edu`)
- `/me` — redirect to your profile
- `/users` — user list
- `/users/<id>` — profile
- `/lobbies` — lobby feed
- `/lobbies/new` — create lobby
- `/lobbies/<id>` — lobby detail (leader actions, proof, ratings)
- `/invites` — view invites you sent/received
- `/join-requests` — view join requests you made/received
- `/invites/respond/<token>` — invitation accept/reject page

## TODO (MVP Demo Checklist)

Goal: ship a bare-minimum demo that shows the full loop — **Profile → Lobby → Handshake/Team → Proof → Rate → Reputation updates**.

### Backend / Data (Person A)

- [x] Add login/logout + session auth (supports seeded users)
- [x] Add real accounts: email/password login + registration (hashed passwords)
- [x] Add contest lifecycle flag (`finished`, `finished_at`) and gate proof/ratings behind “contest finished”
- [x] Allow members to submit/delete proof entries (tracks submitter)
- [x] Allow members to create/update/delete ratings; render ratings matrix in lobby detail
- [ ] Enforce **Proof-of-Work gate** for ratings: require at least 1 proof submission before any ratings are accepted (both UI route + API route)
- [x] Implement the “handshake” join flow (replaces instant join): request → leader review → accept/reject
- [x] Add invitation flow: invite by email + tokenized accept/reject (with a confirmation page)
- [x] Add join-request API endpoints (`/api/lobbies/<id>/join-requests`)
- [x] Enable CORS for local Next.js development (`localhost:3000`)
- [ ] Add lobby `status` ("looking_for_members" | "looking_to_join") to support recruitment intent + feed filters
- [ ] Add minimal “Teammate CV” fields: GitHub/LinkedIn links + skills/tags (can be a simple text field for demo)
- [ ] Align reputation wording with pitch (Reliability + Skill) in the reputation endpoint and templates
- [ ] Quick happy-path sanity test (login as 2 users → request/join → finish → proof → rate → see reputation change)

### Frontend Demo UI (Person B)

- [x] Implement multi-page Bootstrap UI (home, login, users, profile, lobbies, lobby detail, create lobby)
- [x] Profile page supports inline edits for the current user (bio/contact/email/phone/etc.)
- [x] Lobby detail supports leader-only actions (edit lobby, lock team, mark finished)
- [x] Proof submission + teammate rating UI exists on finished contests
- [x] (Optional) Add “create user” form for faster demo setup (registration page)
- [x] Add Next.js frontend (`trs-webapp/`) covering the same flows as the Jinja demo
- [ ] Update lobby UI to show/apply `status` once backend adds it (badges + filters)
- [x] Add join-request UI (request button + leader accept/reject + listing pages)
- [ ] Make ratings clearly gated in the UI (show an alert if contest finished but no proof exists yet)

### Seed + Demo Script (Person C)

- [x] Seed script creates a finished lobby with proof + ratings (so the app is not empty)
- [ ] Expand `seed_db.py` to generate 6–10 users with varied majors/skills + 2–3 lobbies with different `status` values
- [x] Seed script generates many users and sets a default password (`123456`) for quick login
- [ ] Seed a handshake scenario (pending join requests) so the leader view looks populated
- [ ] Write a short click-through demo script (60–90 seconds): handshake → finish → proof gate → rate → reputation updates
- [ ] Add README “Demo steps” bullets (exact buttons/sequence to click)