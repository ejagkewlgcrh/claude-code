#!/usr/bin/env python3
"""Dump all videos of a public YouTube playlist via the public Innertube API."""
import json
import sys
import time
import urllib.request

KEY = "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"
PLAYLIST_ID = "PLyzTA8cetPdHtlGw1X8Kt7Ea4bd27ApR7"
CLIENT_VERSION = "2.20261029.11.00"

URL = "https://www.youtube.com/youtubei/v1/browse?key=" + KEY
CONTEXT = {
    "client": {
        "clientName": "WEB",
        "clientVersion": CLIENT_VERSION,
        "hl": "en",
        "gl": "US",
    }
}


def browse(payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64)",
        },
        method="POST",
    )
    last_exc = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            print("attempt %d failed: %r" % (attempt + 1, exc), file=sys.stderr)
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("browse request failed after retries: %r" % last_exc)


def walk(obj, key):
    """Recursively yield every value found under `key` in nested dict/list."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key:
                yield v
            else:
                yield from walk(v, key)
    elif isinstance(obj, list):
        for item in obj:
            yield from walk(item, key)


def parse_lockup(l):
    vid = l.get("contentId", "") or ""
    title = ""
    author = ""
    length = ""
    md = l.get("metadata") or {}
    lmv = md.get("lockupMetadataViewModel") or {}
    t = lmv.get("title") or {}
    title = (t.get("content") or "").strip()
    img = lmv.get("image") or {}
    dav = img.get("decoratedAvatarViewModel") or {}
    a11y = dav.get("a11yLabel") or ""
    if a11y.startswith("Go to channel "):
        author = a11y[len("Go to channel "):]
    elif a11y:
        author = a11y
    cimg = l.get("contentImage") or {}
    tvm = cimg.get("thumbnailViewModel") or {}
    overlays = tvm.get("overlays") or []
    for ov in overlays:
        bo = ov.get("thumbnailBottomOverlayViewModel")
        if bo:
            badges = bo.get("badges") or []
            for b in badges:
                tb = b.get("thumbnailBadgeViewModel") or {}
                txt = tb.get("text")
                if txt and ":" in txt:
                    length = txt
                    break
        if length:
            break
    return {"videoId": vid, "title": title, "author": author, "length": length}


def parse_old(r):
    vid = r.get("videoId", "") or ""
    title = ""
    t = r.get("title") or {}
    if t.get("runs"):
        title = t["runs"][0].get("text", "")
    elif t.get("simpleText"):
        title = t["simpleText"]
    author = ""
    b = r.get("shortBylineText") or {}
    if b.get("runs"):
        author = b["runs"][0].get("text", "")
    elif b.get("simpleText"):
        author = b["simpleText"]
    length = ""
    lt = r.get("lengthText") or {}
    if isinstance(lt, dict):
        length = lt.get("simpleText", "") or ""
    return {"videoId": vid, "title": title, "author": author, "length": length}


def extract_videos(data):
    videos = []
    for l in walk(data, "lockupViewModel"):
        if isinstance(l, dict) and l.get("contentId"):
            videos.append(parse_lockup(l))
    for r in walk(data, "playlistVideoRenderer"):
        if isinstance(r, dict) and r.get("videoId"):
            videos.append(parse_old(r))
    return videos


def extract_token(data):
    for ncd in walk(data, "nextContinuationData"):
        if isinstance(ncd, dict) and ncd.get("continuation"):
            return ncd["continuation"]
    for cc in walk(data, "continuationCommand"):
        if isinstance(cc, dict) and cc.get("token"):
            return cc["token"]
    return None


def main():
    videos = []
    seen = set()
    payload = {"context": CONTEXT, "browseId": "VL" + PLAYLIST_ID}
    page = 0
    while True:
        page += 1
        print("fetching page %d ..." % page, file=sys.stderr)
        data = browse(payload)
        batch = extract_videos(data)
        new = 0
        for v in batch:
            if v["videoId"] and v["videoId"] not in seen:
                seen.add(v["videoId"])
                v["index"] = len(videos)
                videos.append(v)
                new += 1
        print("page %d: %d items (%d new), total %d" % (page, len(batch), new, len(videos)), file=sys.stderr)
        token = extract_token(data)
        if not token:
            break
        payload = {"context": CONTEXT, "continuation": token}
        time.sleep(0.8)
        if page >= 10:
            print("page safety limit reached", file=sys.stderr)
            break

    result = {"playlistId": PLAYLIST_ID, "count": len(videos), "videos": videos}
    with open("playlist.json", "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)

    line = json.dumps(result, ensure_ascii=False)
    print("===PLAYLIST_JSON_BEGIN===")
    print(line)
    print("===PLAYLIST_JSON_END===")
    print("total videos:", len(videos), file=sys.stderr)


if __name__ == "__main__":
    main()
