"""
Football Trend Agent v3 ÃÂ¢ÃÂÃÂ Fixed field names + rich email with links
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

# ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ CONFIG ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
APIFY_TOKEN    = os.environ.get("APIFY_TOKEN", "")
EMAIL_FROM     = os.environ.get("EMAIL_FROM", "therealjoshjames22@gmail.com")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "")
EMAIL_TO       = os.environ.get("EMAIL_TO", "therealjoshjames22@gmail.com")
BRIEF_TYPE     = os.environ.get("BRIEF_TYPE", "morning")  # morning | afternoon | night

APIFY_BASE = "https://api.apify.com/v2"

# ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ CONTENT PILLARS ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
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
        "1v1 drill against [opponent type] ÃÂ¢ÃÂÃÂ show 3 reps, win each one, caption: 'Nobody getting past me ÃÂ°ÃÂÃÂÃÂ #1v1 #db'",
        "Film yourself shutting down a WR route for route ÃÂ¢ÃÂÃÂ voiceover explaining your read at each step",
        "React to a viral 1v1 clip then show your version of the same matchup",
        "Press coverage tutorial: 3 different WR releases, how you handle each one",
        "'Can you guard me?' challenge ÃÂ¢ÃÂÃÂ invite a WR friend, film the whole session raw",
    ],
    "drills": [
        "4 drills every DB should do before practice ÃÂ¢ÃÂÃÂ list format, each drill 5 seconds",
        "The ONE drill that fixed my backpedal ÃÂ¢ÃÂÃÂ before/after clip",
        "Morning drill routine from zero ÃÂ¢ÃÂÃÂ film your actual warmup start to finish",
        "Breakdown: how to mirror a WR's hips on a double move (slow-mo + voiceover)",
        "'DB Fundamentals Day [X]' series ÃÂ¢ÃÂÃÂ one technique per video, consistent format",
    ],
    "workout": [
        "Speed workout that adds 0.2 seconds to your 40 ÃÂ¢ÃÂÃÂ 3 exercises, film each one",
        "DB combine prep workout ÃÂ¢ÃÂÃÂ show exactly what you do 8 weeks out",
        "Gym session focused on explosion: box jumps, hip thrusts, band work",
        "The workout nobody talks about for DBs ÃÂ¢ÃÂÃÂ hip flexibility and change of direction",
        "Morning vs night workout routine ÃÂ¢ÃÂÃÂ film both, show the difference in energy",
    ],
    "motivation": [
        "Voiceover on outdoor training: 'This is what the offseason looks like when you want it'",
        "'Nobody is outworking me this offseason' ÃÂ¢ÃÂÃÂ raw training clips, no music just sounds",
        "Show a rejection or setback + what you did the next morning (authentic story)",
        "Day in the life: 5AM to 10PM grind day ÃÂ¢ÃÂÃÂ full vlog style",
        "'I train like this so game day feels easy' ÃÂ¢ÃÂÃÂ connect your drills to real game situations",
    ]
}

# ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ APIFY HELPERS ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
def run_actor(actor_id, input_data, timeout=240):
    """Run Apify actor and return dataset items. Verbose debug logging."""
    try:
        if not APIFY_TOKEN:
            print("  [ERROR] APIFY_TOKEN is not set!")
            return []
        actor_slug = actor_id.replace("/", "~")
        print(f"  [DEBUG] Starting {actor_slug} input={input_data}")
        resp = requests.post(
            f"{APIFY_BASE}/acts/{actor_slug}/runs",
            params={"token": APIFY_TOKEN},
            json=input_data,
            timeout=30
        )
        print(f"  [DEBUG] Actor start HTTP {resp.status_code}")
        if not resp.ok:
            print(f"  [ERROR] Start failed: {resp.text[:300]}")
            return []
        run_data   = resp.json()["data"]
        run_id     = run_data["id"]
        dataset_id = run_data["defaultDatasetId"]
        print(f"  [DEBUG] Run ID={run_id} dataset={dataset_id}")

        deadline = time.time() + timeout
        status   = "RUNNING"
        while time.time() < deadline:
            sr = requests.get(
                f"{APIFY_BASE}/actor-runs/{run_id}",
                params={"token": APIFY_TOKEN},
                timeout=15
            )
            if not sr.ok:
                print(f"  [WARN] Poll HTTP {sr.status_code}")
                time.sleep(10)
                continue
            status = sr.json()["data"]["status"]
            usage  = sr.json()["data"].get("usageTotalUsd", "?")
            print(f"  [DEBUG] status={status} usd={usage}")
            if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
                break
            time.sleep(10)

        if status != "SUCCEEDED":
            print(f"  [WARN] {actor_id} ended with status={status}")
            return []

        items_resp = requests.get(
            f"{APIFY_BASE}/datasets/{dataset_id}/items",
            params={"token": APIFY_TOKEN, "clean": "true", "limit": 500},
            timeout=30
        )
        print(f"  [DEBUG] Dataset HTTP {items_resp.status_code}")
        if not items_resp.ok:
            print(f"  [ERROR] Dataset failed: {items_resp.text[:200]}")
            return []
        items = items_resp.json()
        print(f"  [DEBUG] Got {len(items)} items from dataset")
        return items
    except Exception as e:
        print(f"  [ERROR] {actor_id}: {e}")
        return []


def fetch_all_raw():
    """Single actor call — 5 hashtags x 10 results = ~50 items. Stays in free tier."""
    print("  Fetching TikTok data (single actor call)...")
    return run_actor("clockworks/tiktok-hashtag-scraper", {
        "hashtags": ["footballtraining", "dbtraining", "cornerback", "1v1football", "footballdrills"],
        "resultsPerPage": 10,
        "shouldDownloadCovers": False,
        "shouldDownloadVideos": False,
    }, timeout=240)


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


# ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ DATA FETCHERS ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
def fetch_trending_sounds(raw):
    """Extract trending sounds from pre-fetched hashtag video results."""
    print("  Parsing trending soundsâ¦")

    sound_counts = {}
    for item in raw:
        music = item.get("musicMeta") or {}
        title  = music.get("musicName", "") or music.get("musicOriginal", "")
        author = music.get("musicAuthor", "") or ""
        music_id = music.get("musicId", "") or ""
        plays  = item.get("playCount", 0) or 0
        if not title or title.lower() in ("original sound", ""):
            continue
        key = music_id or (title + "|" + author)
        if key not in sound_counts:
            sound_counts[key] = {
                "title": title, "author": author,
                "usedCount": 0, "maxPlays": 0,
                "link": f"https://www.tiktok.com/music/{title.replace(' ','-')}-{music_id}" if music_id else "",
                "cover": "",
            }
        sound_counts[key]["usedCount"] += 1
        if plays > sound_counts[key]["maxPlays"]:
            sound_counts[key]["maxPlays"] = plays

    sounds = []
    for s in sound_counts.values():
        if s["usedCount"] < 2:
            continue
        sc, cat = score_sound({"title": s["title"], "author": s["author"]})
        sounds.append({
            "title":     s["title"],
            "author":    s["author"],
            "rank":      0,
            "rank_diff": 0,
            "link":      s["link"],
            "cover":     s["cover"],
            "score":     sc,
            "category":  cat,
            "rising":    s["usedCount"] >= 3,
            "usedCount": s["usedCount"],
            "maxPlays":  s["maxPlays"],
        })

    sounds.sort(key=lambda x: (0 if x["category"] == "football" else 1, -x["usedCount"], -x["maxPlays"]))
    return sounds[:15]


def fetch_creator_spy(raw):
    """Find emerging creators from pre-fetched hashtag video results."""
    print("  Parsing creator dataÃ¢ÂÂ¦")

    seen_handles = set()
    creator_map  = {}

    for v in raw:
        author = v.get("authorMeta") or {}
        handle = author.get("name", "") or ""
        if not handle or handle in seen_handles:
            continue
        fans   = author.get("fans", 0) or 0
        plays  = v.get("playCount", 0) or 0
        likes  = v.get("diggCount", 0) or 0
        shares = v.get("shareCount", 0) or 0
        saves  = v.get("collectCount", 0) or 0
        desc   = v.get("text", "") or ""
        sound  = (v.get("musicMeta") or {}).get("musicName", "") or ""
        sound_author = (v.get("musicMeta") or {}).get("musicAuthor", "") or ""
        thumb  = (v.get("videoMeta") or {}).get("coverUrl", "") or ""
        url    = v.get("webVideoUrl", "") or ""

        if fans > 500_000:
            continue

        viral_reason = ""
        if plays > 500_000:
            viral_reason = "Ã°ÂÂÂ¥ Mega viral Ã¢ÂÂ massive reach"
        elif plays > 100_000:
            if shares > likes * 0.05:
                viral_reason = "Ã¢ÂÂ¡ High share rate Ã¢ÂÂ relatable/shareable content"
            elif saves > likes * 0.1:
                viral_reason = "Ã°ÂÂÂ High saves Ã¢ÂÂ educational/reference value"
            else:
                viral_reason = "Ã°ÂÂÂ Strong engagement Ã¢ÂÂ good hook/timing"

        if handle not in creator_map:
            size = "small" if fans < 50_000 else "mid"
            creator_map[handle] = {"handle": handle, "size": size, "fans": fans, "videos": []}

        if len(creator_map[handle]["videos"]) < 3:
            creator_map[handle]["videos"].append({
                "desc": desc[:100], "plays": plays, "likes": likes,
                "shares": shares, "saves": saves, "sound": sound,
                "sound_author": sound_author, "thumb": thumb, "url": url,
                "fans": fans, "viral": plays > 30_000,
                "pillar": None, "viral_reason": viral_reason,
            })
        seen_handles.add(handle)

    results = sorted(creator_map.values(), key=lambda c: max((v["plays"] for v in c["videos"]), default=0), reverse=True)
    return results[:15]

def fetch_hashtags(raw):
    print("  Parsing hashtag dataÃÂ¢ÃÂÃÂ¦")

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


# ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ VIDEO IDEA GENERATOR ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
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
        priority   = "ÃÂ°ÃÂÃÂÃÂ¥ HOT" if hot_pillars.get(pillar, 0) > 0 else "ÃÂ°ÃÂÃÂÃÂ"
        inspo      = next((v for v in viral_inspo if v["pillar"] == pillar), None)
        inspo_note = f" (inspired by @{inspo['handle']} ÃÂ¢ÃÂÃÂ {inspo['plays']:,} plays)" if inspo else ""

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
            "priority":  "ÃÂ¢ÃÂÃÂ¡ URGENT",
            "idea":      f"@{v['handle']} just got {v['plays']:,} plays on: '{v['desc'][:50]}' ÃÂ¢ÃÂÃÂ post YOUR version before it peaks",
            "sound":     top_sound,
            "hashtags":  "#footballtraining #db #cornerback",
            "inspo":     "",
            "inspo_url": v["url"],
        })

    return ideas


# ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ EMAIL CSS ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
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

# ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ SOUND COLOR ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
def sound_tag(cat, score):
    if cat == "football":
        return f'<span class="tag tag-green">ÃÂ°ÃÂÃÂÃÂ FOOTBALL ÃÂÃÂ· {score}/10</span>'
    elif cat == "workout":
        return f'<span class="tag tag-yellow">ÃÂ°ÃÂÃÂÃÂª WORKOUT ÃÂÃÂ· {score}/10</span>'
    elif cat == "sport":
        return f'<span class="tag tag-blue">ÃÂ°ÃÂÃÂÃÂ SPORT ÃÂÃÂ· {score}/10</span>'
    else:
        return f'<span class="tag tag-gray">ÃÂ°ÃÂÃÂÃÂµ GENERAL ÃÂÃÂ· {score}/10</span>'


# ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ EMAIL BUILDERS ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
def build_morning_email(sounds, creators, tags, top_videos, ideas, date_str):
    top = sounds[0] if sounds else {"title": "ÃÂ¢ÃÂÃÂ", "link": ""}

    # ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ SOUNDS ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
    sound_rows = ""
    for i, s in enumerate(sounds[:10], 1):
        rising_badge = ' <span class="tag tag-green" style="font-size:9px;">ÃÂ¢ÃÂÃÂ² RISING</span>' if s["rising"] else ""
        link_open  = f'<a href="{s["link"]}" style="color:#e8e8e8;">' if s["link"] else ""
        link_close = "</a>" if s["link"] else ""
        sound_rows += f"""
        <div style="display:flex;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid #1a1a22;">
          {'<img src="' + s['cover'] + '" style="width:40px;height:40px;border-radius:8px;object-fit:cover;flex-shrink:0;" />' if s.get('cover') else '<div style="width:40px;height:40px;border-radius:8px;background:#1e2028;flex-shrink:0;"></div>'}
          <div style="flex:1;min-width:0;">
            <div style="font-weight:600;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{link_open}#{i} {s['title']}{link_close}{rising_badge}</div>
            <div class="stat" style="margin-top:2px;">{s['author']} &nbsp;ÃÂÃÂ·&nbsp; Rank #{s['rank']}</div>
          </div>
          <div style="flex-shrink:0;">{sound_tag(s['category'], s['score'])}</div>
        </div>"""

    # ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ CREATORS ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
    creator_html = ""
    # Sort: small first (emphasize emerging), large last
    sorted_creators = sorted(creators, key=lambda c: {"small":0,"mid":1,"large":2}.get(c["size"],1))
    for c in sorted_creators:
        size_icons = {"small": "ÃÂ°ÃÂÃÂÃÂ± EMERGING", "mid": "ÃÂ°ÃÂÃÂÃÂ MID-TIER", "large": "ÃÂ¢ÃÂÃÂ¡ LARGE"}
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
            {'<span class="tag tag-red">ÃÂ°ÃÂÃÂÃÂ¥ VIRAL</span>' if viral_vids else ''}
          </div>"""

        if not c["videos"]:
            creator_html += '<div style="font-size:12px;color:#555;">No recent videos found</div>'
        else:
            for v in c["videos"][:3]:
                pillar_tag = f'<span class="tag tag-green" style="font-size:9px;">{v["pillar"].upper()}</span> ' if v["pillar"] else ""
                watch_btn  = f'<a href="{v["url"]}" style="display:inline-block;padding:4px 10px;background:#1e2028;border-radius:6px;font-size:10px;color:#60a5fa;font-weight:600;margin-top:6px;">ÃÂ¢ÃÂÃÂ¶ Watch on TikTok</a>' if v["url"] else ""
                viral_why  = f'<div style="font-size:10px;color:#fbbf24;margin-top:3px;">{v["viral_reason"]}</div>' if v["viral_reason"] else ""
                thumb_html = f'<img src="{v["thumb"]}" style="width:52px;height:70px;border-radius:6px;object-fit:cover;flex-shrink:0;" />' if v["thumb"] else ""

                creator_html += f"""
                <div style="display:flex;gap:10px;margin-bottom:10px;background:#0d0f14;border-radius:8px;padding:8px;">
                  {thumb_html}
                  <div style="flex:1;min-width:0;">
                    <div style="font-size:11px;color:#bbb;margin-bottom:4px;line-height:1.4;">{pillar_tag}{v['desc'] or '(no caption)'}</div>
                    <div class="stat"><strong style="color:#4ade80;">{v['plays']:,} plays</strong> ÃÂÃÂ· {v['likes']:,} likes ÃÂÃÂ· {v['saves']:,} saves</div>
                    {f'<div class="stat" style="margin-top:2px;">ÃÂ°ÃÂÃÂÃÂµ {v["sound"]}</div>' if v["sound"] else ""}
                    {viral_why}
                    {watch_btn}
                  </div>
                </div>"""
        creator_html += "</div>"

    # ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ HASHTAGS ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
    ht_html = ""
    for tag, data in tags[:8]:
        views = data["views"]
        views_fmt = f"{views/1_000_000_000:.1f}B" if views >= 1e9 else f"{views/1_000_000:.0f}M" if views >= 1e6 else f"{views:,}"
        ht_html += f'<span style="background:#0a1a2e;color:#60a5fa;padding:5px 12px;border-radius:20px;margin:3px;display:inline-block;font-size:12px;font-weight:600;">#{tag} <span style="color:#2563eb;font-size:10px;">{views_fmt} views</span></span>'

    # ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ TOP HASHTAG VIDEOS ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
    ht_videos_html = ""
    for v in top_videos[:4]:
        thumb_html = f'<img src="{v["thumb"]}" style="width:48px;height:64px;border-radius:6px;object-fit:cover;flex-shrink:0;" />' if v["thumb"] else ""
        watch_btn  = f'<a href="{v["url"]}" style="display:inline-block;padding:3px 8px;background:#1e2028;border-radius:5px;font-size:10px;color:#60a5fa;font-weight:600;">ÃÂ¢ÃÂÃÂ¶ Watch</a>' if v["url"] else ""
        fans_fmt   = f"{v['fans']/1000:.0f}K" if v["fans"] >= 1000 else str(v["fans"])
        ht_videos_html += f"""
        <div style="display:flex;gap:10px;margin-bottom:10px;background:#0d0f14;border-radius:8px;padding:8px;">
          {thumb_html}
          <div style="flex:1;min-width:0;">
            <div style="font-size:11px;color:#bbb;margin-bottom:4px;">#{v['tag']} ÃÂÃÂ· @{v['author']} ({fans_fmt} followers)</div>
            <div style="font-size:12px;color:#e8e8e8;margin-bottom:4px;line-height:1.4;">{v['desc']}</div>
            <div class="stat"><strong style="color:#4ade80;">{v['plays']:,} plays</strong> ÃÂÃÂ· {v['shares']:,} shares</div>
            {f'<div class="stat">ÃÂ°ÃÂÃÂÃÂµ {v["sound"]}</div>' if v["sound"] else ""}
            {watch_btn}
          </div>
        </div>"""

    # ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ VIDEO IDEAS ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
    ideas_html = ""
    for idea in ideas:
        p_color = "#f87171" if "URGENT" in idea["priority"] else "#fbbf24" if "HOT" in idea["priority"] else "#666"
        inspo_link = f' <a href="{idea["inspo_url"]}" style="color:#60a5fa;font-size:10px;">ÃÂ¢ÃÂÃÂ¶ Watch inspo</a>' if idea.get("inspo_url") else ""
        ideas_html += f"""
        <div style="border-left:3px solid {p_color};padding:10px 14px;margin-bottom:10px;background:#0d0f14;border-radius:0 8px 8px 0;">
          <div style="font-size:10px;font-weight:700;color:{p_color};margin-bottom:4px;letter-spacing:.5px;">{idea['priority']} ÃÂÃÂ· {idea['pillar']}{idea['inspo']}{inspo_link}</div>
          <div style="font-size:13px;color:#e8e8e8;margin-bottom:6px;line-height:1.5;">{idea['idea']}</div>
          <div style="font-size:10px;color:#555;">ÃÂ°ÃÂÃÂÃÂµ Use: <strong style="color:#888;">{idea['sound']}</strong> &nbsp;ÃÂÃÂ·&nbsp; {idea['hashtags']}</div>
        </div>"""

    top_sound_link = f'<a href="{top["link"]}" style="color:#4ade80;text-decoration:underline;">"{top["title"]}"</a>' if top.get("link") else f'"{top["title"]}"'

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{email_style()}</style></head><body>

<div style="background:linear-gradient(135deg,#0d1117,#161b22);border-radius:16px;padding:24px;margin-bottom:14px;text-align:center;border:1px solid #21262d;">
  <div style="font-size:40px;margin-bottom:8px;">ÃÂ°ÃÂÃÂÃÂ</div>
  <h1 style="font-size:22px;font-weight:900;color:#fff;margin-bottom:4px;">Good Morning, Joshua</h1>
  <p style="color:#666;font-size:13px;">6AM Football Trend Brief &nbsp;ÃÂÃÂ·&nbsp; {date_str}</p>
</div>

<div style="background:#0a1f0a;border:1px solid #166534;border-radius:12px;padding:18px;margin-bottom:14px;">
  <h2 style="color:#4ade80;">ÃÂ¢ÃÂÃÂ¡ Your Move Today</h2>
  <p style="font-size:14px;margin-bottom:8px;line-height:1.6;"><strong>Hottest sound right now:</strong> {top_sound_link}</p>
  <p style="font-size:13px;color:#bbb;line-height:1.6;"><strong style="color:#fff;">Post idea:</strong> Film a DB press coverage drill. Name a specific WR or school you're preparing for in the caption.</p>
  <p style="font-size:12px;color:#555;margin-top:8px;">ÃÂ°ÃÂÃÂÃÂ Best posting window: 6ÃÂ¢ÃÂÃÂ9PM ET tonight</p>
</div>

<div class="card">
  <h2>ÃÂ°ÃÂÃÂÃÂ¯ Video Ideas For Today</h2>
  {ideas_html}
</div>

<div class="card">
  <h2>ÃÂ°ÃÂÃÂÃÂµ Trending Sounds ÃÂ¢ÃÂÃÂ Color Coded For You</h2>
  <div style="font-size:10px;color:#555;margin-bottom:10px;">ÃÂ°ÃÂÃÂÃÂ¢ Football/DB &nbsp;ÃÂÃÂ·&nbsp; ÃÂ°ÃÂÃÂÃÂ¡ Workout/Hype &nbsp;ÃÂÃÂ·&nbsp; ÃÂ°ÃÂÃÂÃÂµ Sport &nbsp;ÃÂÃÂ·&nbsp; ÃÂ¢ÃÂÃÂª General</div>
  {sound_rows}
</div>

<div class="card">
  <h2>ÃÂ°ÃÂÃÂÃÂÃÂ¯ÃÂ¸ÃÂ Creator Spy</h2>
  <div style="font-size:11px;color:#555;margin-bottom:12px;">ÃÂ°ÃÂÃÂÃÂ± Emerging creators first ÃÂÃÂ· ÃÂ¢ÃÂÃÂ¡ Large shown last for reference</div>
  {creator_html}
</div>

<div class="card">
  <h2>ÃÂ°ÃÂÃÂÃÂ·ÃÂ¯ÃÂ¸ÃÂ Trending Hashtags</h2>
  {ht_html}
  {('<hr class="divider"><div style="font-size:13px;font-weight:700;color:#fff;margin-bottom:10px;">ÃÂ°ÃÂÃÂÃÂ¥ Top Videos Under These Hashtags</div>' + ht_videos_html) if ht_videos_html else ""}
</div>

<p style="text-align:center;font-size:10px;color:#333;padding:16px 0;">Football Trend Agent &nbsp;ÃÂÃÂ·&nbsp; 6AM Brief &nbsp;ÃÂÃÂ·&nbsp; therealjoshjames22@gmail.com</p>
</body></html>"""
    return html


def build_afternoon_email(sounds, creators, top_videos, ideas, date_str):
    urgent      = [i for i in ideas if "URGENT" in i["priority"] or "HOT" in i["priority"]]
    new_viral   = [v for c in creators for v in c["videos"] if v["viral"]]

    viral_html = ""
    for v in new_viral[:5]:
        watch_btn = f'<a href="{v["url"]}" style="display:inline-block;padding:3px 8px;background:#1e2028;border-radius:5px;font-size:10px;color:#60a5fa;font-weight:600;margin-top:4px;">ÃÂ¢ÃÂÃÂ¶ Watch on TikTok</a>' if v["url"] else ""
        viral_html += f"""
        <div style="padding:10px 0;border-bottom:1px solid #1e2028;">
          <div style="font-size:13px;"><strong style="color:#4ade80;">{v['plays']:,} plays</strong> ÃÂ¢ÃÂÃÂ {v['desc'][:70]}</div>
          {f'<div class="stat" style="margin-top:2px;">{v["viral_reason"]}</div>' if v["viral_reason"] else ""}
          {watch_btn}
        </div>"""
    if not viral_html:
        viral_html = '<p style="font-size:13px;color:#444;">No major viral spikes since this morning.</p>'

    ideas_html = ""
    for idea in (urgent or ideas[:3]):
        p_color = "#f87171" if "URGENT" in idea["priority"] else "#fbbf24"
        inspo_link = f' <a href="{idea["inspo_url"]}" style="color:#60a5fa;font-size:10px;">ÃÂ¢ÃÂÃÂ¶ Watch inspo</a>' if idea.get("inspo_url") else ""
        ideas_html += f"""
        <div style="border-left:3px solid {p_color};padding:10px 14px;margin-bottom:10px;background:#0d0f14;border-radius:0 8px 8px 0;">
          <div style="font-size:10px;font-weight:700;color:{p_color};margin-bottom:4px;">{idea['priority']} ÃÂÃÂ· {idea['pillar']}{inspo_link}</div>
          <div style="font-size:13px;color:#e8e8e8;margin-bottom:4px;">{idea['idea']}</div>
          <div style="font-size:10px;color:#555;">ÃÂ°ÃÂÃÂÃÂµ {idea['sound']}</div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{email_style()}</style></head><body>
<div style="background:linear-gradient(135deg,#0d1a0d,#162416);border-radius:16px;padding:20px;margin-bottom:14px;text-align:center;border:1px solid #166534;">
  <div style="font-size:32px;margin-bottom:6px;">ÃÂ°ÃÂÃÂÃÂ</div>
  <h1 style="font-size:20px;font-weight:900;color:#fff;">Afternoon Update</h1>
  <p style="color:#555;font-size:12px;">2PM Trend Check &nbsp;ÃÂÃÂ·&nbsp; {date_str}</p>
</div>
<div class="card">
  <h2>ÃÂ°ÃÂÃÂÃÂ¥ Viral Right Now ÃÂ¢ÃÂÃÂ Post Before It Peaks</h2>
  {viral_html}
</div>
<div class="card">
  <h2>ÃÂ°ÃÂÃÂÃÂ¯ Top Ideas This Afternoon</h2>
  {ideas_html}
</div>
<p style="text-align:center;font-size:10px;color:#333;padding:16px 0;">Football Trend Agent &nbsp;ÃÂÃÂ·&nbsp; 2PM Brief &nbsp;ÃÂÃÂ·&nbsp; therealjoshjames22@gmail.com</p>
</body></html>"""
    return html


def build_night_email(sounds, creators, ideas, date_str):
    viral_today  = [v for c in creators for v in c["videos"] if v["viral"]]
    top_sound    = sounds[0] if sounds else {"title": "ÃÂ¢ÃÂÃÂ", "link": ""}

    recap_html = ""
    for v in viral_today[:5]:
        watch_btn = f'<a href="{v["url"]}" style="display:inline-block;padding:3px 8px;background:#1e2028;border-radius:5px;font-size:10px;color:#60a5fa;font-weight:600;margin-top:4px;">ÃÂ¢ÃÂÃÂ¶ Watch</a>' if v["url"] else ""
        recap_html += f"""
        <div style="padding:10px 0;border-bottom:1px solid #1e2028;">
          <div style="font-size:13px;"><strong style="color:#4ade80;">{v['plays']:,} plays</strong> ÃÂ¢ÃÂÃÂ {v['desc'][:70]}</div>
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
          <div style="font-size:10px;color:#555;">ÃÂ°ÃÂÃÂÃÂµ {idea['sound']} &nbsp;ÃÂÃÂ·&nbsp; {idea['hashtags']}</div>
        </div>"""

    top_sound_link = f'<a href="{top_sound["link"]}" style="color:#4ade80;">{top_sound["title"]}</a>' if top_sound.get("link") else top_sound["title"]

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{email_style()}</style></head><body>
<div style="background:linear-gradient(135deg,#0a0a14,#0f0f1e);border-radius:16px;padding:20px;margin-bottom:14px;text-align:center;border:1px solid #21262d;">
  <div style="font-size:32px;margin-bottom:6px;">ÃÂ°ÃÂÃÂÃÂ</div>
  <h1 style="font-size:20px;font-weight:900;color:#fff;">Night Brief</h1>
  <p style="color:#555;font-size:12px;">9PM Recap &nbsp;ÃÂÃÂ·&nbsp; {date_str}</p>
</div>
<div class="card">
  <h2>ÃÂ°ÃÂÃÂÃÂ What Went Viral In Your Niche Today</h2>
  {recap_html}
</div>
<div class="card">
  <h2>ÃÂ°ÃÂÃÂÃÂÃÂ¯ÃÂ¸ÃÂ Tomorrow's Content Plan</h2>
  {tomorrow_html}
</div>
<div style="background:#0a1f0a;border:1px solid #166534;border-radius:12px;padding:16px;margin-bottom:14px;">
  <h2 style="color:#4ade80;">ÃÂ°ÃÂÃÂÃÂµ Use This Sound Tomorrow</h2>
  <p style="font-size:14px;line-height:1.6;">{top_sound_link} ÃÂ¢ÃÂÃÂ post with this first thing in the morning for max reach</p>
</div>
<p style="text-align:center;font-size:10px;color:#333;padding:16px 0;">Football Trend Agent &nbsp;ÃÂÃÂ·&nbsp; 9PM Brief &nbsp;ÃÂÃÂ·&nbsp; therealjoshjames22@gmail.com</p>
</body></html>"""
    return html


# ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ EMAIL SENDER ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
def send_email(subject, html_body):
    if not EMAIL_PASSWORD:
        print(f"[WARN] No EMAIL_PASSWORD ÃÂ¢ÃÂÃÂ skipping send. Subject: {subject}")
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
        print(f"[ÃÂ¢ÃÂÃÂ] Email sent: {subject}")
    except Exception as e:
        print(f"[ERROR] Email failed: {e}")


# ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ WRITE DATA.JSON (dashboard reads this on load) ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
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

    import os as _os
    _path = _os.path.abspath("data.json")
    print(f"  [DEBUG] Writing to {_path}")
    with open("data.json", "w") as f:
        json.dump(data, f, indent=2)
    _sz = _os.path.getsize(_path)
    print(f"  [DEBUG] Wrote {_sz} bytes to {_path}")
    print(f"[ÃÂ¢ÃÂÃÂ] data.json written ÃÂ¢ÃÂÃÂ {len(sounds)} sounds, {len(creators)} creators, {len(breakouts)} breakouts")


# ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ MAIN ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
def main():
    date_str = datetime.now().strftime("%A, %B %-d %Y")
    brief    = BRIEF_TYPE.lower()

    print(f"\n{'='*52}")
    print(f"Football Trend Agent v3 ÃÂ¢ÃÂÃÂ {brief.upper()} RUN")
    print(f"{date_str}")
    print(f"{'='*52}\n")

    # Afternoon/night reuse morning data to save Apify credits
    if brief in ("afternoon", "night") and os.path.exists("data.json"):
        print("  Reusing cached data.json (no new Apify call)...")
        with open("data.json") as f:
            cached = json.load(f)
        sounds     = cached.get("sounds", [])
        creators   = cached.get("creators", [])
        tags       = cached.get("hashtags", [])
        top_videos = cached.get("topVideos", [])
        ideas      = cached.get("ideas", [])
    else:
        raw              = fetch_all_raw()
        sounds           = fetch_trending_sounds(raw)
        creators         = fetch_creator_spy(raw)
        tags, top_videos = fetch_hashtags(raw)
        ideas            = generate_video_ideas(sounds, creators, top_videos)

    print(f"\n  Sounds: {len(sounds)}  |  Creators: {len(creators)}  |  Tags: {len(tags)}  |  Top videos: {len(top_videos)}\n")

    # Always write data.json ÃÂ¢ÃÂÃÂ dashboard reads this on every load
    write_data_json(sounds, creators, tags, top_videos, ideas)

    # Send full email only on the 3 daily brief times
    if brief in ("morning", "afternoon", "night"):
        if brief == "morning":
            html    = build_morning_email(sounds, creators, tags, top_videos, ideas, date_str)
            subject = f"ÃÂ°ÃÂÃÂÃÂ Good Morning Joshua ÃÂ¢ÃÂÃÂ Football Brief {date_str}"
        elif brief == "afternoon":
            html    = build_afternoon_email(sounds, creators, top_videos, ideas, date_str)
            subject = f"ÃÂ°ÃÂÃÂÃÂ Afternoon Update ÃÂ¢ÃÂÃÂ {date_str}"
        else:
            html    = build_night_email(sounds, creators, ideas, date_str)
            subject = f"ÃÂ°ÃÂÃÂÃÂ Night Brief ÃÂ¢ÃÂÃÂ {date_str}"
        send_email(subject, html)
        print("[ÃÂ¢ÃÂÃÂ] Email sent.\n")
    else:
        # Hourly scan ÃÂ¢ÃÂÃÂ only email if there's a breakout (50K+ views in last 6hrs)
        if breakouts := json.load(open("data.json")).get("breakouts"):
            b = breakouts[0]
            html = f"""<h2>ÃÂ¢ÃÂÃÂ¡ BREAKOUT ALERT</h2>
            <p><strong>@{b['handle']}</strong> just hit <strong>{b['plays']:,} views</strong> in the last 6 hours.</p>
            <p>Sound: ÃÂ°ÃÂÃÂÃÂµ {b['sound']}</p>
            <p>Caption: {b['desc']}</p>
            <p><a href="{b['url']}">Watch Video ÃÂ¢ÃÂÃÂ</a></p>"""
            send_email(f"ÃÂ¢ÃÂÃÂ¡ BREAKOUT: @{b['handle']} ÃÂ¢ÃÂÃÂ {b['plays']:,} views right now", html)
            print(f"[ÃÂ¢ÃÂÃÂ] Breakout alert sent for @{b['handle']}\n")
        else:
            print("[ÃÂ¢ÃÂÃÂ] Hourly scan complete. No breakouts. data.json updated.\n")

    print("[ÃÂ¢ÃÂÃÂ] Done.\n")


if __name__ == "__main__":
    main()
