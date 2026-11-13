"""我的個人檔案 — a scout's profile: progress at a glance, a few words about
themselves, and the other scouts whose profiles are open to visit.

Personal words live in their own `profiles` row (one per scout). Every scout
must complete every field and publish the profile: the platform shows a
blocking pop-up after sign-in until that is done, and saving always sets
`visible` on. Only a complete, published profile can be opened from the
patrol list. The progress figures are the ordinary `progress_for` numbers,
so this page never keeps a second set of books.
"""
from __future__ import annotations

import base64
import os
from datetime import datetime, timezone

import requests
from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, url_for

from ..auth import scout_required
from ..engine import progress_for
from ..schema import patrol_label
from ..util import now_iso, to_bool
from .helpers import audit, fail, ok, store, wants_json

profile_routes = Blueprint("profile_routes", __name__)

INTERESTS_MAX = 120
TEXT_MAX = 1000
POSITION_MAX = 40

#: 職位 is written by the scout in their own words and shown on the front of
#: the card. Profiles saved before it became free text hold one of these
#: codes; they still read as the matching title in either language, and the
#: edit form offers that title back as ordinary text.
POSITIONS = {
    "member": {"zh": "隊員", "en": "Patrol member"},
    "apl": {"zh": "副小隊長", "en": "Assistant Patrol Leader"},
    "pl": {"zh": "小隊長", "en": "Patrol Leader"},
    "spl": {"zh": "高級小隊長", "en": "Senior Patrol Leader"},
}


def load_profile(st, user_id: str) -> dict:
    row = st.get("profiles", user_id) or {}
    position = str(row.get("position") or "").strip()
    labels = POSITIONS.get(position, {})
    return {
        "user_id": user_id,
        "position": position,
        # Free text reads the same in both languages; only the old codes
        # translate. `position_edit` is what the form offers back.
        "position_zh": labels.get("zh", position),
        "position_en": labels.get("en", position),
        "position_edit": labels.get("zh", position),
        "interests": str(row.get("interests") or ""),
        "experience": str(row.get("experience") or ""),
        "share": str(row.get("share") or ""),
        "visible": to_bool(row.get("visible")),
        "updated_at": row.get("updated_at") or "",
        "card_image_url": str(row.get("card_image_url") or ""),
        "card_image_id": str(row.get("card_image_id") or ""),
        "card_generated_at": str(row.get("card_generated_at") or ""),
    }


def profile_complete(profile: dict) -> bool:
    """All personal information is filled in and the profile is public."""
    return bool(
        str(profile.get("position") or "").strip()
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


#: For the AI card picture, each patrol mascot becomes the scout's partner
#: creature, with the type the card generator expects.
CARD_PARTNERS = {
    "Tiger": {"partner": "老虎", "type": "火"},
    "Otter": {"partner": "水獺", "type": "水"},
    "Seagull": {"partner": "海鷗", "type": "超能"},
}


def card_fields(person: dict, profile: dict, stats: dict, overall: dict) -> dict:
    """The card generator's Pokémon fields, filled from the profile itself.

    The scout never fills a second form: 職位 and 興趣 become the ability,
    童軍經驗 and 想和大家分享的事 become the two moves, and the progress
    numbers become their damage.
    """
    english = request.cookies.get("scout_lang") == "en"
    partner = CARD_PARTNERS.get(str(person.get("patrol") or ""), {"partner": "小狐狸", "type": "草"})
    name = str(person.get("display_name_en") if english else person.get("display_name_zh")
               or person.get("display_name_zh") or person.get("display_name_en") or "")
    position = profile["position_en"] if english else profile["position_zh"]
    kind = partner["type"]
    return {
        "name": name,
        "partner_pokemon": partner["partner"],
        "pokemon_type": kind,
        "move1_name": "Scout experience" if english else "童軍經驗",
        "move1_energy": f"2{kind}",
        "move1_damage": str(max(10, int(overall.get("tasks_done") or 0) * 10)),
        "move1_text": profile["experience"],
        "move2_name": "Something to share" if english else "想和大家分享的事",
        "move2_energy": f"3{kind}",
        "move2_damage": str(max(50, int(stats.get("badges_done") or 0) * 50)),
        "move2_text": profile["share"],
        "ability": (f"Ability: {position}. {profile['interests']}" if english
                    else f"特性：{position}。{profile['interests']}"),
        "finish_pokemon": "Full Art Rainbow Holographic Foil",
        "card_number": str(person.get("scout_no") or "82HKG"),
    }


def _context(st, person: dict, *, own: bool) -> dict:
    progress = progress_for(st, person["id"])
    profile = load_profile(st, person["id"])
    return {
        "person": person,
        "profile": profile,
        "progress": progress,
        "stats": progress["stats"],
        "overall": progress["overall"],
        "earned_badges": [b for b in progress["badges"] if b["earned"]],
        "groups": patrol_groups(st, g.user["id"]),
        "card": card_fields(person, profile, progress["stats"], progress["overall"]),
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
    if not values["position"]:
        return fail(400, "profile_position", "請填寫你的職位。",
                    "Please write your position.")
    if not values["interests"] or not values["experience"] or not values["share"]:
        return fail(400, "profile_empty", "請填寫全部資料，才可以繼續。",
                    "Please fill in everything before you continue.")
    if len(values["position"]) > POSITION_MAX or len(values["interests"]) > INTERESTS_MAX \
            or len(values["experience"]) > TEXT_MAX or len(values["share"]) > TEXT_MAX:
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


CARD_PROMPT_MAX = 12000
CARD_WAIT_SECONDS = 30


def _call_gemini(api_key: str, model: str, prompt: str) -> tuple[bytes, str]:
    """One image from Gemini. Returns (bytes, mime); raises on any failure."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    response = requests.post(
        url, params={"key": api_key}, timeout=110,
        json={"contents": [{"role": "user", "parts": [{"text": prompt}]}],
              "generationConfig": {"imageConfig": {"aspectRatio": "2:3"}}},
    )
    if response.status_code != 200:
        raise RuntimeError(f"Gemini answered {response.status_code}")
    payload = response.json()
    candidates = payload.get("candidates") or []
    parts = ((candidates[0].get("content") or {}).get("parts") if candidates else []) or []
    for part in parts:
        data = part.get("inlineData") or part.get("inline_data") or {}
        if data.get("data"):
            return base64.b64decode(data["data"]), data.get("mimeType") or data.get("mime_type") or "image/png"
    raise RuntimeError("Gemini returned no image")


def _card_display_url(uploaded: dict) -> str:
    # A Drive file's web link opens a viewer page, not the picture itself;
    # the thumbnail address is the one an <img> can show (the upload is
    # shared with anyone who has the link).
    if uploaded.get("stored") == "drive" and uploaded.get("id"):
        return f"https://drive.google.com/thumbnail?id={uploaded['id']}&sz=w1000"
    return str(uploaded.get("url") or "")


@profile_routes.post("/profile/card-image")
@scout_required
def card_image():
    """Generate this scout's AI card picture and keep it on the profile.

    The browser builds the prompt with the card generator's remote prompt
    vault; this route only lends it the platform's Gemini key (which never
    reaches the page) and stores the finished picture.
    """
    st = store()
    profile = load_profile(st, g.user["id"])
    if not profile_complete(profile):
        return fail(400, "profile_incomplete", "請先完成個人檔案，才可以生成卡圖。",
                    "Please complete your profile before making a card picture.")
    body = request.get_json(silent=True) or {}
    prompt = str(body.get("prompt") or "").strip()
    if not prompt or len(prompt) > CARD_PROMPT_MAX:
        return fail(400, "card_prompt", "卡圖資料不完整，請再試一次。",
                    "The card details are incomplete — please try again.")
    if profile["card_generated_at"]:
        try:
            last = datetime.fromisoformat(profile["card_generated_at"].replace("Z", "+00:00"))
            if (datetime.now(timezone.utc) - last).total_seconds() < CARD_WAIT_SECONDS:
                return fail(429, "card_wait", "剛生成了一張卡圖，請等半分鐘再試。",
                            "A card picture was just made — please wait half a minute.")
        except ValueError:
            pass
    api_key = str(current_app.config.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY") or "")
    if not api_key:
        return fail(503, "card_no_key", "領袖尚未開啟卡圖生成功能。",
                    "Card pictures are not switched on yet — please ask a leader.")
    model = str(current_app.config.get("GEMINI_IMAGE_MODEL") or "gemini-2.5-flash-image")
    try:
        data, mime = _call_gemini(api_key, model, prompt)
    except Exception:
        return fail(502, "card_failed", "卡圖生成失敗，請稍後再試。",
                    "The card picture could not be made — please try again later.")
    ext = ".jpg" if "jpeg" in mime or "jpg" in mime else ".png"
    uploaded = st.upload_file(name=f"card-{g.user['id']}{ext}", mime_type=mime, data=data)
    url = _card_display_url(uploaded)
    stamp = now_iso()
    patch = {"card_image_url": url, "card_image_id": str(uploaded.get("id") or ""),
             "card_generated_at": stamp}
    if st.get("profiles", g.user["id"]):
        st.update("profiles", g.user["id"], patch)
    else:
        st.insert("profiles", {"user_id": g.user["id"], **patch})
    audit(g.user, "profile_card_image", "profiles", g.user["id"], {"stored": uploaded.get("stored")})
    return ok(card_image_url=url)


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
