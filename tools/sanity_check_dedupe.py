import os
import sys
from pathlib import Path

# Prevent app auto-seeding from running during this script.
os.environ["TRS_DISABLE_AUTOSEED"] = "1"

# Ensure repo root is on sys.path (so `import app` works when executing from tools/).
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app import app  # noqa: E402
from extensions import db  # noqa: E402
from models import User, Rating  # noqa: E402


def _core_fields(rep: dict) -> dict:
    return {
        "contribution_avg": rep.get("contribution_avg"),
        "communication_avg": rep.get("communication_avg"),
        "would_work_again_ratio": rep.get("would_work_again_ratio"),
    }


def main() -> None:
    with app.app_context():
        trust = User.compute_transitive_trust_scores()

        some_rating = Rating.query.first()
        if some_rating is None:
            raise SystemExit("No ratings found in DB. Run seed_db.py first.")

        target = User.query.get(some_rating.target_user_id)
        if target is None:
            raise SystemExit("Target user not found.")

        rater_id = some_rating.rater_id

        rep_before = target.reputation(trust_scores=trust)
        core_before = _core_fields(rep_before)

        client = app.test_client()
        resp = client.get(f"/api/users/{target.id}/reputation")
        if resp.status_code != 200:
            raise SystemExit(f"API call failed: {resp.status_code} {resp.data!r}")
        api_before = resp.get_json() or {}
        api_core_before = _core_fields(api_before)
        if api_core_before != core_before:
            print("WARNING: API core fields differ from model output")
            print("model:", core_before)
            print("api  :", api_core_before)
        else:
            print("API_OK: endpoint matches model output")

        dup = Rating(
            team_id=some_rating.team_id,
            rater_id=rater_id,
            target_user_id=some_rating.target_user_id,
            contribution=some_rating.contribution,
            communication=some_rating.communication,
            would_work_again=some_rating.would_work_again,
            comment="DUPLICATE FOR TEST",
        )
        db.session.add(dup)
        db.session.commit()

        trust2 = User.compute_transitive_trust_scores()
        rep_after = target.reputation(trust_scores=trust2)
        core_after = _core_fields(rep_after)

        print("target:", target.id, target.name)
        print("before:", core_before, "rating_count=", rep_before.get("rating_count"))
        print("after :", core_after, "rating_count=", rep_after.get("rating_count"))
        print(
            "trust_rater_before=",
            trust.get(rater_id, 0.0),
            "trust_rater_after=",
            trust2.get(rater_id, 0.0),
        )

        if core_before == core_after:
            print("DEDUP_OK: weighted fields unchanged after exact duplicate")
        else:
            print("DEDUP_FAILED: weighted fields changed after exact duplicate")

        db.session.delete(dup)
        db.session.commit()


if __name__ == "__main__":
    main()
