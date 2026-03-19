#!/usr/bin/env python3
import feedparser
from xml.dom.minidom import Document, parseString
from xml.parsers.expat import ExpatError
import email.utils
from datetime import datetime, timezone
import os

RSS_URLS = [
    "https://feeds.content.dowjones.io/public/rss/RSSWorldNews"
]

ARCHIVE_PREFIX = "https://archive.is/o/soww3/"
OUTPUT_FILE = "combined.xml"
MAX_ITEMS = 500

def parse_entry_datetime(entry):
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        from time import mktime
        ts = mktime(entry.published_parsed)
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    if hasattr(entry, "updated_parsed") and entry.updated_parsed:
        from time import mktime
        ts = mktime(entry.updated_parsed)
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    return datetime.now(tz=timezone.utc)

def load_existing_guids_and_items(filepath):
    """Parse existing XML and return (list of item dicts, set of guids)."""
    if not os.path.exists(filepath):
        return [], set()
    try:
        with open(filepath, "rb") as f:
            dom = parseString(f.read())
    except ExpatError:
        return [], set()

    items = []
    guids = set()
    for item_el in dom.getElementsByTagName("item"):
        def get_text(tag):
            nodes = item_el.getElementsByTagName(tag)
            return nodes[0].firstChild.nodeValue if nodes and nodes[0].firstChild else ""

        guid = get_text("guid")
        pub = get_text("pubDate")
        try:
            dt = datetime(*email.utils.parsedate(pub)[:6], tzinfo=timezone.utc) if pub else datetime.now(tz=timezone.utc)
        except Exception:
            dt = datetime.now(tz=timezone.utc)

        items.append({
            "title": get_text("title"),
            "orig_link": guid,
            "archive_link": get_text("link"),
            "summary": get_text("description"),
            "published_dt": dt
        })
        guids.add(guid)

    return items, guids

# --- Load existing ---
existing_items, existing_guids = load_existing_guids_and_items(OUTPUT_FILE)

# --- Fetch new entries, skip duplicates ---
new_entries = []
for feed_url in RSS_URLS:
    feed = feedparser.parse(feed_url)
    for entry in feed.entries:
        if entry.link in existing_guids:
            continue
        dt = parse_entry_datetime(entry)
        new_entries.append({
            "title": getattr(entry, "title", "Untitled"),
            "orig_link": entry.link,
            "archive_link": ARCHIVE_PREFIX + entry.link,
            "summary": getattr(entry, "summary", "") or getattr(entry, "description", ""),
            "published_dt": dt
        })

# --- Merge, sort newest first, cap at 500 ---
all_entries = existing_items + new_entries
all_entries.sort(key=lambda x: x["published_dt"], reverse=True)
all_entries = all_entries[:MAX_ITEMS]

# --- Build XML ---
doc = Document()
rss = doc.createElement("rss")
rss.setAttribute("version", "2.0")
doc.appendChild(rss)

channel = doc.createElement("channel")
rss.appendChild(channel)
channel.appendChild(doc.createElement("title")).appendChild(doc.createTextNode("Project Syndicate Archive Feed"))
channel.appendChild(doc.createElement("link")).appendChild(doc.createTextNode("https://washingtonpost.com"))
channel.appendChild(doc.createElement("description")).appendChild(doc.createTextNode("Combined feed with archive links"))

for it in all_entries:
    item_el = doc.createElement("item")
    channel.appendChild(item_el)
    item_el.appendChild(doc.createElement("title")).appendChild(doc.createTextNode(it["title"]))
    item_el.appendChild(doc.createElement("link")).appendChild(doc.createTextNode(it["archive_link"]))
    item_el.appendChild(doc.createElement("guid")).appendChild(doc.createTextNode(it["orig_link"]))
    item_el.appendChild(doc.createElement("description")).appendChild(doc.createTextNode(it["summary"]))
    pubdate = email.utils.format_datetime(it["published_dt"])
    item_el.appendChild(doc.createElement("pubDate")).appendChild(doc.createTextNode(pubdate))

with open(OUTPUT_FILE, "wb") as f:
    f.write(doc.toxml(encoding="utf-8"))

print(f"✅ combined.xml written: {len(new_entries)} new + {len(existing_items)} existing → {len(all_entries)} total (cap {MAX_ITEMS}).")
