import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "jobspace.settings")
django.setup()

from website.context_processors import _apply_seen

PASS = FAIL = 0


def check(label, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print("  FAIL:", label)


class FakeSession(dict):
    modified = False


class Req:
    def __init__(self):
        self.session = FakeSession()


# The queue this badge counts.
BADGES = {"candidates": 5}
SEEN = {"candidates": False}

# 1. Never visited, nothing recorded -> badge shows.
r = Req()
check("fresh user sees badge", _apply_seen(r, BADGES, SEEN)["candidates"] == 5)

# 2. Visit the page -> badge hidden and 5 recorded as seen.
r = Req()
out = _apply_seen(r, BADGES, {"candidates": True})
check("badge hidden while on page", out["candidates"] == 0)
check("seen count recorded in session", r.session["seen_badges"]["candidates"] == 5)

# 3. THE BUG: navigate to a different page with the same request/session.
#    Count unchanged -> badge must stay hidden.
r = Req()
_apply_seen(r, BADGES, {"candidates": True})
after = _apply_seen(r, BADGES, SEEN)
check("badge stays hidden after navigating away", after["candidates"] == 0)

# 4. Something genuinely new arrives -> badge comes back with only the delta.
r = Req()
_apply_seen(r, BADGES, {"candidates": True})
grew = _apply_seen(r, {"candidates": 8}, SEEN)
check("badge returns when queue grows", grew["candidates"] == 8)

# 5. Re-visiting the page absorbs the new items again.
r = Req()
_apply_seen(r, BADGES, {"candidates": True})
_apply_seen(r, {"candidates": 8}, SEEN)
cleared = _apply_seen(r, {"candidates": 8}, {"candidates": True})
check("re-visit clears the new items", cleared["candidates"] == 0)
check("seen updated to latest", r.session["seen_badges"]["candidates"] == 8)

# 6. Queue shrinking must NOT resurrect the badge.
r = Req()
_apply_seen(r, {"candidates": 9}, {"candidates": True})
shrunk = _apply_seen(r, {"candidates": 2}, SEEN)
check("shrinking queue stays hidden", shrunk["candidates"] == 0)

# 7. Several independent badges are tracked separately.
r = Req()
both = {"candidates": 4, "requests": 3}
_apply_seen(r, both, {"candidates": True, "requests": False})
res = _apply_seen(r, both, {"candidates": False, "requests": False})
check("unvisited badge still shows", res["candidates"] == 0 and res["requests"] == 3)

# 8. A request with no session (or a broken one) must not explode.
class NoSession:
    pass


try:
    out = _apply_seen(NoSession(), BADGES, SEEN)
    check("missing session degrades gracefully", out["candidates"] == 5)
except Exception as exc:
    check(f"missing session degrades gracefully ({exc})", False)

print(f"RESULT: {PASS} passed, {FAIL} failed")
raise SystemExit(1 if FAIL else 0)
