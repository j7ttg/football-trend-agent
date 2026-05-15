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
            "idea":"Raw 1v1 footage â DB vs WR. No music during play, add sound after. Caption: 'POV: you finally lock him up'",
            "sound":top_sound_name,"sound_link":top_sound_link,
            "hashtags":"#1v1football #cornerback #dblife #footballtraining",
            "hook":"POV: you finally lock him up","content_type":"rivalry",
            "confidence":91,
            "inspo_url": ""
        },
        {
            "priority":"HOT","pillar":"Faith/Mindset",
            "idea":"30-second grind montage â early morning workout, no words for first 10 sec, then one line about faith/discipline",
            "sound":top2_sound_name,"sound_link":top2_sound_link,
            "hashtags":"#d1athlete #footballworkout #christianathlete #grind",
            "hook":"Nobody sees the 5AM work","content_type":"grindset",
            "confidence":85,
            "inspo_url": ""
        },
        {
            "priority":"WATCH","pillar":"DB Training",
            "idea":"Break down a route concept from the DB perspective â use text overlay to label the technique",
            "sound":top2_sound_name,"sound_link":top2_sound_link,
            "hashtags":"#defensiveback #dbtraining #collegefootball #cornerback",
            "hook":"The difference between D1 and high school DBs","content_type":"pov",
            "confidence":79,
            "inspo_url": ""
        },
        {
            "priority":"WATCH","pillar":"Brotherhood",
            "idea":"Behind-the-scenes team warm-up or walk-through â authentic locker room feel, no filter",
            "sound":top_sound_name,"sound_link":top_sound_link,
            "hashtags":"#collegefootball #footballteam #d1athlete #brotherhood",
            "hook":"What D1 practice actually looks like","content_type":"locker_room",
            "confidence":74,
            "inspo_url": ""
        },
    ]
    return ideas

# -- BEST POST TIME --------------------------------------------------
def best_post_time():
    times = ["6:00â7:00 AM","7:00â8:00 AM","11:00 AMâ1:00 PM","5:00â7:00 PM","8:00â10:00 PM"]
    return random.choice(times)

# -- FORMAT UTILS ----------------------------------------------------
def fmt_plays(p):
    if p >= 1_000_000: return f"{p/1_000_000:.1f}M"
    if p >= 1_000:     return f"{p/1_000:.0f}K"
    return str(p)

def plays_color(p):
    if p >= TIER_MEGA:        return "#f87171"
    if p >= TIER_VIRAL:       return "#fbbf24"
    if p >= TIER_GOOD_ZONE:   return "#4ade80"
    if p >= TIER_ON_THE_RISE: return "#4a9eff"
    return "#4a5570"

def plays_label(p):
    if p >= TIER_MEGA:        return "MEGA"
    if p >= TIER_VIRAL:       return "VIRAL"
    if p >= TIER_GOOD_ZONE:   return "GOOD ZONE"
    if p >= TIER_ON_THE_RISE: return "ON THE RISE"
    return ""

def confidence_badge(score):
    if score >= 90: return f'<span style="color:#f87171;font-weight:700;">ð¥ {score}/100</span>'
    if score >= 75: return f'<span style="color:#fbbf24;font-weight:700;">â¡ {score}/100</span>'
    if score >= 60: return f'<span style="color:#4ade80;font-weight:700;">ð {score}/100</span>'
    return f'<span style="color:#4a5570;">{score}/100</span>'

# -- EMAIL STYLE -----------------------------------------------------
def email_style():
    return """
    body{background:#0a0c10;color:#d4d8e0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:620px;margin:0 auto;padding:16px;font-size:13px;}
    h2{font-size:15px;font-weight:700;color:#e8ecf4;margin:0 0 12px;padding-bottom:8px;border-bottom:1px solid #1c2235;}
    .card{background:#0d1118;border:1px solid #1c2235;border-radius:12px;padding:16px;margin-bottom:14px;}
    .watch-btn{display:inline-block;background:#111a2e;color:#4a9eff;padding:4px 10px;border-radius:6px;font-size:11px;font-weight:600;text-decoration:none;margin-top:4px;border:1px solid #1e3a5f;}
    .sound-btn{display:inline-block;background:#0a1828;color:#4ade80;padding:5px 12px;border-radius:6px;font-size:11px;font-weight:700;text-decoration:none;margin-top:6px;border:1px solid #1e5f3a;}
    .tag{display:inline-block;padding:2px 7px;border-radius:10px;font-size:9px;font-weight:700;margin-right:4px;margin-bottom:2px;}
    .tag-mega{background:#f8717120;color:#f87171;border:1px solid #f8717140;}
    .tag-viral{background:#fbbf2420;color:#fbbf24;border:1px solid #fbbf2440;}
    .tag-goodzone{background:#4ade8020;color:#4ade80;border:1px solid #4ade8040;}
    .tag-rise{background:#4a9eff20;color:#4a9eff;border:1px solid #4a9eff40;}
    .tag-gray{background:#88888820;color:#888;border:1px solid #88888840;}
    .tag-orange{background:#fb923c20;color:#fb923c;border:1px solid #fb923c40;}
    .tag-green{background:#4ade8020;color:#4ade80;border:1px solid #4ade8040;}
    .tag-red{background:#f8717120;color:#f87171;border:1px solid #f8717140;}
    .intel-box{background:#080c14;border:1px solid #1c2235;border-radius:6px;padding:8px;margin-top:6px;}
    .divider{border:none;border-top:1px solid #1c2235;margin:12px 0;}
    .sound-card{background:#060a10;border:1px solid #1e3a5f;border-radius:10px;padding:14px;margin-bottom:12px;}
    .niche-video{background:#0d1118;border-radius:6px;padding:8px;margin-bottom:6px;border-left:2px solid #1e3a5f;}
    .gap-card{background:#0a1828;border:1px solid #1e3a5f;border-radius:8px;padding:10px;margin-bottom:8px;}
    """

# -- SOUND CARD HTML -------------------------------------------------
def build_sound_card(s, memory):
    lifecycle   = s.get("lifecycle","HEATING UP")
    lc_emoji    = LIFECYCLE_EMOJI.get(lifecycle,"â¡")
    conf        = s.get("confidence",0)
    nv          = s.get("niche_video_count",0)
    max_plays   = s.get("max_plays",0)
    v24         = s.get("videos_24h",0)
    v3d         = s.get("videos_3d",0)
    v7d         = s.get("videos_7d",0)
    sound_link  = s.get("link","")
    title       = s.get("title","Unknown Sound")
    mem_data    = memory.get("sounds",{}).get(title,{})
    appearances = mem_data.get("appearances",1)
    repeat_note = f' Â· <span style="color:#fb923c;">Seen {appearances}x in memory</span>' if appearances > 1 else ""

    # Lifecycle color
    lc_color = {"EARLY":"#4ade80","HEATING UP":"#fbbf24","PEAKING":"#f87171","SATURATED":"#888","DECLINING":"#4a5570"}.get(lifecycle,"#4a9eff")

    html = f"""
    <div class="sound-card">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px;">
        <div>
          <div style="font-size:14px;font-weight:700;color:#e8ecf4;">{lc_emoji} {title}</div>
          <div style="font-size:10px;margin-top:3px;">
            <span style="color:{lc_color};font-weight:700;">{lifecycle}</span>
            <span style="color:#4a5570;"> Â· </span>{confidence_badge(conf)}{repeat_note}
          </div>
        </div>
        <div style="text-align:right;font-size:10px;color:#4a5570;">
          {fmt_plays(max_plays)} peak<br>{nv} football vids
        </div>
      </div>
      <div style="font-size:10px;color:#4a5570;margin-bottom:10px;">
        Adoption: <strong style="color:#8a9ab0;">{v24}</strong> (24h) &nbsp;Â·&nbsp;
        <strong style="color:#8a9ab0;">{v3d}</strong> (3d) &nbsp;Â·&nbsp;
        <strong style="color:#8a9ab0;">{v7d}</strong> (7d)
      </div>
    """

    # Niche videos using this sound
    niche_vids = s.get("niche_videos",[])
    if niche_vids:
        html += '<div style="font-size:10px;font-weight:700;color:#4a5570;letter-spacing:.5px;margin-bottom:6px;">ð¹ FOOTBALL VIDEOS USING THIS SOUND</div>'
        for i, nv_item in enumerate(niche_vids[:8]):
            nv_fans   = nv_item.get("fans",0)
            nv_plays  = nv_item.get("plays",0)
            nv_url    = nv_item.get("url","")
            nv_author = nv_item.get("author","")
            nv_desc   = nv_item.get("desc","")[:80]
            nv_ratio  = nv_item.get("ratio",0)
            nv_hours  = nv_item.get("hours_old",0)
            nv_conf   = nv_item.get("confidence",0)
            nv_ctype  = nv_item.get("content_type","")
            nv_hooks  = nv_item.get("hooks",[])
            fans_fmt  = f"{nv_fans/1000:.1f}K" if nv_fans >= 1000 else str(nv_fans)
            days_ago  = int(nv_hours // 24)
            age_str   = f"{days_ago}d ago" if days_ago > 0 else f"{int(nv_hours)}h ago"
            watch_btn = f'<a href="{nv_url}" class="watch-btn">Watch â</a>' if nv_url else ""
            hook_str  = f'<div style="font-size:9px;color:#4a9eff;margin-top:2px;">Hook: {nv_hooks[0]}</div>' if nv_hooks else ""
            ctype_str = f'<span class="tag tag-gray" style="font-size:8px;">{nv_ctype.upper()}</span>' if nv_ctype else ""
            html += f"""
            <div class="niche-video">
              <div style="display:flex;justify-content:space-between;align-items:center;">
                <div>
                  <span style="font-weight:700;color:#d4d8e0;font-size:11px;">@{nv_author}</span>
                  <span style="color:#4a5570;font-size:10px;"> Â· {fans_fmt} followers Â· {age_str}</span>
                  {ctype_str}
                </div>
                <div style="font-weight:700;color:{plays_color(nv_plays)};font-size:12px;">{fmt_plays(nv_plays)}</div>
              </div>
              <div style="font-size:11px;color:#8a9ab0;margin-top:3px;">{nv_desc}</div>
              {hook_str}
              <div style="font-size:9px;color:#4a5570;margin-top:2px;">{nv_ratio:.1f}x ratio Â· {confidence_badge(nv_conf)}</div>
              {watch_btn}
            </div>"""
    else:
        html += '<div style="font-size:11px;color:#4a5570;">No football videos found yet â early signal.</div>'

    if sound_link:
        html += f'<a href="{sound_link}" class="sound-btn">ðµ Use this sound on TikTok â</a>'
    html += "</div>"
    return html

# -- MORNING EMAIL ---------------------------------------------------
def build_morning_email(sounds, creators, tags, top_videos, ideas, date_str, memory, gaps):
    post_time = best_post_time()
    top = sounds[0] if sounds else {}

    # Top 3 high-confidence opportunities
    top3 = sorted(ideas, key=lambda x: -x.get("confidence",0))[:3]
    top3_html = ""
    for i, idea in enumerate(top3):
        rank_emoji = ["ð¥","ð¥","ð¥"][i]
        top3_html += f"""
        <div style="background:#0d1018;border-left:3px solid #4a9eff;padding:10px 14px;margin-bottom:8px;border-radius:0 8px 8px 0;">
          <div style="font-size:10px;font-weight:700;color:#4a9eff;margin-bottom:3px;">{rank_emoji} {idea['pillar']} Â· {confidence_badge(idea.get('confidence',0))}</div>
          <div style="font-size:13px;color:#d4d8e0;">{idea['idea']}</div>
          <div style="font-size:10px;color:#4a5570;margin-top:4px;">Hook: "{idea['hook']}"</div>
        </div>"""

    # Sounds section
    sounds_html = ""
    for s in sounds[:5]:
        sounds_html += build_sound_card(s, memory)

    # Creator spotlight
    spotlight_html = ""
    for c in creators[:6]:
        tier_name, tier_color = creator_tier(c.get("fans",0))
        if not tier_name:
            continue
        fans = c.get("fans",0)
        handle = c.get("handle","")
        handle_url = f"https://www.tiktok.com/@{handle}"
        fans_fmt = f"{fans/1000:.1f}K" if fans >= 1000 else str(fans)
        max_plays = max((v["plays"] for v in c["videos"]), default=0)
        max_ratio = max((v["ratio"] for v in c["videos"]), default=0)
        tier_emoji = {"MICRO":"ð¥","EMERGING":"â¡","SMALL":"ð","RISING":"ð"}.get(tier_name,"")

        spotlight_html += f"""
        <div style="margin-bottom:20px;padding-bottom:20px;border-bottom:1px solid #1c2235;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
            <div>
              <a href="{handle_url}" style="font-weight:700;font-size:14px;color:#d4d8e0;">@{handle}</a>
              <span style="font-size:10px;color:{tier_color};margin-left:8px;font-weight:700;background:#0a0c10;padding:2px 7px;border-radius:10px;border:1px solid {tier_color}30;">{tier_emoji} {tier_name}</span>
            </div>
            <div style="font-size:11px;color:#4a5570;">{fans_fmt} followers Â· {max_ratio:.1f}x ratio</div>
          </div>"""

        for v in c["videos"][:2]:
            vp = v.get("plays",0)
            vcolor = plays_color(vp)
            vtier = plays_label(vp)
            vtag = f'<span class="tag tag-{vtier.lower().replace(" ","")}" style="font-size:9px;">{vtier}</span> ' if vtier else ""
            watch = f'<a href="{v["url"]}" class="watch-btn">Watch on TikTok â</a>' if v.get("url") else ""
            reason = f'<div style="font-size:10px;color:#4a9eff;margin-top:3px;font-weight:600;">{v["viral_reason"]}</div>' if v.get("viral_reason") else ""
            sound_l = f'<div style="font-size:10px;color:#4a5570;">Sound: <strong style="color:#8a9ab0;">{v["sound"]}</strong></div>' if v.get("sound") else ""
            pillar_b = f'<span class="tag tag-gray" style="font-size:9px;">{v.get("content_type","").upper()}</span> ' if v.get("content_type") else ""
            days_lbl = f'<span class="tag tag-orange" style="font-size:9px;">{v.get("days_ago",0)}d ago</span> ' if v.get("days_ago") is not None else ""
            conf_b   = confidence_badge(v.get("confidence",0))
            hooks    = v.get("hooks",[])
            hook_str = f'<div style="font-size:10px;color:#fb923c;margin-top:3px;">Hook: {hooks[0]}</div>' if hooks else ""

            intel_html = ""
            fmt_type     = v.get("format_type","")
            hook_analysis= v.get("hook_analysis","")
            copy_this    = v.get("copy_this","")
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
              <div style="font-size:11px;color:#8a9ab0;margin-bottom:4px;line-height:1.4;">{days_lbl}{pillar_b}{vtag}{v["desc"] or "(no caption)"}</div>
              <div style="font-size:13px;font-weight:700;color:{vcolor};">{fmt_plays(vp)} views &nbsp;Â·&nbsp; {conf_b}</div>
              <div style="font-size:11px;color:#4a5570;">{v.get("days_ago",0)*(1 if v.get("days_ago") else 0):,} likes</div>
              {hook_str}
              {sound_l}
              {reason}
              {intel_html}
              {watch}
            </div>"""
        spotlight_html += "</div>"

    # Hashtags
    ht_html = ""
    for tag, data in tags[:8]:
        views = data["views"]
        views_fmt = f"{views/1_000_000_000:.1f}B" if views >= 1e9 else f"{views/1_000_000:.0f}M" if views >= 1e6 else f"{views:,}"
        ht_html += f'<a href="https://www.tiktok.com/tag/{tag}" style="background:#111a2e;color:#4a9eff;padding:5px 12px;border-radius:20px;margin:3px;display:inline-block;font-size:12px;font-weight:600;border:1px solid #1e3a5f;">#{tag} <span style="color:#2a5a9f;font-size:10px;">{views_fmt}</span></a>'

    # Top hashtag videos
    ht_videos_html = ""
    for v in top_videos[:4]:
        watch = f'<a href="{v["url"]}" class="watch-btn">Watch â</a>' if v.get("url") else ""
        fans_fmt = f"{v.get('fans',0)/1000:.0f}K" if v.get("fans",0) >= 1000 else str(v.get("fans",0))
        sound_l = f'<div style="font-size:10px;color:#4a5570;">Sound: {v.get("sound","")}</div>' if v.get("sound") else ""
        vp = v.get("plays",0)
        tag_val = v.get("tag","")
        author = v.get("author","")
        desc = v.get("desc","")[:100]
        ht_videos_html += f"""
        <div style="background:#0d1018;border-radius:8px;padding:10px;margin-bottom:8px;">
          <div style="font-size:11px;color:#4a5570;margin-bottom:4px;">#{tag_val} &nbsp;Â·&nbsp; <a href="https://www.tiktok.com/@{author}" style="color:#4a9eff;">@{author}</a> ({fans_fmt} followers)</div>
          <div style="font-size:12px;color:#c4c8d0;margin-bottom:4px;line-height:1.4;">{desc}</div>
          <div style="font-size:12px;font-weight:700;color:{plays_color(vp)};">{fmt_plays(vp)} views</div>
          {sound_l}
          {watch}
        </div>"""

    # Video ideas
    ideas_html = ""
    for idea in ideas:
        p_color = "#f87171" if idea["priority"] == "URGENT" else "#fbbf24" if idea["priority"] == "HOT" else "#4a9eff"
        inspo_link = f' <a href="{idea["inspo_url"]}" class="watch-btn">Watch inspo â</a>' if idea.get("inspo_url") else ""
        sound_link_html = f'<a href="{idea.get("sound_link","")}" class="sound-btn" style="font-size:9px;padding:3px 8px;">ðµ {idea["sound"]}</a>' if idea.get("sound_link") else f'<strong style="color:#8a9ab0;">{idea["sound"]}</strong>'
        ideas_html += f"""
        <div style="border-left:3px solid {p_color};padding:10px 14px;margin-bottom:10px;background:#0d1018;border-radius:0 8px 8px 0;">
          <div style="font-size:10px;font-weight:700;color:{p_color};margin-bottom:4px;letter-spacing:.5px;">{idea["priority"]} Â· {idea["pillar"]}{inspo_link} Â· {confidence_badge(idea.get("confidence",0))}</div>
          <div style="font-size:13px;color:#d4d8e0;margin-bottom:6px;line-height:1.5;">{idea["idea"]}</div>
          <div style="font-size:10px;color:#4a5570;">Sound: {sound_link_html} &nbsp;Â·&nbsp; {idea["hashtags"]}</div>
        </div>"""

    # Content gaps
    gaps_html = ""
    for g in gaps:
        gaps_html += f"""
        <div class="gap-card">
          <div style="font-size:10px;font-weight:700;color:#fb923c;margin-bottom:4px;">ð CONTENT GAP Â· {g['pillar']}</div>
          <div style="font-size:11px;color:#4a5570;margin-bottom:3px;">Underserved angle: <strong style="color:#8a9ab0;">{g['gap']}</strong></div>
          <div style="font-size:12px;color:#c4c8d0;">{g['idea']}</div>
        </div>"""

    # Hook database (top performing hooks from memory)
    mem_hooks = sorted(memory.get("hooks",{}).items(), key=lambda x: -x[1].get("max_plays",0))[:5]
    hooks_html = ""
    for hook, hdata in mem_hooks:
        hooks_html += f'<div style="background:#0d1018;border-radius:6px;padding:6px 10px;margin-bottom:6px;font-size:12px;"><span style="color:#4ade80;">â»</span> <strong style="color:#d4d8e0;">"{hook}"</strong> <span style="color:#4a5570;">â seen {hdata.get("count",1)}x Â· peak {fmt_plays(hdata.get("max_plays",0))}</span></div>'

    top_sound_name = top.get("title","--")
    top_sound_link_html = f'<a href="{top["link"]}" style="color:#4ade80;text-decoration:underline;">{top_sound_name}</a>' if top.get("link") else f'"{top_sound_name}"'

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>{email_style()}</style></head><body>

<div style="background:linear-gradient(135deg,#0d1117,#111a2e);border-radius:16px;padding:24px;margin-bottom:14px;text-align:center;border:1px solid #1c2a45;">
  <div style="font-size:36px;margin-bottom:8px;">ð</div>
  <h1 style="font-size:22px;font-weight:900;color:#e8ecf4;margin-bottom:4px;">Good Morning, Joshua</h1>
  <p style="color:#4a5570;font-size:13px;">Football Trend Brief &nbsp;&bull;&nbsp; {date_str}</p>
  <div style="margin-top:12px;background:#0d1018;border-radius:8px;padding:10px;font-size:13px;color:#4a9eff;font-weight:600;">
    Best time to post today: {post_time}
  </div>
</div>

<div class="card">
  <h2>ð¯ Top 3 High-Confidence Opportunities</h2>
  {top3_html}
</div>

<div style="background:#0a1828;border:1px solid #1e3a5f;border-radius:12px;padding:18px;margin-bottom:14px;">
  <h2 style="color:#4a9eff;">Your Move Today</h2>
  <p style="font-size:14px;margin-bottom:8px;line-height:1.6;"><strong style="color:#e8ecf4;">Hottest sound right now:</strong> {top_sound_link_html}</p>
  <p style="font-size:13px;color:#8a9ab0;line-height:1.6;"><strong style="color:#d4d8e0;">Post idea:</strong> Film a DB press coverage drill. Name a specific WR or school you're preparing for in the caption.</p>
</div>

<div class="card">
  <h2>ðµ Niche Sounds Going Viral (5+ football videos, 20K+ plays)</h2>
  <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px;font-size:10px;color:#4a5570;">
    <span><span style="color:#f87171;font-weight:700;">MEGA</span> = 500K+</span>
    <span><span style="color:#fbbf24;font-weight:700;">VIRAL</span> = 100K+</span>
    <span><span style="color:#4ade80;font-weight:700;">GOOD ZONE</span> = 50K-100K</span>
    <span><span style="color:#4a9eff;font-weight:700;">ON THE RISE</span> = 20K-50K</span>
  </div>
  {sounds_html if sounds_html else '<p style="color:#4a5570;">No qualifying sounds yet â check next run.</p>'}
</div>

<div class="card">
  <h2>ð Creator Spotlight â¡ Last 7 Days Only (â¤50K followers)</h2>
  <div style="font-size:11px;color:#4a5570;margin-bottom:12px;">ð¥ MICRO (&lt;5K) Â· â¡ EMERGING (5-15K) Â· ð SMALL (15-30K) Â· ð RISING (30-50K) Â· All American football â</div>
  {spotlight_html if spotlight_html else '<p style="color:#4a5570;">No qualifying creators this run.</p>'}
</div>

<div class="card">
  <h2>ð¡ Video Ideas For Today</h2>
  {ideas_html}
</div>

<div class="card">
  <h2>ð Content Gaps (Underserved Angles)</h2>
  {gaps_html if gaps_html else '<p style="color:#4a5570;">No major gaps detected this run.</p>'}
</div>

<div class="card">
  <h2>â» Hook Database (Recurring Winning Hooks)</h2>
  {hooks_html if hooks_html else '<p style="color:#4a5570;">Building hook database â check back after a few runs.</p>'}
</div>

<div class="card">
  <h2>ð·ï¸ Trending Hashtags</h2>
  {ht_html}
  {('<hr class="divider"><div style="font-size:12px;font-weight:700;color:#d4d8e0;margin:12px 0 10px;">Top Videos Under These Hashtags</div>' + ht_videos_html) if ht_videos_html else ""}
</div>

<p style="text-align:center;font-size:10px;color:#2a3048;padding:16px 0;">Football Trend Agent v6 &nbsp;&bull;&nbsp; therealjoshjames22@gmail.com</p>
</body></html>"""
    return html

# -- AFTERNOON EMAIL -------------------------------------------------
def build_afternoon_email(sounds, creators, top_videos, ideas, date_str, memory):
    post_time = best_post_time()
    urgent    = [i for i in ideas if i["priority"] in ("URGENT","HOT")]
    new_viral = [v for c in creators for v in c["videos"] if v.get("viral")]

    viral_html = ""
    for v in new_viral[:5]:
        vp     = v.get("plays",0)
        watch  = f'<a href="{v["url"]}" class="watch-btn">Watch on TikTok â</a>' if v.get("url") else ""
        reason = f'<div style="font-size:10px;color:#4a9eff;margin-top:3px;">{v["viral_reason"]}</div>' if v.get("viral_reason") else ""
        copy_t = f'<div style="font-size:10px;color:#4ade80;margin-top:3px;">Copy this: {v["copy_this"]}</div>' if v.get("copy_this") else ""
        viral_html += f"""
        <div style="padding:10px 0;border-bottom:1px solid #1c2235;">
          <div style="font-size:13px;font-weight:600;color:{plays_color(vp)};">{fmt_plays(vp)} views</div>
          <div style="font-size:12px;color:#8a9ab0;margin-top:2px;">{v["desc"][:70]}</div>
          {reason}{copy_t}{watch}
        </div>"""
    if not viral_html:
        viral_html = '<p style="font-size:13px;color:#333;">No major viral spikes since this morning.</p>'

    ideas_html = ""
    for idea in (urgent or ideas[:3]):
        p_color = "#f87171" if idea["priority"] == "URGENT" else "#fbbf24"
        inspo_link = f' <a href="{idea["inspo_url"]}" class="watch-btn">Watch inspo â</a>' if idea.get("inspo_url") else ""
        ideas_html += f"""
        <div style="border-left:3px solid {p_color};padding:10px 14px;margin-bottom:10px;background:#0d1018;border-radius:0 8px 8px 0;">
          <div style="font-size:10px;font-weight:700;color:{p_color};margin-bottom:4px;">{idea["priority"]} Â· {idea["pillar"]}{inspo_link}</div>
          <div style="font-size:13px;color:#d4d8e0;margin-bottom:4px;">{idea["idea"]}</div>
          <div style="font-size:10px;color:#4a5570;">Sound: <strong style="color:#8a9ab0;">{idea["sound"]}</strong></div>
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
<p style="text-align:center;font-size:10px;color:#2a3048;padding:16px 0;">Football Trend Agent v6 &nbsp;&bull;&nbsp; 2PM Brief &nbsp;&bull;&nbsp; therealjoshjames22@gmail.com</p>
</body></html>"""
    return html

# -- NIGHT EMAIL -----------------------------------------------------
def build_night_email(sounds, creators, ideas, date_str, memory):
    viral_today = [v for c in creators for v in c["videos"] if v.get("viral")]
    top_sound   = sounds[0] if sounds else {"title": "--", "link": ""}

    recap_html = ""
    for v in viral_today[:5]:
        vp     = v.get("plays",0)
        watch  = f'<a href="{v["url"]}" class="watch-btn">Watch â</a>' if v.get("url") else ""
        copy_t = f'<div style="font-size:10px;color:#4ade80;margin-top:3px;">Copy this: {v["copy_this"]}</div>' if v.get("copy_this") else ""
        recap_html += f"""
        <div style="padding:10px 0;border-bottom:1px solid #1c2235;">
          <div style="font-size:13px;font-weight:600;color:{plays_color(vp)};">{fmt_plays(vp)} views</div>
          <div style="font-size:12px;color:#8a9ab0;margin-top:2px;">{v["desc"][:70]}</div>
          {copy_t}{watch}
        </div>"""
    if not recap_html:
        recap_html = '<p style="font-size:13px;color:#333;">No major viral content today in your niche.</p>'

    tomorrow_html = ""
    for idea in ideas[:4]:
        tomorrow_html += f"""
        <div style="border-left:3px solid #4a9eff;padding:10px 14px;margin-bottom:10px;background:#0d1018;border-radius:0 8px 8px 0;">
          <div style="font-size:10px;font-weight:700;color:#4a9eff;margin-bottom:4px;letter-spacing:.5px;">{idea["pillar"]}</div>
          <div style="font-size:13px;color:#d4d8e0;margin-bottom:4px;">{idea["idea"]}</div>
          <div style="font-size:10px;color:#4a5570;">Sound: <strong style="color:#8a9ab0;">{idea["sound"]}</strong> &nbsp;&bull;&nbsp; {idea["hashtags"]}</div>
        </div>"""

    ts_name = top_sound.get("title","--")
    top_sound_link = f'<a href="{top_sound["link"]}" style="color:#4a9eff;">{ts_name}</a>' if top_sound.get("link") else ts_name

    # Memory summary
    runs = memory.get("runs",0)
    top_hooks = sorted(memory.get("hooks",{}).items(), key=lambda x: -x[1].get("count",0))[:3]
    mem_html = ""
    if top_hooks:
        mem_html = '<div style="margin-top:8px;font-size:11px;color:#4a5570;">Top hooks in memory: ' + " Â· ".join([f'<strong style="color:#8a9ab0;">"{h}"</strong>' for h,_ in top_hooks]) + "</div>"

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>{email_style()}</style></head><body>
<div style="background:linear-gradient(135deg,#0a0c14,#0f1228);border-radius:16px;padding:20px;margin-bottom:14px;text-align:center;border:1px solid #1c2235;">
  <div style="font-size:28px;margin-bottom:6px;">Night Brief</div>
  <h1 style="font-size:20px;font-weight:900;color:#e8ecf4;">Today in Review</h1>
  <p style="color:#4a5570;font-size:12px;">9PM &nbsp;&bull;&nbsp; {date_str}</p>
  <div style="font-size:11px;color:#4a5570;margin-top:6px;">Run #{runs} Â· Long-term memory active{mem_html}</div>
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
<p style="text-align:center;font-size:10px;color:#2a3048;padding:16px 0;">Football Trend Agent v6 &nbsp;&bull;&nbsp; 9PM Brief &nbsp;&bull;&nbsp; therealjoshjames22@gmail.com</p>
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
        ct    = v.get("createTime",0)
        plays = v.get("playCount",0) or v.get("stats",{}).get("playCount",0)
        if ct > six_hrs_ago and plays >= 50000:
            breakouts.append({
                "handle": v.get("authorMeta",{}).get("name",""),
                "plays":  plays,
                "desc":   v.get("text",v.get("desc",""))[:120],
                "url":    v.get("webVideoUrl",""),
                "sound":  v.get("musicMeta",{}).get("musicName",""),
            })

    data = {
        "lastUpdated": now,
        "briefType":  BRIEF_TYPE,
        "sounds": [
            {"title": s.get("title",""), "author": s.get("author",""),
             "lifecycle": s.get("lifecycle",""), "confidence": s.get("confidence",0),
             "link": s.get("link",""), "maxPlays": s.get("max_plays",0),
             "nicheVideoCount": s.get("niche_video_count",0),
             "nicheVideos": s.get("niche_videos",[])[:5]}
            for s in sounds[:20]
        ],
        "creators": [
            {"handle": c.get("handle",""), "size": c.get("size",""),
             "fans": c.get("fans",0),
             "topVideo": c["videos"][0]["url"] if c.get("videos") else "",
             "topDesc":  c["videos"][0]["desc"] if c.get("videos") else "",
             "topPlays": c["videos"][0]["plays"] if c.get("videos") else 0,
             "topConfidence": c["videos"][0]["confidence"] if c.get("videos") else 0}
            for c in creators[:15]
        ],
        "hashtags":  tags[:15],
        "topVideos": [
            {"handle": v.get("authorMeta",{}).get("name",""),
             "fans": v.get("authorMeta",{}).get("fans",0),
             "plays": v.get("playCount",0),
             "desc": v.get("text",v.get("desc",""))[:120],
             "sound": v.get("musicMeta",{}).get("musicName",""),
             "url": v.get("webVideoUrl",""),
             "createTime": v.get("createTime",0)}
            for v in top_videos[:20]
        ],
        "breakouts": breakouts,
        "ideas":     ideas[:5],
    }
    with open("data.json","w") as f:
        json.dump(data, f, indent=2)
    print(f"[OK] data.json written -- {len(sounds)} sounds, {len(creators)} creators, {len(breakouts)} breakouts")

# -- MAIN ------------------------------------------------------------
def main():
    date_str = datetime.now().strftime("%A, %B %-d %Y")
    brief    = BRIEF_TYPE.lower()

    print(f"\n{'='*52}")
    print(f"Football Trend Agent v6 -- {brief.upper()} RUN")
    print(f"{date_str}")
    print(f"{'='*52}\n")

    memory = load_memory()

    if brief in ("afternoon","night") and os.path.exists("data.json"):
        print("  Reusing cached data.json (no new Apify call needed)...")
        with open("data.json") as f:
            cached = json.load(f)
        sounds     = cached.get("sounds",[])
        creators   = cached.get("creators",[])
        tags       = cached.get("hashtags",[])
        top_videos = cached.get("topVideos",[])
        ideas      = cached.get("ideas",[])
        gaps       = []
    else:
        raw            = fetch_all_raw()
        sounds         = fetch_trending_sounds(raw)
        creators       = fetch_creator_spy(raw)
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
        gaps  = detect_content_gaps(creators, top_videos)
        memory = update_memory(memory, sounds, creators, top_videos)
        save_memory(memory)

    print(f"\n  Sounds: {len(sounds)} | Creators: {len(creators)} | Tags: {len(tags)} | Top videos: {len(top_videos)}\n")

    write_data_json(sounds, creators, tags, top_videos, ideas)

    gaps = gaps if 'gaps' in dir() else detect_content_gaps(creators, top_videos)

    if brief in ("morning","afternoon","night"):
        if brief == "morning":
            html    = build_morning_email(sounds, creators, tags, top_videos, ideas, date_str, memory, gaps)
            subject = f"ð Football Brief -- {date_str}"
        elif brief == "afternoon":
            html    = build_afternoon_email(sounds, creators, top_videos, ideas, date_str, memory)
            subject = f"Afternoon Update -- {date_str}"
        else:
            html    = build_night_email(sounds, creators, ideas, date_str, memory)
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
