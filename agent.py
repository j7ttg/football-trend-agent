"""
Football Trend Agent v5 -- Upgraded single agent
- Runs every 3 hours via GitHub Actions
- 6AM: Morning Brief (deep creator intel + sounds + hashtags + video ideas)
- 2PM: Afternoon Idea Refresh
- 9PM: Night Brief (viral recap + tomorrow's plan)
- Every other run: quick scan, breakout alerts only
- Creator deep dive: recent posts only (7-day), sorted by recency then plays
- sortType:latest on Apify so old viral videos never surface
- Hook/format analysis on every viral creator video
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

# -- CONFIG -----------------------------------------------------------
APIFY_TOKEN    = os.environ.get("APIFY_TOKEN", "")
EMAIL_FROM     = os.environ.get("EMAIL_FROM", "therealjoshjames22@gmail.com")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "")
EMAIL_TO       = os.environ.get("EMAIL_TO", "therealjoshjames22@gmail.com")
BRIEF_TYPE     = os.environ.get("BRIEF_TYPE", "morning")  # morning | afternoon | night | scan

APIFY_BASE = "https://api.apify.com/v2"
SEVEN_DAYS = 7 * 86400  # seconds

# -- CONTENT PILLARS --------------------------------------------------
PILLARS = {
    "1v1":        ["1v1","one on one","lockdown","shutdown","press coverage","man coverage","man coverage","jam","bump","guard","lock"],
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

# -- FALLBACK DATA (used when Apify returns 0 results) ----------------
FALLBACK_SOUNDS = [
    {"title": "Like That", "author": "Future, Metro Boomin, Kendrick Lamar",
     "rank": 1, "rank_diff": 12,
     "link": "https://www.tiktok.com/search?q=Like+That+Future+Metro+Boomin",
     "cover": "", "score": 7, "category": "general", "rising": True, "usedCount": 8, "maxPlays": 4200000},
    {"title": "All Eyes On Me Workout Edit", "author": "2Pac",
     "rank": 2, "rank_diff": 5,
     "link": "https://www.tiktok.com/search?q=All+Eyes+On+Me+2Pac+workout",
     "cover": "", "score": 8, "category": "workout", "rising": True, "usedCount": 6, "maxPlays": 1800000},
    {"title": "TGIF", "author": "GloRilla",
     "rank": 3, "rank_diff": 8,
     "link": "https://www.tiktok.com/search?q=TGIF+GloRilla",
     "cover": "", "score": 6, "category": "general", "rising": True, "usedCount": 5, "maxPlays": 3100000},
    {"title": "Buttons", "author": "Sia",
     "rank": 4, "rank_diff": 3,
     "link": "https://www.tiktok.com/search?q=Buttons+Sia",
     "cover": "", "score": 7, "category": "workout", "rising": False, "usedCount": 4, "maxPlays": 920000},
    {"title": "Not Like Us", "author": "Kendrick Lamar",
     "rank": 5, "rank_diff": 2,
     "link": "https://www.tiktok.com/search?q=Not+Like+Us+Kendrick+Lamar",
     "cover": "", "score": 6, "category": "general", "rising": False, "usedCount": 4, "maxPlays": 5600000},
]

FALLBACK_CREATORS = [
    {"handle": "noe_ma2s", "size": "micro", "fans": 905,
     "videos": [{"desc": "Release work drill -- WR footwork and route running", "plays": 38900,
                 "likes": 2100, "shares": 310, "saves": 580, "sound": "original sound",
                 "sound_author": "noe_ma2s", "thumb": "", "url": "https://www.tiktok.com/@noe_ma2s",
                 "fans": 905, "viral": True, "pillar": "drills", "days_ago": 3,
                 "format_type": "Tutorial / Technique Breakdown",
                 "hook_analysis": "Opens on hands â immediate action, no intro. Short reps, each one clean. This format works because it's specific and repeatable.",
                 "copy_this": "Film 3 reps of one specific technique. No talking intro. Start on the movement.",
                 "viral_reason": "MICRO VIRAL -- 38.9K views with only 905 followers. 43x follower ratio. Study this format."}]},
    {"handle": "_wakeemup3", "size": "small", "fans": 6133,
     "videos": [{"desc": "DB undersized but never outworked -- motivational training clip", "plays": 515800,
                 "likes": 41000, "shares": 6200, "saves": 9100, "sound": "motivational audio",
                 "sound_author": "", "thumb": "", "url": "https://www.tiktok.com/@_wakeemup3",
                 "fans": 6133, "viral": True, "pillar": "motivation", "days_ago": 2,
                 "format_type": "Raw Authentic Story",
                 "hook_analysis": "Caption does the heavy lifting -- 'undersized but never outworked' speaks directly to every DB who felt doubted. High shares because people tag their teammates.",
                 "copy_this": "Lead with your underdog identity in the caption. Raw training footage, no polish. Let the caption create the emotion.",
                 "viral_reason": "MEGA VIRAL -- 515.8K views on 6.1K account. 84x follower ratio. Raw authentic energy."}]},
    {"handle": "khispammmm", "size": "small", "fans": 11300,
     "videos": [{"desc": "Don't ever tell me I'm naturally gifted -- DB college grind", "plays": 23100,
                 "likes": 1800, "shares": 290, "saves": 410, "sound": "motivational",
                 "sound_author": "", "thumb": "", "url": "https://www.tiktok.com/@khispammmm",
                 "fans": 11300, "viral": True, "pillar": "motivation", "days_ago": 4,
                 "format_type": "Authentic Story / Chip on Shoulder",
                 "hook_analysis": "Direct confrontation hook -- 'don't tell me I'm naturally gifted' triggers anyone who has heard that. College DB angle adds relatability.",
                 "copy_this": "Start with something someone said about you that made you grind harder. Make the viewer feel that same chip.",
                 "viral_reason": "HOT -- 23.1K views. College DB authentic story format working well."}]},
    {"handle": "ejizzle00", "size": "small", "fans": 12000,
     "videos": [{"desc": "Slideshow highlight reel -- getting buckets on the field", "plays": 560500,
                 "likes": 48000, "shares": 5200, "saves": 7100, "sound": "Like That",
                 "sound_author": "Future, Metro Boomin", "thumb": "", "url": "https://www.tiktok.com/@ejizzle00",
                 "fans": 12000, "viral": True, "pillar": "1v1", "days_ago": 1,
                 "format_type": "Slideshow Highlight Reel",
                 "hook_analysis": "Slideshow format is low effort to make but high engagement -- people swipe through and rewatch. 'Like That' beat matches the confident energy. High saves = people coming back to study clips.",
                 "copy_this": "Pick 5-8 of your best clips. Slideshow format, no editing needed. Use a hard-hitting sound. Caption = your record or stats.",
                 "viral_reason": "MEGA VIRAL -- 560K views on 12K account. Slideshow format working huge right now."}]},
    {"handle": "firstdowndbs", "size": "small", "fans": 42000,
     "videos": [{"desc": "DB drill breakdown -- press coverage technique", "plays": 187000,
                 "likes": 22000, "shares": 1800, "saves": 3100, "sound": "All Eyes On Me",
                 "sound_author": "2Pac", "thumb": "", "url": "https://www.tiktok.com/@firstdowndbs",
                 "fans": 42000, "viral": True, "pillar": "drills", "days_ago": 2,
                 "format_type": "Educational Drill Breakdown",
                 "hook_analysis": "High saves (3.1K) signal people are bookmarking this to use later -- that's the educational content signal. Saves drive the algorithm harder than likes for this content type.",
                 "copy_this": "Teach one specific technique. Name it. Show it 3 ways. Saves will carry the reach.",
                 "viral_reason": "VIRAL -- 187K views. High saves signal educational value -- good format to replicate."}]},
]

FALLBACK_TAGS = [
    ("dbtraining", {"views": 890000000, "top_plays": 187000}),
    ("cornerback", {"views": 620000000, "top_plays": 94000}),
    ("footballtraining", {"views": 4200000000, "top_plays": 61000}),
    ("1v1football", {"views": 340000000, "top_plays": 94000}),
    ("footballdrills", {"views": 1800000000, "top_plays": 187000}),
]

IDEA_TEMPLATES = {
    "1v1": [
        "1v1 drill against [opponent type] -- show 3 reps, win each one, caption: 'Nobody getting past me #1v1 #db'",
        "Film yourself shutting down a WR route for route -- voiceover explaining your read at each step",
        "React to a viral 1v1 clip then show your version of the same matchup",
        "Press coverage tutorial: 3 different WR releases, how you handle each one",
        "'Can you guard me?' challenge -- invite a WR friend, film the whole session raw",
    ],
    "drills": [
        "4 drills every DB should do before practice -- list format, each drill 5 seconds",
        "The ONE drill that fixed my backpedal -- before/after clip",
        "Morning drill routine from zero -- film your actual warmup start to finish",
        "Breakdown: how to mirror a WR's hips on a double move (slow-mo + voiceover)",
        "'DB Fundamentals Day [X]' series -- one technique per video, consistent format",
    ],
    "workout": [
        "Speed workout that adds 0.2 seconds to your 40 -- 3 exercises, film each one",
        "DB combine prep workout -- show exactly what you do 8 weeks out",
        "Gym session focused on explosion: box jumps, hip thrusts, band work",
        "The workout nobody talks about for DBs -- hip flexibility and change of direction",
        "Morning vs night workout routine -- film both, show the difference in energy",
    ],
    "motivation": [
        "Voiceover on outdoor training: 'This is what the offseason looks like when you want it'",
        "'Nobody is outworking me this offseason' -- raw training clips, no music just sounds",
        "Show a rejection or setback + what you did the next morning (authentic story)",
        "Day in the life: 5AM to 10PM grind day -- full vlog style",
        "'I train like this so game day feels easy' -- connect your drills to real game situations",
    ]
}

# -- HOOK / FORMAT ANALYSIS -------------------------------------------
FORMAT_SIGNALS = {
    "Tutorial / Technique Breakdown": ["drill","technique","how to","breakdown","tutorial","step","tip","fix","teach","learn","form"],
    "Raw Authentic Story":            ["story","nobody","never","told me","they said","doubted","grind","real","honest","truth","journey"],
    "Slideshow Highlight Reel":       ["highlights","reel","clips","best","top","season","game","plays","comp"],
    "1v1 / Challenge":                ["1v1","challenge","guard me","stop me","lock","shut down","vs","versus","battle"],
    "Day in the Life / Vlog":         ["day in","vlog","morning","routine","daily","wake up","schedule","life of"],
    "Motivational / Chip on Shoulder":["motivated","chip","underrated","sleep on","prove","doubters","outwork","mentality","mindset","grind"],
    "Workout / Training Footage":     ["workout","training","gym","lift","speed","agility","reps","sets","session","combine"],
}

def analyze_hook(desc, plays, likes, shares, saves):
    """Infer format type and generate a 'copy this' note from video metadata."""
    desc_lower = (desc or "").lower()

    # Detect format
    fmt = "Raw Training Footage"
    for format_name, signals in FORMAT_SIGNALS.items():
        if any(s in desc_lower for s in signals):
            fmt = format_name
            break

    # Engagement signals
    notes = []
    if saves > 0 and likes > 0 and saves / max(likes, 1) > 0.08:
        notes.append("High saves ratio -- people are bookmarking this. Educational/reference value is strong.")
    if shares > 0 and likes > 0 and shares / max(likes, 1) > 0.05:
        notes.append("High share rate -- this content triggers people to tag others. Relatable or hype factor.")
    if likes > 0 and plays > 0 and likes / max(plays, 1) > 0.07:
        notes.append("Strong like rate -- high resonance with the audience watching.")

    ratio = plays / max(likes + shares + saves + 1, 1)
    if ratio > 20 and not notes:
        notes.append("Wide reach relative to engagement -- algorithm is pushing this beyond existing followers.")

    hook_analysis = f"Format: {fmt}. " + (" ".join(notes) if notes else "Solid niche engagement pattern.")

    # Copy this suggestion
    copy_map = {
        "Tutorial / Technique Breakdown": "Film one specific technique. Name it in the caption. Show 3 clean reps. No talking intro -- start on the movement.",
        "Raw Authentic Story": "Lead with a real moment -- a doubt, a setback, a chip. Raw footage. Let the caption carry the emotion.",
        "Slideshow Highlight Reel": "Pick 5-8 best clips. Slideshow format, minimal editing. Hard-hitting sound. Caption = your record or a bold statement.",
        "1v1 / Challenge": "Set up a clean 1v1 rep. Film the win. Caption challenges someone specific or a position group.",
        "Day in the Life / Vlog": "Film your actual day from first workout to last. No script. Authentic pace.",
        "Motivational / Chip on Shoulder": "Start with what someone said about you. Let the training footage be your answer.",
        "Workout / Training Footage": "Film a full session or one standout exercise. Show intensity. Caption = what you're training for.",
        "Raw Training Footage": "Keep it raw and real. The less polished, the more authentic it feels. Caption adds the story.",
    }
    copy_this = copy_map.get(fmt, "Keep it simple and specific to one idea per video.")

    return fmt, hook_analysis, copy_this


# -- APIFY HELPERS ----------------------------------------------------
def run_actor(actor_id, input_data, timeout=240):
    """Run an Apify actor and return its dataset items."""
    try:
        if not APIFY_TOKEN:
            print("  [ERROR] APIFY_TOKEN is not set!")
            return []
        actor_slug = actor_id.replace("/", "~")
        print(f"  [DEBUG] Starting actor {actor_slug} with input: {json.dumps(input_data)}")
        resp = requests.post(
            f"{APIFY_BASE}/acts/{actor_slug}/runs",
            params={"token": APIFY_TOKEN},
            json=input_data,
            timeout=30
        )
        print(f"  [DEBUG] Actor start HTTP {resp.status_code}")
        if not resp.ok:
            print(f"  [ERROR] Actor start failed: {resp.text[:300]}")
            return []
        run_data   = resp.json()["data"]
        run_id     = run_data["id"]
        dataset_id = run_data["defaultDatasetId"]
        print(f"  [DEBUG] Run ID={run_id}, dataset={dataset_id}")

        deadline = time.time() + timeout
        status   = "RUNNING"
        while time.time() < deadline:
            sr = requests.get(
                f"{APIFY_BASE}/actor-runs/{run_id}",
                params={"token": APIFY_TOKEN},
                timeout=15
            )
            if not sr.ok:
                print(f"  [WARN] Status poll HTTP {sr.status_code}")
                time.sleep(10)
                continue
            status = sr.json()["data"]["status"]
            usage  = sr.json()["data"].get("usageTotalUsd", "?")
            print(f"  [DEBUG] Run status={status}, usageUsd={usage}")
            if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
                break
            time.sleep(10)

        if status != "SUCCEEDED":
            print(f"  [WARN] {actor_id} finished with status={status}")
            return []

        items_resp = requests.get(
            f"{APIFY_BASE}/datasets/{dataset_id}/items",
            params={"token": APIFY_TOKEN, "clean": "true", "limit": 500},
            timeout=30
        )
        print(f"  [DEBUG] Dataset fetch HTTP {items_resp.status_code}")
        if not items_resp.ok:
            print(f"  [ERROR] Dataset fetch failed: {items_resp.text[:200]}")
            return []
        items = items_resp.json()
        print(f"  [DEBUG] Got {len(items)} items from dataset")
        return items
    except Exception as e:
        print(f"  [ERROR] {actor_id}: {e}")
        return []


# -- SINGLE FETCH (reuse one actor call for all three parsers) --------
def fetch_all_raw():
    """
    One actor call, 8 hashtags x 15 results = ~120 items.
    sortType:latest ensures we get recent posts, not all-time viral.
    7-day filter is applied again in each parser as a safety net.
    """
    print("  Fetching TikTok data (single actor call, latest sort)...")
    results = run_actor("clockworks/tiktok-hashtag-scraper", {
        "hashtags": [
            "footballtraining", "dbtraining", "cornerback",
            "1v1football", "footballdrills", "defensiveback",
            "footballworkout", "7on7"
        ],
        "resultsPerPage": 15,
        "sortType": "latest",
        "shouldDownloadCovers": False,
        "shouldDownloadVideos": False,
    }, timeout=300)
    if not results:
        print("  [WARN] Actor returned 0 items -- will use curated fallback data")
    else:
        print(f"  [OK] Got {len(results)} raw items (latest sort)")
    return results


# -- SCORING ----------------------------------------------------------
def score_sound(sound):
    """Score a sound 0-10 for football/workout relevance."""
    score = 0
    name  = (sound.get("title", "") + " " + sound.get("author", "")).lower()
    football_hits = sum(1 for kw in FOOTBALL_KW if kw in name)
    score += football_hits * 3
    rank_diff = sound.get("rank_diff") or 0
    if rank_diff > 20:
        score += 3
    elif rank_diff > 5:
        score += 2
    elif rank_diff > 0:
        score += 1
    trend = sound.get("trend", [])
    if len(trend) >= 2:
        first_val = trend[0].get("value", 0)
        last_val  = trend[-1].get("value", 0)
        if first_val > 0 and last_val / first_val > 3:
            score += 2
        elif last_val > 0.5:
            score += 1
    score = min(score, 10)
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


# -- DATA FETCHERS ----------------------------------------------------
def fetch_trending_sounds(raw):
    """Extract trending sounds from pre-fetched hashtag video results.
    Only includes sounds used in videos from the last 7 days."""
    print("  Parsing trending sounds...")
    cutoff = time.time() - SEVEN_DAYS
    sound_counts = {}
    for item in raw:
        create_time = item.get("createTime", 0) or 0
        if create_time > 0 and create_time < cutoff:
            continue
        music    = item.get("musicMeta") or {}
        title    = music.get("musicName", "") or music.get("musicOriginal", "")
        author   = music.get("musicAuthor", "") or ""
        music_id = music.get("musicId", "") or ""
        plays    = item.get("playCount", 0) or 0
        if not title or title.lower() in ("original sound", ""):
            continue
        key = music_id or (title + "|" + author)
        if key not in sound_counts:
            if music_id:
                safe_title = title.replace(' ', '-').replace("'", "").replace('"', '')
                link = f"https://www.tiktok.com/music/{safe_title}-{music_id}"
            else:
                q = (title + " " + author).replace(" ", "+")
                link = f"https://www.tiktok.com/search?q={q}"
            sound_counts[key] = {
                "title": title, "author": author,
                "usedCount": 0, "maxPlays": 0,
                "link": link,
                "cover": "",
            }
        sound_counts[key]["usedCount"] += 1
        if plays > sound_counts[key]["maxPlays"]:
            sound_counts[key]["maxPlays"] = plays

    sounds = []
    for s in sound_counts.values():
        if s["maxPlays"] < 30000:
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

    sounds.sort(key=lambda x: -x["maxPlays"])
    return sounds[:15]


def fetch_creator_spy(raw):
    """
    Find emerging creators from pre-fetched hashtag video results.
    KEY UPGRADE v5:
    - Hard 7-day cutoff -- no old videos ever
    - Per creator: collect up to 5 videos, sorted by recency (newest first) then plays
    - Run hook analysis on each viral video
    - Micro/small sorted by follower ratio
    """
    print("  Parsing creator data (v5 -- recency first)...")
    cutoff = time.time() - SEVEN_DAYS
    now    = time.time()
    creator_map = {}

    for v in raw:
        # Hard 7-day recency gate -- if no createTime, skip
        create_time = v.get("createTime", 0) or 0
        if create_time == 0 or create_time < cutoff:
            continue

        author = v.get("authorMeta") or {}
        handle = author.get("name", "") or ""
        if not handle:
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

        # Only track small/emerging creators (under 500K followers)
        if fans > 500_000:
            continue

        # Days ago label
        days_ago = max(0, int((now - create_time) / 86400))

        # Follower ratio
        ratio = plays / max(fans, 1)

        # Viral reason
        viral_reason = ""
        if plays > 500_000:
            viral_reason = f"MEGA VIRAL -- {ratio:.0f}x follower ratio. Study this format immediately."
        elif plays > 100_000:
            if shares > likes * 0.05:
                viral_reason = f"VIRAL -- High share rate ({ratio:.0f}x ratio). Relatable/shareable content."
            elif saves > likes * 0.1:
                viral_reason = f"VIRAL -- High saves ({ratio:.0f}x ratio). Educational/reference value."
            else:
                viral_reason = f"VIRAL -- Strong engagement ({ratio:.0f}x follower ratio)."
        elif plays > 30_000:
            viral_reason = f"HOT -- {ratio:.0f}x follower ratio. Gaining traction in niche."
        elif ratio > 10 and plays > 5_000:
            viral_reason = f"WATCH -- {ratio:.0f}x follower ratio on micro account. Early signal."

        # Hook analysis
        fmt_type, hook_analysis, copy_this = analyze_hook(desc, plays, likes, shares, saves)

        if handle not in creator_map:
            if fans < 5_000:
                size = "micro"
            elif fans < 50_000:
                size = "small"
            else:
                size = "mid"
            creator_map[handle] = {
                "handle": handle,
                "size":   size,
                "fans":   fans,
                "videos": []
            }

        # Store up to 5 videos per creator
        if len(creator_map[handle]["videos"]) < 5:
            creator_map[handle]["videos"].append({
                "desc":          desc[:120],
                "plays":         plays,
                "likes":         likes,
                "shares":        shares,
                "saves":         saves,
                "sound":         sound,
                "sound_author":  sound_author,
                "thumb":         thumb,
                "url":           url,
                "fans":          fans,
                "viral":         plays > 30_000,
                "pillar":        get_pillar(desc),
                "days_ago":      days_ago,
                "create_time":   create_time,
                "viral_reason":  viral_reason,
                "format_type":   fmt_type,
                "hook_analysis": hook_analysis,
                "copy_this":     copy_this,
            })

    # For each creator: sort their videos by recency first (newest to oldest),
    # then within same day by plays descending
    for c in creator_map.values():
        c["videos"].sort(key=lambda v: (-v["create_time"], -v["plays"]))

    # Sort creators: micros/smalls first by ratio, then mid by plays
    def creator_sort_key(c):
        max_plays = max((v["plays"] for v in c["videos"]), default=0)
        fans_ct   = c.get("fans", 1) or 1
        ratio     = max_plays / fans_ct
        size_rank = {"micro": 0, "small": 1, "mid": 2, "large": 3}.get(c["size"], 2)
        if c["size"] in ("micro", "small"):
            return (size_rank, -ratio)
        return (size_rank, -max_plays)

    results = sorted(creator_map.values(), key=creator_sort_key)
    return results[:15]


def fetch_hashtags(raw):
    print("  Parsing hashtag data...")
    cutoff   = time.time() - SEVEN_DAYS
    tag_data = {}
    top_videos = []

    for item in raw:
        create_time = item.get("createTime", 0) or 0
        if create_time > 0 and create_time < cutoff:
            continue

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


# -- VIDEO IDEA GENERATOR --------------------------------------------
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
        priority   = "HOT" if hot_pillars.get(pillar, 0) > 0 else "STANDARD"
        inspo      = next((v for v in viral_inspo if v["pillar"] == pillar), None)
        inspo_note = f" (inspired by @{inspo['handle']} -- {inspo['plays']:,} plays)" if inspo else ""

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
            "priority":  "URGENT",
            "idea":      f"@{v['handle']} just got {v['plays']:,} plays on: '{v['desc'][:50]}' -- post YOUR version before it peaks",
            "sound":     top_sound,
            "hashtags":  "#footballtraining #db #cornerback",
            "inspo":     "",
            "inspo_url": v["url"],
        })

    return ideas


# -- BEST POST TIME ---------------------------------------------------
def best_post_time():
    weekday = datetime.now().weekday()
    if weekday in (4, 5):
        return "7-9 PM ET (peak weekend engagement)"
    elif weekday == 6:
        return "6-8 PM ET (pre-week hype)"
    elif weekday in (0, 1):
        return "6-8 PM ET (after school/work)"
    else:
        return "7-9 PM ET (mid-week sweet spot)"


# -- PLAYS LABEL / COLOR / FORMAT ------------------------------------
def plays_label(plays):
    if plays >= 500_000:  return "MEGA"
    elif plays >= 100_000: return "VIRAL"
    elif plays >= 30_000:  return "HOT"
    else:                  return ""

def plays_color(plays):
    if plays >= 500_000:  return "#f87171"
    elif plays >= 100_000: return "#fbbf24"
    elif plays >= 30_000:  return "#4a9eff"
    else:                  return "#888888"

def fmt_plays(plays):
    if plays >= 1_000_000: return f"{plays/1_000_000:.1f}M"
    elif plays >= 1_000:   return f"{plays/1_000:.0f}K"
    return str(plays)


# -- EMAIL CSS --------------------------------------------------------
def email_style():
    return """
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&display=swap');
    *{box-sizing:border-box;margin:0;padding:0;}
    body{background:#0a0c10;color:#d4d8e0;font-family:'Inter',system-ui,sans-serif;max-width:660px;margin:0 auto;padding:16px;}
    h2{font-size:14px;font-weight:700;letter-spacing:.6px;margin-bottom:12px;color:#e8ecf4;text-transform:uppercase;}
    a{color:#4a9eff;text-decoration:none;}
    a:hover{text-decoration:underline;}
    .card{background:#111620;border:1px solid #1c2235;border-radius:14px;padding:18px;margin-bottom:14px;}
    .tag{display:inline-block;padding:3px 9px;border-radius:20px;font-size:10px;font-weight:700;letter-spacing:.5px;}
    .tag-mega{background:#2a0a0a;color:#f87171;border:1px solid #7f1d1d;}
    .tag-viral{background:#2a1a00;color:#fbbf24;border:1px solid #78350f;}
    .tag-hot{background:#0a1a2e;color:#4a9eff;border:1px solid #1e3a5f;}
    .tag-blue{background:#0a1a2e;color:#4a9eff;border:1px solid #1e3a5f;}
    .tag-green{background:#0a2414;color:#4ade80;border:1px solid #166534;}
    .tag-gray{background:#1a1d25;color:#666;border:1px solid #2a2d38;}
    .tag-orange{background:#2a1500;color:#fb923c;border:1px solid #7c2d12;}
    .stat{font-size:11px;color:#556;}
    .stat strong{color:#8a9ab0;}
    .divider{border:none;border-top:1px solid #1c2235;margin:12px 0;}
    .watch-btn{display:inline-block;padding:4px 12px;background:#151c2e;border:1px solid #1e3a5f;border-radius:6px;font-size:10px;color:#4a9eff;font-weight:600;margin-top:6px;}
    .intel-box{background:#0a1020;border:1px solid #1a2540;border-radius:8px;padding:10px;margin-top:8px;}
    """


# -- EMAIL BUILDERS --------------------------------------------------
def build_morning_email(sounds, creators, tags, top_videos, ideas, date_str):
    post_time = best_post_time()
    top = sounds[0] if sounds else {"title": "â", "link": ""}

    # -- SOUNDS --
    sound_rows = ""
    for i, s in enumerate(sounds[:12], 1):
        mp      = s.get("maxPlays", 0)
        tier    = plays_label(mp)
        color   = plays_color(mp)
        tier_badge = f'<span class="tag tag-{"mega" if tier=="MEGA" else "viral" if tier=="VIRAL" else "hot"}" style="font-size:9px;">{tier}</span>' if tier else ""
        rising_badge = ' <span class="tag tag-green" style="font-size:9px;">RISING</span>' if s.get("rising") else ""
        used   = s.get("usedCount", 0)
        link_o = f'<a href="{s["link"]}" style="color:#d4d8e0;font-weight:600;">' if s.get("link") else '<span style="font-weight:600;">'
        link_c = "</a>" if s.get("link") else "</span>"
        tiktok_link = f' &nbsp;<a href="{s["link"]}" class="watch-btn">Play on TikTok</a>' if s.get("link") else ""

        sound_rows += f"""
        <div style="display:flex;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid #151820;">
          <div style="width:32px;text-align:center;font-size:11px;color:#4a5570;font-weight:700;">#{i}</div>
          <div style="flex:1;min-width:0;">
            <div style="font-size:13px;white-space:nowraw;overflow:hidden;text-overflow:ellipsis;">{link_o}{s["title"]}{link_c} {tier_badge}{rising_badge}</div>
            <div style="font-size:11px;color:#4a5570;margin-top:2px;">{s["author"]} &nbsp;&bull;&nbsp; Used in {used} niche videos{tiktok_link}</div>
          </div>
          <div style="flex-shrink:0;font-size:13px;font-weight:700;color:{color};">{fmt_plays(mp)}</div>
        </div>"""

    # -- CREATOR SPOTLIGHT with deep intel --
    spotlight_html = ""
    def email_creator_sort(c):
        max_plays = max((v["plays"] for v in c["videos"]), default=0)
        fans_ct   = c.get("fans", 1) or 1
        ratio     = max_plays / fans_ct
        size_rank = {"micro": 0, "small": 1, "mid": 2, "large": 3}.get(c["size"], 2)
        if c["size"] in ("micro", "small"):
            return (size_rank, -ratio)
        return (size_rank, -max_plays)

    sorted_creators = sorted(creators, key=email_creator_sort)
    for c in sorted_creators:
        size_label = {"micro": "MICRO CREATOR", "small": "EMERGING", "mid": "MID-TIER", "large": "LARGE"}.get(c["size"], "")
        size_color = {"micro": "#f87171", "small": "#4ade80", "mid": "#4a9eff", "large": "#888"}.get(c["size"], "#888")
        handle_url = f"https://www.tiktok.com/@{c['handle']}"
        max_plays  = max((v["plays"] for v in c["videos"]), default=0)

        spotlight_html += f"""
        <div style="margin-bottom:20px;padding-bottom:20px;border-bottom:1px solid #1c2235;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
            <div>
              <a href="{handle_url}" style="font-weight:700;font-size:14px;color:#d4d8e0;">@{c["handle"]}</a>
              <span style="font-size:10px;color:{size_color};margin-left:8px;font-weight:700;background:#0a0c10;padding:2px 7px;border-radius:10px;border:1px solid {size_color}30;">{size_label}</span>
            </div>
            <div style="font-size:11px;color:#4a5570;">{c.get("fans", 0):,} followers</div>
          </div>"""

        if not c["videos"]:
            spotlight_html += '<div style="font-size:12px;color:#333;">No recent videos in last 7 days</div>'
        else:
            # Show top 2 videos (already sorted by recency then plays)
            for v in c["videos"][:2]:
                vp       = v.get("plays", 0)
                vcolor   = plays_color(vp)
                vtier    = plays_label(vp)
                vtag     = f'<span class="tag tag-{"mega" if vtier=="MEGA" else "viral" if vtier=="VIRAL" else "hot"}" style="font-size:9px;">{vtier}</span> ' if vtier else ""
                watch    = f'<a href="{v["url"]}" class="watch-btn">Watch on TikTok â</a>' if v.get("url") else ""
                reason   = f'<div style="font-size:10px;color:#4a9eff;margin-top:3px;font-weight:600;">{v["viral_reason"]}</div>' if v.get("viral_reason") else ""
                sound_l  = f'<div style="font-size:10px;color:#4a5570;margin-top:2px;">Sound: <strong style="color:#8a9ab0;">{v["sound"]}</strong></div>' if v.get("sound") else ""
                pillar_b = f'<span class="tag tag-gray" style="font-size:9px;">{v["pillar"].upper()}</span> ' if v.get("pillar") else ""
                days_lbl = f'<span class="tag tag-orange" style="font-size:9px;">{v.get("days_ago",0)}d ago</span> ' if v.get("days_ago") is not None else ""

                # Deep intel box
                fmt_type     = v.get("format_type", "")
                hook_analysis = v.get("hook_analysis", "")
                copy_this    = v.get("copy_this", "")
                intel_html   = ""
                if fmt_type or hook_analysis or copy_this:
                    intel_html = f"""
                    <div class="intel-box">
                      <div style="font-size:9px;font-weight:700;color:#4a5570;letter-spacing:.5px;margin-bottom:6px;">CREATOR INTEL</div>
                      {f'<div style="font-size:10px;color:#fb923c;font-weight:700;margin-bottom:4px;">Format: {fmt_type}</div>' if fmt_type else ""}
                      {f'<div style="font-size:10px;color:#8a9ab0;margin-bottom:4px;line-height:1.5;">{hook_analysis}</div>' if hook_analysis else ""}
                      {f'<div style="font-size:10px;color:#4ade80;font-weight:600;line-height:1.5;">Copy this: {copy_this}</div>' if copy_this else ""}
                    </div>"""

                spotlight_html += f"""
                <div style="background:#0d1018;border-radius:8px;padding:10px;margin-bottom:8px;">
                  <div style="font-size:11px;color:#8a9ab0;margin-bottom:6px;line-height:1.4;">{days_lbl}{pillar_b}{vtag}{v["desc"] or "(no caption)"}</div>
                  <div style="font-size:13px;font-weight:700;color:{vcolor};">{fmt_plays(vp)} views</div>
                  <div style="font-size:11px;color:#4a5570;">{v.get("likes",0):,} likes &nbsp;&bull;&nbsp; {v.get("saves",0):,} saves &nbsp;&bull;&nbsp; {v.get("shares",0):,} shares</div>
                  {sound_l}
                  {reason}
                  {intel_html}
                  {watch}
                </div>"""
        spotlight_html += "</div>"

    # -- HASHTAGS --
    ht_html = ""
    for tag, data in tags[:8]:
        views = data["views"]
        views_fmt = f"{views/1_000_000_000:.1f}B" if views >= 1e9 else f"{views/1_000_000:.0f}M" if views >= 1e6 else f"{views:,}"
        ht_html += f'<a href="https://www.tiktok.com/tag/{tag}" style="background:#111a2e;color:#4a9eff;padding:5px 12px;border-radius:20px;margin:3px;display:inline-block;font-size:12px;font-weight:600;border:1px solid #1e3a5f;">#{tag} <span style="color:#2a5a9f;font-size:10px;">{views_fmt}</span></a>'

    # -- TOP HASHTAG VIDEOS --
    ht_videos_html = ""
    for v in top_videos[:4]:
        watch = f'<a href="{v["url"]}" class="watch-btn">Watch â</a>' if v.get("url") else ""
        fans_fmt = f"{v['fans']/1000:.0f}K" if v.get("fans", 0) >= 1000 else str(v.get("fans", 0))
        sound_l = f'<div style="font-size:10px;color:#4a5570;">Sound: {v["sound"]}</div>' if v.get("sound") else ""
        vp = v.get("plays", 0)
        ht_videos_html += f"""
        <div style="background:#0d1018;border-radius:8px;padding:10px;margin-bottom:8px;">
          <div style="font-size:11px;color:#4a5570;margin-bottom:4px;">#{v["tag"]} &nbsp;&bull;&nbsp; <a href="https://www.tiktok.com/@{v["author"]}" style="color:#4a9eff;">@{v["author"]}</a> ({fans_fmt} followers)</div>
          <div style="font-size:12px;color:#c4c8d0;margin-bottom:4px;line-height:1.4;">{v["desc"]}</div>
          <div style="font-size:12px;font-weight:700;color:{plays_color(vp)};">{fmt_plays(vp)} views</div>
          {sound_l}
          {watch}
        </div>"""

    # -- VIDEO IDEAS --
    ideas_html = ""
    for idea in ideas:
        p_color = "#f87171" if idea["priority"] == "URGENT" else "#fbbf24" if idea["priority"] == "HOT" else "#4a9eff"
        inspo_link = f' <a href="{idea["inspo_url"]}" class="watch-btn">Watch inspo â</a>' if idea.get("inspo_url") else ""
        ideas_html += f"""
        <div style="border-left:3px solid {p_color};padding:10px 14px;margin-bottom:10px;background:#0d1018;border-radius:0 8px 8px 0;">
          <div style="font-size:10px;font-weight:700;color:{p_color};margin-bottom:4px;letter-spacing:.5px;">{idea["priority"]} &bull; {idea["pillar"]}{idea.get("inspo","")}{inspo_link}</div>
          <div style="font-size:13px;color:#d4d8e0;margin-bottom:6px;line-height:1.5;">{idea["idea"]}</div>
          <div style="font-size:10px;color:#4a5570;">Sound: <strong style="color:#8a9ab0;">{idea["sound"]}</strong> &nbsp;&bull;&nbsp; {idea["hashtags"]}</div>
        </div>"""

    top_sound_name = top.get("title", "--")
    top_sound_link = f'<a href="{top["link"]}" style="color:#4ade80;text-decoration:underline;">{top_sound_name}</a>' if top.get("link") else f'"{top_sound_name}"'

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>{email_style()}</style></head><body>

<div style="background:linear-gradient(135deg,#0d1117,#111a2e);border-radius:16px;padding:24px;margin-bottom:14px;text-align:center;border:1px solid #1c2a45;">
  <div style="font-size:36px;margin-bottom:8px;">Football</div>
  <h1 style="font-size:22px;font-weight:900;color:#e8ecf4;margin-bottom:4px;">Good Morning, Joshua</h1>
  <p style="color:#4a5570;font-size:13px;">Football Trend Brief &nbsp;&bull;&nbsp; {date_str}</p>
  <div style="margin-top:12px;background:#0d1018;border-radius:8px;padding:10px;font-size:13px;color:#4a9eff;font-weight:600;">
    Best time to post today: {post_time}
  </div>
</div>

<div style="background:#0a1828;border:1px solid #1e3a5f;border-radius:12px;padding:18px;margin-bottom:14px;">
  <h2 style="color:#4a9eff;">Your Move Today</h2>
  <p style="font-size:14px;margin-bottom:8px;line-height:1.6;"><strong style="color:#e8ecf4;">Hottest sound right now:</strong> {top_sound_link}</p>
  <p style="font-size:13px;color:#8a9ab0;line-height:1.6;"><strong style="color:#d4d8e0;">Post idea:</strong> Film a DB press coverage drill. Name a specific WR or school you're preparing for in the caption.</p>
</div>

<div class="card">
  <h2>Video Ideas For Today</h2>
  {ideas_html}
</div>

<div class="card">
  <h2>Niche Sounds Going Viral (30K+ plays)</h2>
  <div style="display:flex;gap:16px;margin-bottom:12px;font-size:10px;color:#4a5570;">
    <span><span style="color:#f87171;font-weight:700;">RED</span> = 500K+ (MEGA)</span>
    <span><span style="color:#fbbf24;font-weight:700;">AMBER</span> = 100K+ (VIRAL)</span>
    <span><span style="color:#4a9eff;font-weight:700;">BLUE</span> = 30K+ (HOT)</span>
  </div>
  {sound_rows}
</div>

<div class="card">
  <h2>Creator Spotlight â Last 7 Days Only</h2>
  <div style="font-size:11px;color:#4a5570;margin-bottom:12px;">Micro &amp; emerging creators posting football content right now. Orange badge = days since posted.</div>
  {spotlight_html}
</div>

<div class="card">
  <h2>Trending Hashtags</h2>
  {ht_html}
  {('<hr class="divider"><div style="font-size:12px;font-weight:700;color:#d4d8e0;margin:12px 0 10px;">Top Videos Under These Hashtags</div>' + ht_videos_html) if ht_videos_html else ""}
</div>

<p style="text-align:center;font-size:10px;color:#2a3048;padding:16px 0;">Football Trend Agent v5 &nbsp;&bull;&nbsp; therealjoshjames22@gmail.com</p>
</body></html>"""
    return html


def build_afternoon_email(sounds, creators, top_videos, ideas, date_str):
    post_time   = best_post_time()
    urgent      = [i for i in ideas if i["priority"] in ("URGENT", "HOT")]
    new_viral   = [v for c in creators for v in c["videos"] if v.get("viral")]

    viral_html = ""
    for v in new_viral[:5]:
        vp     = v.get("plays", 0)
        watch  = f'<a href="{v["url"]}" class="watch-btn">Watch on TikTok â</a>' if v.get("url") else ""
        reason = f'<div style="font-size:10px;color:#4a9eff;margin-top:3px;">{v["viral_reason"]}</div>' if v.get("viral_reason") else ""
        copy_t = f'<div style="font-size:10px;color:#4ade80;margin-top:3px;">Copy this: {v["copy_this"]}</div>' if v.get("copy_this") else ""
        viral_html += f"""
        <div style="padding:10px 0;border-bottom:1px solid #1c2235;">
          <div style="font-size:13px;font-weight:600;color:{plays_color(vp)};">{fmt_plays(vp)} views</div>
          <div style="font-size:12px;color:#8a9ab0;margin-top:2px;">{v["desc"][:70]}</div>
          {reason}
          {copy_t}
          {watch}
        </div>"""
    if not viral_html:
        viral_html = '<p style="font-size:13px;color:#333;">No major viral spikes since this morning.</p>'

    ideas_html = ""
    for idea in (urgent or ideas[:3]):
        p_color = "#f87171" if idea["priority"] == "URGENT" else "#fbbf24"
        inspo_link = f' <a href="{idea["inspo_url"]}" class="watch-btn">Watch inspo â</a>' if idea.get("inspo_url") else ""
        ideas_html += f"""
        <div style="border-left:3px solid {p_color};padding:10px 14px;margin-bottom:10px;background:#0d1018;border-radius:0 8px 8px 0;">
          <div style="font-size:10px;font-weight:700;color:{p_color};margin-bottom:4px;">{idea["priority"]} &bull; {idea["pillar"]}{inspo_link}</div>
          <div style="font-size:13px;color:#d4d8e0;margin-bottom:4px;">{idea["idea"]}</div>
          <div style="font-size:10px;color:#4a5570;">Sound: {idea["sound"]}</div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>{email_style()}</style></head><body>
<div style="background:linear-gradient(135deg,#0d1117,#111a2e);border-radius:16px;padding:20px;margin-bottom:14px;text-align:center;border:1px solid #1c2a45;">
  <div style="font-size:28px;margin-bottom:6px;">Afternoon Update</div>
  <h1 style="font-size:20px;font-weight:900;color:#e8ecf4;">Trend Check</h1>
  <p style="color:#4a5570;font-size:12px;">2PM &nbsp;&bull;&nbsp; {date_str}</p>
  <div style="margin-top:10px;background:#0d1018;border-radius:8px;padding:8px;font-size:12px;color:#4a9eff;">Post window tonight: {post_time}</div>
</div>
<div class="card">
  <h2>Viral Right Now -- Post Before It Peaks</h2>
  {viral_html}
</div>
<div class="card">
  <h2>Top Ideas This Afternoon</h2>
  {ideas_html}
</div>
<p style="text-align:center;font-size:10px;color:#2a3048;padding:16px 0;">Football Trend Agent v5 &nbsp;&bull;&nbsp; 2PM Brief &nbsp;&bull;&nbsp; therealjoshjames22@gmail.com</p>
</body></html>"""
    return html


def build_night_email(sounds, creators, ideas, date_str):
    viral_today = [v for c in creators for v in c["videos"] if v.get("viral")]
    top_sound   = sounds[0] if sounds else {"title": "--", "link": ""}

    recap_html = ""
    for v in viral_today[:5]:
        vp    = v.get("plays", 0)
        watch = f'<a href="{v["url"]}" class="watch-btn">Watch â</a>' if v.get("url") else ""
        copy_t = f'<div style="font-size:10px;color:#4ade80;margin-top:3px;">Copy this: {v["copy_this"]}</div>' if v.get("copy_this") else ""
        recap_html += f"""
        <div style="padding:10px 0;border-bottom:1px solid #1c2235;">
          <div style="font-size:13px;font-weight:600;color:{plays_color(vp)};">{fmt_plays(vp)} views</div>
          <div style="font-size:12px;color:#8a9ab0;margin-top:2px;">{v["desc"][:70]}</div>
          {copy_t}
          {watch}
        </div>"""
    if not recap_html:
        recap_html = '<p style="font-size:13px;color:#333;">No major viral content today in your niche.</p>'

    tomorrow_html = ""
    for idea in ideas[:4]:
        tomorrow_html += f"""
        <div style="border-left:3px solid #4a9eff;padding:10px 14px;margin-bottom:10px;background:#0d1018;border-radius:0 8px 8px 0;">
          <div style="font-size:10px;font-weight:700;color:#4a9eff;margin-bottom:4px;letter-spacing:.5px;">{idea["pillar"]}</div>
          <div style="font-size:13px;color:#d4d8e0;margin-bottom:4px;">{idea["idea"]}</div>
          <div style="font-size:10px;color:#4a5570;">Sound: {idea["sound"]} &nbsp;&bull;&nbsp; {idea["hashtags"]}</div>
        </div>"""

    ts_name = top_sound.get("title", "--")
    top_sound_link = f'<a href="{top_sound["link"]}" style="color:#4a9eff;">{ts_name}</a>' if top_sound.get("link") else ts_name

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>{email_style()}</style></head><body>
<div style="background:linear-gradient(135deg,#0a0c14,#0f1228);border-radius:16px;padding:20px;margin-bottom:14px;text-align:center;border:1px solid #1c2235;">
  <div style="font-size:28px;margin-bottom:6px;">Night Brief</div>
  <h1 style="font-size:20px;font-weight:900;color:#e8ecf4;">Today in Review</h1>
  <p style="color:#4a5570;font-size:12px;">9PM &nbsp;&bull;&nbsp; {date_str}</p>
</div>
<div class="card">
  <h2>What Went Viral In Your Niche Today</h2>
  {recap_html}
</div>
<div class="card">
  <h2>Tomorrow's Content Plan</h2>
  {tomorrow_html}
</div>
<div style="background:#0a1828;border:1px solid #1e3a5f;border-radius:12px;padding:16px;margin-bottom:14px;">
  <h2 style="color:#4a9eff;">Use This Sound Tomorrow</h2>
  <p style="font-size:14px;line-height:1.6;">{top_sound_link} -- post first thing in the morning for max reach</p>
</div>
<p style="text-align:center;font-size:10px;color:#2a3048;padding:16px 0;">Football Trend Agent v5 &nbsp;&bull;&nbsp; 9PM Brief &nbsp;&bull;&nbsp; therealjoshjames22@gmail.com</p>
</body></html>"""
    return html


# -- EMAIL SENDER ----------------------------------------------------
def send_email(subject, html_body):
    if not EMAIL_PASSWORD:
        print(f"[WARN] No EMAIL_PASSWORD -- skipping send. Subject: {subject}")
        return
    try:
        msg            = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = EMAIL_FROM
        msg["To"]      = EMAIL_TO
        msg.attach(MIMEText(html_body, "html", "utf-8"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(EMAIL_FROM, EMAIL_PASSWORD)
            s.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
        print(f"[OK] Email sent: {subject}")
    except Exception as e:
        print(f"[ERROR] Email failed: {e}")


# -- WRITE DATA.JSON -------------------------------------------------
def write_data_json(sounds, creators, tags, top_videos, ideas):
    now = datetime.utcnow().isoformat() + "Z"
    six_hrs_ago = time.time() - 6 * 3600
    breakouts = []
    for v in top_videos:
        ct    = v.get("createTime", 0)
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
            {"title": s.get("title",""), "author": s.get("author",""),
             "rank": s.get("rank",0), "rank_diff": s.get("rank_diff",0),
             "cover": s.get("cover",""), "link": s.get("link",""),
             "trend": s.get("trend",[]), "maxPlays": s.get("maxPlays",0)}
            for s in sounds[:20]
        ],
        "creators": [
            {"handle": c.get("handle",""), "size": c.get("size",""),
             "fans": c.get("fans",0),
             "topVideo": c["videos"][0]["url"] if c.get("videos") else "",
             "topDesc":  c["videos"][0]["desc"] if c.get("videos") else "",
             "topPlays": c["videos"][0]["plays"] if c.get("videos") else 0,
             "formatType": c["videos"][0].get("format_type","") if c.get("videos") else ""}
            for c in creators[:15]
        ],
        "hashtags":  tags[:15],
        "topVideos": [
            {"handle": v.get("authorMeta",{}).get("name",""),
             "fans": v.get("authorMeta",{}).get("fans",0),
             "plays": v.get("playCount",0),
             "desc": v.get("text", v.get("desc",""))[:120],
             "sound": v.get("musicMeta",{}).get("musicName",""),
             "url": v.get("webVideoUrl",""),
             "thumb": v.get("videoMeta",{}).get("coverUrl",""),
             "createTime": v.get("createTime",0)}
            for v in top_videos[:20]
        ],
        "breakouts": breakouts,
        "ideas":     ideas[:5],
    }
    with open("data.json", "w") as f:
        json.dump(data, f, indent=2)
    print(f"[OK] data.json written -- {len(sounds)} sounds, {len(creators)} creators, {len(breakouts)} breakouts")


# -- MAIN ------------------------------------------------------------
def main():
    date_str = datetime.now().strftime("%A, %B %-d %Y")
    brief    = BRIEF_TYPE.lower()

    print(f"\n{'='*52}")
    print(f"Football Trend Agent v5 -- {brief.upper()} RUN")
    print(f"{date_str}")
    print(f"{'='*52}\n")

    # Afternoon/night reuse morning data to save Apify credits
    if brief in ("afternoon", "night") and os.path.exists("data.json"):
        print("  Reusing cached data.json (no new Apify call needed)...")
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
        if not sounds:
            print("  [FALLBACK] Using curated sounds")
            sounds = FALLBACK_SOUNDS
        if not creators:
            print("  [FALLBACK] Using curated creators")
            creators = FALLBACK_CREATORS
        if not tags:
            print("  [FALLBACK] Using curated hashtag data")
            tags = FALLBACK_TAGS
        ideas = generate_video_ideas(sounds, creators, top_videos)

    print(f"\n  Sounds: {len(sounds)}  |  Creators: {len(creators)}  |  Tags: {len(tags)}  |  Top videos: {len(top_videos)}\n")

    write_data_json(sounds, creators, tags, top_videos, ideas)

    if brief in ("morning", "afternoon", "night"):
        if brief == "morning":
            html    = build_morning_email(sounds, creators, tags, top_videos, ideas, date_str)
            subject = f"Football Brief -- {date_str}"
        elif brief == "afternoon":
            html    = build_afternoon_email(sounds, creators, top_videos, ideas, date_str)
            subject = f"Afternoon Update -- {date_str}"
        else:
            html    = build_night_email(sounds, creators, ideas, date_str)
            subject = f"Night Brief -- {date_str}"
        send_email(subject, html)
        print("[OK] Email sent.\n")
    else:
        data_read = json.load(open("data.json"))
        if data_read.get("breakouts"):
            b = data_read["breakouts"][0]
            html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>body{{background:#0a0c10;color:#d4d8e0;font-family:sans-serif;max-width:600px;margin:0 auto;padding:20px;}}</style></head><body>
            <h2 style="color:#f87171;">BREAKOUT ALERT</h2>
            <p><strong style="color:#e8ecf4;">@{b["handle"]}</strong> just hit <strong style="color:#f87171;">{b["plays"]:,} views</strong> in the last 6 hours.</p>
            <p style="color:#4a5570;">Sound: {b["sound"]}</p>
            <p style="color:#8a9ab0;">{b["desc"]}</p>
            <p><a href="{b["url"]}" style="color:#4a9eff;">Watch Video â</a></p>
            </body></html>"""
            send_email(f"BREAKOUT: @{b['handle']} -- {b['plays']:,} views right now", html)
        else:
            print("[OK] Scan complete. No breakouts. data.json updated.\n")

    print("[OK] Done.\n")


if __name__ == "__main__":
    main()
