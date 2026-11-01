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


def parse_renderer(item):
    r = item.get("playlistVideoRenderer") or {}
    vid = r.get("videoId", "")

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

    index = ""
    ix = r.get("index") or {}
    if isinstance(ix, dict):
        index = ix.get("simpleText", "") or ""

    return {
        "index": index,
        "videoId": vid,
        "title": title,
        "author": author,
        "length": length,
    }


def main():
    videos = []
    payload = {"context": CONTEXT, "browseId": "VL" + PLAYLIST_ID}
    page = 0
    while True:
        page += 1
        print("fetching page %d ..." % page, file=sys.stderr)
        data = browse(payload)

        if page == 1:
            tabs = data["contents"]["twoColumnBrowseResultsRenderer"]["tabs"]
            tab = tabs[0]["tabRenderer"]
            sections = tab["content"]["sectionListRenderer"]["contents"]
            plr = sections[0]["playlistVideoListRenderer"]
        else:
            plr = data["continuationContents"]["playlistVideoListContinuation"]

        for item in plr.get("contents", []):
            if "playlistVideoRenderer" in item:
                videos.append(parse_renderer(item))

        continuations = plr.get("continuations") or []
        if not continuations:
            break
        token = continuations[0]["nextContinuationData"]["continuation"]
        payload = {"context": CONTEXT, "continuation": token}
        time.sleep(0.8)

    result = {
        "playlistId": PLAYLIST_ID,
        "count": len(videos),
        "videos": videos,
    }
    with open("playlist.json", "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)

    print("===PLAYLIST_JSON_BEGIN===")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("===PLAYLIST_JSON_END===")
    print("total videos:", len(videos), file=sys.stderr)


if __name__ == "__main__":
    main()
