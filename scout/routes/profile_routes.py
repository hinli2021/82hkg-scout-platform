"""我的個人檔案 — a scout's profile: progress at a glance, a few words about
themselves, and the other scouts whose profiles are open to visit.

Personal words live in their own `profiles` row (one per scout). Every scout
must complete all three fields and publish the profile: the platform shows a
blocking pop-up after sign-in until that is done, and saving always sets
`visible` on. Only a complete, published profile can be opened from the
patrol list. The progress figures are the ordinary `progress_for` numbers,
so this page never keeps a second set of books.
"""
from __future__ import annotations

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from ..auth import scout_required
from ..engine import progress_for
from ..schema import patrol_label
from ..util import now_iso, to_bool
from .helpers import audit, fail, ok, store, wants_json

profile_routes = Blueprint("profile_routes", __name__)

INTERESTS_MAX = 120
TEXT_MAX = 1000

#: 職位 — the scout's job in the patrol, shown on the front of the card.
POSITIONS = {
    "member": {"zh": "隊員", "en": "Patrol member"},
    "apl": {"zh": "副小隊長", "en": "Assistant Patrol Leader"},
    "pl": {"zh": "小隊長", "en": "Patrol Leader"},
    "spl": {"zh": "高級小隊長", "en": "Senior Patrol Leader"},
}


def load_profile(st, user_id: str) -> dict:
    row = st.get("profiles", user_id) or {}
    position = str(row.get("position") or "")
    labels = POSITIONS.get(position, {})
    return {
        "user_id": user_id,
        "position": position,
        "position_zh": labels.get("zh", ""),
        "position_en": labels.get("en", ""),
        "interests": str(row.get("interests") or ""),
        "experience": str(row.get("experience") or ""),
        "share": str(row.get("share") or ""),
        "visible": to_bool(row.get("visible")),
        "updated_at": row.get("updated_at") or "",
    }


def profile_complete(profile: dict) -> bool:
    """All personal information is filled in and the profile is public."""
    return bool(
        str(profile.get("position") or "") in POSITIONS
        and str(profile.get("interests") or "").strip()
        and str(profile.get("experience") or "").strip()
        and str(profile.get("share") or "").strip()
        and to_bool(profile.get("visible"))
    )


def save_profile(st, user_id: str, values: dict) -> dict:
    row = {**values, "user_id": user_id, "updated_at": now_iso()}
    if st.get("profiles", user_id):
        st.update("profiles", user_id, row)
    else:
        st.insert("profiles", row)
    return load_profile(st, user_id)


def patrol_groups(st, viewer_id: str) -> list[dict]:
    """Every scout, grouped by patrol, with who can be visited."""
    profiles = {row.get("user_id"): load_profile(st, row.get("user_id"))
                for row in st.list("profiles")}
    scouts = [u for u in st.list("users") if u.get("role") == "scout"]
    scouts.sort(key=lambda u: (str(u.get("display_name_en") or u.get("display_name_zh") or ""),
                               str(u.get("username") or "")))
    order = [str(p) for p in (st.settings_cached().get("patrols") or ["Tiger", "Otter", "Seagull"])]
    seen = [p for p in order if any(u.get("patrol") == p for u in scouts)]
    seen += sorted({str(u.get("patrol") or "") for u in scouts} - set(seen))
    groups = []
    for patrol in seen:
        members = []
        for user in scouts:
            if str(user.get("patrol") or "") != patrol:
                continue
            profile = profiles.get(user["id"]) or load_profile(st, user["id"])
            members.append({
                "user": user, "profile": profile,
                "is_self": user["id"] == viewer_id,
                "can_visit": user["id"] == viewer_id or profile_complete(profile),
            })
        if members:
            groups.append({"patrol": patrol, "label": patrol_label(patrol), "members": members})
    return groups


def _context(st, person: dict, *, own: bool) -> dict:
    progress = progress_for(st, person["id"])
    return {
        "person": person,
        "profile": load_profile(st, person["id"]),
        "progress": progress,
        "stats": progress["stats"],
        "overall": progress["overall"],
        "earned_badges": [b for b in progress["badges"] if b["earned"]],
        "groups": patrol_groups(st, g.user["id"]),
        "positions": POSITIONS,
        "own": own,
    }


@profile_routes.get("/profile")
@scout_required
def page():
    st = store()
    context = _context(st, g.user, own=True)
    context["profile_required"] = not profile_complete(context["profile"])
    return render_template("scout/profile.html", **context)


@profile_routes.post("/profile")
@scout_required
def save():
    st = store()
    body = request.form
    values = {
        "position": str(body.get("position") or "").strip(),
        "interests": str(body.get("interests") or "").strip(),
        "experience": str(body.get("experience") or "").strip(),
        "share": str(body.get("share") or "").strip(),
        # Profiles are public by rule, not by choice: completing the form is
        # also the scout's agreement to let the rest of the troop read it.
        "visible": True,
    }
    if values["position"] not in POSITIONS:
        return fail(400, "profile_position", "請選擇你的職位。",
                    "Please choose your position.")
    if not values["interests"] or not values["experience"] or not values["share"]:
        return fail(400, "profile_empty", "請填寫全部資料，才可以繼續。",
                    "Please fill in everything before you continue.")
    if len(values["interests"]) > INTERESTS_MAX or len(values["experience"]) > TEXT_MAX \
            or len(values["share"]) > TEXT_MAX:
        return fail(400, "profile_long", "內容太長，請寫短一點。",
                    "That is too long — please keep it shorter.")
    save_profile(st, g.user["id"], values)
    audit(g.user, "profile_update", "profiles", g.user["id"], {"visible": True})
    if wants_json():
        return ok(visible=True)
    flash({"kind": "success", "zh": "個人檔案已儲存並公開。", "en": "Your profile is saved and public."}, "result")
    return_to = str(body.get("return_to") or "")
    if return_to.startswith("/") and not return_to.startswith("//"):
        return redirect(return_to)
    return redirect(url_for("profile_routes.page"))


@profile_routes.get("/profile/<user_id>")
@scout_required
def visit(user_id: str):
    st = store()
    if user_id == g.user["id"]:
        return redirect(url_for("profile_routes.page"))
    person = st.get("users", user_id)
    if not person or person.get("role") != "scout":
        abort(404)
    profile = load_profile(st, user_id)
    if not profile_complete(profile):
        # the name and patrol are already on the patrol list; nothing else
        # is shared until this scout has completed and published a profile
        return render_template("scout/profile.html", person=person, profile=None,
                               progress=None, stats=None, overall=None,
                               earned_badges=[], groups=[], own=False, locked=True)
    return render_template("scout/profile.html", **_context(st, person, own=False))
