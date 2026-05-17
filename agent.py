"""
Football Trend Agent v7
=======================
Philosophy: SIGNAL DISCOVERY over strict filtering.
- Confidence scoring replaces hard rejection
- Early trend detection over perfect purity
- WR content flagged for DB adaptation
- Seed creator analytics (handles, hashtags, sounds they use)
- Commit-based persistence (data.json + trend_memory.json stay in repo)
- Morning: deep scrape (40-50 results/hashtag)
- Afternoon/Night: acceleration monitoring, re-scrape only hot signals
"""

import os, time, json, random, smtplib, requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

# ── CONFIG ────────────────────────────────────────────────────────────────────
APIFY_TOKEN    = os.environ.get("APIFY_TOKEN", "")
EMAIL_FROM     = os.environ.get("EMAIL_FROM", "therealjoshjames22@gmail.com")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "")
EMAIL_TO       = os.environ.get("EMAIL_TO",   "therealjoshjames22@gmail.com")
BRIEF_TYPE     = os.environ.get("BRIEF_TYPE", "morning")

# ── HASHTAGS ──────────────────────────────────────────────────────────────────
# Priority tags get 40 results each on morning run
PRIORITY_HASHTAGS = [
    "cfb", "footballtiktok", "collegefootball", "dbtraining",
    "footballtraining", "d1football", "athletetok", "footballworkout",
    "footballculture", "widereceiver", "defensiveback", "grindseason",
    "wr", "d1athlete", "dblife", "1v1football", "cornerback",
]
# Secondary tags get 20 results on morning run, skipped on afternoon/night
SECONDARY_HASHTAGS = [
    "footballdrills", "highschoolfootball", "footballhighlight",
    "footballedit", "7on7", "dbcamp", "gridiron", "nfl",
    "widereceiverstraining", "footballrecruiting", "footballmotivation",
    "christianathlete", "d1commit", "footballlife", "qb", "linebacker",
]

# ── SEED CREATORS (niche anchors — scrape their recent videos) ────────────────
SEED_CREATORS = [
    "showtimecaleb1", "yo.imcam", "ejizzle00", "yellobeezy",
    "iammike1x_", "lifeofat13",
    # legacy seeds
    "jalen.ramsey", "sauce.gardner.db", "patricksuisala",
    "db_elite_training", "cornerback.university",
]

# ── THRESHOLDS ────────────────────────────────────────────────────────────────
CREATOR_MAX_FANS        = 75_000   # raised ceiling slightly
CREATOR_MIN_FANS        = 100
CREATOR_MIN_VIEWS       = 5_000    # dropped from 20K
SOUND_MIN_NICHE_VIDS    = 2        # dropped from 5
SOUND_MIN_TOP_PLAYS     = 5_000    # dropped from 20K
ACCELERATION_THRESHOLD  = 2.0      # re-scrape if velocity 2x since morning
SEVEN_DAYS_SECS         = 7 * 24 * 3600
TIER_ON_THE_RISE        = 10_000
TIER_GOOD_ZONE          = 50_000
TIER_VIRAL              = 100_000
TIER_MEGA               = 500_000

# ── FOOTBALL CONFIDENCE KEYWORDS ─────────────────────────────────────────────
# Weighted scoring — hard rejection
FOOTBALL_STRONG = {
    "quarterback","qb","cornerback","defensive back","db","linebacker","lb",
    "safety","wide receiver","wr","tight end","te","running back","rb",
    "offensive lineman","defensive end","pass rush","blitz","coverage",
    "press coverage","zone","man coverage","route","go route","slant",
    "fade route","7on7","d1",1","d1athlete","d1football","ncaa","cfb",
    "college football","nfl","gridiron","football","american football",
    "snap","scrimmage","playbook","spring ball","fall ball","camp",
    "db camp","dbcamp","dbtraining","footballtraining","footballdrills",
    "1v1football","defensiveback","collegefootball","highschoolfootball",
    "footballworkout","footballhighlight","footballedit","footballtiktok",
    "footballculture","grindseason","athletetok","footballrecruiting",
    "dblife","cornerback","widereceiver","widereceiverstraining",
}
FOOTBALL_WEAK = {
    "athlete","training","drill","workout","grind","hustle","highlight",
    "sports","field","game","team","coach","recruit","offer","commit",
    "speed","agility","footwork","film","reps","sets","lift","gym",
    "brotherhood","culture","faith","christian","blessed","god",
    "discipline","mindset","motivation","pov","locker room",
}
SOCCER_REJECT = {
    "soccer","premier league","uefa","fifa","futbol","hat trick",
    "nil nil","clean sheet","goalkeeper","bundesliga","la liga",
    "serie a","ligue 1","champions league","football club",
    "penalty kick","free kick","offside",
}
WR_SIGNALS = {
    "wr","wide receiver","widereceiver","route running","separation",
    "release","`ands","catch radius","route tree","wideout",
}

def football_confidence(text):
    """
    Returns (confidence 0-100, is_wr bool, reject bool).
    Only reject if pure soccer or confidence < 10.
    """
    if not text:
        return 20, False, False   # unknown = give benefit of doubt
    t = text.lower()

    # Hard soccer reject
    soccer_hits = sum(1 for s in SOCCER_REJECT if s in t)
    if soccer_hits >= 2:
        return 0, False, True

    strong = sum(1 for k in FOOTBALL_STRONG if k in t)
    weak   = sum(1 for k in FOOTBALL_WEAK   if k in t)
    is_wr  = any(k in t for k in WR_SIGNALS)

    score = min(strong * 20 + weak * 5, 100)
    if score == 0:
        score = 15   # give unknown content benefit of doubt

    reject = score < 10
    return score, is_wr, reject

# ── HOOK PATTERNS ─────────────────────────────────────────────────────────────
HOOK_PATTERNS = [
    "pov", "nobody talks about", "the difference between", "this is what",
    "coach finally", "day in the life", "watch me", "they don't show you",
    "d1 vs", "high school vs college", "what db camp really looks like",
    "before and after", "this drill", "if you play db", "grind don't stop",
    "they called me", "committed", "offer day", "first practice",
    "nobody saw this coming", "raw footage", "unfiltered", "real talk",
    "things they don't teach", "most underrated", "why i",
    "when the coach", "every db needs", "stop doing this",
    "this is why", "you're losing because", "the secret to",
]

def extract_hooks(desc):
    if not desc: return []
    d = desc.lower()
    matched = [p for p in HOOK_PATTERNS if p in d]
    return matched

def extract_opening_line(desc):
    """Pull the first ~60 chars as the raw hook opener."""
    if not desc: return ""
    return desc.strip()[:80]

# ── CONTENT TYPE ──────────────────────────────────────────────────────────────
CONTENT_TYPES = {
    "pov":            ["pov","point of view"],
    "rivalry":        ["1v1","vs","battle","competition","who wins"],
    "transformation": ["transformation","glow up","before","after","progress"],
    "emotional":      ["real talk","truth","story","honest","felt this"],
    "motivational":   ["motivation","grind","work","believe","faith","god","blessed"],
    "locker_room":    ["locker room","team","brotherhood","culture","family"],
    "grindset":       ["grind","work ethic","no days off","discipline","sacrifice","5am","6am"],
    "cinematic":      ["cinematic","slow mo","film","aesthetic","vibes"],
    "tutorial":       ["how to","technique","drill","breakdown","watch this"],
    "hype":           ["hype","lit","fire","lets go","lock in","sauce"],
}
def classify_content(desc):
    if not desc: return "general"
    d = desc.lower()
    for ctype, kws in CONTENT_TYPES.items():
        if any(k in d for k in kws): return ctype
    return "general"

# ── CREATOR TIER ──────────────────────────────────────────────────────────────
def creator_tier(fans):
    if fans < 1_000:   return "NANO",     "#f87171"
    if fans < 5_000:   return "MICRO",    "#fb923c"
    if fans < 15_000:  return "EMERGING", "#4ade80"
    if fans < 30_000:  return "SMALL",    "#4a9eff"
    if fans <= 75_000: return "RISING",   "#888"
    return None, None

# ── CONFIDENCE SCORE ──────────────────────────────────────────────────────────
def video_confidence(plays, fans, hours_old, football_conf, hook_count, ctype):
    score = 0
    # plays tier (max 25)
    if plays >= TIER_MEGA:         score += 25
    elif plays >= TIER_VIRAL:      score += 20
    elif plays >= TIER_GOOD_ZONE:  score += 14
    elif plays >= TIER_ON_THE_RISE:score += 8
    else:                          score += 3
    # follower/view ratio (max 30) — breakout efficiency
    ratio = plays / max(fans, 1)
    if ratio >= 100:  score += 30
    elif ratio >= 50: score += 25
    elif ratio >= 20: score += 18
    elif ratio >= 10: score += 12
    elif ratio >= 5:  score += 7
    else:             score += 2
    # recency (max 20)
    if hours_old <= 12:   score += 20
    elif hours_old <= 24: score += 16
    elif hours_old <= 48: score += 12
    elif hours_old <= 72: score += 7
    elif hours_old <= 168:score += 3
    # football confidence bonus (max 15)
    score += int(football_conf / 100 * 15)
    # hook bonus (max 5)
    score += min(hook_count * 2, 5)
    # content type bonus (max 5)
    if ctype in ("rivalry","grindset","pov","tutorial"): score += 5
    elif ctype in ("motivational","locker_room","transformation","emotional"): score += 3
    return min(score, 100)

def sound_confidence(niche_vids, max_plays, hours_since_first, accel):
    score = 0
    if niche_vids >= 10:  score += 30
    elif niche_vids >= 5: score += 20
    elif niche_vids >= 3: score += 13
    elif niche_vids >= 2: score += 8
    else:                 score += 3
    if max_plays >= TIER_MEGA:         score += 25
    elif max_plays >= TIER_VIRAL:      score += 20
    elif max_plays >= TIER_GOOD_ZONE:  score += 14
    elif max_plays >= TIER_ON_THE_RISE:score += 8
    else:                              score += 3
    if hours_since_first <= 12:    score += 25
    elif hours_since_first <= 24:  score += 20
    elif hours_since_first <= 48:  score += 14
    elif hours_since_first <= 72:  score += 8
    elif hours_since_first <= 168: score += 4
    score += min(int(accel * 20), 20)
    return min(score, 100)

def audio_lifecycle(niche_vids, hours_since_first, accel):
    if niche_vids < 3:
        return "EARLY"
    if niche_vids < 6 and hours_since_first < 48:
        return "HEATING UP"
    if niche_vids >= 6 and accel > 0.4:
        return "PEAKING"
    if niche_vids >= 12 and hours_since_first > 96:
        return "SATURATED"
    if accel < 0.08 and hours_since_first > 72:
        return "DECLINING"
    return "HEATING UP"

LIFECYCLE_EMOJI = {
    "EARLY":      "👀",
    "HEATING UP": "⚡",
    "PEAKING":    "🔥",
    "SATURATED":  "⚠️",
    "DECLINING":  "📉",
}

# ── MEMORY ────────────────────────────────────────────────────────────────────
MEMORY_FILE = "trend_memory.json"
DATA_FILE   = "data.json"

def load_memory():
    try:
        with open(MEMORY_FILE) as f: return json.load(f)
    except:
        return {"sounds":{}, "hooks":{}, "creators":{}, "hashtags":{},
                "openers":[], "runs":0, "last_morning_ts":0}

def save_memory(m):
    with open(MEMORY_FILE, "w") as f: json.dump(m, f, indent=2)

def load_prev_data():
    try:
        with open(DATA_FILE) as f: return json.load(f)
    except:
        return {}

def update_memory(memory, sounds, creators, top_videos, hashtags):
    memory["runs"] = memory.get("runs", 0) + 1
    now = time.time()
    if BRIEF_TYPE == "morning":
        memory["last_morning_ts"] = now

    for s in sounds:
        t = s.get("title","")
        if not t: continue
        if t not in memory["sounds"]:
            memory["sounds"][t] = {"first_seen": now, "appearances": 0, "max_plays": 0, "link": ""}
        memory["sounds"][t]["appearances"] += 1
        memory["sounds"][t]["max_plays"] = max(memory["sounds"][t].get("max_plays",0), s.get("max_plays",0))
        memory["sounds"][t]["link"] = s.get("link","")
        memory["sounds"][t]["last_seen"] = now

    for v in top_videos:
        desc  = v.get("text", v.get("desc",""))
        hooks = extract_hooks(desc)
        opener = extract_opening_line(desc)
        for hook in hooks:
            if hook not in memory["hooks"]:
                memory["hooks"][hook] = {"count":0, "max_plays":0}
            memory["hooks"][hook]["count"] += 1
            memory["hooks"][hook]["max_plays"] = max(
                memory["hooks"][hook].get("max_plays",0),
                v.get("playCount",0))
        if opener and len(opener) > 10:
            if opener not in memory.get("openers",[]):
                memory.setdefault("openers",[]).append(opener)
                if len(memory["openers"]) > 200:
                    memory["openers"] = memory["openers"][-200:]

    for tag, data in hashtags:
        if tag not in memory["hashtags"]:
            memory["hashtags"][tag] = {"first_seen": now, "appearances":0, "max_views":0}
        memory["hashtags"][tag]["appearances"] += 1
        memory["hashtags"][tag]["max_views"] = max(
            memory["hashtags"][tag].get("max_views",0),
            data.get("views",0))

    for c in creators:
        h = c.get("handle","")
        if not h: continue
        if h not in memory["creators"]:
            memory["creators"][h] = {"first_seen": now, "appearances":0, "max_plays":0}
        memory["creators"][h]["appearances"] += 1
        if c.get("videos"):
            memory["creators"][h]["max_plays"] = max(
                memory["creators"][h].get("max_plays",0),
                max((v.get("plays",0) for v in c["videos"]), default=0))

    return memory

# ── APIFY ─────────────────────────────────────────────────────────────────────
def apify_run(actor, input_data, timeout=300):
    if not APIFY_TOKEN:
        print(f"[WARN] No APIFY_TOKEN — skipping {actor}")
        return []
    try:
        r = requests.post(
            f"https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items",
            params={"token": APIFY_TOKEN, "timeout": timeout, "memory": 512},
            json=input_data, timeout=timeout + 30
        )
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []
    except Exception as e:
        print(f"[ERROR] Apify {actor}: {e}")
        return []

def fetch_hashtag_batch(tags, results_per):
    print(f"  Scraping {len(tags)} hashtags × {results_per} results...")
    return apify_run("clockworks/tiktok-hashtag-scraper", {
        "hashtags":         tags,
        "resultsPerPage":   results_per,
        "sortType":         "latest",
        "proxyConfiguration": {"useApifyProxy": True},
    }, timeout=360)

def fetch_creator_videos(handles):
    """Fetch recent videos for seed creator handles."""
    if not handles: return []
    print(f"  Scraping {len(handles)} seed creators...")
    results = []
    for handle in handles:
        batch = apify_run("clockworks/tiktok-scraper", {
            "profiles":       [handle],
            "resultsPerPage": 10,
            "sortType":       "latest",
            "proxyConfiguration": {"useApifyProxy": True},
        }, timeout=120)
        results.extend(batch)
    return results

def fetch_all_raw():
    """Morning: deep scrape. Afternoon/night: targeted refresh."""
    brief = BRIEF_TYPE.lower()

    if brief == "morning":
        # Priority hashtags: 40 results each
        raw = fetch_hashtag_batch(PRIORITY_HASHTAGS, 40)
        # Secondary hashtags: 20 results each
        raw += fetch_hashtag_batch(SECONDARY_HASHTAGS, 20)
        # Seed creator videos
        raw += fetch_creator_videos(SEED_CREATORS)
        print(f"  Total raw items (morning deep scrape): {len(raw)}")
        return raw

    # Afternoon / night / scan — check if we should re-scrape accelerating signals
    prev = load_prev_data()
    hot_tags = _get_accelerating_hashtags(prev)
    if hot_tags:
        print(f"  Hot hashtags detected — refreshing: {hot_tags}")
        raw = fetch_hashtag_batch(hot_tags, 30)
    else:
        print("  No major acceleration detected — using cached morning data")
        raw = []

    print(f"  Total raw items (refresh): {len(raw)}")
    return raw

def _get_accelerating_hashtags(prev_data):
    """Return hashtags whose view velocity has 2x'd since morning data."""
    if not prev_data: return PRIORITY_HASHTAGS[:5]
    hot = []
    for tag, data in prev_data.get("hashtags", {}).items():
        prev_views = data.get("views", 0)
        curr_views = data.get("views_latest", prev_views)
        if prev_views > 0 and curr_views / prev_views >= ACCELERATION_THRESHOLD:
            hot.append(tag)
    # Always refresh top priority tags on afternoon/night
    for t in PRIORITY_HASHTAGS[:6]:
        if t not in hot:
            hot.append(t)
    return hot[:8]

# ── PROCESS VIDEOS ────────────────────────────────────────────────────────────
def enrich_video(v, now_ts):
    """Extract and enrich all fields from a raw Apify video item."""
    ct      = v.get("createTime", 0)
    plays   = v.get("playCount",0) or v.get("stats",{}).get("playCount",0)
    fans    = v.get("authorMeta",{}).get("fans",0) or v.get("authorMeta",{}).get("followers",0)
    hours   = (now_ts - ct) / 3600 if ct else 999
    desc    = v.get("text", v.get("desc",""))
    author  = v.get("authorMeta",{}).get("name","") or v.get("authorMeta",{}).get("uniqueId","")
    uid     = v.get("authorMeta",{}).get("uniqueId","") or author
    url     = v.get("webVideoUrl","") or v.get("videoUrl","")
    music   = v.get("musicMeta",{})
    tags    = " ".join(c.get("title","") for c in v.get("challenges",[]) if isinstance(c,dict))
    combo   = f"{desc} {tags} {music.get('musicName','')} {author}"

    fconf, is_wr, reject = football_confidence(combo)
    hooks   = extract_hooks(desc)
    opener  = extract_opening_line(desc)
    ctype   = classify_content(desc)
    ratio   = plays / max(fans, 1)
    vconf   = video_confidence(plays, fans, hours, fconf, len(hooks), ctype)

    return {
        "plays":      plays,
        "fans":       fans,
        "hours_old":  hours,
        "desc":       desc[:120],
        "opener":     opener,
        "author":     author,
        "uid":        uid,
        "url":        url,
        "profile_url":f"https://www.tiktok.com/@{uid}" if uid else "",
        "music_id":   music.get("musicId",""),
        "music_name": music.get("musicName",""),
        "music_author":music.get("musicAuthor",""),
        "music_link": f"https://www.tiktok.com/music/-{music.get('musicId','')}" if music.get("musicId") else "",
        "tags":       tags,
        "hooks":      hooks,
        "opener":     opener,
        "ctype":      ctype,
        "ratio":      ratio,
        "fconf":      fconf,
        "is_wr":      is_wr,
        "reject":     reject,
        "vconf":      vconf,
        "ct":         ct,
        "viral":      plays >= TIER_VIRAL,
        "viral_reason": _viral_reason(plays, fans, hours, ctype),
        "copy_this":  _copy_this(desc, ctype, hooks, is_wr),
        "db_flip":    _db_flip(desc, ctype) if is_wr else "",
    }

def _viral_reason(plays, fans, hours, ctype):
    ratio = plays / max(fans, 1)
    parts = []
    if ratio >= 50:   parts.append(f"{ratio:.0f}x follower ratio")
    if hours < 24:    parts.append("posted <24h ago")
    if hours < 48:    parts.append("posted <48h ago")
    if ctype in ("rivalry","tutorial","pov"): parts.append(f"{ctype} format")
    return " · ".join(parts) if parts else ""

def _copy_this(desc, ctype, hooks, is_wr):
    if hooks: return f'Hook: "{hooks[0].title()}" angle works here'
    if is_wr: return "Mirror from DB perspective — press/trail coverage angle"
    if ctype == "rivalry":      return "Film a 1v1 drill battle with this audio"
    if ctype == "pov":          return "POV caption + intense training clip"
    if ctype == "grindset":     return "Early morning solo workout, no talking"
    if ctype == "tutorial":     return "Technique breakdown — label the footwork"
    if ctype == "emotional":    return "Raw honest caption, slow-mo reps"
    if ctype == "locker_room":  return "Authentic team moment, no filter"
    return "Adapt to your DB/training content"

def _db_flip(desc, ctype):
    """Suggest how a DB creator can flip WR content."""
    if ctype == "tutorial":  return "DB FLIP: Film the same drill from cornerback side — press technique"
    if ctype == "rivalry":   return "DB FLIP: 1v1 with a WR — show the lockup from your angle"
    if ctype == "pov":       return "DB FLIP: POV of reading the route, not running it"
    if ctype == "grindset":  return "DB FLIP: Same grind energy, DB-specific drills"
    return "DB FLIP: Mirror this concept from the defensive side"

# ── TRENDING SOUNDS ───────────────────────────────────────────────────────────
def fetch_trending_sounds(enriched):
    now_ts = time.time()
    sound_map = {}

    for e in enriched:
        if e["reject"]: continue
        if e["hours_old"] > 7 * 24: continue
        if not e["music_id"]: continue

        sid = e["music_id"]
        if sid not in sound_map:
            sound_map[sid] = {
                "title":       e["music_name"] or "Unknown Sound",
                "author":      e["music_author"],
                "link":        e["music_link"],
                "niche_videos":[],
                "max_plays":   0,
                "first_seen":  e["ct"],
                "last_seen":   e["ct"],
                "videos_24h":  0, "videos_3d":0, "videos_7d":0,
                "plays_24h":   0, "plays_3d":0,  "plays_7d":0,
            }
        s = sound_map[sid]
        s["niche_videos"].append(e)
        s["max_plays"]   = max(s["max_plays"], e["plays"])
        if e["ct"]:
            s["first_seen"] = min(s["first_seen"], e["ct"]) if s["first_seen"] else e["ct"]
            s["last_seen"]  = max(s["last_seen"],  e["ct"])
        if e["hours_old"] <= 24:  s["videos_24h"] += 1; s["plays_24h"] += e["plays"]
        if e["hours_old"] <= 72:  s["videos_3d"]  += 1; s["plays_3d"]  += e["plays"]
        s["videos_7d"] += 1; s["plays_7d"] += e["plays"]

    sounds = []
    for sid, s in sound_map.items():
        nv = len(s["niche_videos"])
        if nv < SOUND_MIN_NICHE_VIDS or s["max_plays"] < SOUND_MIN_TOP_PLAYS:
            continue
        hrs = (now_ts - s["first_seen"]) / 3600 if s["first_seen"] else 168
        accel = s["videos_24h"] / max(nv, 1)
        lifecycle = audio_lifecycle(nv, hrs, accel)
        conf = sound_confidence(nv, s["max_plays"], hrs, accel)
        s["niche_videos"].sort(key=lambda x: (-x["vconf"], x["hours_old"]))
        sounds.append({**s,
            "niche_video_count": nv,
            "lifecycle": lifecycle,
            "confidence": conf,
            "accel": accel,
            "hours_since_first": hrs,
        })

    sounds.sort(key=lambda x: (-x["confidence"], -x["max_plays"]))
    print(f"  Trending sounds: {len(sounds)}")
    return sounds[:20]

# ── CREATOR SPY ───────────────────────────────────────────────────────────────
def fetch_creator_spy(enriched):
    creator_map = {}

    for e in enriched:
        if e["reject"]: continue
        if e["hours_old"] > 7 * 24: continue
        if e["plays"] < CREATOR_MIN_VIEWS: continue

        fans = e["fans"]
        if fans > CREATOR_MAX_FANS or fans < CREATOR_MIN_FANS: continue
        tier_name, _ = creator_tier(fans)
        if tier_name is None: continue

        handle = e["uid"] or e["author"]
        if not handle: continue

        vid_entry = {
            "plays":        e["plays"],
            "desc":         e["desc"],
            "opener":       e["opener"],
            "url":          e["url"],
            "profile_url":  e["profile_url"],
            "sound":        e["music_name"],
            "sound_link":   e["music_link"],
            "days_ago":     int(e["hours_old"] // 24),
            "hours_old":    e["hours_old"],
            "ratio":        e["ratio"],
            "confidence":   e["vconf"],
            "hooks":        e["hooks"],
            "ctype":        e["ctype"],
            "is_wr":        e["is_wr"],
            "db_flip":      e["db_flip"],
            "viral":        e["viral"],
            "viral_reason": e["viral_reason"],
            "copy_this":    e["copy_this"],
            "fconf":        e["fconf"],
        }

        if handle not in creator_map:
            creator_map[handle] = {
                "handle":      handle,
                "fans":        fans,
                "size":        tier_name,
                "profile_url": e["profile_url"],
                "videos":      [],
                "hashtags_used": set(),
                "sounds_used":   set(),
            }
        creator_map[handle]["videos"].append(vid_entry)
        # Track what hashtags and sounds this creator uses
        for tag in e["tags"].split():
            creator_map[handle]["hashtags_used"].add(tag.lstrip("#").lower())
        if e["music_name"]:
            creator_map[handle]["sounds_used"].add(e["music_name"])

    for c in creator_map.values():
        c["videos"].sort(key=lambda v: (v["hours_old"], -v["plays"]))
        c["hashtags_used"] = sorted(c["hashtags_used"])[:10]
        c["sounds_used"]   = sorted(c["sounds_used"])[:5]
        max_ratio = max((v["ratio"] for v in c["videos"]), default=0)
        c["max_ratio"] = max_ratio
        c["best_conf"] = max((v["confidence"] for v in c["videos"]), default=0)

    def sort_key(c):
        tier_order = {"NANO":0,"MICRO":1,"EMERGING":2,"SMALL":3,"RISING":4}
        t = tier_order.get(c["size"], 5)
        return (t, -c["max_ratio"])

    creators = sorted(creator_map.values(), key=sort_key)
    print(f"  Creators (≤{CREATOR_MAX_FANS:,} fans): {len(creators)}")
    return creators[:15]

# ── HASHTAG DISCOVERY ─────────────────────────────────────────────────────────
def fetch_hashtags(enriched):
    tag_map  = {}
    top_vids = []

    for e in enriched:
        if e["reject"]: continue
        if e["hours_old"] > 7 * 24: continue
        if e["plays"] < 5_000: continue

        for tag in e["tags"].split():
            tag = tag.lstrip("#").lower()
            if not tag: continue
            if tag not in tag_map:
                tag_map[tag] = {"views": 0, "video_count": 0, "top_plays": 0}
            tag_map[tag]["views"]       += e["plays"]
            tag_map[tag]["video_count"] += 1
            tag_map[tag]["top_plays"]    = max(tag_map[tag]["top_plays"], e["plays"])

        if e["plays"] >= 20_000:
            top_vids.append({
                "authorMeta": {"name": e["author"], "uniqueId": e["uid"]},
                "playCount":  e["plays"],
                "text":       e["desc"],
                "webVideoUrl":e["url"],
                "createTime": e["ct"],
                "musicMeta":  {"musicName": e["music_name"], "musicId": e["music_id"]},
            })

    # Inject our priority hashtags with at least placeholder data so they always show
    for tag in PRIORITY_HASHTAGS:
        if tag not in tag_map:
            tag_map[tag] = {"views": 0, "video_count": 0, "top_plays": 0}

    tags = sorted(tag_map.items(), key=lambda x: -x[1]["views"])
    print(f"  Hashtags found: {len(tags)}")
    return tags[:30], top_vids

# ── HOOK DATABASE ─────────────────────────────────────────────────────────────
def build_hook_database(enriched, memory):
    """Build hook database from live data + memory history."""
    hooks_seen = {}

    for e in enriched:
        if e["plays"] < 10_000: continue
        for hook in e["hooks"]:
            if hook not in hooks_seen:
                hooks_seen[hook] = {"count":0, "max_plays":0, "examples":[]}
            hooks_seen[hook]["count"] += 1
            hooks_seen[hook]["max_plays"] = max(hooks_seen[hook]["max_plays"], e["plays"])
            if len(hooks_seen[hook]["examples"]) < 3:
                hooks_seen[hook]["examples"].append(e["opener"])

    # Merge with memory hooks
    for hook, data in memory.get("hooks",{}).items():
        if hook not in hooks_seen:
            hooks_seen[hook] = data
            hooks_seen[hook].setdefault("examples",[])
        else:
            hooks_seen[hook]["count"] += data.get("count",0)
            hooks_seen[hook]["max_plays"] = max(
                hooks_seen[hook]["max_plays"], data.get("max_plays",0))

    # Build openers cluster from memory
    openers = memory.get("openers", [])
    opener_patterns = _cluster_openers(openers)

    sorted_hooks = sorted(hooks_seen.items(), key=lambda x: -x[1].get("max_plays",0))
    return sorted_hooks[:20], opener_patterns

def _cluster_openers(openers):
    """Find recurring opening patterns from accumulated opener lines."""
    patterns = {}
    trigger_words = ["pov","nobody","they","this is","the difference","watch","if you",
                     "day in","real talk","committed","before","after","why i","stop"]
    for op in openers:
        low = op.lower()
        for tw in trigger_words:
            if low.startswith(tw):
                patterns[tw] = patterns.get(tw, 0) + 1
    return sorted(patterns.items(), key=lambda x: -x[1])[:10]

# ── CONTENT GAP DETECTION ────────────────────────────────────────────────────
def detect_content_gaps(creators, top_vids):
    seen_ctypes = set()
    for c in creators:
        for v in c.get("videos",[]):
            seen_ctypes.add(v.get("ctype",""))

    all_ctypes = set(CONTENT_TYPES.keys())
    gaps = all_ctypes - seen_ctypes

    gap_ideas = []
    if "locker_room" in gaps:
        gap_ideas.append({"gap":"Locker Room Culture","idea":"Behind-the-scenes team moments — almost no one does this authentically","pillar":"Brotherhood"})
    if "transformation" in gaps:
        gap_ideas.append({"gap":"Transformation","idea":"Before/after speed or strength progression — extremely shareable","pillar":"Training"})
    if "emotional" in gaps:
        gap_ideas.append({"gap":"Emotional/Raw","idea":"Real talk about the grind, faith, or setbacks — underserved in football niche","pillar":"Faith/Mindset"})
    if "cinematic" in gaps:
        gap_ideas.append({"gap":"Cinematic Training","idea":"Slow-mo DB drill with cinematic edit — very repeatable, low competition","pillar":"DB Training"})
    if "tutorial" in gaps:
        gap_ideas.append({"gap":"Tutorial/Breakdown","idea":"Technique breakdown with text overlays — strong D1 credibility signal","pillar":"DB Training"})
    return gap_ideas[:4]

# ── VIDEO IDEAS ───────────────────────────────────────────────────────────────
def generate_video_ideas(sounds, creators, top_vids):
    top  = sounds[0] if sounds else {}
    top2 = sounds[1] if len(sounds) > 1 else {}
    ts   = top.get("title","--");  tl  = top.get("link","")
    t2s  = top2.get("title","--"); t2l = top2.get("link","")

    ideas = [
        {"priority":"URGENT","pillar":"DB Training",
         "idea":"Film a DB press coverage drill — show the footwork in slow-mo. Caption: 'The technique they don't teach at most camps'",
         "sound":ts,"sound_link":tl,
         "hashtags":"#dbtraining #cornerback #footballtraining #d1",
         "hook":"They don't teach this at most camps","ctype":"tutorial","confidence":88,
         "inspo_url": top.get("niche_videos",[{}])[0].get("url","") if top.get("niche_videos") else ""},
        {"priority":"HOT","pillar":"1v1 Competition",
         "idea":"Raw 1v1 footage — DB vs WR. No music during play, add sound after. Caption: 'POV: you finally lock him up'",
         "sound":ts,"sound_link":tl,
         "hashtags":"#1v1football #cornerback #dblife #footballtraining",
         "hook":"POV: you finally lock him up","ctype":"rivalry","confidence":91,
         "inspo_url":""},
        {"priority":"HOT","pillar":"Faith/Mindset",
         "idea":"30-second grind montage — early morning workout, no words for first 10 sec, then one line about faith/discipline",
         "sound":t2s,"sound_link":t2l,
         "hashtags":"#d1athlete #footballworkout #christianathlete #grind",
         "hook":"Nobody sees the 5AM work","ctype":"grindset","confidence":85,
         "inspo_url":""},
        {"priority":"WATCH","pillar":"DB Training",
         "idea":"Break down a route concept from the DB perspective — use text overlay to label the technique",
         "sound":t2s,"sound_link":t2l,
         "hashtags":"#defensiveback #dbtraining #collegefootball #cornerback",
         "hook":"The difference between D1 and high school DBs","ctype":"tutorial","confidence":79,
         "inspo_url":""},
        {"priority":"WATCH","pillar":"Brotherhood",
         "idea":"Behind-the-scenes team warm-up or walk-through — authentic locker room feel, no filter",
         "sound":ts,"sound_link":tl,
         "hashtags":"#collegefootball #footballteam #d1athlete #brotherhood",
         "hook":"What D1 practice actually looks like","ctype":"locker_room","confidence":74,
         "inspo_url":""},
    ]
    return ideas

# ── BEST POST TIME ────────────────────────────────────────────────────────────
def best_post_time():
    times = ["6:00–7:00 AM","7:00–8:00 AM","11:00 AM–1:00 PM","5:00–7:00 PM","8:00–10:00 PM"]
    return random.choice(times)

# ── FORMAT UTILS ─────────────────────────────────────────────────────────────
def fmt_plays(p):
    if p >= 1_000_000: return f"{p/1_000_000:.1f}M"
    if p >= 1_000:     return f"{p/1_000:.0f}K"
    return str(p)

def plays_color(p):
    if p >= TIER_MEGA:         return "#f87171"
    if p >= TIER_VIRAL:        return "#fbbf24"
    if p >= TIER_GOOD_ZONE:    return "#4ade80"
    if p >= TIER_ON_THE_RISE:  return "#4a9eff"
    return "#4a5570"

def confidence_badge(score):
    if score >= 90: return f'<span style="color:#f87171;font-weight:700;">🔥 {score}/100</span>'
    if score >= 75: return f'<span style="color:#fbbf24;font-weight:700;">⚡ {score}/100</span>'
    if score >= 60: return f'<span style="color:#4ade80;font-weight:700;">✅ {score}/100</span>'
    return f'<span style="color:#4a5570;">{score}/100</span>'

def fconf_badge(score):
    if score >= 80: return f'<span style="color:#4ade80;">⚑ {score}% football</span>'
    if score >= 50: return f'<span style="color:#4a9eff;">⚑ {score}% football</span>'
    return f'<span style="color:#4a5570;">⚑ {score}% conf</span>'

# ── EMAIL STYLE ───────────────────────────────────────────────────────────────
def email_style():
    return """
    body{background:#0a0c10;color:#d4d8e0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:640px;margin:0 auto;padding:16px;font-size:13px;}
    h2{font-size:15px;font-weight:700;color:#e8ecf4;margin:0 0 12px;padding-bottom:8px;border-bottom:1px solid #1c2235;}
    h3{font-size:13px;font-weight:700;color:#8a9ab0;margin:10px 0 6px;letter-spacing:.5px;}
    .card{background:#0d1118;border:1px solid #1c2235;border-radius:12px;padding:16px;margin-bottom:14px;}
    .sound-card{background:#060a10;border:1px solid #1e3a5f;border-radius:10px;padding:14px;margin-bottom:12px;}
    .creator-card{background:#060a10;border:1px solid #1e3a5f;border-radius:10px;padding:12px;margin-bottom:10px;}
    .niche-video{background:#0d1118;border-radius:6px;padding:8px;margin-bottom:6px;border-left:2px solid #1e3a5f;}
    .wr-video{background:#0d1118;border-radius:6px;padding:8px;margin-bottom:6px;border-left:2px solid #fb923c;}
    .gap-card{background:#0a1828;border:1px solid #1e3a5f;border-radius:8px;padding:10px;margin-bottom:8px;}
    .idea-card{border-left:3px solid #4a9eff;padding:10px 14px;margin-bottom:10px;background:#0d1018;border-radius:0 8px 8px 0;}
    .hook-card{background:#080c14;border:1px solid #1c2235;border-radius:6px;padding:8px;margin-bottom:6px;}
    .watch-btn{display:inline-block;background:#111a2e;color:#4a9eff;padding:4px 10px;border-radius:6px;font-size:11px;font-weight:600;text-decoration:none;margin-top:4px;border:1px solid #1e3a5f;}
    .sound-btn{display:inline-block;background:#0a1828;color:#4ade80;padding:5px 12px;border-radius:6px;font-size:11px;font-weight:700;text-decoration:none;margin-top:6px;border:1px solid #1e5f3a;}
    .profile-btn{display:inline-block;background:#0a1828;color:#fb923c;padding:4px 10px;border-radius:6px;font-size:11px;font-weight:600;text-decoration:none;margin-top:4px;border:1px solid #5f3a1e;}
    .tag{display:inline-block;padding:2px 7px;border-radius:10px;font-size:9px;font-weight:700;margin-right:4px;margin-bottom:2px;}
    .tag-mega{background:#f8717120;color:#f87171;border:1px solid #f8717140;}
    .tag-viral{background:#fbbf2420;color:#fbbf24;border:1px solid #fbbf2440;}
    .tag-good{background:#4ade8020;color:#4ade80;border:1px solid #4ade8040;}
    .tag-rise{background:#4a9eff20;color:#4a9eff;border:1px solid #4a9eff40;}
    .tag-wr{background:#fb923c20;color:#fb923c;border:1px solid #fb923c40;}
    .tag-gray{background:#88888820;color:#888;border:1px solid #88888840;}
    .divider{border:none;border-top:1px solid #1c2235;margin:12px 0;}
    """

# ── SOUND CARD ────────────────────────────────────────────────────────────────
def build_sound_card(s, memory, idx):
    lc      = s.get("lifecycle","HEATING UP")
    lc_em   = LIFECYCLE_EMOJI.get(lc,"⚡")
    conf    = s.get("confidence",0)
    nv      = s.get("niche_video_count",0)
    mp      = s.get("max_plays",0)
    v24     = s.get("videos_24h",0)
    v3d     = s.get("videos_3d",0)
    v7d     = s.get("videos_7d",0)
    link    = s.get("link","")
    title   = s.get("title","Unknown Sound")
    author  = s.get("author","")
    mem_data = memory.get("sounds",{}).get(title,{})
    appears  = mem_data.get("appearances",1)
    repeat   = f' <span style="color:#fb923c;font-size:9px;">Seen {appears}x in memory</span>' if appears > 1 else ""

    lc_colors = {"EARLY":"#4ade80","HEATING UP":"#fbbf24","PEAKING":"#f87171","SATURATED":"#888","DECLINING":"#4a5570"}
    lcc = lc_colors.get(lc,"#4a9eff")

    sound_btn = f'<a href="{link}" class="sound-btn">🎵 Use This Sound ↗</a>' if link else ""

    html = f"""
    <div class="sound-card">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px;">
        <div>
          <div style="font-size:14px;font-weight:700;color:#e8ecf4;">{lc_em} #{idx+1} {title}</div>
          <div style="font-size:10px;color:#4a5570;margin-top:2px;">{author}</div>
          <div style="font-size:10px;margin-top:3px;">
            <span style="color:{lcc};font-weight:700;">{lc}</span>
            <span style="color:#4a5570;"> · </span>{confidence_badge(conf)}{repeat}
          </div>
        </div>
        <div style="text-align:right;font-size:10px;color:#4a5570;">
          {fmt_plays(mp)} peak plays<br>
          {nv} football vids
        </div>
      </div>
      <div style="font-size:10px;color:#4a5570;margin-bottom:8px;">
        Adoption: <strong style="color:#8a9ab0;">{v24}</strong> (24h) &nbsp;·&nbsp;
        <strong style="color:#8a9ab0;">{v3d}</strong> (3d) &nbsp;·&nbsp;
        <strong style="color:#8a9ab0;">{v7d}</strong> (7d)
      </div>
      {sound_btn}
    """

    niche_vids = s.get("niche_videos",[])
    if niche_vids:
        html += '<div style="font-size:10px;font-weight:700;color:#4a5570;letter-spacing:.5px;margin:10px 0 6px;">📹 FOOTBALL VIDEOS USING THIS SOUND</div>'
        for nv_item in niche_vids[:4]:
            is_wr_item = nv_item.get("is_wr", False)
            card_cls   = "wr-video" if is_wr_item else "niche-video"
            wr_label   = '<span class="tag tag-wr">WR</span>' if is_wr_item else ""
            db_flip    = nv_item.get("db_flip","")
            watch_btn  = f'<a href="{nv_item["url"]}" class="watch-btn">Watch ↗</a>' if nv_item.get("url") else ""
            prof_btn   = f'<a href="{nv_item.get("profile_url","")}" class="profile-btn">@{nv_item.get("author","")} ↗</a>' if nv_item.get("profile_url") else ""
            html += f"""
            <div class="{card_cls}">
              <div style="font-size:11px;font-weight:600;color:{plays_color(nv_item['plays'])};">{fmt_plays(nv_item['plays'])} views {wr_label}</div>
              <div style="font-size:10px;color:#8a9ab0;margin-top:2px;">{nv_item['desc'][:80]}</div>
              <div style="font-size:10px;color:#4a5570;margin-top:2px;">{fconf_badge(nv_item.get('fconf',0))} · {confidence_badge(nv_item['confidence'])}</div>
              {"<div style='font-size:10px;color:#fb923c;margin-top:3px;'>"+db_flip+"</div>" if db_flip else ""}
              <div style="margin-top:4px;">{watch_btn} {prof_btn}</div>
            </div>"""

    html += "</div>"
    return html

# ── CREATOR CARD ──────────────────────────────────────────────────────────────
def build_creator_card(c):
    fans    = c.get("fans",0)
    size    = c.get("size","MICRO")
    handle  = c.get("handle","")
    profile = c.get("profile_url","")
    videos  = c.get("videos",[])
    best_v  = videos[0] if videos else {}
    ratio   = c.get("max_ratio",0)
    bconf   = c.get("best_conf",0)
    htags   = c.get("hashtags_used",[])
    sounds  = c.get("sounds_used",[])

    tier_colors = {"NANO":"#f87171","MICRO":"#fb923c","EMERGING":"#4ade80","SMALL":"#4a9eff","RISING":"#888"}
    tc = tier_colors.get(size,"#4a9eff")
    prof_btn = f'<a href="{profile}" class="profile-btn">@{handle} ↗</a>' if profile else f'<span style="color:#8a9ab0;">@{handle}</span>'

    html = f"""
    <div class="creator-card">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;">
        <div>
          {prof_btn}
          <div style="font-size:10px;margin-top:3px;">
            <span style="color:{tc};font-weight:700;">{size}</span>
            <span style="color:#4a5570;"> · </span>
            <span style="color:#8a9ab0;">{fans:,} fans</span>
            <span style="color:#4a5570;"> · </span>
            <span style="color:#4ade80;">{ratio:.0f}x ratio</span>
          </div>
        </div>
        <div style="text-align:right;">{confidence_badge(bconf)}</div>
      </div>
    """

    for v in videos[:3]:
        is_wr   = v.get("is_wr",False)
        card_cls = "wr-video" if is_wr else "niche-video"
        wr_tag  = '<span class="tag tag-wr">WR</span>' if is_wr else ""
        db_flip = v.get("db_flip","")
        watch   = f'<a href="{v["url"]}" class="watch-btn">Watch ↗</a>' if v.get("url") else ""
        sound_l = f'<a href="{v["sound_link"]}" class="sound-btn" style="font-size:10px;padding:3px 8px;">🎵 {v["sound"][:25]}</a>' if v.get("sound_link") else (f'<span style="font-size:10px;color:#4a5570;">🎵 {v["sound"][:25]}</span>' if v.get("sound") else "")
        copy    = v.get("copy_this","")
        opener  = v.get("opener","")
        opener_html  = f"<div style='font-size:10px;color:#4a9eff;margin-top:2px;font-style:italic;'>&quot;{opener}&quot;</div>" if opener else ""
        db_flip_html = f"<div style='font-size:10px;color:#fb923c;margin-top:3px;'>{db_flip}</div>" if db_flip else ""
        copy_html    = f"<div style='font-size:10px;color:#4ade80;margin-top:3px;'>💡 {copy}</div>" if copy else ""
        html += f"""
        <div class="{card_cls}" style="margin-top:8px;">
          <div style="font-size:12px;font-weight:600;color:{plays_color(v['plays'])};">{fmt_plays(v['plays'])} views {wr_tag} <span style="font-size:10px;color:#4a5570;">{v['days_ago']}d ago</span></div>
          {opener_html}
          <div style="font-size:10px;color:#8a9ab0;margin-top:2px;">{v['desc'][:80]}</div>
          {db_flip_html}
          {copy_html}
          <div style="margin-top:4px;">{watch} {sound_l}</div>
        </div>"""

    if htags:
        html += f'<div style="margin-top:8px;font-size:10px;color:#4a5570;">Hashtags: <span style="color:#8a9ab0;">#{(" #".join(htags[:8]))}</span></div>'
    if sounds:
        html += f'<div style="font-size:10px;color:#4a5570;margin-top:2px;">Sounds: <span style="color:#8a9ab0;">{" · ".join(sounds[:3])}</span></div>'

    html += "</div>"
    return html

# ── HOOK DATABASE HTML ────────────────────────────────────────────────────────
def build_hooks_html(hooks_sorted, opener_patterns):
    if not hooks_sorted and not opener_patterns:
        return '<p style="color:#4a5570;font-size:12px;">No hook patterns detected yet — will populate as more data accumulates.</p>'

    html = ""
    if hooks_sorted:
        html += '<h3>🎯 RECURRING HOOK PATTERNS</h3>'
        for hook, data in hooks_sorted[:10]:
            mp = data.get("max_plays",0) or data.get("max_plays",0)
            ct = data.get("count",0)
            examples = data.get("examples",[])
            ex_html  = f"<div style='font-size:10px;color:#4a9eff;margin-top:3px;'>e.g. &quot;{examples[0][:60]}...&quot;</div>" if examples else ""
            html += f"""
            <div class="hook-card">
              <div style="font-size:12px;font-weight:700;color:#e8ecf4;">"{hook.title()}"</div>
              <div style="font-size:10px;color:#4a5570;margin-top:2px;">
                Seen <strong style="color:#8a9ab0;">{ct}x</strong> &nbsp;·&nbsp;
                Peak <strong style="color:{plays_color(mp)};">{fmt_plays(mp)}</strong> views
              </div>
              {ex_html}
            </div>"""

    if opener_patterns:
        html += '<h3 style="margin-top:12px;">📝 OPENER PATTERNS (from memory)</h3>'
        for pattern, count in opener_patterns[:8]:
            html += f'<div style="font-size:11px;color:#8a9ab0;margin-bottom:4px;">• <strong style="color:#e8ecf4;">"{pattern}..."</strong> — used {count}x in top videos</div>'

    return html

# ── MORNING EMAIL ─────────────────────────────────────────────────────────────
def build_morning_email(sounds, creators, tags, top_vids, ideas, date_str, memory, gaps):
    post_time = best_post_time()
    hooks_sorted, opener_patterns = build_hook_database(
        [{"plays": v.get("playCount",0), "hooks": extract_hooks(v.get("text","")),
          "opener": extract_opening_line(v.get("text","")),
          "fconf": 50, "vconf": 50}
         for v in top_vids], memory)

    # Sounds HTML
    sounds_html = ""
    if sounds:
        for i, s in enumerate(sounds[:6]):
            sounds_html += build_sound_card(s, memory, i)
    else:
        sounds_html = '<p style="color:#4a5570;">No trending sounds detected — check Apify token and try again.</p>'

    # Creators HTML
    creators_html = ""
    if creators:
        for c in creators[:8]:
            creators_html += build_creator_card(c)
    else:
        creators_html = '<p style="color:#4a5570;">No creator spotlights this run. Thresholds may need adjustment or Apify returned limited data.</p>'

    # Hashtags HTML
    tags_html = ""
    for tag, data in tags[:20]:
        views = data.get("views",0)
        vcount = data.get("video_count",0)
        color = plays_color(views) if views > 0 else "#4a5570"
        tags_html += f'<span class="tag" style="background:{color}20;color:{color};border:1px solid {color}40;">#{tag} {fmt_plays(views) if views else "—"}</span>'

    # Ideas HTML
    ideas_html = ""
    pcolors = {"URGENT":"#f87171","HOT":"#fbbf24","WATCH":"#4a9eff"}
    for idea in ideas[:5]:
        pc = pcolors.get(idea["priority"],"#4a9eff")
        sl = f'<a href="{idea["sound_link"]}" class="sound-btn" style="font-size:10px;padding:3px 8px;">🎵 {idea["sound"][:30]}</a>' if idea.get("sound_link") else f'<span style="font-size:10px;color:#4a5570;">🎵 {idea.get("sound","--")}</span>'
        inspo = f'<a href="{idea["inspo_url"]}" class="watch-btn">Watch inspo ↗</a>' if idea.get("inspo_url") else ""
        ideas_html += f"""
        <div class="idea-card" style="border-color:{pc};">
          <div style="font-size:10px;font-weight:700;color:{pc};margin-bottom:4px;">{idea["priority"]} · {idea["pillar"]}{" "+inspo}</div>
          <div style="font-size:13px;color:#d4d8e0;margin-bottom:4px;">{idea["idea"]}</div>
          <div style="font-size:10px;color:#4a5570;">Hook: <em style="color:#8a9ab0;">"{idea["hook"]}"</em></div>
          <div style="font-size:10px;color:#4a5570;margin-top:3px;">{idea["hashtags"]} &nbsp; {sl}</div>
        </div>"""

    # Gaps HTML
    gaps_html = ""
    for g in gaps[:3]:
        gaps_html += f"""
        <div class="gap-card">
          <div style="font-size:11px;font-weight:700;color:#4a9eff;">{g["gap"]} GAP <span style="color:#4a5570;font-weight:400;">· {g["pillar"]}</span></div>
          <div style="font-size:12px;color:#d4d8e0;margin-top:3px;">{g["idea"]}</div>
        </div>"""

    hooks_html = build_hooks_html(hooks_sorted, opener_patterns)
    mem_runs = memory.get("runs",0)

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>{email_style()}</style></head><body>
<div style="background:linear-gradient(135deg,#0d1117,#111a2e);border-radius:16px;padding:20px;margin-bottom:14px;text-align:center;border:1px solid #1c2a45;">
  <div style="font-size:28px;margin-bottom:6px;">🏈</div>
  <h1 style="font-size:22px;font-weight:900;color:#e8ecf4;margin:0 0 4px;">Morning Brief</h1>
  <p style="color:#4a5570;font-size:12px;margin:0;">{date_str} &nbsp;·&nbsp; Post window: <span style="color:#4a9eff;">{post_time}</span></p>
  <div style="font-size:11px;color:#4a5570;margin-top:6px;">Run #{mem_runs} · v7 signal discovery mode</div>
</div>

<div class="card">
  <h2>🎵 TRENDING SOUNDS</h2>
  {sounds_html}
</div>

<div class="card">
  <h2>👤 CREATOR SPOTLIGHTS</h2>
  {creators_html}
</div>

<div class="card">
  <h2>🎯 HOOK DATABASE</h2>
  {hooks_html}
</div>

<div class="card">
  <h2>📈 TRENDING HASHTAGS</h2>
  <div style="margin-bottom:8px;">{tags_html}</div>
</div>

<div class="card">
  <h2>🎬 VIDEO IDEAS</h2>
  {ideas_html}
</div>

{"<div class='card'><h2>🕳️ CONTENT GAPS</h2>"+gaps_html+"</div>" if gaps_html else ""}

<p style="text-align:center;font-size:10px;color:#2a3048;padding:16px 0;">Football Trend Agent v7 &nbsp;·&nbsp; Morning Brief &nbsp;·&nbsp; therealjoshjames22@gmail.com</p>
</body></html>"""
    return html

# ── AFTERNOON EMAIL ───────────────────────────────────────────────────────────
def build_afternoon_email(sounds, creators, top_vids, ideas, date_str, memory):
    post_time = best_post_time()
    urgent = [i for i in ideas if i["priority"] in ("URGENT","HOT")]

    viral_html = ""
    new_viral = [v for c in creators for v in c.get("videos",[]) if v.get("viral")]
    for v in new_viral[:5]:
        watch = f'<a href="{v["url"]}" class="watch-btn">Watch ↗</a>' if v.get("url") else ""
        viral_html += f"""
        <div style="padding:10px 0;border-bottom:1px solid #1c2235;">
          <div style="font-size:13px;font-weight:600;color:{plays_color(v['plays'])};">{fmt_plays(v['plays'])} views</div>
          <div style="font-size:12px;color:#8a9ab0;margin-top:2px;">{v['desc'][:70]}</div>
          {"<div style='font-size:10px;color:#4a9eff;margin-top:2px;'>"+v.get('viral_reason','')+"</div>" if v.get('viral_reason') else ""}
          {"<div style='font-size:10px;color:#4ade80;margin-top:2px;'>"+v.get('copy_this','')+"</div>" if v.get('copy_this') else ""}
          {watch}
        </div>"""
    if not viral_html:
        viral_html = '<p style="color:#4a5570;">No major viral spikes since morning.</p>'

    ideas_html = ""
    pcolors = {"URGENT":"#f87171","HOT":"#fbbf24","WATCH":"#4a9eff"}
    for idea in (urgent or ideas[:3]):
        pc = pcolors.get(idea.get("priority","WATCH"),"#4a9eff")
        ideas_html += f"""
        <div class="idea-card" style="border-color:{pc};">
          <div style="font-size:10px;font-weight:700;color:{pc};margin-bottom:4px;">{idea.get("priority")} · {idea.get("pillar")}</div>
          <div style="font-size:13px;color:#d4d8e0;">{idea.get("idea")}</div>
          <div style="font-size:10px;color:#4a5570;margin-top:3px;">Sound: <strong style="color:#8a9ab0;">{idea.get("sound","--")}</strong></div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>{email_style()}</style></head><body>
<div style="background:linear-gradient(135deg,#0d1117,#111a2e);border-radius:16px;padding:20px;margin-bottom:14px;text-align:center;border:1px solid #1c2a45;">
  <div style="font-size:28px;margin-bottom:6px;">☀️</div>
  <h1 style="font-size:20px;font-weight:900;color:#e8ecf4;">Afternoon Update</h1>
  <p style="color:#4a5570;font-size:12px;">3PM &nbsp;·&nbsp; {date_str}</p>
  <div style="margin-top:10px;background:#0d1018;border-radius:8px;padding:8px;font-size:12px;color:#4a9eff;">Post window tonight: {post_time}</div>
</div>
<div class="card"><h2>🔥 Viral Right Now</h2>{viral_html}</div>
<div class="card"><h2>💡 Top Ideas This Afternoon</h2>{ideas_html}</div>
<p style="text-align:center;font-size:10px;color:#2a3048;padding:16px 0;">Football Trend Agent v7 &nbsp;·&nbsp; 3PM Brief</p>
</body></html>"""
    return html

# ── NIGHT EMAIL ───────────────────────────────────────────────────────────────
def build_night_email(sounds, creators, ideas, date_str, memory):
    viral_today = [v for c in creators for v in c.get("videos",[]) if v.get("viral")]
    top_sound   = sounds[0] if sounds else {"title":"--","link":""}
    runs = memory.get("runs",0)
    top_hooks = sorted(memory.get("hooks",{}).items(), key=lambda x: -x[1].get("count",0))[:3]

    recap_html = ""
    for v in viral_today[:5]:
        watch = f'<a href="{v["url"]}" class="watch-btn">Watch ↗</a>' if v.get("url") else ""
        copy  = v.get("copy_this","")
        recap_html += f"""
        <div style="padding:10px 0;border-bottom:1px solid #1c2235;">
          <div style="font-size:13px;font-weight:600;color:{plays_color(v['plays'])};">{fmt_plays(v['plays'])} views</div>
          <div style="font-size:12px;color:#8a9ab0;margin-top:2px;">{v['desc'][:70]}</div>
          {"<div style='font-size:10px;color:#4ade80;margin-top:2px;'>"+copy+"</div>" if copy else ""}
          {watch}
        </div>"""
    if not recap_html:
        recap_html = '<p style="color:#4a5570;">No major viral content today in your niche.</p>'

    tomorrow_html = ""
    for idea in ideas[:4]:
        tomorrow_html += f"""
        <div class="idea-card">
          <div style="font-size:10px;font-weight:700;color:#4a9eff;margin-bottom:4px;">{idea.get("pillar")}</div>
          <div style="font-size:13px;color:#d4d8e0;margin-bottom:4px;">{idea.get("idea")}</div>
          <div style="font-size:10px;color:#4a5570;">{idea.get("hashtags","")}</div>
        </div>"""

    ts_name = top_sound.get("title","--")
    ts_link = top_sound.get("link","")
    sound_rec = f'<a href="{ts_link}" style="color:#4a9eff;">{ts_name}</a>' if ts_link else ts_name

    mem_html = ""
    if top_hooks:
        mem_html = '<div style="margin-top:8px;font-size:11px;color:#4a5570;">Top hooks in memory: ' + \
            " · ".join([f'<strong style="color:#8a9ab0;">"{h}"</strong>' for h,_ in top_hooks]) + "</div>"

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>{email_style()}</style></head><body>
<div style="background:linear-gradient(135deg,#0a0c14,#0f1228);border-radius:16px;padding:20px;margin-bottom:14px;text-align:center;border:1px solid #1c2235;">
  <div style="font-size:28px;margin-bottom:6px;">🌙</div>
  <h1 style="font-size:20px;font-weight:900;color:#e8ecf4;">Night Brief</h1>
  <p style="color:#4a5570;font-size:12px;">8PM &nbsp;·&nbsp; {date_str}</p>
  <div style="font-size:11px;color:#4a5570;margin-top:6px;">Run #{runs} · Long-term memory active{mem_html}</div>
</div>
<div class="card"><h2>📊 What Went Viral In Your Niche Today</h2>{recap_html}</div>
<div class="card"><h2>📅 Tomorrow's Content Plan</h2>{tomorrow_html}</div>
<div style="background:#0a1828;border:1px solid #1e3a5f;border-radius:12px;padding:16px;margin-bottom:14px;">
  <h2 style="color:#4a9eff;">Use This Sound Tomorrow</h2>
  <p style="font-size:14px;line-height:1.6;">{sound_rec} — post first thing in the morning for max reach</p>
</div>
<p style="text-align:center;font-size:10px;color:#2a3048;padding:16px 0;">Football Trend Agent v7 &nbsp;·&nbsp; 8PM Brief</p>
</body></html>"""
    return html

# ── EMAIL SENDER ──────────────────────────────────────────────────────────────
def send_email(subject, html_body):
    if not EMAIL_PASSWORD:
        print(f"[WARN] No EMAIL_PASSWORD — skipping send. Subject: {subject}")
        return
    try:
        msg             = MIMEMultipart("alternative")
        msg["Subject"]  = subject
        msg["From"]     = EMAIL_FROM
        msg["To"]       = EMAIL_TO
        msg.attach(MIMEText(html_body, "html", "utf-8"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(EMAIL_FROM, EMAIL_PASSWORD)
            s.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
        print(f"[OK] Email sent: {subject}")
    except Exception as e:
        print(f"[ERROR] Email failed: {e}")

# ── WRITE DATA.JSON ───────────────────────────────────────────────────────────
def write_data_json(sounds, creators, tags, top_vids, ideas, enriched):
    now   = datetime.utcnow().isoformat() + "Z"
    six_h = time.time() - 6 * 3600
    breakouts = []
    for e in enriched:
        if e["ct"] > six_h and e["plays"] >= 50_000:
            breakouts.append({
                "handle": e["author"], "uid": e["uid"],
                "plays":  e["plays"],  "desc": e["desc"][:120],
                "url":    e["url"],    "sound": e["music_name"],
                "fconf":  e["fconf"],
            })

    # Build hashtag velocity dict (for acceleration detection next run)
    htag_dict = {tag: {**data, "views_latest": data.get("views",0)} for tag, data in tags}

    data = {
        "lastUpdated": now,
        "briefType":   BRIEF_TYPE,
        "sounds": [
            {"title":s.get("title",""), "author":s.get("author",""),
             "lifecycle":s.get("lifecycle",""), "confidence":s.get("confidence",0),
             "link":s.get("link",""), "max_plays":s.get("max_plays",0),
             "niche_video_count":s.get("niche_video_count",0),
             "videos_24h":s.get("videos_24h",0),
             "niche_videos":[{
                 "url":v.get("url",""),"author":v.get("author",""),
                 "plays":v.get("plays",0),"desc":v.get("desc",""),
                 "profile_url":v.get("profile_url",""),
                 "is_wr":v.get("is_wr",False),
             } for v in s.get("niche_videos",[])[:5]]}
            for s in sounds[:20]
        ],
        "creators": [
            {"handle":c.get("handle",""), "size":c.get("size",""),
             "fans":c.get("fans",0), "profile_url":c.get("profile_url",""),
             "max_ratio":c.get("max_ratio",0),
             "hashtags_used":c.get("hashtags_used",[]),
             "sounds_used":c.get("sounds_used",[]),
             "top_plays":c["videos"][0]["plays"] if c.get("videos") else 0,
             "top_url":c["videos"][0]["url"] if c.get("videos") else ""}
            for c in creators[:15]
        ],
        "hashtags": htag_dict,
        "topVideos": [
            {"handle":v.get("authorMeta",{}).get("name",""),
             "fans":v.get("authorMeta",{}).get("fans",0),
             "plays":v.get("playCount",0),
             "desc":v.get("text",v.get("desc",""))[:120],
             "url":v.get("webVideoUrl",""),
             "sound":v.get("musicMeta",{}).get("musicName",""),
             "createTime":v.get("createTime",0)}
            for v in top_vids[:20]
        ],
        "breakouts": breakouts,
        "ideas": ideas[:5],
    }
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)
    print(f"[OK] data.json written — {len(sounds)} sounds, {len(creators)} creators, {len(breakouts)} breakouts")

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    date_str = datetime.now().strftime("%A, %B %-d %Y")
    brief    = BRIEF_TYPE.lower()

    print(f"\n{'='*54}")
    print(f"Football Trend Agent v7 -- {brief.upper()} RUN")
    print(f"{date_str}")
    print(f"{'='*54}\n")

    memory = load_memory()
    prev   = load_prev_data()

    # ── FETCH ──────────────────────────────────────────────────────────────
    if brief in ("afternoon","night","scan") and prev and prev.get("briefType") == "morning":
        print("  Using cached morning data as base...")
        # Re-fetch only accelerating signals
        fresh_raw = fetch_all_raw()
        # Build enriched from cached + fresh
        enriched = []
        # Re-enrich cached top videos
        now_ts = time.time()
        for v in prev.get("topVideos",[]):
            ct = v.get("createTime",0)
            hrs = (now_ts - ct) / 3600 if ct else 999
            fconf, is_wr, reject = football_confidence(v.get("desc","") + " " + v.get("sound",""))
            enriched.append({
                "plays": v.get("plays",0), "fans": 0,
                "hours_old": hrs, "desc": v.get("desc","")[:120],
                "opener": extract_opening_line(v.get("desc","")),
                "author": v.get("handle",""), "uid": v.get("handle",""),
                "url": v.get("url",""), "profile_url": "",
                "music_id": "", "music_name": v.get("sound",""),
                "music_author": "", "music_link": "",
                "tags": "", "hooks": extract_hooks(v.get("desc","")),
                "ctype": classify_content(v.get("desc","")),
                "ratio": 0, "fconf": fconf, "is_wr": is_wr, "reject": reject,
                "vconf": 50, "ct": ct, "viral": v.get("plays",0) >= TIER_VIRAL,
                "viral_reason": "", "copy_this": "", "db_flip": "",
            })
        # Add fresh raw
        for v in fresh_raw:
            enriched.append(enrich_video(v, now_ts))
        # Re-use cached sounds/creators if no fresh data
        sounds   = fetch_trending_sounds(enriched) or [
            {**s, "niche_videos": []} for s in prev.get("sounds",[])
        ]
        creators = fetch_creator_spy(enriched) or [
            {"handle":c["handle"],"fans":c["fans"],"size":c["size"],
             "profile_url":c.get("profile_url",""),"videos":[],"max_ratio":c.get("max_ratio",0),
             "best_conf":0,"hashtags_used":c.get("hashtags_used",[]),
             "sounds_used":c.get("sounds_used",[])}
            for c in prev.get("creators",[])
        ]
        tags, top_vids = fetch_hashtags(enriched)
        if not tags:
            tags = list(prev.get("hashtags",{}).items())
    else:
        # Morning or no cache: full fresh fetch
        raw      = fetch_all_raw()
        now_ts   = time.time()
        enriched = [enrich_video(v, now_ts) for v in raw]
        sounds   = fetch_trending_sounds(enriched)
        creators = fetch_creator_spy(enriched)
        tags, top_vids = fetch_hashtags(enriched)

    # ── FALLBACKS ─────────────────────────────────────────────────────────
    if not sounds:
        print("  [FALLBACK] No sounds — check Apify token/results")
    if not creators:
        print("  [FALLBACK] No creators detected this run")

    print(f"\n  Sounds: {len(sounds)} | Creators: {len(creators)} | Tags: {len(tags)} | Top vids: {len(top_vids)}\n")

    ideas = generate_video_ideas(sounds, creators, top_vids)
    gaps  = detect_content_gaps(creators, top_vids)

    memory = update_memory(memory, sounds, creators, top_vids, tags)
    save_memory(memory)

    write_data_json(sounds, creators, tags, top_vids, ideas, enriched)

    # ── SEND EMAIL ────────────────────────────────────────────────────────
    if brief == "morning":
        html    = build_morning_email(sounds, creators, tags, top_vids, ideas, date_str, memory, gaps)
        subject = f"🏈 Football Brief — {date_str}"
    elif brief == "afternoon":
        html    = build_afternoon_email(sounds, creators, top_vids, ideas, date_str, memory)
        subject = f"Afternoon Update — {date_str}"
    elif brief == "night":
        html    = build_night_email(sounds, creators, ideas, date_str, memory)
        subject = f"Night Brief — {date_str}"
    else:
        # scan: check for breakouts
        breakouts = [e for e in enriched if e["ct"] > time.time() - 6*3600 and e["plays"] >= 50_000 and not e["reject"]]
        if breakouts:
            b = breakouts[0]
            html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>body{{background:#0a0c10;color:#d4d8e0;font-family:sans-serif;max-width:600px;margin:0 auto;padding:20px;}}</style></head><body>
            <h2 style="color:#f87171;">BREAKOUT ALERT 🚨</h2>
            <p><strong style="color:#e8ecf4;">@{b['author']}</strong> just hit <strong style="color:#f87171;">{b['plays']:,} views</strong> in the last 6 hours.</p>
            <p style="color:#8a9ab0;">{b['desc']}</p>
            <p style="color:#4a5570;">Sound: {b['music_name']}</p>
            <p><a href="{b['url']}" style="color:#4a9eff;">Watch Video ↗</a></p>
            </body></html>"""
            subject = f"BREAKOUT: @{b['author']} — {b['plays']:,} views right now"
            send_email(subject, html)
        else:
            print("[OK] Scan complete. No breakouts. data.json updated.\n")
        print("[OK] Done.\n")
        return

    send_email(subject, html)
    print("[OK] Done.\n")


if __name__ == "__main__":
    main()
