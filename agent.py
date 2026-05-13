"""
Football Trend Agent v3 — Fixed field names + rich email with links
- 6AM: Morning Brief (sounds + creator spy + hashtags + video ideas)
- 2PM: Afternoon Idea Refresh
- 9PM: Night Brief (viral recap + tomorrow's plan)
Content pillars: 1v1 competition, DB drills, workout/training, motivation
"""

import os
import time
import json
import random
import requests
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

# ── CONFIG ────────────────────────────────────────────────────────
APIFY_TOKEN    = os.environ.get("APIFY_TOKEN", "")
EMAIL_FROM     = os.environ.get("EMAIL_FROM", "therealjoshjames22@gmail.com")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "")
EMAIL_TO       = os.environ.get("EMAIL_TO", "therealjoshjames22@gmail.com")
BRIEF_TYPE     = os.environ.get("BRIEF_TYPE", "morning")  # morning | afternoon | night

APIFY_BASE = "https://api.apify.com/v2"

# ── CONTENT PILLARS ───────────────────────────────────────────────
PILLARS = {
    "1v1":        ["1v1","one on one","lockdown","shutdown","press coverage","man coverage","jam","bump","guard","lock"],
    "drills":     ["drill","technique","route","break","backpedal","hip","turn","db drill","cornerback","footwork","press","off coverage","ladder","cone"],
    "workout":    ["workout","training","speed","agility","strength","lift","gym","combine","40 yard","vertical","explosive","faster"],
    "motivation": ["grind","mindset","motivation","nobody believed","outwork","hunger","dog","dawg","elite","mentality","sacrifice","offseason"]
}

FOOTBALL_KW = [
    "football","training","drill","qb","quarterback","receiver","wr","db",
    "cornerback","linebacker","defense","offense","route","7on7","combine",
    "camp","athlete","speed","agility","grind","workout","lockdown","1v1",
    "defensiveback","dbdrills","footballtraining"
]

CREATORS = [
    {"handle": "pick6athletics",   "size": "small"},
    {"handle": "firstdowndbs",     "size": "small"},
    {"handle": "jarrettpaul",      "size": "small"},
    {"handle": "trickx_5",         "size": "small"},
    {"handle": "prest0ndavenport", "size": "mid"},
    {"handle": "overtimeszn",      "size": "large"},
    {"handle": "ajgreene15",       "size": "large"},
]

HASHTAGS = [
    "footballtraining","dbtraining","cornerback","1v1football",
    "widereceivertraining","footballdrills","footballworkout",
    "highschoolfootball","collegefootball","defensiveback","7on7"
]

IDEA_TEMPLATES = {
    "1v1": [
        "1v1 drill against [opponent type] — show 3 reps, win each one, caption: 'Nobody getting past me 🔒 #1v1 #db'",
        "Film yourself shutting down a WR route for route — voiceover explaining your read at each step",
        "React to a viral 1v1 clip then show your version of the same matchup",
        "Press coverage tutorial: 3 different WR releases, how you handle each one",
        "'Can you guard me?' challenge — invite a WR friend, film the whole session raw",
    ],
    "drills": [
        "4 drills every DB should do before practice — list format, each drill 5 seconds",
        "The ONE drill that fixed my backpedal — before/after clip",
        "Morning drill routine from zero — film your actual warmup start to finish",
        "Breakdown: how to mirror a WR's hips on a double move (slow-mo + voiceover)",
        "'DB Fundamentals Day [X]' series — one technique per video, consistent format",
    ],
    "workout": [
        "Speed workout that adds 0.2 seconds to your 40 — 3 exercises, film each one",
        "DB combine prep workout — show exactly what you do 8 weeks out",
        "Gym session focused on explosion: box jumps, hip thrusts, band work",
        "The workout nobody talks about for DBs — hip flexibility and change of direction",
        "Morning vs night workout routine — film both, show the difference in energy",
    ],
    "motivation": [
        "Voiceover on outdoor training: 'This is what the offseason looks like when you want it'",
        "'Nobody is outworking me this offseason' — raw training clips, no music just sounds",
        "Show a rejection or setback + what you did the next morning (authentic story)",
        "Day in the life: 5AM to 10PM grind day — full vlog style",
        "'I train like this so game day feels easy' — connect your drills to real game situations",
    ]
}

# ── APIFY HELPERS ──────────────────────────────────────────────────
def run_actor(actor_id, input_data, timeout=120):
    try:
        actor_slug = actor_id.replace("/", "~")  # CRITICAL: API requires ~ not /
        resp = requests.post(
            f"{APIFY_BASE}/acts/{actor_slug}/runs",
            params={"token": APIFY_TOKEN},
            json=input_data,
            timeout=30
        )
        resp.raise_for_status()
        run_id    = resp.json()["data"]["id"]
        dataset_id = resp.json()["data"]["defaultDatasetId"]

        deadline = time.time() + timeout
        status   = "RUNNING"
        while time.time() < deadline:
            sr = requests.get(
                f"{APIFY_BASE}/actor-runs/{run_id}",
                params={"token": APIFY_TOKEN},
                timeout=15
            )
            status = sr.json()["data"]["status"]
            if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
                break
            time.sleep(8)

        if status != "SUCCEEDED":
            print(f"  [WARN] {actor_id} → {status}")
            return []

        items = requests.get(
            f"{APIFY_BASE}/datasets/{dataset_id}/items",
            params={"token": APIFY_TOKEN, "clean": "true"},
            timeout=30
        )
        return items.json() if items.ok else []
    except Exception as e:
        print(f"  [ERROR] {actor_id}: {e}")
        return []


# ── SCORING ───────────────────────────────────────────────────────
def score_sound(sound):
    """Score a sound for football/workout relevance. Returns (score 0-10, category)."""
    score = 0
    name  = (sound.get("title", "") + " " + sound.get("author", "")).lower()

    # Football/workout keywords in title
    football_hits = sum(1 for kw in FOOTBALL_KW if kw in name)
    score += football_hits * 3

    # Trending momentum: rank_diff > 0 means rising fast
    rank_diff = sound.get("rank_diff") or 0
    if rank_diff > 20:
        score += 3
    elif rank_diff > 5:
        score += 2
    elif rank_diff > 0:
        score += 1

    # Trend trajectory: last value in trend array vs first
    trend = sound.get("trend", [])
    if len(trend) >= 2:
        first_val = trend[0].get("value", 0)
        last_val  = trend[-1].get("value", 0)
        if first_val > 0 and last_val / first_val > 3:
            score += 2  # rapidly rising
        elif last_val > 0.5:
            score += 1  # already popular

    # Cap at 10
    score = min(score, 10)

    # Category
    if football_hits > 0:
        cat = "football"
    elif any(k in name for k in ["gym","lift","pump","grind","beast","power","energy","fire","hype","motivation"]):
        cat = "workout"
    elif any(k in name for k in ["sport","game","play","team","win","champion","goat"]):
        cat = "sport"
    else:
        cat = "general"

    return score, cat


def get_pillar(text):
    text = text.lower()
    for pillar, kws in PILLARS.items():
        for kw in kws:
            if kw in text:
                return pillar
    return None


# ── DATA FETCHERS ──────────────────────────────────────────────────
def fetch_trending_sounds():
    print("  Fetching trending sounds…")
    raw = run_actor("burbn/tiktok-trending-sounds", {
        "country_code": "US", "period": 7, "rank_type": "popular", "maxResults": 50
    })
    sounds = []
    for s in raw:
        sc, cat = score_sound(s)
        sounds.append({
            "title":    s.get("title", "Unknown"),
            "author":   s.get("author", ""),
            "rank":     s.get("rank", 99),
            "rank_diff": s.get("rank_diff") or 0,
            "link":     s.get("link", ""),          # direct TikTok sound URL
            "cover":    s.get("cover", ""),          # album art
            "score":    sc,
            "category": cat,
            "rising":   (s.get("rank_diff") or 0) > 5,
        })
    # Sort: football first, then by score
    sounds.sort(key=lambda x: (0 if x["category"] == "football" else 1, -x["score"]))
    return sounds[:15]


def fetch_creator_spy():
    print("  Running Creator Spy…")
    all_handles  = [c["handle"] for c in CREATORS]
    handle_size  = {c["handle"]: c["size"] for c in CREATORS}
    results      = []
    try:
        raw = run_actor("clockworks/tiktok-scraper", {
            "profiles":       all_handles,
            "resultsPerPage": 6,
            "profileSorting": "latest"
        }, timeout=200)

        # Group videos by creator handle
        by_handle = {}
        for v in raw:
            h = (v.get("authorMeta") or {}).get("name", "") or v.get("input", "")
            if h:
                by_handle.setdefault(h, []).append(v)

        for handle in all_handles:
            videos = by_handle.get(handle, [])
            recent = []
            for v in videos[:5]:
                plays   = v.get("playCount",    0) or 0
                likes   = v.get("diggCount",    0) or 0
                shares  = v.get("shareCount",   0) or 0
                saves   = v.get("collectCount", 0) or 0
                desc    = v.get("text", v.get("desc", "")) or ""
                sound   = (v.get("musicMeta") or {}).get("musicName", "") or ""
                sound_author = (v.get("musicMeta") or {}).get("musicAuthor", "") or ""
                thumb   = (v.get("videoMeta") or {}).get("coverUrl", "") or ""
                url     = v.get("webVideoUrl", "") or ""
                fans    = (v.get("authorMeta") or {}).get("fans", 0) or 0

                # Why it went viral
                viral_reason = ""
                if plays > 500_000:
                    viral_reason = "🔥 Mega viral — massive reach"
                elif plays > 100_000:
                    if shares > likes * 0.05:
                        viral_reason = "⚡ High share rate — relatable/shareable content"
                    elif saves > likes * 0.1:
                        viral_reason = "📌 High saves — educational/reference value"
                    else:
                        viral_reason = "📈 Strong engagement — good hook/timing"

                recent.append({
                    "desc":         desc[:100],
                    "plays":        plays,
                    "likes":        likes,
                    "shares":       shares,
                    "saves":        saves,
                    "sound":        sound,
                    "sound_author": sound_author,
                    "thumb":        thumb,
                    "url":          url,
                    "fans":         fans,
                    "viral":        plays > 100_000,
                    "pillar":       get_pillar(desc),
                    "viral_reason": viral_reason,
                })
            results.append({
                "handle": handle,
                "size":   handle_size.get(handle, "mid"),
                "videos": recent
            })
    except Exception as e:
        print(f"  [ERROR] Creator spy failed: {e}")
        for c in CREATORS:
            results.append({"handle": c["handle"], "size": c["size"], "videos": []})
    return results


def fetch_hashtags():
    print("  Scanning hashtags…")
    raw = run_actor("clockworks/tiktok-hashtag-scraper", {
        "hashtags": HASHTAGS[:6], "resultsPerPage": 20
    }, timeout=120)

    # Collect top videos per hashtag + trending sounds used
    tag_data   = {}
    top_videos = []

    for item in raw:
        tag      = item.get("input", "").lower().strip("#")
        plays    = item.get("playCount", 0) or 0
        likes    = item.get("diggCount", 0) or 0
        shares   = item.get("shareCount", 0) or 0
        saves    = item.get("collectCount", 0) or 0
        url      = item.get("webVideoUrl", "") or ""
        desc     = item.get("text", "") or ""
        thumb    = (item.get("videoMeta") or {}).get("coverUrl", "") or ""
        sound    = (item.get("musicMeta") or {}).get("musicName", "") or ""
        author   = (item.get("authorMeta") or {}).get("name", "") or ""
        fans     = (item.get("authorMeta") or {}).get("fans", 0) or 0
        ht_views = (item.get("searchHashtag") or {}).get("views", 0) or 0

        if tag:
            if tag not in tag_data or plays > tag_data[tag]["top_plays"]:
                tag_data[tag] = {"views": ht_views, "top_plays": plays}

        if plays > 50_000 and url:
            top_videos.append({
                "tag":    tag,
                "desc":   desc[:80],
                "plays":  plays,
                "likes":  likes,
                "shares": shares,
                "saves":  saves,
                "url":    url,
                "thumb":  thumb,
                "sound":  sound,
                "author": author,
                "fans":   fans,
            })

    top_videos.sort(key=lambda x: x["plays"], reverse=True)
    tags_sorted = sorted(tag_data.items(), key=lambda x: x[1]["views"], reverse=True)
    return tags_sorted[:10], top_videos[:6]


# ── VIDEO IDEA GENERATOR ──────────────────────────────────────────
def generate_video_ideas(sounds, creators, top_videos):
    ideas       = []
    hot_pillars = {}
    viral_inspo = []

    for c in creators:
        for v in c["videos"]:
            if v["viral"] and v["pillar"]:
                hot_pillars[v["pillar"]] = hot_pillars.get(v["pillar"], 0) + 1
                viral_inspo.append({
                    "handle": c["handle"],
                    "desc":   v["desc"],
                    "plays":  v["plays"],
                    "pillar": v["pillar"],
                    "url":    v["url"],
                })

    top_sound  = sounds[0]["title"] if sounds else "a trending sound"
    top_sound2 = sounds[1]["title"] if len(sounds) > 1 else top_sound

    for pillar, templates in IDEA_TEMPLATES.items():
        template   = random.choice(templates)
        priority   = "🔥 HOT" if hot_pillars.get(pillar, 0) > 0 else "📌"
        inspo      = next((v for v in viral_inspo if v["pillar"] == pillar), None)
        inspo_note = f" (inspired by @{inspo['handle']} — {inspo['plays']:,} plays)" if inspo else ""

        ideas.append({
            "pillar":    pillar.upper(),
            "priority":  priority,
            "idea":      template,
            "sound":     top_sound if pillar in ["1v1", "drills"] else top_sound2,
            "hashtags":  f"#{'dbtraining' if pillar in ['1v1','drills'] else 'footballworkout' if pillar=='workout' else 'footballmotivation'} #db #cornerback",
            "inspo":     inspo_note,
            "inspo_url": inspo["url"] if inspo else "",
        })

    for v in viral_inspo[:2]:
        ideas.append({
            "pillar":    "TREND HIJACK",
            "priority":  "⚡ URGENT",
            "idea":      f"@{v['handle']} just got {v['plays']:,} plays on: '{v['desc'][:50]}' — post YOUR version before it peaks",
            "sound":     top_sound,
            "hashtags":  "#footballtraining #db #cornerback",
            "inspo":     "",
            "inspo_url": v["url"],
        })

    return ideas


# ── EMAIL CSS ─────────────────────────────────────────────────────
def email_style():
    return """
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&display=swap');
    *{box-sizing:border-box;margin:0;padding:0;}
    body{background:#060606;color:#e8e8e8;font-family:'Inter',system-ui,sans-serif;max-width:660px;margin:0 auto;padding:16px;}
    h2{font-size:15px;font-weight:700;letter-spacing:.5px;margin-bottom:12px;color:#fff;}
    a{color:inherit;text-decoration:none;}
    .card{background:#111217;border:1px solid #1e2028;border-radius:14px;padding:18px;margin-bottom:14px;}
    .tag{display:inline-block;padding:3px 9px;border-radius:20px;font-size:10px;font-weight:700;letter-spacing:.5px;}
    .tag-green{background:#0a2e14;color:#4ade80;border:1px solid #166534;}
    .tag-yellow{background:#2a1a00;color:#fbbf24;border:1px solid #78350f;}
    .tag-red{background:#2a0808;color:#f87171;border:1px solid #7f1d1d;}
    .tag-blue{background:#0a1a2e;color:#60a5fa;border:1px solid #1e3a5f;}
    .tag-gray{background:#1a1a1a;color:#888;border:1px solid #333;}
    .stat{font-size:11px;color:#666;}
    .stat strong{color:#aaa;}
    .divider{border:none;border-top:1px solid #1e2028;margin:12px 0;}
    """

# ── SOUND COLOR ───────────────────────────────────────────────────
def sound_tag(cat, score):
    if cat == "football":
        return f'<span class="tag tag-green">🏈 FOOTBALL · {score}/10</span>'
    elif cat == "workout":
        return f'<span class="tag tag-yellow">💪 WORKOUT · {score}/10</span>'
    elif cat == "sport":
        return f'<span class="tag tag-blue">🏅 SPORT · {score}/10</span>'
    else:
        return f'<span class="tag tag-gray">🎵 GENERAL · {score}/10</span>'


# ── EMAIL BUILDERS ─────────────────────────────────────────────────
def build_morning_email(sounds, creators, tags, top_videos, ideas, date_str):
    top = sounds[0] if sounds else {"title": "—", "link": ""}

    # ── SOUNDS ──
    sound_rows = ""
    for i, s in enumerate(sounds[:10], 1):
        rising_badge = ' <span class="tag tag-green" style="font-size:9px;">▲ RISING</span>' if s["rising"] else ""
        link_open  = f'<a href="{s["link"]}" style="color:#e8e8e8;">' if s["link"] else ""
        link_close = "</a>" if s["link"] else ""
        sound_rows += f"""
        <div style="display:flex;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid #1a1a22;">
          {'<img src="' + s['cover'] + '" style="width:40px;height:40px;border-radius:8px;object-fit:cover;flex-shrink:0;" />' if s.get('cover') else '<div style="width:40px;height:40px;border-radius:8px;background:#1e2028;flex-shrink:0;"></div>'}
          <div style="flex:1;min-width:0;">
            <div style="font-weight:600;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{link_open}#{i} {s['title']}{link_close}{rising_badge}</div>
            <div class="stat" style="margin-top:2px;">{s['author']} &nbsp;·&nbsp; Rank #{s['rank']}</div>
          </div>
          <div style="flex-shrink:0;">{sound_tag(s['category'], s['score'])}</div>
        </div>"""

    # ── CREATORS ──
    creator_html = ""
    # Sort: small first (emphasize emerging), large last
    sorted_creators = sorted(creators, key=lambda c: {"small":0,"mid":1,"large":2}.get(c["size"],1))
    for c in sorted_creators:
        size_icons = {"small": "🌱 EMERGING", "mid": "📈 MID-TIER", "large": "⚡ LARGE"}
        size_label = size_icons.get(c["size"], "")
        size_color = {"small": "#4ade80", "mid": "#fbbf24", "large": "#60a5fa"}.get(c["size"], "#888")
        viral_vids = [v for v in c["videos"] if v["viral"]]

        creator_html += f"""
        <div style="margin-bottom:16px;padding-bottom:16px;border-bottom:1px solid #1e2028;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
            <div>
              <span style="font-weight:700;font-size:14px;">@{c['handle']}</span>
              <span style="font-size:10px;color:{size_color};margin-left:8px;font-weight:700;">{size_label}</span>
            </div>
            {'<span class="tag tag-red">🔥 VIRAL</span>' if viral_vids else ''}
          </div>"""

        if not c["videos"]:
            creator_html += '<div style="font-size:12px;color:#555;">No recent videos found</div>'
        else:
            for v in c["videos"][:3]:
                pillar_tag = f'<span class="tag tag-green" style="font-size:9px;">{v["pillar"].upper()}</span> ' if v["pillar"] else ""
                watch_btn  = f'<a href="{v["url"]}" style="display:inline-block;padding:4px 10px;background:#1e2028;border-radius:6px;font-size:10px;color:#60a5fa;font-weight:600;margin-top:6px;">▶ Watch on TikTok</a>' if v["url"] else ""
                viral_why  = f'<div style="font-size:10px;color:#fbbf24;margin-top:3px;">{v["viral_reason"]}</div>' if v["viral_reason"] else ""
                thumb_html = f'<img src="{v["thumb"]}" style="width:52px;height:70px;border-radius:6px;object-fit:cover;flex-shrink:0;" />' if v["thumb"] else ""

                creator_html += f"""
                <div style="display:flex;gap:10px;margin-bottom:10px;background:#0d0f14;border-radius:8px;padding:8px;">
                  {thumb_html}
                  <div style="flex:1;min-width:0;">
                    <div style="font-size:11px;color:#bbb;margin-bottom:4px;line-height:1.4;">{pillar_tag}{v['desc'] or '(no caption)'}</div>
                    <div class="stat"><strong style="color:#4ade80;">{v['plays']:,} plays</strong> · {v['likes']:,} likes · {v['saves']:,} saves</div>
                    {f'<div class="stat" style="margin-top:2px;">🎵 {v["sound"]}</div>' if v["sound"] else ""}
                    {viral_why}
                    {watch_btn}
                  </div>
                </div>"""
        creator_html += "</div>"

    # ── HASHTAGS ──
    ht_html = ""
    for tag, data in tags[:8]:
        views = data["views"]
        views_fmt = f"{views/1_000_000_000:.1f}B" if views >= 1e9 else f"{views/1_000_000:.0f}M" if views >= 1e6 else f"{views:,}"
        ht_html += f'<span style="background:#0a1a2e;color:#60a5fa;padding:5px 12px;border-radius:20px;margin:3px;display:inline-block;font-size:12px;font-weight:600;">#{tag} <span style="color:#2563eb;font-size:10px;">{views_fmt} views</span></span>'

    # ── TOP HASHTAG VIDEOS ──
    ht_videos_html = ""
    for v in top_videos[:4]:
        thumb_html = f'<img src="{v["thumb"]}" style="width:48px;height:64px;border-radius:6px;object-fit:cover;flex-shrink:0;" />' if v["thumb"] else ""
        watch_btn  = f'<a href="{v["url"]}" style="display:inline-block;padding:3px 8px;background:#1e2028;border-radius:5px;font-size:10px;color:#60a5fa;font-weight:600;">▶ Watch</a>' if v["url"] else ""
        fans_fmt   = f"{v['fans']/1000:.0f}K" if v["fans"] >= 1000 else str(v["fans"])
        ht_videos_html += f"""
        <div style="display:flex;gap:10px;margin-bottom:10px;background:#0d0f14;border-radius:8px;padding:8px;">
          {thumb_html}
          <div style="flex:1;min-width:0;">
            <div style="font-size:11px;color:#bbb;margin-bottom:4px;">#{v['tag']} · @{v['author']} ({fans_fmt} followers)</div>
            <div style="font-size:12px;color:#e8e8e8;margin-bottom:4px;line-height:1.4;">{v['desc']}</div>
            <div class="stat"><strong style="color:#4ade80;">{v['plays']:,} plays</strong> · {v['shares']:,} shares</div>
            {f'<div class="stat">🎵 {v["sound"]}</div>' if v["sound"] else ""}
            {watch_btn}
          </div>
        </div>"""

    # ── VIDEO IDEAS ──
    ideas_html = ""
    for idea in ideas:
        p_color = "#f87171" if "URGENT" in idea["priority"] else "#fbbf24" if "HOT" in idea["priority"] else "#666"
        inspo_link = f' <a href="{idea["inspo_url"]}" style="color:#60a5fa;font-size:10px;">▶ Watch inspo</a>' if idea.get("inspo_url") else ""
        ideas_html += f"""
        <div style="border-left:3px solid {p_color};padding:10px 14px;margin-bottom:10px;background:#0d0f14;border-radius:0 8px 8px 0;">
          <div style="font-size:10px;font-weight:700;color:{p_color};margin-bottom:4px;letter-spacing:.5px;">{idea['priority']} · {idea['pillar']}{idea['inspo']}{inspo_link}</div>
          <div style="font-size:13px;color:#e8e8e8;margin-bottom:6px;line-height:1.5;">{idea['idea']}</div>
          <div style="font-size:10px;color:#555;">🎵 Use: <strong style="color:#888;">{idea['sound']}</strong> &nbsp;·&nbsp; {idea['hashtags']}</div>
        </div>"""

    top_sound_link = f'<a href="{top["link"]}" style="color:#4ade80;text-decoration:underline;">"{top["title"]}"</a>' if top.get("link") else f'"{top["title"]}"'

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{email_style()}</style></head><body>

<div style="background:linear-gradient(135deg,#0d1117,#161b22);border-radius:16px;padding:24px;margin-bottom:14px;text-align:center;border:1px solid #21262d;">
  <div style="font-size:40px;margin-bottom:8px;">🏈</div>
  <h1 style="font-size:22px;font-weight:900;color:#fff;margin-bottom:4px;">Good Morning, Joshua</h1>
  <p style="color:#666;font-size:13px;">6AM Football Trend Brief &nbsp;·&nbsp; {date_str}</p>
</div>

<div style="background:#0a1f0a;border:1px solid #166534;border-radius:12px;padding:18px;margin-bottom:14px;">
  <h2 style="color:#4ade80;">⚡ Your Move Today</h2>
  <p style="font-size:14px;margin-bottom:8px;line-height:1.6;"><strong>Hottest sound right now:</strong> {top_sound_link}</p>
  <p style="font-size:13px;color:#bbb;line-height:1.6;"><strong style="color:#fff;">Post idea:</strong> Film a DB press coverage drill. Name a specific WR or school you're preparing for in the caption.</p>
  <p style="font-size:12px;color:#555;margin-top:8px;">📅 Best posting window: 6–9PM ET tonight</p>
</div>

<div class="card">
  <h2>🎯 Video Ideas For Today</h2>
  {ideas_html}
</div>

<div class="card">
  <h2>🎵 Trending Sounds — Color Coded For You</h2>
  <div style="font-size:10px;color:#555;margin-bottom:10px;">🟢 Football/DB &nbsp;·&nbsp; 🟡 Workout/Hype &nbsp;·&nbsp; 🔵 Sport &nbsp;·&nbsp; ⚪ General</div>
  {sound_rows}
</div>

<div class="card">
  <h2>👁️ Creator Spy</h2>
  <div style="font-size:11px;color:#555;margin-bottom:12px;">🌱 Emerging creators first · ⚡ Large shown last for reference</div>
  {creator_html}
</div>

<div class="card">
  <h2>🏷️ Trending Hashtags</h2>
  {ht_html}
  {('<hr class="divider"><div style="font-size:13px;font-weight:700;color:#fff;margin-bottom:10px;">🔥 Top Videos Under These Hashtags</div>' + ht_videos_html) if ht_videos_html else ""}
</div>

<p style="text-align:center;font-size:10px;color:#333;padding:16px 0;">Football Trend Agent &nbsp;·&nbsp; 6AM Brief &nbsp;·&nbsp; therealjoshjames22@gmail.com</p>
</body></html>"""
    return html


def build_afternoon_email(sounds, creators, top_videos, ideas, date_str):
    urgent      = [i for i in ideas if "URGENT" in i["priority"] or "HOT" in i["priority"]]
    new_viral   = [v for c in creators for v in c["videos"] if v["viral"]]

    viral_html = ""
    for v in new_viral[:5]:
        watch_btn = f'<a href="{v["url"]}" style="display:inline-block;padding:3px 8px;background:#1e2028;border-radius:5px;font-size:10px;color:#60a5fa;font-weight:600;margin-top:4px;">▶ Watch on TikTok</a>' if v["url"] else ""
        viral_html += f"""
        <div style="padding:10px 0;border-bottom:1px solid #1e2028;">
          <div style="font-size:13px;"><strong style="color:#4ade80;">{v['plays']:,} plays</strong> — {v['desc'][:70]}</div>
          {f'<div class="stat" style="margin-top:2px;">{v["viral_reason"]}</div>' if v["viral_reason"] else ""}
          {watch_btn}
        </div>"""
    if not viral_html:
        viral_html = '<p style="font-size:13px;color:#444;">No major viral spikes since this morning.</p>'

    ideas_html = ""
    for idea in (urgent or ideas[:3]):
        p_color = "#f87171" if "URGENT" in idea["priority"] else "#fbbf24"
        inspo_link = f' <a href="{idea["inspo_url"]}" style="color:#60a5fa;font-size:10px;">▶ Watch inspo</a>' if idea.get("inspo_url") else ""
        ideas_html += f"""
        <div style="border-left:3px solid {p_color};padding:10px 14px;margin-bottom:10px;background:#0d0f14;border-radius:0 8px 8px 0;">
          <div style="font-size:10px;font-weight:700;color:{p_color};margin-bottom:4px;">{idea['priority']} · {idea['pillar']}{inspo_link}</div>
          <div style="font-size:13px;color:#e8e8e8;margin-bottom:4px;">{idea['idea']}</div>
          <div style="font-size:10px;color:#555;">🎵 {idea['sound']}</div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{email_style()}</style></head><body>
<div style="background:linear-gradient(135deg,#0d1a0d,#162416);border-radius:16px;padding:20px;margin-bottom:14px;text-align:center;border:1px solid #166534;">
  <div style="font-size:32px;margin-bottom:6px;">📈</div>
  <h1 style="font-size:20px;font-weight:900;color:#fff;">Afternoon Update</h1>
  <p style="color:#555;font-size:12px;">2PM Trend Check &nbsp;·&nbsp; {date_str}</p>
</div>
<div class="card">
  <h2>🔥 Viral Right Now — Post Before It Peaks</h2>
  {viral_html}
</div>
<div class="card">
  <h2>🎯 Top Ideas This Afternoon</h2>
  {ideas_html}
</div>
<p style="text-align:center;font-size:10px;color:#333;padding:16px 0;">Football Trend Agent &nbsp;·&nbsp; 2PM Brief &nbsp;·&nbsp; therealjoshjames22@gmail.com</p>
</body></html>"""
    return html


def build_night_email(sounds, creators, ideas, date_str):
    viral_today  = [v for c in creators for v in c["videos"] if v["viral"]]
    top_sound    = sounds[0] if sounds else {"title": "—", "link": ""}

    recap_html = ""
    for v in viral_today[:5]:
        watch_btn = f'<a href="{v["url"]}" style="display:inline-block;padding:3px 8px;background:#1e2028;border-radius:5px;font-size:10px;color:#60a5fa;font-weight:600;margin-top:4px;">▶ Watch</a>' if v["url"] else ""
        recap_html += f"""
        <div style="padding:10px 0;border-bottom:1px solid #1e2028;">
          <div style="font-size:13px;"><strong style="color:#4ade80;">{v['plays']:,} plays</strong> — {v['desc'][:70]}</div>
          {watch_btn}
        </div>"""
    if not recap_html:
        recap_html = '<p style="font-size:13px;color:#444;">No major viral content today in your niche.</p>'

    tomorrow_html = ""
    for idea in ideas[:4]:
        tomorrow_html += f"""
        <div style="border-left:3px solid #60a5fa;padding:10px 14px;margin-bottom:10px;background:#0d0f14;border-radius:0 8px 8px 0;">
          <div style="font-size:10px;font-weight:700;color:#60a5fa;margin-bottom:4px;letter-spacing:.5px;">{idea['pillar']}</div>
          <div style="font-size:13px;color:#e8e8e8;margin-bottom:4px;">{idea['idea']}</div>
          <div style="font-size:10px;color:#555;">🎵 {idea['sound']} &nbsp;·&nbsp; {idea['hashtags']}</div>
        </div>"""

    top_sound_link = f'<a href="{top_sound["link"]}" style="color:#4ade80;">{top_sound["title"]}</a>' if top_sound.get("link") else top_sound["title"]

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{email_style()}</style></head><body>
<div style="background:linear-gradient(135deg,#0a0a14,#0f0f1e);border-radius:16px;padding:20px;margin-bottom:14px;text-align:center;border:1px solid #21262d;">
  <div style="font-size:32px;margin-bottom:6px;">🌙</div>
  <h1 style="font-size:20px;font-weight:900;color:#fff;">Night Brief</h1>
  <p style="color:#555;font-size:12px;">9PM Recap &nbsp;·&nbsp; {date_str}</p>
</div>
<div class="card">
  <h2>📊 What Went Viral In Your Niche Today</h2>
  {recap_html}
</div>
<div class="card">
  <h2>🗓️ Tomorrow's Content Plan</h2>
  {tomorrow_html}
</div>
<div style="background:#0a1f0a;border:1px solid #166534;border-radius:12px;padding:16px;margin-bottom:14px;">
  <h2 style="color:#4ade80;">🎵 Use This Sound Tomorrow</h2>
  <p style="font-size:14px;line-height:1.6;">{top_sound_link} — post with this first thing in the morning for max reach</p>
</div>
<p style="text-align:center;font-size:10px;color:#333;padding:16px 0;">Football Trend Agent &nbsp;·&nbsp; 9PM Brief &nbsp;·&nbsp; therealjoshjames22@gmail.com</p>
</body></html>"""
    return html


# ── EMAIL SENDER ──────────────────────────────────────────────────
def send_email(subject, html_body):
    if not EMAIL_PASSWORD:
        print(f"[WARN] No EMAIL_PASSWORD — skipping send. Subject: {subject}")
        return
    try:
        msg            = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = EMAIL_FROM
        msg["To"]      = EMAIL_TO
        msg.attach(MIMEText(html_body, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(EMAIL_FROM, EMAIL_PASSWORD)
            s.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
        print(f"[✓] Email sent: {subject}")
    except Exception as e:
        print(f"[ERROR] Email failed: {e}")


# ── WRITE DATA.JSON (dashboard reads this on load) ────────────────
def write_data_json(sounds, creators, tags, top_videos, ideas):
    """Write fresh scan data to data.json so the dashboard is always current."""
    now = datetime.utcnow().isoformat() + "Z"

    # Breakout alert: any video with 50K+ views posted in last 6 hours
    six_hrs_ago = time.time() - 6 * 3600
    breakouts = []
    for v in top_videos:
        ct = v.get("createTime", 0)
        plays = v.get("playCount", 0) or v.get("stats", {}).get("playCount", 0)
        if ct > six_hrs_ago and plays >= 50000:
            breakouts.append({
                "handle": v.get("authorMeta", {}).get("name", ""),
                "plays":  plays,
                "desc":   v.get("text", v.get("desc", ""))[:120],
                "url":    v.get("webVideoUrl", ""),
                "sound":  v.get("musicMeta", {}).get("musicName", ""),
            })

    data = {
        "lastUpdated": now,
        "briefType":  BRIEF_TYPE,
        "sounds": [
            {
                "title":     s.get("title", s.get("soundTitle", "")),
                "author":    s.get("author", s.get("artistName", "")),
                "rank":      s.get("rank", 0),
                "rank_diff": s.get("rank_diff", 0),
                "cover":     s.get("cover", ""),
                "link":      s.get("link", ""),
                "trend":     s.get("trend", []),
            }
            for s in sounds[:20]
        ],
        "creators": [
            {
                "handle":   c.get("handle", ""),
                "size":     c.get("size", ""),
                "fans":     c.get("fans", 0),
                "maxPlays": c.get("maxPlays", 0),
                "topVideo": c.get("topVideo", ""),
                "topSound": c.get("topSound", ""),
                "topDesc":  c.get("topDesc", ""),
            }
            for c in creators[:15]
        ],
        "hashtags":  tags[:15],
        "topVideos": [
            {
                "handle":     v.get("authorMeta", {}).get("name", ""),
                "fans":       v.get("authorMeta", {}).get("fans", 0),
                "plays":      v.get("playCount", 0),
                "desc":       v.get("text", v.get("desc", ""))[:120],
                "sound":      v.get("musicMeta", {}).get("musicName", ""),
                "url":        v.get("webVideoUrl", ""),
                "thumb":      v.get("videoMeta", {}).get("coverUrl", ""),
                "createTime": v.get("createTime", 0),
            }
            for v in top_videos[:20]
        ],
        "breakouts": breakouts,
        "ideas":     ideas[:5],
    }

    with open("data.json", "w") as f:
        json.dump(data, f, indent=2)
    print(f"[✓] data.json written — {len(sounds)} sounds, {len(creators)} creators, {len(breakouts)} breakouts")


# ── MAIN ──────────────────────────────────────────────────────────
def main():
    date_str = datetime.now().strftime("%A, %B %-d %Y")
    brief    = BRIEF_TYPE.lower()

    print(f"\n{'='*52}")
    print(f"Football Trend Agent v3 — {brief.upper()} RUN")
    print(f"{date_str}")
    print(f"{'='*52}\n")

    sounds         = fetch_trending_sounds()
    creators       = fetch_creator_spy()
    tags, top_videos = fetch_hashtags()
    ideas          = generate_video_ideas(sounds, creators, top_videos)

    print(f"\n  Sounds: {len(sounds)}  |  Creators: {len(creators)}  |  Tags: {len(tags)}  |  Top videos: {len(top_videos)}\n")

    # Always write data.json — dashboard reads this on every load
    write_data_json(sounds, creators, tags, top_videos, ideas)

    # Send full email only on the 3 daily brief times
    if brief in ("morning", "afternoon", "night"):
        if brief == "morning":
            html    = build_morning_email(sounds, creators, tags, top_videos, ideas, date_str)
            subject = f"🏈 Good Morning Joshua — Football Brief {date_str}"
        elif brief == "afternoon":
            html    = build_afternoon_email(sounds, creators, top_videos, ideas, date_str)
            subject = f"📈 Afternoon Update — {date_str}"
        else:
            html    = build_night_email(sounds, creators, ideas, date_str)
            subject = f"🌙 Night Brief — {date_str}"
        send_email(subject, html)
        print("[✓] Email sent.\n")
    else:
        # Hourly scan — only email if there's a breakout (50K+ views in last 6hrs)
        if breakouts := json.load(open("data.json")).get("breakouts"):
            b = breakouts[0]
            html = f"""<h2>⚡ BREAKOUT ALERT</h2>
            <p><strong>@{b['handle']}</strong> just hit <strong>{b['plays']:,} views</strong> in the last 6 hours.</p>
            <p>Sound: 🎵 {b['sound']}</p>
            <p>Caption: {b['desc']}</p>
            <p><a href="{b['url']}">Watch Video →</a></p>"""
            send_email(f"⚡ BREAKOUT: @{b['handle']} — {b['plays']:,} views right now", html)
            print(f"[✓] Breakout alert sent for @{b['handle']}\n")
        else:
            print("[✓] Hourly scan complete. No breakouts. data.json updated.\n")

    print("[✓] Done.\n")


if __name__ == "__main__":
    main()
