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

import os
import re
from datetime import datetime, timezone

import requests
from flask import (Blueprint, Response, abort, current_app, flash, g, jsonify,
                   redirect, render_template, request, url_for)

from ..auth import scout_required
from ..engine import progress_for
from ..schema import patrol_label
from ..util import now_iso, to_bool
from .helpers import audit, fail, ok, store, wants_json

profile_routes = Blueprint("profile_routes", __name__)

INTERESTS_MAX = 120
TEXT_MAX = 1000
POSITION_MAX = 40

#: 童軍經驗 is picked, not written: how many days under canvas and how many
#: hikes, each from a list that runs 0–20 and then opens out at 20+. The
#: values are stored as text ("0"…"20", "20+") so a Sheet cell keeps them
#: exactly as picked; 0 is a real answer, only an unpicked list is blank.
COUNT_VALUES = {str(n) for n in range(21)} | {"20+"}


def _count_value(raw) -> str:
    """One picked count, cleaned: a stored value outside the list is blank."""
    text = str(raw if raw is not None else "").strip()
    if text.endswith(".0"):
        text = text[:-2]
    if text in ("20 or more", "20以上"):
        text = "20+"
    return text if text in COUNT_VALUES else ""


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

#: 職位、我的強項 and 興趣 are picked from lists now, with an Other at the
#: end of each that opens a text box. The stored value stays a plain string
#: in the scout's own language-neutral words: the picked option itself, or
#: 「其他：…」 with what they wrote — which is also how the card shows it.
#: (Values are the Chinese words in either language, so a patrol 聯絡 is
#: still found by the word 聯絡 wherever the profile is read.)
OTHER_VALUE = "__other__"

POSITION_OPTIONS = [
    ("隊員", "Patrol member"),
    ("副小隊長", "Assistant Patrol Leader"),
    ("小隊長", "Patrol Leader"),
    ("高級小隊長", "Senior Patrol Leader"),
    ("聯絡", "Patrol contact"),
    ("康樂", "Activities"),
    ("文書", "Secretary"),
    ("物資管理", "Quartermaster"),
    ("氣象員", "Weather reporter"),
    ("報時員", "Timekeeper"),
    ("情緒輔助", "Emotional support"),
    ("情緒價值專員", "Morale officer"),
    ("心理委員", "Wellbeing officer"),
    ("法官", "Judge"),
]

STRENGTH_OPTIONS = [
    ("繩結", "Knots"), ("急救", "First aid"), ("生火", "Fire lighting"),
    ("煮食", "Cooking"), ("唱歌", "Singing"), ("畫畫", "Drawing"),
    ("跑步", "Running"), ("游泳", "Swimming"), ("領導", "Leadership"),
    ("解難", "Problem solving"), ("觀察", "Observation"), ("手工藝", "Crafts"),
    ("音樂", "Music"), ("運動", "Sports"), ("照顧他人", "Caring for others"),
]

INTEREST_OPTIONS = [
    ("露營", "Camping"), ("行山", "Hiking"), ("繩結", "Knots"),
    ("足球", "Football"), ("籃球", "Basketball"), ("游泳", "Swimming"),
    ("音樂", "Music"), ("唱歌", "Singing"), ("畫畫", "Drawing"),
    ("閱讀", "Reading"), ("天文", "Astronomy"), ("科學", "Science"),
    ("電子遊戲", "Video games"), ("烹飪", "Cooking"), ("舞蹈", "Dance"),
    ("攝影", "Photography"), ("手工藝", "Crafts"),
]


def _other_text(value: str) -> str | None:
    """What follows an 「其他：」 prefix, or None when there is no prefix."""
    text = str(value or "").strip()
    for prefix in ("其他：", "其他:", "Other:"):
        if text.startswith(prefix):
            return text[len(prefix):].strip()
    return None


def _single_choice(value: str, options: list) -> tuple[str, str]:
    """(picked option or Other, the Other words) for one stored string."""
    text = str(value or "").strip()
    if not text:
        return "", ""
    if text in {item[0] for item in options}:
        return text, ""
    other = _other_text(text)
    return OTHER_VALUE, (other if other is not None else text)


def _interest_choices(value: str) -> tuple[list, bool, str]:
    """(picked options, Other picked?, the Other words) for 興趣.

    The stored string joins interests with 、; anything on it that is not
    a listed option — words written while 興趣 was free text — comes back
    as the Other words, so an edit offers them back instead of losing them.
    """
    known = {item[0] for item in INTEREST_OPTIONS}
    picked: list[str] = []
    other_words: list[str] = []
    other = False
    for token in re.split(r"[、,，;；\n]+", str(value or "")):
        token = token.strip()
        if not token:
            continue
        rest = _other_text(token)
        if token in known:
            if token not in picked:
                picked.append(token)
        elif rest is not None:
            other = True
            if rest:
                other_words.append(rest)
        else:
            other = True
            other_words.append(token)
    return picked, other, "、".join(other_words)


def load_profile(st, user_id: str) -> dict:
    row = st.get("profiles", user_id) or {}
    position = str(row.get("position") or "").strip()
    labels = POSITIONS.get(position, {})
    # The form works on the picked words, not the stored string: a listed
    # 職位 is offered back as that option, anything else as Other + words.
    position_value = labels.get("zh", position)
    position_labels = dict(POSITION_OPTIONS)
    other_words = _other_text(position_value)
    if labels:
        position_zh, position_en = labels["zh"], labels["en"]
    elif position_value in position_labels:
        position_zh, position_en = position_value, position_labels[position_value]
    elif other_words is not None and position_value.startswith("其他"):
        position_zh, position_en = position_value, f"Other: {other_words}"
    else:
        position_zh = position_en = position_value
    position_choice, position_other = _single_choice(position_value, POSITION_OPTIONS)
    strength = str(row.get("strength") or "")
    strength_choice, strength_other = _single_choice(strength, STRENGTH_OPTIONS)
    interests = str(row.get("interests") or "")
    interest_choices, interests_other_on, interests_other = _interest_choices(interests)
    return {
        "user_id": user_id,
        "position": position,
        # Free text reads the same in both languages; only the old codes
        # translate. `position_edit` is what the form offers back.
        "position_zh": position_zh,
        "position_en": position_en,
        "position_edit": position_value,
        "position_options": POSITION_OPTIONS,
        "position_choice": position_choice,
        "position_other": position_other,
        "interests": interests,
        "interest_options": INTEREST_OPTIONS,
        "interest_choices": interest_choices,
        "interests_other": interests_other if interests_other_on else "",
        "interests_other_on": interests_other_on,
        "experience": str(row.get("experience") or ""),
        "camping_days": _count_value(row.get("camping_days")),
        "hiking_times": _count_value(row.get("hiking_times")),
        "share": str(row.get("share") or ""),
        "strength": strength,
        "strength_options": STRENGTH_OPTIONS,
        "strength_choice": strength_choice,
        "strength_other": strength_other,
        "visible": to_bool(row.get("visible")),
        "updated_at": row.get("updated_at") or "",
        "card_image_url": str(row.get("card_image_url") or ""),
        "card_image_id": str(row.get("card_image_id") or ""),
        "card_generated_at": str(row.get("card_generated_at") or ""),
    }


def _experience_complete(profile: dict) -> bool:
    """童軍經驗 counts as filled once both counts are picked.

    A profile saved while the experience was a written paragraph keeps
    counting on that paragraph until its owner picks the two counts —
    nobody is locked out, or loses their words, for a field that did
    not exist when they wrote them.
    """
    if _count_value(profile.get("camping_days")) and _count_value(profile.get("hiking_times")):
        return True
    return bool(str(profile.get("experience") or "").strip())


def profile_complete(profile: dict) -> bool:
    """All personal information is filled in and the profile is public."""
    return bool(
        str(profile.get("position") or "").strip()
        and str(profile.get("interests") or "").strip()
        and _experience_complete(profile)
        and str(profile.get("share") or "").strip()
        and str(profile.get("strength") or "").strip()
        and to_bool(profile.get("visible"))
    )


def _picked_single(body, choice_name: str, other_name: str, options: list) -> str | None:
    """The stored string for one dropdown, or None when it is not filled.

    A listed option is stored as itself; Other is stored as 「其他：…」,
    the words included, so the card can show exactly that.
    """
    choice = str(body.get(choice_name) or "").strip()
    if choice == OTHER_VALUE:
        other = str(body.get(other_name) or "").strip()
        return f"其他：{other}" if other else None
    if choice in {item[0] for item in options}:
        return choice
    return None


def _picked_interests(body) -> str | None:
    """The stored 興趣 string for the multi-pick list, or None if empty."""
    known = {item[0] for item in INTEREST_OPTIONS}
    picked: list[str] = []
    other = False
    for value in body.getlist("interest_picks"):
        value = str(value or "").strip()
        if value == OTHER_VALUE:
            other = True
        elif value in known and value not in picked:
            picked.append(value)
        elif value:
            return None  # a value that is not on the list at all
    if other:
        words = str(body.get("interests_other") or "").strip()
        if not words:
            return None
        picked.append(f"其他：{words}")
    return "、".join(picked) if picked else None


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
    profile = load_profile(st, person["id"])
    return {
        "person": person,
        "profile": profile,
        "progress": progress,
        "stats": progress["stats"],
        "overall": progress["overall"],
        "earned_badges": [b for b in progress["badges"] if b["earned"]],
        "groups": patrol_groups(st, g.user["id"]),
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
        "share": str(body.get("share") or "").strip(),
        # Profiles are public by rule, not by choice: completing the form is
        # also the scout's agreement to let the rest of the troop read it.
        "visible": True,
    }
    # 職位、我的強項 and 興趣 arrive picked from lists (an Other opens a text
    # box). A caller still sending the old plain fields — a page left open
    # in a tab — is kept on them, so nobody's save is lost mid-change.
    if any(name in body for name in ("position_choice", "strength_choice",
                                     "interest_picks", "interests_other")):
        position = _picked_single(body, "position_choice", "position_other", POSITION_OPTIONS)
        if position is None:
            return fail(400, "profile_position", "請選擇你的職位；揀「其他」的話，請寫明是甚麼職位。",
                        "Please pick your position — and if you pick Other, write what it is.")
        interests = _picked_interests(body)
        if interests is None:
            return fail(400, "profile_empty", "請選擇你的興趣；揀「其他」的話，請寫明是甚麼興趣。",
                        "Please pick your interests — and if you pick Other, write what they are.")
        strength = _picked_single(body, "strength_choice", "strength_other", STRENGTH_OPTIONS)
        if strength is None:
            return fail(400, "profile_empty", "請選擇你的強項；揀「其他」的話，請寫明是甚麼強項。",
                        "Please pick your strength — and if you pick Other, write what it is.")
        values.update({"position": position, "interests": interests, "strength": strength})
    else:
        values.update({
            "position": str(body.get("position") or "").strip(),
            "interests": str(body.get("interests") or "").strip(),
            "strength": str(body.get("strength") or "").strip(),
        })
        if not values["position"]:
            return fail(400, "profile_position", "請填寫你的職位。",
                        "Please write your position.")
    # 童軍經驗 arrives as the two picked counts; the counts take the written
    # paragraph's place. A caller still sending the paragraph (an old page
    # in an open tab) is kept on it, so nobody's save is lost mid-change.
    if "camping_days" in body or "hiking_times" in body:
        camping = _count_value(body.get("camping_days"))
        hiking = _count_value(body.get("hiking_times"))
        if not camping or not hiking:
            return fail(400, "profile_empty", "請選擇露營天數和行山次數，才可以繼續。",
                        "Please choose your camping days and hikes before you continue.")
        values.update({"experience": "", "camping_days": camping, "hiking_times": hiking})
    else:
        values["experience"] = str(body.get("experience") or "").strip()
        if not values["experience"]:
            return fail(400, "profile_empty", "請填寫全部資料，才可以繼續。",
                        "Please fill in everything before you continue.")
    if not values["interests"] or not values["share"] or not values["strength"]:
        return fail(400, "profile_empty", "請填寫全部資料，才可以繼續。",
                    "Please fill in everything before you continue.")
    if len(values["position"]) > POSITION_MAX or len(values["interests"]) > INTERESTS_MAX \
            or len(values["strength"]) > INTERESTS_MAX \
            or len(values.get("experience") or "") > TEXT_MAX or len(values["share"]) > TEXT_MAX:
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


CARD_WAIT_SECONDS = 30


def _compact_card_picture(data: bytes, mime: str, ext: str) -> tuple[bytes, str, str]:
    """Store card art as AVIF (or WebP): the same picture at a tenth of the size.

    Gemini and phones hand us PNG/JPEG files of a megabyte or more, and every
    one is kept on the unit's Drive. AVIF (WebP where AVIF is unavailable)
    holds the same card far more lightly. Any failure — Pillow missing, or a
    file that is not really a picture — keeps the scout's original bytes.
    """
    try:
        from io import BytesIO

        from PIL import Image, features
    except Exception:
        return data, mime, ext
    try:
        image = Image.open(BytesIO(data))
        image.load()
        out = BytesIO()
        if features.check("avif"):
            image.save(out, format="AVIF", quality=80)
            return out.getvalue(), "image/avif", "avif"
        if features.check("webp"):
            image.save(out, format="WEBP", quality=85, method=6)
            return out.getvalue(), "image/webp", "webp"
    except Exception:
        pass
    return data, mime, ext


def _card_display_url(uploaded: dict) -> str:
    # A Drive file's web link opens a viewer page, not the picture itself;
    # the thumbnail address is the one an <img> can show (the upload is
    # shared with anyone who has the link).
    if uploaded.get("stored") == "drive" and uploaded.get("id"):
        return f"https://drive.google.com/thumbnail?id={uploaded['id']}&sz=w1000"
    return str(uploaded.get("url") or "")


CARD_PROXY_MAX_BYTES = 12 * 1024 * 1024
CARD_PROXY_DAILY_MAX = 20


def _gemini_error(status: int, message: str):
    """An error in Gemini's own shape, so the generator can show it as-is."""
    return jsonify(error={"message": message}), status


@profile_routes.post("/profile/card-image-proxy")
@scout_required
def card_image_proxy():
    """Lend the platform's Gemini key to the in-page card generator.

    The generator builds its own prompt (and may attach the scout's photo);
    this route only forwards the request with the server-side key, so no
    scout ever needs an API key of their own. The key never reaches the
    browser, and the audit trail caps how often each scout may generate.
    """
    st = store()
    profile = load_profile(st, g.user["id"])
    if not profile_complete(profile):
        return _gemini_error(400, "請先完成個人檔案，才可以生成卡圖。")
    if (request.content_length or 0) > CARD_PROXY_MAX_BYTES:
        return _gemini_error(400, "相片太大，請用一張較小的相片再試。")
    body = request.get_json(silent=True) or {}
    contents = body.get("contents")
    if not isinstance(contents, list) or not contents:
        return _gemini_error(400, "卡圖資料不完整，請再試一次。")
    api_key = str(current_app.config.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY") or "")
    if not api_key:
        return _gemini_error(400, "平台尚未設定出圖金鑰，請告訴領袖。")
    mine = [row for row in st.list("audit_log")
            if row.get("actor_id") == g.user["id"] and row.get("action") == "profile_card_proxy"]
    now = datetime.now(timezone.utc)
    if mine:
        try:
            last = datetime.fromisoformat(str(mine[-1].get("created_at") or "").replace("Z", "+00:00"))
            if (now - last).total_seconds() < CARD_WAIT_SECONDS:
                return _gemini_error(429, "生成太頻密，請等半分鐘再試。")
        except ValueError:
            pass
        today = now.strftime("%Y-%m-%d")
        if sum(1 for row in mine if str(row.get("created_at") or "")[:10] == today) >= CARD_PROXY_DAILY_MAX:
            return _gemini_error(429, "今日的出圖次數已用完，請明天再試。")
    aspect = str(((body.get("generationConfig") or {}).get("imageConfig") or {}).get("aspectRatio") or "2:3")
    if not re.fullmatch(r"\d{1,2}:\d{1,2}", aspect):
        aspect = "2:3"
    model = str(current_app.config.get("GEMINI_IMAGE_MODEL") or "gemini-2.5-flash-image")
    audit(g.user, "profile_card_proxy", "profiles", g.user["id"], {})
    try:
        upstream = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            params={"key": api_key}, timeout=110,
            json={"contents": contents,
                  "generationConfig": {"imageConfig": {"aspectRatio": aspect}}},
        )
    except Exception:
        return _gemini_error(502, "出圖服務暫時未能連接，請稍後再試。")
    return Response(upstream.content, status=upstream.status_code,
                    content_type="application/json")


@profile_routes.get("/card-maker")
@scout_required
def card_maker():
    """The card generator, embedded: Pokémon cards only.

    The generator page itself talks to its remote prompt vault and to
    Gemini with the key typed into it; the platform only hosts the page and
    keeps the finished picture (see the upload below).
    """
    return render_template("scout/card_maker.html",
                           profile=load_profile(store(), g.user["id"]))


@profile_routes.post("/profile/card-upload")
@scout_required
def card_upload():
    """Keep a card picture made in the generator on this scout's profile."""
    st = store()
    if not profile_complete(load_profile(st, g.user["id"])):
        return fail(400, "profile_incomplete", "請先完成個人檔案，才可以放上卡圖。",
                    "Please complete your profile before adding a card picture.")
    file = request.files.get("card_image")
    name = str(getattr(file, "filename", "") or "")
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if file is None or ext not in {"png", "jpg", "jpeg", "webp", "avif"}:
        return fail(400, "card_file", "請選擇一張卡圖（PNG、JPG 或 WebP）。",
                    "Please choose a card picture (PNG, JPG or WebP).")
    data = file.read()
    if not data:
        return fail(400, "card_file", "請選擇一張卡圖（PNG、JPG 或 WebP）。",
                    "Please choose a card picture (PNG, JPG or WebP).")
    data, mime, ext = _compact_card_picture(data, file.mimetype or "image/png", ext)
    uploaded = st.upload_file(name=f"card-{g.user['id']}.{ext}", mime_type=mime, data=data)
    url = _card_display_url(uploaded)
    patch = {"card_image_url": url, "card_image_id": str(uploaded.get("id") or ""),
             "card_generated_at": now_iso()}
    if st.get("profiles", g.user["id"]):
        st.update("profiles", g.user["id"], patch)
    else:
        st.insert("profiles", {"user_id": g.user["id"], **patch})
    audit(g.user, "profile_card_upload", "profiles", g.user["id"], {"stored": uploaded.get("stored")})
    if wants_json():
        return ok(card_image_url=url)
    flash({"kind": "success", "zh": "卡圖已放到你的個人檔案。", "en": "Your card picture is on your profile."}, "result")
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
