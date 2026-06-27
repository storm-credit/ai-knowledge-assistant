from dataclasses import dataclass
from typing import List
import yaml

YT_FEED = "https://www.youtube.com/feeds/videos.xml?channel_id={}"

@dataclass
class Source:
    name: str
    rss: str
    type: str

@dataclass
class SourcesConfig:
    youtube: List[Source]
    newsletters: List[Source]

def load_sources(path: str) -> SourcesConfig:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    yt = [Source(name=e["name"], rss=YT_FEED.format(e["channel_id"]), type="youtube")
          for e in data.get("youtube", [])]
    nl = [Source(name=e["name"], rss=e["rss"], type="newsletter")
          for e in data.get("newsletters", [])]
    return SourcesConfig(youtube=yt, newsletters=nl)
