"""
Football Trend Agent v6 -- AI Content Intelligence System
- Runs every 3 hours via GitHub Actions
- 6AM: Morning Brief (deep creator intel + sounds + hashtags + video ideas)
- 2PM: Afternoon Idea Refresh
- 9PM: Night Brief (viral recap + tomorrow's plan)
- Every other run: quick scan, breakout alerts only
- Creator deep dive: recent posts only (7-day), sorted by recency then plays
- sortType:latest on Apify so old viral videos never surface
- Hook/format analysis on every viral video
- Confidence scoring 1-100 on all signals
- Audio lifecycle: EARLY / HEATING UP / PEAKING / SATURATED / DECLINING
- American football filter: rejects soccer/non-football content
- Micro creator priority: ceiling 50K, prioritizes under 5K
- Sound cards with actual clickable football videos
- Long-term memory via data.json trend history
Content pillars: 1v1 competition, DB drills, workout/training, motivation, Christian athlete
"""

import os
import time
import json
import random
import requests
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta

# -- CONFIG ----------------------------------------------------------
APIFY_TOKEN    = os.environ.get("APIFY_TOKEN", "")
EMAIL_FROM     = os.environ.get("EMAIL_FROM", "therealjoshjames22@gmail.com")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "")
EMAIL_TO       = os.environ.get("EMAIL_TO", "therealjoshjames22@gmail.com")
BRIEF_TYPE     = os.environ.get("BRIEF_TYPE", "morning")

HASHTAGS = [
    "footballtraining","dbtraining","cornerback","1v1football",
    "widereceiverstraining","footballdrills","footballworkout",
    "highschoolfootball","collegefootball","defensiveback","7on7",
    "cfb","footballtiktok","d1","d1athlete","footballedit",
    "footballhighlight","dblife","nfl","dbcamp","gridiron"
]

CREATOR_HANDLES = [
    "jalen.ramsey","sauce.gardner.db","patricksuisala",
    "db_elite_training","cornerback.university","dbcamp.official",
    "footballgrind.official","athletelifestyle.db"
]

MIN_VIEWS_HARD       = 20_000
MIN_VIEWS_FAST_RISE  = 10_000
TIER_ON_THE_RISE     = 20_000
TIER_GOOD_ZONE       = 50_000
TIER_VIRAL           = 100_000
TIER_MEGA            = 500_000
SOUND_MIN_NICHE_VIDS = 5
SOUND_MIN_TOP_PLAYS  = 20_000
CREATOR_MAX_FANS     = 50_000
SEVEN_DAYS_SECS      = 7 * 24 * 3600

# -- AMERICAN FOOTBALL FILTER ----------------------------------------
FOOTBALL_KEEP = {
    "quarterback","qb","db","wr","cornerback","corner","linebacker","lb",
    "safety","defensive back","snap","route","blitz","7on7","d1","gridiron",
    "pigskin","end zone","touchdown","td","field goal","punt","recruit",
    "spring ball","pads","helmet","nfl","ncaa","cfb","college football",
    "football","scrimmage","playbook","offense","defense","lineman",
    "running back","rb","tight end","te","wide receiver","pass rush",
    "db camp","football camp","dbcamp","dbtraining","footballtraining",
    "footballdrills","footballworkout","footballhighlight","footballedit",
    "footballtiktok","dblife","d1athlete","highschoolfootball","collegefootball",
    "defensiveback","1v1football","widereceiverstraining","dbtraining",
    "cornerback","gridiron","american football"
}

SOCCER_REJECT = {
    "soccer","pitch","keeper","penalty kick","premier league","uefa","fifa",
    "footy","futbol","hat trick","nil nil","clean sheet","offside",
    "dribble","header","free kick","goalkeeper","bundesliga","la liga",
    "serie a","ligue 1","mls","champions league","world cup soccer",
    "football club","fc ","united fc","city fc"
}

def is_american_football(text):
    """Returns True if content is American football, False if soccer/other."""
    if not text:
        return False
    t = text.lower()
    # Hard reject soccer
    for s in SOCCER_REJECT:
        if s in t:
            return False
    # Must have at least one American football signal
    for k in FOOTBALL_KEEP:
        if k in t:
            return True
    return False

def score_football_confidence(text):
    """Score 0-10 how strongly American football this content is."""
    if not text:
        return 0
    t = text.lower()
    for s in SOCCER_REJECT:
        if s in t:
            return 0
    score = sum(1 for k in FOOTBALL_KEEP if k in t)
    return min(score, 10)

# -- HOOK DATABASE ---------------------------------------------------
HOOK_PATTERNS = [
    "pov", "nobody talks about", "the difference between", "this is what",
    "coach finally", "day in the life", "watch me", "they don't show you",
    "d1 vs", "high school vs college", "what db camp really looks like",
    "before and after", "this drill", "if you play db", "grind don't stop",
    "they called me", "committed", "offer day", "first practice",
    "nobody saw this coming", "raw footage", "unfiltered", "real talk"
]

def extract_hooks(desc):
    """Extract matching hook patterns from a video description."""
    if not desc:
        return []
    d = desc.lower()
    return [p for p in HOOK_PATTERNS if p in d]

# -- CONTENT TYPE CLASSIFIER -----------------------------------------
CONTENT_TYPES = {
    "hype":         ["hype","lit","fire","lets go","lock in"],
    "cinematic":    ["cinematic","slow mo","film","aesthetic","vibes"],
    "pov":          ["pov","point of view"],
    "emotional":    ["emotional","feel","real talk","truth","story"],
    "motivational": ["motivation","grind","work","believe","faith","god"],
    "locker_room":  ["locker room","team","brotherhood","culture","family"],
    "grindset":     ["grind","work ethic","no days off","discipline","sacrifice"],
    "rivalry":      ["1v1","competition","who wins","battle","vs"],
    "transformation":["transformation","glow up","before","after","progress"],
    "relatable":    ["relatable","fr","real","facts","too real","same"]
}

def classify_content(desc):
    if not desc:
        return "general"
    d = desc.lower()
    for ctype, keywords in CONTENT_TYPES.items():
        if any(k in d for k in keywords):
            return ctype
    return "general"

# -- FORMAT FATIGUE SIGNALS ------------------------------------------
FATIGUED_FORMATS = [
    "put this audio on your page","comment your number","follow for part 2",
    "duet this","stitch this","which one are you","rate yourself",
    "this went viral","blew up","millions of views"
]

def is_fatigued_format(desc):
    if not desc:
        return False
    d = desc.lower()
    return any(f in d for f in FATIGUED_FORMATS)

# -- CONFIDENCE SCORING ----------------------------------------------
def confidence_score(plays, fans, hours_old, niche_signals, is_football, hook_count, content_type):
    """Score 0-100 confidence that this is a high-value opportunity."""
    if not is_football:
        return 0
    score = 0
    # Views tier (max 30)
    if plays >= TIER_MEGA:       score += 30
    elif plays >= TIER_VIRAL:    score += 25
    elif plays >= TIER_GOOD_ZONE:score += 18
    elif plays >= TIER_ON_THE_RISE:score += 10
    else:                        score += 5
    # Follower-to-view ratio (max 30)
    ratio = plays / max(fans, 1)
    if ratio >= 50:   score += 30
    elif ratio >= 20: score += 22
    elif ratio >= 10: score += 15
    elif ratio >= 5:  score += 8
    else:             score += 2
    # Recency (max 20)
    if hours_old <= 24:   score += 20
    elif hours_old <= 48: score += 15
    elif hours_old <= 72: score += 10
    elif hours_old <= 168:score += 5
    # Niche signals (max 10)
    score += min(niche_signals * 2, 10)
    # Hook quality (max 5)
    score += min(hook_count * 2, 5)
    # Content type bonus (max 5)
    if content_type in ("rivalry","grindset","pov","emotional"):
        score += 5
    elif content_type in ("motivational","locker_room","transformation"):
        score += 3
    return min(score, 100)

def sound_confidence(niche_vids, max_plays, hours_since_first, adoption_accel):
    """Score 0-100 for a trending sound."""
    score = 0
    if niche_vids >= 20:  score += 30
    elif niche_vids >= 10:score += 20
    elif niche_vids >= 5: score += 12
    else:                 score += 5
    if max_plays >= TIER_MEGA:       score += 25
    elif max_plays >= TIER_VIRAL:    score += 20
    elif max_plays >= TIER_GOOD_ZONE:score += 14
    elif max_plays >= TIER_ON_THE_RISE:score += 8
    # Recency of trend start (max 25)
    if hours_since_first <= 24:   score += 25
    elif hours_since_first <= 48: score += 18
    elif hours_since_first <= 72: score += 12
    elif hours_since_first <= 168:score += 6
    # Adoption acceleration (max 20)
    score += min(int(adoption_accel * 20), 20)
    return min(score, 100)

def audio_lifecycle(niche_vids, hours_since_first, adoption_accel):
    """Classify sound lifecycle stage."""
    if niche_vids < 3:
        return "EARLY"
    if niche_vids < 8 and hours_since_first < 48:
        return "HEATING UP"
    if niche_vids >= 8 and adoption_accel > 0.5:
        return "PEAKING"
    if niche_vids >= 15 and hours_since_first > 120:
        return "SATURATED"
    if adoption_accel < 0.1 and hours_since_first > 72:
        return "DECLINING"
    return "HEATING UP"

LIFECYCLE_EMOJI = {
    "EARLY":      "ð",
    "HEATING UP": "â¡",
    "PEAKING":    "ð¥",
    "SATURATED":  "â ï¸",
    "DECLINING":  "ð"
}

# -- CREATOR TIER ----------------------------------------------------
def creator_tier(fans):
    if fans < 5_000:    return "MICRO", "#f87171"
    if fans < 15_000:   return "EMERGING", "#4ade80"
    if fans < 30_000:   return "SMALL", "#4a9eff"
    if fans <= 50_000:  return "RISING", "#888"
    return None, None

# -- LONG-TERM MEMORY ------------------------------------------------
MEMORY_FILE = "trend_memory.json"

def load_memory():
    try:
        with open(MEMORY_FILE) as f:
            return json.load(f)
    except:
        return {"sounds": {}, "hooks": {}, "creators": {}, "formats": {}, "runs": 0}

def save_memory(memory):
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=2)

def update_memory(memory, sounds, creators, top_videos):
    memory["runs"] = memory.get("runs", 0) + 1
    now_ts = time.time()
    # Track sounds
    for s in sounds:
        title = s.get("title", "")
        if not title:
            continue
        if title not in memory["sounds"]:
            memory["sounds"][title] = {"first_seen": now_ts, "appearances": 0, "max_plays": 0}
        memory["sounds"][title]["appearances"] += 1
        memory["sounds"][title]["max_plays"] = max(memory["sounds"][title]["max_plays"], s.get("maxPlays", 0))
        memory["sounds"][title]["last_seen"] = now_ts
    # Track hooks
    for v in top_videos:
        desc = v.get("text", v.get("desc", ""))
        for hook in extract_hooks(desc):
            if hook not in memory["hooks"]:
                memory["hooks"][hook] = {"count": 0, "max_plays": 0}
            memory["hooks"][hook]["count"] += 1
            memory["hooks"][hook]["max_plays"] = max(
                memory["hooks"][hook]["max_plays"],
                v.get("playCount", 0)
            )
    # Track creators
    for c in creators:
        handle = c.get("handle", "")
        if not handle:
            continue
        if handle not in memory["creators"]:
            memory["creators"][handle] = {"first_seen": now_ts, "appearances": 0, "max_plays": 0}
        memory["creators"][handle]["appearances"] += 1
        if c.get("videos"):
            memory["creators"][handle]["max_plays"] = max(
                memory["creators"][handle]["max_plays"],
                max((v.get("plays",0) for v in c["videos"]), default=0)
            )
    return memory

# -- FALLBACK DATA ---------------------------------------------------
FALLBACK_SOUNDS = [
    {"title": "Thought About That", "author": "Future", "rank": 1, "rank_diff": 2,
     "cover": "", "link": "https://www.tiktok.com/music/Thought-About-That-7234567890",
     "trend": [], "maxPlays": 85000, "niche_videos": [], "lifecycle": "HEATING UP", "confidence": 72},
]
FALLBACK_CREATORS = []
FALLBACK_TAGS = [("footballtraining", {"views": 2_500_000_000})]

# -- APIFY FETCH -----------------------------------------------------
def apify_run(actor, input_data, timeout=300):
    if not APIFY_TOKEN:
        print("[WARN] No APIFY_TOKEN")
        return []
    try:
        r = requests.post(
            f"https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items",
            params={"token": APIFY_TOKEN, "timeout": timeout, "memory": 512},
            json=input_data, timeout=timeout + 30
        )
        r.raise_for_status()
        return r.json() if isinstance(r.json(), list) else []
    except Exception as e:
        print(f"[ERROR] Apify {actor}: {e}")
        return []

def fetch_all_raw():
    print("  Fetching TikTok data via Apify (sortType:latest)...")
    raw = apify_run("clockworks/tiktok-hashtag-scraper", {
        "hashtags": HASHTAGS,
        "resultsPerPage": 20,
        "sortType": "latest",
        "proxyConfiguration": {"useApifyProxy": True}
    })
    print(f"  Raw items: {len(raw)}")
    return raw

# -- VIDEO FILTER (American football gate) ---------------------------
def video_passes_football_gate(v):
    """Must pass American football check. Returns (passes, confidence_score)."""
    desc    = v.get("text", v.get("desc", ""))
    tags    = " ".join(c.get("title","") for c in v.get("challenges",[]) if isinstance(c,dict))
    sound   = v.get("musicMeta",{}).get("musicName","")
    author  = v.get("authorMeta",{}).get("name","")
    combo   = f"{desc} {tags} {sound} {author}"
    passes  = is_american_football(combo)
    signals = score_football_confidence(combo)
    return passes, signals

# -- FETCH TRENDING SOUNDS -------------------------------------------
def fetch_trending_sounds(raw):
    now_ts = time.time()
    sound_map = {}

    for v in raw:
        ct = v.get("createTime", 0)
        if now_ts - ct > SEVEN_DAYS_SECS:
            continue
        passes, signals = video_passes_football_gate(v)
        if not passes:
            continue
        plays = v.get("playCount", 0) or v.get("stats",{}).get("playCount",0)
        if plays < MIN_VIEWS_HARD:
            # fast-rise exception
            hours_old = (now_ts - ct) / 3600 if ct else 999
            ratio = plays / max(v.get("authorMeta",{}).get("fans",1), 1)
            if not (hours_old < 24 and ratio > 5 and plays >= MIN_VIEWS_FAST_RISE):
                continue

        m    = v.get("musicMeta", {})
        sid  = m.get("musicId","") or m.get("musicName","")
        if not sid:
            continue

        hours_old = (now_ts - ct) / 3600 if ct else 999
        fans  = v.get("authorMeta",{}).get("fans",1)
        ratio = plays / max(fans, 1)
        url   = v.get("webVideoUrl","")
        author= v.get("authorMeta",{}).get("name","")
        desc  = v.get("text", v.get("desc",""))
        hooks = extract_hooks(desc)
        ctype = classify_content(desc)
        cscore = confidence_score(plays, fans, hours_old, signals, True, len(hooks), ctype)

        niche_video = {
            "url":    url,
            "author": author,
            "fans":   fans,
            "plays":  plays,
            "desc":   desc[:100],
            "hours_old": hours_old,
            "ratio":  ratio,
            "confidence": cscore,
            "hooks":  hooks,
            "content_type": ctype
        }

        if sid not in sound_map:
            sound_map[sid] = {
                "title":       m.get("musicName","Unknown Sound"),
                "author":      m.get("musicAuthor",""),
                "link":        f"https://www.tiktok.com/music/{m.get('musicName','').replace(' ','-')}-{m.get('musicId','')}",
                "cover":       m.get("musicCover",""),
                "niche_videos":[],
                "max_plays":   0,
                "first_seen":  ct,
                "last_seen":   ct,
                "plays_24h":   0,
                "plays_3d":    0,
                "plays_7d":    0,
                "videos_24h":  0,
                "videos_3d":   0,
                "videos_7d":   0,
            }
        entry = sound_map[sid]
        entry["niche_videos"].append(niche_video)
        entry["max_plays"]  = max(entry["max_plays"], plays)
        entry["first_seen"] = min(entry["first_seen"], ct) if ct else entry["first_seen"]
        entry["last_seen"]  = max(entry["last_seen"], ct) if ct else entry["last_seen"]
        if hours_old <= 24:
            entry["videos_24h"] += 1
            entry["plays_24h"]  += plays
        if hours_old <= 72:
            entry["videos_3d"]  += 1
            entry["plays_3d"]   += plays
        entry["videos_7d"] += 1
        entry["plays_7d"]  += plays

    sounds = []
    for sid, s in sound_map.items():
        nv = len(s["niche_videos"])
        if nv < SOUND_MIN_NICHE_VIDS or s["max_plays"] < SOUND_MIN_TOP_PLAYS:
            continue
        hours_since_first = (now_ts - s["first_seen"]) / 3600 if s["first_seen"] else 168
        accel = s["videos_24h"] / max(nv, 1)
        lifecycle = audio_lifecycle(nv, hours_since_first, accel)
        conf = sound_confidence(nv, s["max_plays"], hours_since_first, accel)
        # Sort niche videos by confidence desc, then recency
        s["niche_videos"].sort(key=lambda x: (-x["confidence"], x["hours_old"]))
        sounds.append({
            **s,
            "niche_video_count": nv,
            "lifecycle":   lifecycle,
            "confidence":  conf,
            "accel":       accel,
            "hours_since_first": hours_since_first,
        })

    sounds.sort(key=lambda x: (-x["confidence"], -x["max_plays"]))
    print(f"  Trending sounds (football-filtered): {len(sounds)}")
    return sounds[:15]

# -- FETCH CREATOR SPY -----------------------------------------------
def fetch_creator_spy(raw):
    now_ts = time.time()
    creator_map = {}

    for v in raw:
        ct = v.get("createTime", 0)
        if now_ts - ct > SEVEN_DAYS_SECS:
            continue
        passes, signals = video_passes_football_gate(v)
        if not passes:
            continue
        plays = v.get("playCount",0) or v.get("stats",{}).get("playCount",0)
        if plays < MIN_VIEWS_HARD:
            hours_old = (now_ts - ct) / 3600 if ct else 999
            ratio = plays / max(v.get("authorMeta",{}).get("fans",1),1)
            if not (hours_old < 24 and ratio > 5 and plays >= MIN_VIEWS_FAST_RISE):
                continue

        meta  = v.get("authorMeta",{})
        fans  = meta.get("fans",0)
        if fans > CREATOR_MAX_FANS or fans < 100:
            continue

        tier_name, _ = creator_tier(fans)
        if tier_name is None:
            continue

        handle = meta.get("name","")
        if not handle:
            continue

        hours_old = (now_ts - ct) / 3600 if ct else 999
        ratio = plays / max(fans, 1)
        desc  = v.get("text", v.get("desc",""))
        sound = v.get("musicMeta",{}).get("musicName","")
        hooks = extract_hooks(desc)
        ctype = classify_content(desc)
        fatigued = is_fatigued_format(desc)
        cscore = confidence_score(plays, fans, hours_old, signals, True, len(hooks), ctype)
        url   = v.get("webVideoUrl","")

        vid_entry = {
            "plays":     plays,
            "desc":      desc[:120],
            "url":       url,
            "sound":     sound,
            "days_ago":  int(hours_old // 24),
            "hours_old": hours_old,
            "ratio":     ratio,
            "confidence":cscore,
            "hooks":     hooks,
            "content_type": ctype,
            "fatigued":  fatigued,
            "viral":     plays >= TIER_VIRAL,
            "viral_reason": _viral_reason(plays, fans, hours_old, ctype),
            "copy_this": _copy_this(desc, ctype, hooks),
            "format_type": ctype.upper().replace("_"," "),
            "hook_analysis": _hook_analysis(desc, hooks)
        }

        if handle not in creator_map:
            creator_map[handle] = {
                "handle": handle,
                "fans":   fans,
                "size":   tier_name.lower(),
                "pillar": _guess_pillar(desc),
                "tag":    meta.get("id",""),
                "author": meta.get("name",""),
                "videos": []
            }
        creator_map[handle]["videos"].append(vid_entry)

    # Sort each creator's videos: recency first, then plays
    for c in creator_map.values():
        c["videos"].sort(key=lambda v: (v["hours_old"], -v["plays"]))

    # Sort creators: micro first, then by best ratio
    def sort_key(c):
        tier_order = {"micro":0,"emerging":1,"small":2,"rising":3}
        t = tier_order.get(c["size"],4)
        max_ratio = max((v["ratio"] for v in c["videos"]), default=0)
        return (t, -max_ratio)

    creators = sorted(creator_map.values(), key=sort_key)
    print(f"  Creators (football-filtered, â¤50K): {len(creators)}")
    return creators[:12]

def _viral_reason(plays, fans, hours_old, ctype):
    ratio = plays / max(fans,1)
    parts = []
    if ratio > 30: parts.append(f"{ratio:.0f}x follower ratio")
    if hours_old < 48: parts.append("posted <48h ago")
    if ctype in ("rivalry","grindset","pov"): parts.append(f"{ctype} format converts well")
    return " Â· ".join(parts) if parts else ""

def _copy_this(desc, ctype, hooks):
    if hooks:
        return f'Try hook: "{hooks[0].title()}" angle'
    if ctype == "rivalry": return "Film a 1v1 or drill battle with this audio"
    if ctype == "pov":     return "POV-style caption + intense training clip"
    if ctype == "grindset":return "Early morning grind session, no talking"
    if ctype == "emotional":return "Raw honest caption, slow-mo highlight"
    return "Adapt format to your DB/training content"

def _hook_analysis(desc, hooks):
    if not desc:
        return ""
    d = desc[:80]
    if hooks:
        return f'Hook type: {hooks[0]} â opens strong'
    if d.startswith("POV") or d.startswith("pov"):
        return "POV open â high retention trigger"
    if "?" in d[:30]:
        return "Question hook â curiosity gap"
    return ""

def _guess_pillar(desc):
    d = (desc or "").lower()
    if any(x in d for x in ["1v1","vs","battle","competition"]): return "1v1 Competition"
    if any(x in d for x in ["db","corner","defensive back","press","coverage"]): return "DB Training"
    if any(x in d for x in ["workout","gym","lift","weight"]): return "Gym/Workout"
    if any(x in d for x in ["god","faith","christian","blessed","pray"]): return "Faith"
    if any(x in d for x in ["team","brother","culture","locker"]): return "Brotherhood"
    if any(x in d for x in ["motivat","grind","discipline","mindset"]): return "Mindset"
    return "Training"

# -- FETCH HASHTAGS --------------------------------------------------
def fetch_hashtags(raw):
    now_ts = time.time()
    tag_map = {}
    top_videos = []

    for v in raw:
        ct = v.get("createTime",0)
        if now_ts - ct > SEVEN_DAYS_SECS:
            continue
        passes, signals = video_passes_football_gate(v)
        if not passes:
            continue
        plays = v.get("playCount",0) or v.get("stats",{}).get("playCount",0)
        if plays < MIN_VIEWS_HARD:
            continue
        for ch in v.get("challenges",[]):
            if not isinstance(ch, dict):
                continue
            tag   = ch.get("title","").lower()
            views = ch.get("views",0) or ch.get("viewCount",0)
            if tag:
                tag_map[tag] = tag_map.get(tag, {"views":0,"count":0})
                tag_map[tag]["views"] = max(tag_map[tag]["views"], views)
                tag_map[tag]["count"] += 1
        top_videos.append(v)

    tags = sorted(tag_map.items(), key=lambda x: -x[1]["views"])
    top_videos.sort(key=lambda v: -(v.get("playCount",0) or 0))
    print(f"  Hashtags: {len(tags)} | Top videos (football): {len(top_videos)}")
    return tags, top_videos[:20]

# -- CONTENT GAP DETECTION -------------------------------------------
def detect_content_gaps(creators, top_videos):
    """Find underserved content angles."""
    seen_types = {}
    for c in creators:
        for v in c.get("videos",[]):
            ct = v.get("content_type","general")
            seen_types[ct] = seen_types.get(ct,0) + 1

    all_types = set(CONTENT_TYPES.keys())
    seen = set(seen_types.keys())
    gaps = all_types - seen

    gap_ideas = []
    if "locker_room" in gaps:
        gap_ideas.append({"gap":"Locker Room Culture","idea":"Behind-the-scenes team moments â almost no one in your niche does this authentically","pillar":"Brotherhood"})
    if "transformation" in gaps:
        gap_ideas.append({"gap":"Transformation","idea":"Before/after speed or strength progression â extremely shareable","pillar":"Training"})
    if "emotional" in gaps:
        gap_ideas.append({"gap":"Emotional/Raw","idea":"Real talk about the grind, faith, or setbacks â underserved in football niche","pillar":"Faith/Mindset"})
    if "cinematic" in gaps:
        gap_ideas.append({"gap":"Cinematic Training","idea":"Slow-mo DB drill with cinematic edit â very repeatable, low competition","pillar":"DB Training","pillar":"DB Training"})
        gap_ideas.append({"gap":"Cinematic Training","idea":"Slow-mo DB drill with cinematic edit â very repeatable, low competition","pillar":"DB Training"})
    return gap_ideas[:3]

# -- VIDEO IDEAS -----------------------------------------------------
def generate_video_ideas(sounds, creators, top_videos):
    top  = sounds[0] if sounds else {}
    top2 = sounds[1] if len(sounds) > 1 else {}
    top_sound_name  = top.get("title","--")
    top2_sound_name = top2.get("title","--")
    top_sound_link  = top.get("link","")
    top2_sound_link = top2.get("link","")

    ideas = [
        {
            "priority":"URGENT","pillar":"DB Training",
            "idea":"Film a DB press coverage drill â show the footwork in slow-mo, caption: 'The technique they don't teach at most camps'",
            "sound":top_sound_name,"sound_link":top_sound_link,
            "hashtags":"#dbtraining #cornerback #footballtraining #d1",
            "hook":"They don't teach this at most camps","content_type":"pov",
            "confidence":88,
            "inspo_url": top.get("niche_videos",[{}])[0].get("url","") if top.get("niche_videos") else ""
        },
        {
            "priority":"HOT","pillar":"1v1 Competition",
            "iYXH]È]HÛÝYÙH8 %ÈÔÈ]\ÚXÈ\[È^KYÛÝ[Y\Ø\[Û	ÔÕ[ÝH[[HØÚÈ[H\	ÈÛÝ[ÜÜÛÝ[Û[YKÛÝ[Û[ÈÜÜÛÝ[Û[Ë\ÚYÜÈÌ]YÛÝ[ØÛÜ\XÚÈÙYHÙÛÝ[Z[[ÈÛÚÈÕ[ÝH[[HØÚÈ[H\ÛÛ[Ý\H][HÛÛY[ÙHLK[Ü×Ý\KÂ[Ü]HÕ[\Z]ÓZ[Ù]YXHÌ\ÙXÛÛÜ[[ÛYÙH8 %X\H[Ü[ÈÛÜÛÝ]ÈÛÜÈÜ\ÝLÙXË[ÛH[HXÝ]Z]Ù\ØÚ\[HÛÝ[ÜÜÛÝ[Û[YKÛÝ[Û[ÈÜÜÛÝ[Û[Ë\ÚYÜÈÙX]]HÙÛÝ[ÛÜÛÝ]ØÚ\ÝX[]]HÙÜ[ÛÚÈØÙHÙY\ÈH
PSHÛÜÈÛÛ[Ý\HÜ[Ù]ÛÛY[ÙH
K[Ü×Ý\KÂ[Ü]HÐUÒ[\Z[[ÈYXHXZÈÝÛHÝ]HÛÛÙ\ÛHH\ÜXÝ]H8 %\ÙH^Ý\^HÈX[HXÚ\]YHÛÝ[ÜÜÛÝ[Û[YKÛÝ[Û[ÈÜÜÛÝ[Û[Ë\ÚYÜÈÙY[Ú]XXÚÈÙZ[[ÈØÛÛYÙYÛÝ[ØÛÜ\XÚÈÛÚÈHY\[ÙH]ÙY[H[YÚØÚÛÛÈÛÛ[Ý\HÝÛÛY[ÙHÎK[Ü×Ý\KÂ[Ü]HÐUÒ[\Ý\ÛÙYXHZ[]K\ØÙ[\ÈX[HØ\K]\ÜØ[Ë]ÝYÚ8 %]][XÈØÚÙ\ÛÛHY[È[\ÛÝ[ÜÜÛÝ[Û[YKÛÝ[Û[ÈÜÜÛÝ[Û[Ë\ÚYÜÈØÛÛYÙYÛÝ[ÙÛÝ[X[HÙX]]HØÝ\ÛÙÛÚÈÚ]HXÝXÙHXÝX[HÛÚÜÈZÙHÛÛ[Ý\HØÚÙ\ÜÛÛHÛÛY[ÙHÍ[Ü×Ý\KB]\YX\ÂÈKHTÕÔÕSQHKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKBY\ÝÜÜÝÝ[YJ
N[Y\ÈHÈ8 $ÍÎSHÎ8 $ÎSHLNSx $ÌNHN8 $ÍÎH8 $ÌLHB]\[ÛKÚÚXÙJ[Y\ÊBÈKHÔPUUSÈKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKBY]Ü^\Ê
NYHWÌÌ]\ÜÌWÌÌYSHYHWÌ]\ÜÌWÌRÈ]\Ý
BY^\×ØÛÛÜ
NYHQTÓQQÐN]\Ù
ÌMÌHYHQTÕTS]\ÙYHQTÑÓÓÑÖÓN]\ÍYNYHQTÓÓÕWÔTÑN]\ÍNYY]\ÍMMMÌY^\×ÛX[

NYHQTÓQQÐN]\QQÐHYHQTÕTS]\TSYHQTÑÓÓÑÖÓN]\ÓÓÑÓHYHQTÓÓÕWÔTÑN]\ÓHTÑH]\YÛÛY[ÙWØYÙJØÛÜJNYØÛÜHHL]\ÏÜ[Ý[OHÛÛÜÙ
ÌMÌNÙÛ]ÙZYÚÌÈ¼'å)HÜØÛÜ_KÌLÜÜ[ÂYØÛÜHH
ÍN]\ÏÜ[Ý[OHÛÛÜÙÙÛ]ÙZYÚÌÈ¸¦¨HÜØÛÜ_KÌLÜÜ[ÂYØÛÜHH
]\ÏÜ[Ý[OHÛÛÜÍYNÙÛ]ÙZYÚÌÈ¼'ä`ÜØÛÜ_KÌLÜÜ[Â]\ÏÜ[Ý[OHÛÛÜÍMMMÌÈÜØÛÜ_KÌLÜÜ[ÂÈKHSPRSÕSHKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKBY[XZ[ÜÝ[J
N]\Ù^ØXÚÙÜÝ[ÌLÌLØÛÛÜÙ
LÙÛY[Z[NX\K\Þ\Ý[K[ÓXXÔÞ\Ý[QÛ	ÔÙYÛÙHRIËØ[Ë\Ù\YÛX^]ÚYÛX\Ú[]]ÎÜY[ÎMÙÛ\Ú^NLÜßBÙÛ\Ú^NM\ÙÛ]ÙZYÚÌØÛÛÜÙNXÙÛX\Ú[LÜY[ËXÝÛNØÜ\XÝÛN\ÛÛYÌXÌÍNßBØ\ØXÚÙÜÝ[ÌLLNØÜ\\ÛÛYÌXÌÍNØÜ\\Y]\ÎLÜY[ÎMÛX\Ú[XÝÛNMßBØ]ÚXÙ\Ü^N[[KXØÚÎØXÚÙÜÝ[ÌLLXLNØÛÛÜÍNYYÜY[ÎLØÜ\\Y]\ÎÙÛ\Ú^NL\ÙÛ]ÙZYÚÝ^YXÛÜ][ÛÛNÛX\Ú[]ÜØÜ\\ÛÛYÌYLØMYßBÛÝ[XÙ\Ü^N[[KXØÚÎØXÚÙÜÝ[ÌLNØÛÛÜÍYNÜY[Î\LØÜ\\Y]\ÎÙÛ\Ú^NL\ÙÛ]ÙZYÚÌÝ^YXÛÜ][ÛÛNÛX\Ú[]ÜØÜ\\ÛÛYÌYMYØNßBYÞÙ\Ü^N[[KXØÚÎÜY[Î
ÜØÜ\\Y]\ÎLÙÛ\Ú^N\ÙÛ]ÙZYÚÌÛX\Ú[\YÚÛX\Ú[XÝÛNßBYË[YYØ^ØXÚÙÜÝ[Ù
ÌMÌLØÛÛÜÙ
ÌMÌNØÜ\\ÛÛYÙ
ÌMÌMßBYË]\[ØXÚÙÜÝ[ÙØÛÛÜÙØÜ\\ÛÛYÙ
ßBYËYÛÛÙÛ^ØXÚÙÜÝ[ÍYNØÛÛÜÍYNØÜ\\ÛÛYÍYN
ßBYË\\Ù^ØXÚÙÜÝ[ÍNYYØÛÛÜÍNYYØÜ\\ÛÛYÍNYYßBYËYÜ^^ØXÚÙÜÝ[ÎØÛÛÜÎØÜ\\ÛÛYÎ
ßBYË[Ü[Ù^ØXÚÙÜÝ[ÙLØÌØÛÛÜÙLØÎØÜ\\ÛÛYÙLØÍßBYËYÜY[ØXÚÙÜÝ[ÍYNØÛÛÜÍYNØÜ\\ÛÛYÍYN
ßBYË\YØXÚÙÜÝ[Ù
ÌMÌLØÛÛÜÙ
ÌMÌNØÜ\\ÛÛYÙ
ÌMÌMßB[[XÞØXÚÙÜÝ[ÌÌMØÜ\\ÛÛYÌXÌÍNØÜ\\Y]\ÎÜY[ÎÛX\Ú[]ÜßB]Y\ØÜ\ÛNØÜ\]Ü\ÛÛYÌXÌÍNÛX\Ú[LßBÛÝ[XØ\ØXÚÙÜÝ[Ì
LLØÜ\\ÛÛYÌYLØMYØÜ\\Y]\ÎLÜY[ÎMÛX\Ú[XÝÛNLßBXÚK]Y[ÞØXÚÙÜÝ[ÌLLNØÜ\\Y]\ÎÜY[ÎÛX\Ú[XÝÛNØÜ\[YÛÛYÌYLØMYßBØ\XØ\ØXÚÙÜÝ[ÌLNØÜ\\ÛÛYÌYLØMYØÜ\\Y]\ÎÜY[ÎLÛX\Ú[XÝÛNßBÈKHÓÕSÐTSKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKBYZ[ÜÛÝ[ØØ\
ËY[[ÜJNYXÞXÛHHËÙ]
YXÞXÛHPUSÈTB×Ù[[ÚHHQPÖPÓWÑSSÒKÙ]
YXÞXÛK¸¦¨HBÛÛHËÙ]
ÛÛY[ÙH
BHËÙ]
XÚWÝY[×ØÛÝ[
BX^Ü^\ÈHËÙ]
X^Ü^\È
BHËÙ]
Y[Ü×Ì
BÙHËÙ]
Y[Ü×ÌÙ
BÙHËÙ]
Y[Ü×ÍÙ
BÛÝ[Û[ÈHËÙ]
[ÈB]HHËÙ]
]H[ÛÝÛÛÝ[BY[WÙ]HHY[[ÜKÙ]
ÛÝ[ÈßJKÙ]
]KßJB\X\[Ù\ÈHY[WÙ]KÙ]
\X\[Ù\ÈJB\X]ÛÝHHÈ0­ÈÜ[Ý[OHÛÛÜÙLØÎÈÙY[Ø\X\[Ù\ß^[Y[[ÜOÜÜ[ÈY\X\[Ù\ÈH[ÙHÈYXÞXÛHÛÛÜ×ØÛÛÜHÈPTHÍYNPUSÈTÙPRÒSÈÙ
ÌMÌHÐUTUQÎPÓSSÈÍMMMÌKÙ]
YXÞXÛKÍNYYB[H]Û\ÜÏHÛÝ[XØ\]Ý[OH\Ü^N^Ú\ÝYKXÛÛ[ÜXÙKX]ÙY[Ø[YÛZ][\Î^\Ý\ÛX\Ú[XÝÛNÈ]]Ý[OHÛ\Ú^NMÙÛ]ÙZYÚÌØÛÛÜÙNXÙÈÛ×Ù[[Ú_HÝ]_OÙ]]Ý[OHÛ\Ú^NLÛX\Ú[]ÜÜÈÜ[Ý[OHÛÛÜÛ×ØÛÛÜNÙÛ]ÙZYÚÌÈÛYXÞXÛ_OÜÜ[Ü[Ý[OHÛÛÜÍMMMÌÈ0­ÈÜÜ[ØÛÛY[ÙWØYÙJÛÛ_^Ü\X]ÛÝ_BÙ]Ù]]Ý[OH^X[YÛYÚÙÛ\Ú^NLØÛÛÜÍMMMÌÈÙ]Ü^\ÊX^Ü^\Ê_HXZÏÛHÛÝ[YÂÙ]Ù]]Ý[OHÛ\Ú^NLØÛÛÜÍMMMÌÛX\Ú[XÝÛNLÈYÜ[ÛÝÛÈÝ[OHÛÛÜÎNXXÈÝOÜÝÛÏ

H	Üð­ÉÜÂÝÛÈÝ[OHÛÛÜÎNXXÈÝÙOÜÝÛÏ
Ù
H	Üð­ÉÜÂÝÛÈÝ[OHÛÛÜÎNXXÈÝÙOÜÝÛÏ

Ù
BÙ]ÈXÚHY[ÜÈ\Ú[È\ÈÛÝ[XÚWÝYÈHËÙ]
XÚWÝY[ÜÈ×JBYXÚWÝYÎ[
ÏH	Ï]Ý[OHÛ\Ú^NLÙÛ]ÙZYÚÌØÛÛÜÍMMMÌÛ]\\ÜXÚ[Î\ÛX\Ú[XÝÛNÈ¼'äîHÓÕSQSÔÈTÒSÈTÈÓÕSÙ]ÂÜKÚ][H[[[Y\]JXÚWÝYÖÎJNÙ[ÈHÚ][KÙ]
[È
BÜ^\ÈHÚ][KÙ]
^\È
BÝ\HÚ][KÙ]
\BØ]]ÜHÚ][KÙ]
]]ÜBÙ\ØÈHÚ][KÙ]
\ØÈVÎBÜ][ÈHÚ][KÙ]
][È
BÚÝ\ÈHÚ][KÙ]
Ý\×ÛÛ
BØÛÛHÚ][KÙ]
ÛÛY[ÙH
BØÝ\HHÚ][KÙ]
ÛÛ[Ý\HBÚÛÚÜÈHÚ][KÙ]
ÛÚÜÈ×JB[×Ù]HÛÙ[ËÌLYRÈYÙ[ÈHL[ÙHÝÙ[ÊB^\×ØYÛÈH[
ÚÝ\ÈËÈ
BYÙWÜÝHÙ^\×ØYÛßYYÛÈY^\×ØYÛÈ[ÙHÚ[
ÚÝ\Ê_ZYÛÈØ]ÚØHÏHYHÛÝ\HÛ\ÜÏHØ]ÚXØ]Ú8¡¥ÏØOÈYÝ\[ÙHÛÚ×ÜÝHÏ]Ý[OHÛ\Ú^N\ØÛÛÜÍNYYÛX\Ú[]ÜÈÛÚÎÛÚÛÚÜÖÌ_OÙ]ÈYÚÛÚÜÈ[ÙHÝ\WÜÝHÏÜ[Û\ÜÏHYÈYËYÜ^HÝ[OHÛ\Ú^NÈÛØÝ\K\\
_OÜÜ[ÈYØÝ\H[ÙH[
ÏH]Û\ÜÏHXÚK]Y[È]Ý[OH\Ü^N^Ú\ÝYKXÛÛ[ÜXÙKX]ÙY[Ø[YÛZ][\ÎÙ[\È]Ü[Ý[OHÛ]ÙZYÚÌØÛÛÜÙ
LÙÛ\Ú^NL\ÈÛØ]]ÜOÜÜ[Ü[Ý[OHÛÛÜÍMMMÌÙÛ\Ú^NLÈ0­ÈÙ[×Ù]HÛÝÙ\È0­ÈØYÙWÜÝOÜÜ[ØÝ\WÜÝBÙ]]Ý[OHÛ]ÙZYÚÌØÛÛÜÜ^\×ØÛÛÜÜ^\Ê_NÙÛ\Ú^NLÈÙ]Ü^\ÊÜ^\Ê_OÙ]Ù]]Ý[OHÛ\Ú^NL\ØÛÛÜÎNXXÛX\Ú[]ÜÜÈÛÙ\ØßOÙ]ÚÛÚ×ÜÝB]Ý[OHÛ\Ú^N\ØÛÛÜÍMMMÌÛX\Ú[]ÜÈÛÜ][ÎY^][È0­ÈØÛÛY[ÙWØYÙJØÛÛ_OÙ]ÝØ]ÚØBÙ][ÙN[
ÏH	Ï]Ý[OHÛ\Ú^NL\ØÛÛÜÍMMMÌÈÈÛÝ[Y[ÜÈÝ[Y]8 %X\HÚYÛ[Ù]ÂYÛÝ[Û[Î[
ÏHÏHYHÜÛÝ[Û[ßHÛ\ÜÏHÛÝ[X¼'ã­H\ÙH\ÈÛÝ[ÛZÕÚÈ8¡¥ÏØOÂ[
ÏHÙ]]\[ÈKHSÔSÈSPRSKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKBYZ[Û[Ü[×Ù[XZ[
ÛÝ[ËÜX]ÜËYÜËÜÝY[ÜËYX\Ë]WÜÝY[[ÜKØ\ÊNÜÝÝ[YHH\ÝÜÜÝÝ[YJ
BÜHÛÝ[ÖÌHYÛÝ[È[ÙHßBÈÜÈYÚXÛÛY[ÙHÜÜ[]Y\ÂÜÈHÛÜY
YX\ËÙ^O[[XH^Ù]
ÛÛY[ÙH
JVÎ×BÜ×Ú[HÜKYXH[[[Y\]JÜÊN[×Ù[[ÚHHÈ¼'éaÈ¼'éb¼'ébHVÚWBÜ×Ú[
ÏH]Ý[OHXÚÙÜÝ[ÌLNØÜ\[YÜÛÛYÍNYYÜY[ÎLMÛX\Ú[XÝÛNØÜ\\Y]\ÎÈ]Ý[OHÛ\Ú^NLÙÛ]ÙZYÚÌØÛÛÜÍNYYÛX\Ú[XÝÛNÜÈÜ[×Ù[[Ú_HÚYXVÉÜ[\×_H0­ÈØÛÛY[ÙWØYÙJYXKÙ]
	ØÛÛY[ÙIË
J_OÙ]]Ý[OHÛ\Ú^NLÜØÛÛÜÙ
LÈÚYXVÉÚYXI×_OÙ]]Ý[OHÛ\Ú^NLØÛÛÜÍMMMÌÛX\Ú[]ÜÈÛÚÎÚYXVÉÚÛÚÉ×_HÙ]Ù]ÈÛÝ[ÈÙXÝ[ÛÛÝ[×Ú[HÜÈ[ÛÝ[ÖÎWNÛÝ[×Ú[
ÏHZ[ÜÛÝ[ØØ\
ËY[[ÜJBÈÜX]ÜÜÝYÚÜÝYÚÚ[HÜÈ[ÜX]ÜÖÎNY\Û[YKY\ØÛÛÜHÜX]ÜÝY\ËÙ]
[È
JBYÝY\Û[YNÛÛ[YB[ÈHËÙ]
[È
B[HHËÙ]
[HB[WÝ\HÎËÝÝÝËZÝÚËÛÛKÐÚ[_H[×Ù]HÙ[ËÌLYRÈY[ÈHL[ÙHÝ[ÊBX^Ü^\ÈHX^

È^\ÈHÜ[ÖÈY[ÜÈJKY][L
BX^Ü][ÈHX^

È][ÈHÜ[ÖÈY[ÜÈJKY][L
BY\Ù[[ÚHHÈRPÔÈ¼'å)HSQTÒSÈ¸¦¨HÓPS¼'äâTÒSÈ¼'ä`KÙ]
Y\Û[YKBÜÝYÚÚ[
ÏH]Ý[OHX\Ú[XÝÛNÜY[ËXÝÛNØÜ\XÝÛN\ÛÛYÌXÌÍNÈ]Ý[OH\Ü^N^Ú\ÝYKXÛÛ[ÜXÙKX]ÙY[Ø[YÛZ][\ÎÙ[\ÛX\Ú[XÝÛNÈ]HYHÚ[WÝ\HÝ[OHÛ]ÙZYÚÌÙÛ\Ú^NMØÛÛÜÙ
LÈÚ[_OØOÜ[Ý[OHÛ\Ú^NLØÛÛÜÝY\ØÛÛÜNÛX\Ú[[YÙÛ]ÙZYÚÌØXÚÙÜÝ[ÌLÌLÜY[Î
ÜØÜ\\Y]\ÎLØÜ\\ÛÛYÝY\ØÛÛÜLÌÈÝY\Ù[[Ú_HÝY\Û[Y_OÜÜ[Ù]]Ý[OHÛ\Ú^NL\ØÛÛÜÍMMMÌÈÙ[×Ù]HÛÝÙ\È0­ÈÛX^Ü][ÎY^][ÏÙ]Ù]Ü[ÖÈY[ÜÈVÎNHÙ]
^\È
BÛÛÜH^\×ØÛÛÜ
BY\H^\×ÛX[

BYÈHÏÜ[Û\ÜÏHYÈYË^ÝY\ÝÙ\
K\XÙJ_HÝ[OHÛ\Ú^N\ÈÝY\OÜÜ[	ÈYY\[ÙHØ]ÚHÏHYHÝÈ\_HÛ\ÜÏHØ]ÚXØ]ÚÛZÕÚÈ8¡¥ÏØOÈYÙ]
\H[ÙHX\ÛÛHÏ]Ý[OHÛ\Ú^NLØÛÛÜÍNYYÛX\Ú[]ÜÜÙÛ]ÙZYÚÈÝÈ\[ÜX\ÛÛ_OÙ]ÈYÙ]
\[ÜX\ÛÛH[ÙHÛÝ[ÛHÏ]Ý[OHÛ\Ú^NLØÛÛÜÍMMMÌÈÛÝ[ÝÛÈÝ[OHÛÛÜÎNXXÈÝÈÛÝ[_OÜÝÛÏÙ]ÈYÙ]
ÛÝ[H[ÙH[\ØHÏÜ[Û\ÜÏHYÈYËYÜ^HÝ[OHÛ\Ú^N\ÈÝÙ]
ÛÛ[Ý\HK\\
_OÜÜ[	ÈYÙ]
ÛÛ[Ý\HH[ÙH^\×ÛHÏÜ[Û\ÜÏHYÈYË[Ü[ÙHÝ[OHÛ\Ú^N\ÈÝÙ]
^\×ØYÛÈ
_YYÛÏÜÜ[	ÈYÙ]
^\×ØYÛÈH\ÈÝÛH[ÙHÛÛØHÛÛY[ÙWØYÙJÙ]
ÛÛY[ÙH
JBÛÚÜÈHÙ]
ÛÚÜÈ×JBÛÚ×ÜÝHÏ]Ý[OHÛ\Ú^NLØÛÛÜÙLØÎÛX\Ú[]ÜÜÈÛÚÎÚÛÚÜÖÌ_OÙ]ÈYÛÚÜÈ[ÙH[[Ú[H]Ý\HHÙ]
ÜX]Ý\HBÛÚ×Ø[[\Ú\ÏHÙ]
ÛÚ×Ø[[\Ú\ÈBÛÜWÝ\ÈHÙ]
ÛÜWÝ\ÈBY]Ý\HÜÛÚ×Ø[[\Ú\ÈÜÛÜWÝ\Î[[Ú[H]Û\ÜÏH[[XÞ]Ý[OHÛ\Ú^N\ÙÛ]ÙZYÚÌØÛÛÜÍMMMÌÛ]\\ÜXÚ[Î\ÛX\Ú[XÝÛNÈÔPUÔSSÙ]ÙÏ]Ý[OHÛ\Ú^NLØÛÛÜÙLØÎÙÛ]ÙZYÚÌÛX\Ú[XÝÛNÈÜX]Ù]Ý\_OÙ]ÈY]Ý\H[ÙHBÙÏ]Ý[OHÛ\Ú^NLØÛÛÜÎNXXÛX\Ú[XÝÛNÛ[KZZYÚKNÈÚÛÚ×Ø[[\Ú\ßOÙ]ÈYÛÚ×Ø[[\Ú\È[ÙHBÙÏ]Ý[OHÛ\Ú^NLØÛÛÜÍYNÙÛ]ÙZYÚÛ[KZZYÚKNÈÛÜH\ÎØÛÜWÝ\ßOÙ]ÈYÛÜWÝ\È[ÙHBÙ]ÜÝYÚÚ[
ÏH]Ý[OHXÚÙÜÝ[ÌLNØÜ\\Y]\ÎÜY[ÎLÛX\Ú[XÝÛNÈ]Ý[OHÛ\Ú^NL\ØÛÛÜÎNXXÛX\Ú[XÝÛNÛ[KZZYÚKÈÙ^\×Û^Ü[\Ø^ÝYß^ÝÈ\ØÈHÜÈØ\[ÛHOÙ]]Ý[OHÛ\Ú^NLÜÙÛ]ÙZYÚÌØÛÛÜÝÛÛÜNÈÙ]Ü^\Ê
_HY]ÜÈ	Üð­ÉÜÈØÛÛØOÙ]]Ý[OHÛ\Ú^NL\ØÛÛÜÍMMMÌÈÝÙ]
^\×ØYÛÈ
JHYÙ]
^\×ØYÛÈH[ÙH
NHZÙ\ÏÙ]ÚÛÚ×ÜÝBÜÛÝ[ÛBÜX\ÛÛBÚ[[Ú[BÝØ]ÚBÙ]ÜÝYÚÚ[
ÏHÙ]È\ÚYÜÂÚ[HÜYË]H[YÜÖÎNY]ÜÈH]VÈY]ÜÈBY]Ü×Ù]HÝY]ÜËÌWÌÌÌYPYY]ÜÈHYNH[ÙHÝY]ÜËÌWÌÌSHYY]ÜÈHYM[ÙHÝY]ÜÎHÚ[
ÏHÏHYHÎËÝÝÝËZÝÚËÛÛKÝYËÞÝYßHÝ[OHXÚÙÜÝ[ÌLLXLNØÛÛÜÍNYYÜY[Î\LØÜ\\Y]\ÎÛX\Ú[ÜÙ\Ü^N[[KXØÚÎÙÛ\Ú^NLÙÛ]ÙZYÚØÜ\\ÛÛYÌYLØMYÈÞÝYßHÜ[Ý[OHÛÛÜÌMXNYÙÛ\Ú^NLÈÝY]Ü×Ù]OÜÜ[ØOÂÈÜ\ÚYÈY[ÜÂÝY[Ü×Ú[HÜ[ÜÝY[ÜÖÎNØ]ÚHÏHYHÝÈ\_HÛ\ÜÏHØ]ÚXØ]Ú8¡¥ÏØOÈYÙ]
\H[ÙH[×Ù]HÝÙ]
	Ù[ÉË
KÌLRÈYÙ]
[È
HHL[ÙHÝÙ]
[È
JBÛÝ[ÛHÏ]Ý[OHÛ\Ú^NLØÛÛÜÍMMMÌÈÛÝ[ÝÙ]
ÛÝ[_OÙ]ÈYÙ]
ÛÝ[H[ÙHHÙ]
^\È
BY×Ý[HÙ]
YÈB]]ÜHÙ]
]]ÜB\ØÈHÙ]
\ØÈVÎLBÝY[Ü×Ú[
ÏH]Ý[OHXÚÙÜÝ[ÌLNØÜ\\Y]\ÎÜY[ÎLÛX\Ú[XÝÛNÈ]Ý[OHÛ\Ú^NL\ØÛÛÜÍMMMÌÛX\Ú[XÝÛNÈÞÝY×Ý[H	Üð­ÉÜÈHYHÎËÝÝÝËZÝÚËÛÛKÐØ]]ÜHÝ[OHÛÛÜÍNYYÈØ]]ÜOØO
Ù[×Ù]HÛÝÙ\ÊOÙ]]Ý[OHÛ\Ú^NLØÛÛÜØÍÎÛX\Ú[XÝÛNÛ[KZZYÚKÈÙ\ØßOÙ]]Ý[OHÛ\Ú^NLÙÛ]ÙZYÚÌØÛÛÜÜ^\×ØÛÛÜ
_NÈÙ]Ü^\Ê
_HY]ÜÏÙ]ÜÛÝ[ÛBÝØ]ÚBÙ]ÈY[ÈYX\ÂYX\×Ú[HÜYXH[YX\ÎØÛÛÜHÙ
ÌMÌHYYXVÈ[Ü]HHOHTÑS[ÙHÙYYXVÈ[Ü]HHOHÕ[ÙHÍNYY[Ü×Û[ÈHÈHYHÚYXVÈ[Ü×Ý\_HÛ\ÜÏHØ]ÚXØ]Ú[ÜÈ8¡¥ÏØOÈYYXKÙ]
[Ü×Ý\H[ÙHÛÝ[Û[×Ú[HÏHYHÚYXKÙ]
ÛÝ[Û[È_HÛ\ÜÏHÛÝ[XÝ[OHÛ\Ú^N\ÜY[ÎÜÈ¼'ã­HÚYXVÈÛÝ[_OØOÈYYXKÙ]
ÛÝ[Û[ÈH[ÙHÏÝÛÈÝ[OHÛÛÜÎNXXÈÚYXVÈÛÝ[_OÜÝÛÏÂYX\×Ú[
ÏH]Ý[OHÜ\[YÜÛÛYÜØÛÛÜNÜY[ÎLMÛX\Ú[XÝÛNLØXÚÙÜÝ[ÌLNØÜ\\Y]\ÎÈ]Ý[OHÛ\Ú^NLÙÛ]ÙZYÚÌØÛÛÜÜØÛÛÜNÛX\Ú[XÝÛNÛ]\\ÜXÚ[Î\ÈÚYXVÈ[Ü]H_H0­ÈÚYXVÈ[\_^Ú[Ü×Û[ßH0­ÈØÛÛY[ÙWØYÙJYXKÙ]
ÛÛY[ÙH
J_OÙ]]Ý[OHÛ\Ú^NLÜØÛÛÜÙ
LÛX\Ú[XÝÛNÛ[KZZYÚKNÈÚYXVÈYXH_OÙ]]Ý[OHÛ\Ú^NLØÛÛÜÍMMMÌÈÛÝ[ÜÛÝ[Û[×Ú[H	Üð­ÉÜÈÚYXVÈ\ÚYÜÈ_OÙ]Ù]ÈÛÛ[Ø\ÂØ\×Ú[HÜÈ[Ø\ÎØ\×Ú[
ÏH]Û\ÜÏHØ\XØ\]Ý[OHÛ\Ú^NLÙÛ]ÙZYÚÌØÛÛÜÙLØÎÛX\Ú[XÝÛNÈ¼'å#HÓÓSÐT0­ÈÙÖÉÜ[\×_OÙ]]Ý[OHÛ\Ú^NL\ØÛÛÜÍMMMÌÛX\Ú[XÝÛNÜÈ[\Ù\Y[ÛNÝÛÈÝ[OHÛÛÜÎNXXÈÙÖÉÙØ\	×_OÜÝÛÏÙ]]Ý[OHÛ\Ú^NLØÛÛÜØÍÎÈÙÖÉÚYXI×_OÙ]Ù]ÈÛÚÈ]X\ÙH
Ü\ÜZ[ÈÛÚÜÈÛHY[[ÜJBY[WÚÛÚÜÈHÛÜY
Y[[ÜKÙ]
ÛÚÜÈßJK][\Ê
KÙ^O[[XH^ÌWKÙ]
X^Ü^\È
JVÎWBÛÚÜ×Ú[HÜÛÚË]H[Y[WÚÛÚÜÎÛÚÜ×Ú[
ÏHÏ]Ý[OHXÚÙÜÝ[ÌLNØÜ\\Y]\ÎÜY[ÎLÛX\Ú[XÝÛNÙÛ\Ú^NLÈÜ[Ý[OHÛÛÜÍYNÈ¸¦nÏÜÜ[ÝÛÈÝ[OHÛÛÜÙ
LÈÚÛÚßHÜÝÛÏÜ[Ý[OHÛÛÜÍMMMÌÈ¸ %ÙY[Ú]KÙ]
ÛÝ[J_^0­ÈXZÈÙ]Ü^\Ê]KÙ]
X^Ü^\È
J_OÜÜ[Ù]ÂÜÜÛÝ[Û[YHHÜÙ]
]HKHBÜÜÛÝ[Û[×Ú[HÏHYHÝÜÈ[È_HÝ[OHÛÛÜÍYNÝ^YXÛÜ][Û[\[NÈÝÜÜÛÝ[Û[Y_OØOÈYÜÙ]
[ÈH[ÙHÈÝÜÜÛÝ[Û[Y_HÂ[HQÐÕTH[[XYY]HÚ\Ù]H]NY]H[YOHY]ÜÜÛÛ[HÚYY]XÙK]ÚY[]X[\ØØ[OLHÝ[OÙ[XZ[ÜÝ[J
_OÜÝ[OÚXYÙO]Ý[OHXÚÙÜÝ[[X\YÜYY[
LÍYYËÌLLMËÌLLXLJNØÜ\\Y]\ÎMÜY[ÎÛX\Ú[XÝÛNMÝ^X[YÛÙ[\ØÜ\\ÛÛYÌXÌM
NÈ]Ý[OHÛ\Ú^NÍÛX\Ú[XÝÛNÈ¼'ãâÙ]HÝ[OHÛ\Ú^NÙÛ]ÙZYÚLØÛÛÜÙNXÙÛX\Ú[XÝÛNÈÛÛÙ[Ü[ËÜÚXOÚOÝ[OHÛÛÜÍMMMÌÙÛ\Ú^NLÜÈÛÝ[[YY	ÜÉ[ÉÜÈÙ]WÜÝOÜ]Ý[OHX\Ú[]ÜLØXÚÙÜÝ[ÌLNØÜ\\Y]\ÎÜY[ÎLÙÛ\Ú^NLÜØÛÛÜÍNYYÙÛ]ÙZYÚÈ\Ý[YHÈÜÝÙ^NÜÜÝÝ[Y_BÙ]Ù]]Û\ÜÏHØ\¼'ã«ÈÜÈYÚPÛÛY[ÙHÜÜ[]Y\ÏÚÝÜ×Ú[BÙ]]Ý[OHXÚÙÜÝ[ÌLNØÜ\\ÛÛYÌYLØMYØÜ\\Y]\ÎLÜY[ÎNÛX\Ú[XÝÛNMÈÝ[OHÛÛÜÍNYYÈ[Ý\[ÝHÙ^OÚÝ[OHÛ\Ú^NMÛX\Ú[XÝÛNÛ[KZZYÚKÈÝÛÈÝ[OHÛÛÜÙNXÙÈÝ\ÝÛÝ[YÚÝÎÜÝÛÏÝÜÜÛÝ[Û[×Ú[OÜÝ[OHÛ\Ú^NLÜØÛÛÜÎNXXÛ[KZZYÚKÈÝÛÈÝ[OHÛÛÜÙ
LÈÜÝYXNÜÝÛÏ[HH\ÜÈÛÝ\YÙH[[YHHÜXÚYXÈÔÜØÚÛÛ[ÝIÜH\\[ÈÜ[HØ\[ÛÜÙ]]Û\ÜÏHØ\¼'ã­HXÚHÛÝ[ÈÛÚ[È\[

JÈÛÝ[Y[ÜËÊÈ^\ÊOÚ]Ý[OH\Ü^N^ÙØ\LÙ^]Ü\Ü\ÛX\Ú[XÝÛNLÙÛ\Ú^NLØÛÛÜÍMMMÌÈÜ[Ü[Ý[OHÛÛÜÙ
ÌMÌNÙÛ]ÙZYÚÌÈQQÐOÜÜ[H
LÊÏÜÜ[Ü[Ü[Ý[OHÛÛÜÙÙÛ]ÙZYÚÌÈTSÜÜ[HLÊÏÜÜ[Ü[Ü[Ý[OHÛÛÜÍYNÙÛ]ÙZYÚÌÈÓÓÑÓOÜÜ[H
LËLLÏÜÜ[Ü[Ü[Ý[OHÛÛÜÍNYYÙÛ]ÙZYÚÌÈÓHTÑOÜÜ[HËMLÏÜÜ[Ù]ÜÛÝ[×Ú[YÛÝ[×Ú[[ÙH	ÏÝ[OHÛÛÜÍMMMÌÈÈ]X[YZ[ÈÛÝ[ÈY]8 %ÚXÚÈ^[ÜßBÙ]]Û\ÜÏHØ\¼'äâÜX]ÜÜÝYÚ8¦¨H\Ý
È^\ÈÛH
8¢i
LÈÛÝÙ\ÊOÚ]Ý[OHÛ\Ú^NL\ØÛÛÜÍMMMÌÛX\Ú[XÝÛNLÈ¼'å)HRPÔÈ
	ÍRÊH0­È8¦¨HSQTÒSÈ

KLMRÊH0­È<'äâÓPS
MKLÌÊH0­È<'ä`TÒSÈ
ÌMLÊH0­È[[Y\XØ[ÛÝ[8§!OÙ]ÜÜÝYÚÚ[YÜÝYÚÚ[[ÙH	ÏÝ[OHÛÛÜÍMMMÌÈÈ]X[YZ[ÈÜX]ÜÈ\È[ÜßBÙ]]Û\ÜÏHØ\¼'ä¨HY[ÈYX\ÈÜÙ^OÚÚYX\×Ú[BÙ]]Û\ÜÏHØ\¼'å#HÛÛ[Ø\È
[\Ù\Y[Û\ÊOÚÙØ\×Ú[YØ\×Ú[[ÙH	ÏÝ[OHÛÛÜÍMMMÌÈÈXZÜØ\È]XÝY\È[ÜßBÙ]]Û\ÜÏHØ\¸¦nÈÛÚÈ]X\ÙH
XÝ\[ÈÚ[[ÈÛÚÜÊOÚÚÛÚÜ×Ú[YÛÚÜ×Ú[[ÙH	ÏÝ[OHÛÛÜÍMMMÌÈZ[[ÈÛÚÈ]X\ÙH8 %ÚXÚÈXÚÈY\H]È[ËÜßBÙ]]Û\ÜÏHØ\¼'ãíûî#È[[È\ÚYÜÏÚÚÚ[BÊ	ÏÛ\ÜÏH]Y\]Ý[OHÛ\Ú^NLÙÛ]ÙZYÚÌØÛÛÜÙ
LÛX\Ú[LLÈÜY[ÜÈ[\\ÙH\ÚYÜÏÙ]È
ÈÝY[Ü×Ú[
HYÝY[Ü×Ú[[ÙHBÙ]Ý[OH^X[YÛÙ[\ÙÛ\Ú^NLØÛÛÜÌLÌ
ÜY[ÎMÈÛÝ[[YÙ[	ÜÉ[ÉÜÈ\X[ÜÚ[Y\ÌÛXZ[ÛÛOÜØÙOÚ[]\[ÈKHQTÓÓSPRSKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKBYZ[ØY\ÛÛÙ[XZ[
ÛÝ[ËÜX]ÜËÜÝY[ÜËYX\Ë]WÜÝY[[ÜJNÜÝÝ[YHH\ÝÜÜÝÝ[YJ
B\Ù[HÚHÜH[YX\ÈYVÈ[Ü]HH[
TÑSÕWB]×Ý\[HÝÜÈ[ÜX]ÜÈÜ[ÖÈY[ÜÈHYÙ]
\[WB\[Ú[HÜ[]×Ý\[ÎWNHÙ]
^\È
BØ]ÚHÏHYHÝÈ\_HÛ\ÜÏHØ]ÚXØ]ÚÛZÕÚÈ8¡¥ÏØOÈYÙ]
\H[ÙHX\ÛÛHÏ]Ý[OHÛ\Ú^NLØÛÛÜÍNYYÛX\Ú[]ÜÜÈÝÈ\[ÜX\ÛÛ_OÙ]ÈYÙ]
\[ÜX\ÛÛH[ÙHÛÜWÝHÏ]Ý[OHÛ\Ú^NLØÛÛÜÍYNÛX\Ú[]ÜÜÈÛÜH\ÎÝÈÛÜWÝ\È_OÙ]ÈYÙ]
ÛÜWÝ\ÈH[ÙH\[Ú[
ÏH]Ý[OHY[ÎLØÜ\XÝÛN\ÛÛYÌXÌÍNÈ]Ý[OHÛ\Ú^NLÜÙÛ]ÙZYÚØÛÛÜÜ^\×ØÛÛÜ
_NÈÙ]Ü^\Ê
_HY]ÜÏÙ]]Ý[OHÛ\Ú^NLØÛÛÜÎNXXÛX\Ú[]ÜÈÝÈ\ØÈVÎÌ_OÙ]ÜX\ÛÛ^ØÛÜWÝ^ÝØ]ÚBÙ]YÝ\[Ú[\[Ú[H	ÏÝ[OHÛ\Ú^NLÜØÛÛÜÌÌÌÎÈÈXZÜ\[ÜZÙ\ÈÚ[ÙH\È[Ü[ËÜÂYX\×Ú[HÜYXH[
\Ù[ÜYX\ÖÎ×JNØÛÛÜHÙ
ÌMÌHYYXVÈ[Ü]HHOHTÑS[ÙHÙ[Ü×Û[ÈHÈHYHÚYXVÈ[Ü×Ý\_HÛ\ÜÏHØ]ÚXØ]Ú[ÜÈ8¡¥ÏØOÈYYXKÙ]
[Ü×Ý\H[ÙHYX\×Ú[
ÏH]Ý[OHÜ\[YÜÛÛYÜØÛÛÜNÜY[ÎLMÛX\Ú[XÝÛNLØXÚÙÜÝ[ÌLNØÜ\\Y]\ÎÈ]Ý[OHÛ\Ú^NLÙÛ]ÙZYÚÌØÛÛÜÜØÛÛÜNÛX\Ú[XÝÛNÈÚYXVÈ[Ü]H_H0­ÈÚYXVÈ[\_^Ú[Ü×Û[ßOÙ]]Ý[OHÛ\Ú^NLÜØÛÛÜÙ
LÛX\Ú[XÝÛNÈÚYXVÈYXH_OÙ]]Ý[OHÛ\Ú^NLØÛÛÜÍMMMÌÈÛÝ[ÝÛÈÝ[OHÛÛÜÎNXXÈÚYXVÈÛÝ[_OÜÝÛÏÙ]Ù][HQÐÕTH[[XYY]HÚ\Ù]H]NY]H[YOHY]ÜÜÛÛ[HÚYY]XÙK]ÚY[]X[\ØØ[OLHÝ[OÙ[XZ[ÜÝ[J
_OÜÝ[OÚXYÙO]Ý[OHXÚÙÜÝ[[X\YÜYY[
LÍYYËÌLLMËÌLLXLJNØÜ\\Y]\ÎMÜY[ÎÛX\Ú[XÝÛNMÝ^X[YÛÙ[\ØÜ\\ÛÛYÌXÌM
NÈ]Ý[OHÛ\Ú^NÛX\Ú[XÝÛNÈY\ÛÛ\]OÙ]HÝ[OHÛ\Ú^NÙÛ]ÙZYÚLØÛÛÜÙNXÙÈ[ÚXÚÏÚOÝ[OHÛÛÜÍMMMÌÙÛ\Ú^NLÈH	ÜÉ[ÉÜÈÙ]WÜÝOÜ]Ý[OHX\Ú[]ÜLØXÚÙÜÝ[ÌLNØÜ\\Y]\ÎÜY[ÎÙÛ\Ú^NLØÛÛÜÍNYYÈÜÝÚ[ÝÈÛYÚÜÜÝÝ[Y_OÙ]Ù]]Û\ÜÏHØ\\[YÚÝÈKHÜÝYÜH]XZÜÏÚÝ\[Ú[BÙ]]Û\ÜÏHØ\ÜYX\È\ÈY\ÛÛÚÚYX\×Ú[BÙ]Ý[OH^X[YÛÙ[\ÙÛ\Ú^NLØÛÛÜÌLÌ
ÜY[ÎMÈÛÝ[[YÙ[	ÜÉ[ÉÜÈHYY	ÜÉ[ÉÜÈ\X[ÜÚ[Y\ÌÛXZ[ÛÛOÜØÙOÚ[]\[ÈKHQÒSPRSKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKBYZ[ÛYÚÙ[XZ[
ÛÝ[ËÜX]ÜËYX\Ë]WÜÝY[[ÜJN\[ÝÙ^HHÝÜÈ[ÜX]ÜÈÜ[ÖÈY[ÜÈHYÙ]
\[WBÜÜÛÝ[HÛÝ[ÖÌHYÛÝ[È[ÙHÈ]HKH[ÈBXØ\Ú[HÜ[\[ÝÙ^VÎWNHÙ]
^\È
BØ]ÚHÏHYHÝÈ\_HÛ\ÜÏHØ]ÚXØ]Ú8¡¥ÏØOÈYÙ]
\H[ÙHÛÜWÝHÏ]Ý[OHÛ\Ú^NLØÛÛÜÍYNÛX\Ú[]ÜÜÈÛÜH\ÎÝÈÛÜWÝ\È_OÙ]ÈYÙ]
ÛÜWÝ\ÈH[ÙHXØ\Ú[
ÏH]Ý[OHY[ÎLØÜ\XÝÛN\ÛÛYÌXÌÍNÈ]Ý[OHÛ\Ú^NLÜÙÛ]ÙZYÚØÛÛÜÜ^\×ØÛÛÜ
_NÈÙ]Ü^\Ê
_HY]ÜÏÙ]]Ý[OHÛ\Ú^NLØÛÛÜÎNXXÛX\Ú[]ÜÈÝÈ\ØÈVÎÌ_OÙ]ØÛÜWÝ^ÝØ]ÚBÙ]YÝXØ\Ú[XØ\Ú[H	ÏÝ[OHÛ\Ú^NLÜØÛÛÜÌÌÌÎÈÈXZÜ\[ÛÛ[Ù^H[[Ý\XÚKÜÂÛ[ÜÝ×Ú[HÜYXH[YX\ÖÎNÛ[ÜÝ×Ú[
ÏH]Ý[OHÜ\[YÜÛÛYÍNYYÜY[ÎLMÛX\Ú[XÝÛNLØXÚÙÜÝ[ÌLNØÜ\\Y]\ÎÈ]Ý[OHÛ\Ú^NLÙÛ]ÙZYÚÌØÛÛÜÍNYYÛX\Ú[XÝÛNÛ]\\ÜXÚ[Î\ÈÚYXVÈ[\_OÙ]]Ý[OHÛ\Ú^NLÜØÛÛÜÙ
LÛX\Ú[XÝÛNÈÚYXVÈYXH_OÙ]]Ý[OHÛ\Ú^NLØÛÛÜÍMMMÌÈÛÝ[ÝÛÈÝ[OHÛÛÜÎNXXÈÚYXVÈÛÝ[_OÜÝÛÏ	ÜÉ[ÉÜÈÚYXVÈ\ÚYÜÈ_OÙ]Ù]×Û[YHHÜÜÛÝ[Ù]
]HKHBÜÜÛÝ[Û[ÈHÏHYHÝÜÜÛÝ[È[È_HÝ[OHÛÛÜÍNYYÈÝ×Û[Y_OØOÈYÜÜÛÝ[Ù]
[ÈH[ÙH×Û[YBÈY[[ÜHÝ[[X\B[ÈHY[[ÜKÙ]
[È
BÜÚÛÚÜÈHÛÜY
Y[[ÜKÙ]
ÛÚÜÈßJK][\Ê
KÙ^O[[XH^ÌWKÙ]
ÛÝ[
JVÎ×BY[WÚ[HYÜÚÛÚÜÎY[WÚ[H	Ï]Ý[OHX\Ú[]ÜÙÛ\Ú^NL\ØÛÛÜÍMMMÌÈÜÛÚÜÈ[Y[[ÜN	È
È0­ÈÚ[ÙÏÝÛÈÝ[OHÛÛÜÎNXXÈÚHÜÝÛÏÈÜÈ[ÜÚÛÚÜ×JH
ÈÙ][HQÐÕTH[[XYY]HÚ\Ù]H]NY]H[YOHY]ÜÜÛÛ[HÚYY]XÙK]ÚY[]X[\ØØ[OLHÝ[OÙ[XZ[ÜÝ[J
_OÜÝ[OÚXYÙO]Ý[OHXÚÙÜÝ[[X\YÜYY[
LÍYYËÌLÌMÌL
NØÜ\\Y]\ÎMÜY[ÎÛX\Ú[XÝÛNMÝ^X[YÛÙ[\ØÜ\\ÛÛYÌXÌÍNÈ]Ý[OHÛ\Ú^NÛX\Ú[XÝÛNÈYÚYYÙ]HÝ[OHÛ\Ú^NÙÛ]ÙZYÚLØÛÛÜÙNXÙÈÙ^H[]Y]ÏÚOÝ[OHÛÛÜÍMMMÌÙÛ\Ú^NLÈTH	ÜÉ[ÉÜÈÙ]WÜÝOÜ]Ý[OHÛ\Ú^NL\ØÛÛÜÍMMMÌÛX\Ú[]ÜÈ[ÞÜ[ßH0­ÈÛË]\HY[[ÜHXÝ]^ÛY[WÚ[OÙ]Ù]]Û\ÜÏHØ\Ú]Ù[\[[[Ý\XÚHÙ^OÚÜXØ\Ú[BÙ]]Û\ÜÏHØ\Û[ÜÝÉÜÈÛÛ[[ÚÝÛ[ÜÝ×Ú[BÙ]]Ý[OHXÚÙÜÝ[ÌLNØÜ\\ÛÛYÌYLØMYØÜ\\Y]\ÎLÜY[ÎMÛX\Ú[XÝÛNMÈÝ[OHÛÛÜÍNYYÈ\ÙH\ÈÛÝ[Û[ÜÝÏÚÝ[OHÛ\Ú^NMÛ[KZZYÚKÈÝÜÜÛÝ[Û[ßHKHÜÝ\Ý[È[H[Ü[ÈÜX^XXÚÜÙ]Ý[OH^X[YÛÙ[\ÙÛ\Ú^NLØÛÛÜÌLÌ
ÜY[ÎMÈÛÝ[[YÙ[	ÜÉ[ÉÜÈTHYY	ÜÉ[ÉÜÈ\X[ÜÚ[Y\ÌÛXZ[ÛÛOÜØÙOÚ[]\[ÈKHSPRSÑSTKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKBYÙ[Ù[XZ[
ÝXXÝ[ØÙJNYÝSPRSÔTÔÕÓÔ[
ÕÐTHÈSPRSÔTÔÕÓÔKHÚÚ\[ÈÙ[ÝXXÝÜÝXXÝHB]\N\ÙÈHRSQS][\\
[\]]HB\ÙÖÈÝXXÝHHÝXXÝ\ÙÖÈÛHHHSPRSÑÓB\ÙÖÈÈHHSPRSÕÂ\ÙË]XÚ
RSQU^
[ØÙK[]NJBÚ]Û]XÓUÔÔÓ
Û]ÛXZ[ÛÛH

JH\ÈÎËÙÚ[SPRSÑÓKSPRSÔTÔÕÓÔ
BËÙ[XZ[
SPRSÑÓKSPRSÕË\ÙË\×ÜÝ[Ê
JB[
ÓÒ×H[XZ[Ù[ÜÝXXÝHB^Ù\^Ù\[Û\ÈN[
ÑTÔH[XZ[Z[YÙ_HBÈKHÔUHUKÓÓKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKBYÜ]WÙ]WÚÛÛÛÝ[ËÜX]ÜËYÜËÜÝY[ÜËYX\ÊNÝÈH]][YK]ÛÝÊ
K\ÛÙÜX]

H
ÈÚ^Ú×ØYÛÈH[YK[YJ
HH

ÍXZÛÝ]ÈH×BÜ[ÜÝY[ÜÎÝHÙ]
ÜX]U[YH
B^\ÈHÙ]
^PÛÝ[
HÜÙ]
Ý]ÈßJKÙ]
^PÛÝ[
BYÝÚ^Ú×ØYÛÈ[^\ÈH
LXZÛÝ]Ë\[
Â[HÙ]
]]ÜY]HßJKÙ]
[YHK^\È^\Ë\ØÈÙ]
^Ù]
\ØÈJVÎLK\Ù]
ÙXY[Õ\KÛÝ[Ù]
]\ÚXÓY]HßJKÙ]
]\ÚXÓ[YHKJB]HHÂ\Ý\]YÝËYY\HQQÕTKÛÝ[ÈÂÈ]HËÙ]
]HK]]ÜËÙ]
]]ÜKYXÞXÛHËÙ]
YXÞXÛHKÛÛY[ÙHËÙ]
ÛÛY[ÙH
K[ÈËÙ]
[ÈKX^^\ÈËÙ]
X^Ü^\È
KXÚUY[ÐÛÝ[ËÙ]
XÚWÝY[×ØÛÝ[
KXÚUY[ÜÈËÙ]
XÚWÝY[ÜÈ×JVÎW_BÜÈ[ÛÝ[ÖÎBKÜX]ÜÈÂÈ[HËÙ]
[HKÚ^HËÙ]
Ú^HK[ÈËÙ]
[È
KÜY[ÈÖÈY[ÜÈVÌVÈ\HYËÙ]
Y[ÜÈH[ÙHÜ\ØÈÖÈY[ÜÈVÌVÈ\ØÈHYËÙ]
Y[ÜÈH[ÙHÜ^\ÈÖÈY[ÜÈVÌVÈ^\ÈHYËÙ]
Y[ÜÈH[ÙHÜÛÛY[ÙHÖÈY[ÜÈVÌVÈÛÛY[ÙHHYËÙ]
Y[ÜÈH[ÙHBÜÈ[ÜX]ÜÖÎMWBK\ÚYÜÈYÜÖÎMWKÜY[ÜÈÂÈ[HÙ]
]]ÜY]HßJKÙ]
[YHK[ÈÙ]
]]ÜY]HßJKÙ]
[È
K^\ÈÙ]
^PÛÝ[
K\ØÈÙ]
^Ù]
\ØÈJVÎLKÛÝ[Ù]
]\ÚXÓY]HßJKÙ]
]\ÚXÓ[YHK\Ù]
ÙXY[Õ\KÜX]U[YHÙ]
ÜX]U[YH
_BÜ[ÜÝY[ÜÖÎBKXZÛÝ]ÈXZÛÝ]ËYX\ÈYX\ÖÎWKBÚ]Ü[]KÛÛÈH\ÈÛÛ[\
]K[[LB[
ÓÒ×H]KÛÛÜ][KHÛ[ÛÝ[Ê_HÛÝ[ËÛ[ÜX]ÜÊ_HÜX]ÜËÛ[XZÛÝ]Ê_HXZÛÝ]ÈBÈKHPRSKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKBYXZ[
N]WÜÝH]][YKÝÊ
KÝ[YJPK	P	KY	VHBYYHQQÕTKÝÙ\
B[
ÉÏIÊLHB[
ÛÝ[[YÙ[KHØYY\\
_HSB[
Ù]WÜÝHB[
ÉÏIÊLWBY[[ÜHHØYÛY[[ÜJ
BYYY[
Y\ÛÛYÚH[ÜË]^\ÝÊ]KÛÛN[
]\Ú[ÈØXÚY]KÛÛ
È]È\YHØ[YYY
KBÚ]Ü[]KÛÛH\ÈØXÚYHÛÛØY
BÛÝ[ÈHØXÚYÙ]
ÛÝ[È×JBÜX]ÜÈHØXÚYÙ]
ÜX]ÜÈ×JBYÜÈHØXÚYÙ]
\ÚYÜÈ×JBÜÝY[ÜÈHØXÚYÙ]
ÜY[ÜÈ×JBYX\ÈHØXÚYÙ]
YX\È×JBØ\ÈH×B[ÙN]ÈH]ÚØ[Ü]Ê
BÛÝ[ÈH]ÚÝ[[×ÜÛÝ[Ê]ÊBÜX]ÜÈH]ÚØÜX]ÜÜÜJ]ÊBYÜËÜÝY[ÜÈH]ÚÚ\ÚYÜÊ]ÊBYÝÛÝ[Î[
ÑSPÒ×H\Ú[ÈÝ\]YÛÝ[ÈBÛÝ[ÈHSPÒ×ÔÓÕSÂYÝÜX]ÜÎ[
ÑSPÒ×H\Ú[ÈÝ\]YÜX]ÜÈBÜX]ÜÈHSPÒ×ÐÔPUÔÂYÝYÜÎ[
ÑSPÒ×H\Ú[ÈÝ\]Y\ÚYÈ]HBYÜÈHSPÒ×ÕQÔÂYX\ÈHÙ[\]WÝY[×ÚYX\ÊÛÝ[ËÜX]ÜËÜÝY[ÜÊBØ\ÈH]XÝØÛÛ[ÙØ\ÊÜX]ÜËÜÝY[ÜÊBY[[ÜHH\]WÛY[[ÜJY[[ÜKÛÝ[ËÜX]ÜËÜÝY[ÜÊBØ]WÛY[[ÜJY[[ÜJB[
ÛÝ[ÎÛ[ÛÝ[Ê_HÜX]ÜÎÛ[ÜX]ÜÊ_HYÜÎÛ[YÜÊ_HÜY[ÜÎÛ[ÜÝY[ÜÊ_WBÜ]WÙ]WÚÛÛÛÝ[ËÜX]ÜËYÜËÜÝY[ÜËYX\ÊBØ\ÈHØ\ÈY	ÙØ\ÉÈ[\
H[ÙH]XÝØÛÛ[ÙØ\ÊÜX]ÜËÜÝY[ÜÊBYYY[
[Ü[ÈY\ÛÛYÚNYYYOH[Ü[È[HZ[Û[Ü[×Ù[XZ[
ÛÝ[ËÜX]ÜËYÜËÜÝY[ÜËYX\Ë]WÜÝY[[ÜKØ\ÊBÝXXÝH¼'ãâÛÝ[YYKHÙ]WÜÝH[YYYOHY\ÛÛ[HZ[ØY\ÛÛÙ[XZ[
ÛÝ[ËÜX]ÜËÜÝY[ÜËYX\Ë]WÜÝY[[ÜJBÝXXÝHY\ÛÛ\]HKHÙ]WÜÝH[ÙN[HZ[ÛYÚÙ[XZ[
ÛÝ[ËÜX]ÜËYX\Ë]WÜÝY[[ÜJBÝXXÝHYÚYYKHÙ]WÜÝHÙ[Ù[XZ[
ÝXXÝ[
B[
ÓÒ×H[XZ[Ù[B[ÙN]WÜXYHÛÛØY
Ü[]KÛÛJBY]WÜXYÙ]
XZÛÝ]ÈNH]WÜXYÈXZÛÝ]ÈVÌB[HQÐÕTH[[XYY]HÚ\Ù]H]NÝ[OÙ^ÞØXÚÙÜÝ[ÌLÌLØÛÛÜÙ
LÙÛY[Z[NØ[Ë\Ù\YÛX^]ÚYÛX\Ú[]]ÎÜY[Îß_OÜÝ[OÚXYÙOÝ[OHÛÛÜÙ
ÌMÌNÈPRÓÕUSTÚÝÛÈÝ[OHÛÛÜÙNXÙÈØÈ[H_OÜÝÛÏ\Ý]ÝÛÈÝ[OHÛÛÜÙ
ÌMÌNÈØÈ^\ÈNHY]ÜÏÜÝÛÏ[H\Ý
Ý\ËÜÝ[OHÛÛÜÍMMMÌÈÛÝ[ØÈÛÝ[_OÜÝ[OHÛÛÜÎNXXÈØÈ\ØÈ_OÜHYHØÈ\_HÝ[OHÛÛÜÍNYYÈØ]ÚY[È8¡¥ÏØOÜØÙOÚ[Ù[Ù[XZ[
PRÓÕUØÉÚ[I×_HKHØÉÜ^\É×NHY]ÜÈYÚÝÈ[
B[ÙN[
ÓÒ×HØØ[ÛÛ\]KÈXZÛÝ]Ë]KÛÛ\]YB[
ÓÒ×HÛKBY×Û[YW×ÈOH×ÛXZ[×ÈXZ[
B
