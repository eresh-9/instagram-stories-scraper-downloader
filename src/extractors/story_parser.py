thonfrom __future__ import annotations

import logging
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

from .media_utils import choose_best_version

logger = logging.getLogger(__name__)

@dataclass
class UserInfo:
    username: str
    full_name: Optional[str] = None
    id: Optional[str] = None
    is_verified: bool = False
    is_private: bool = False
    profile_pic_url: Optional[str] = None

    @classmethod
    def from_raw(cls, data: Dict[str, Any]) -> "UserInfo":
        if not data:
            return cls(username="unknown")
        return cls(
            username=str(data.get("username") or "unknown"),
            full_name=data.get("full_name"),
            id=str(data.get("id")) if data.get("id") is not None else None,
            is_verified=bool(data.get("is_verified", False)),
            is_private=bool(data.get("is_private", False)),
            profile_pic_url=data.get("profile_pic_url"),
        )

@dataclass
class Story:
    id: str
    code: Optional[str]
    fbid: Optional[str]
    media_type: int
    product_type: str
    taken_at: int
    taken_at_date: str
    expiring_at: int
    video_url: Optional[str]
    video_duration: Optional[float]
    video_codec: Optional[str]
    video_versions: List[Dict[str, Any]] = field(default_factory=list)
    thumbnail_url: Optional[str] = None
    image_versions: List[Dict[str, Any]] = field(default_factory=list)
    has_audio: bool = False
    original_width: Optional[int] = None
    original_height: Optional[int] = None
    user: Dict[str, Any] = field(default_factory=dict)
    owner: Dict[str, Any] = field(default_factory=dict)
    can_reply: bool = True
    can_reshare: bool = True
    can_save: bool = True
    supports_reel_reactions: bool = True
    creative_config: Dict[str, Any] = field(default_factory=dict)
    caption: Optional[str] = None
    tagged_users: List[Dict[str, Any]] = field(default_factory=list)
    crosspost: List[str] = field(default_factory=list)
    filter_type: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

def _ensure_unix_timestamp(value: Any, default: Optional[int] = None) -> Optional[int]:
    if value is None:
        return default
    try:
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            # Attempt to parse ISO date string
            try:
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return int(dt.replace(tzinfo=timezone.utc).timestamp())
            except ValueError:
                return int(float(value))
    except Exception:  # pragma: no cover - defensive
        logger.debug("Failed to coerce value '%s' to timestamp", value)
    return default

def _format_iso(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()

def _infer_expiring_at(taken_at: int, raw: Dict[str, Any]) -> int:
    existing = _ensure_unix_timestamp(raw.get("expiring_at"))
    if existing is not None:
        return existing
    # Instagram stories expire after 24 hours
    return int((datetime.fromtimestamp(taken_at, tz=timezone.utc) + timedelta(hours=24)).timestamp())

def _normalize_media_versions(raw_versions: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw_versions, Iterable):
        return []
    normalized: List[Dict[str, Any]] = []
    for v in raw_versions:
        if not isinstance(v, dict):
            continue
        normalized.append(
            {
                "url": v.get("url"),
                "width": v.get("width"),
                "height": v.get("height"),
                "id": v.get("id"),
                "type": v.get("type"),
            }
        )
    return normalized

def _extract_user(raw: Dict[str, Any]) -> UserInfo:
    user_data = raw.get("user") or raw.get("owner") or {}
    return UserInfo.from_raw(user_data)

def _extract_caption(raw: Dict[str, Any]) -> Optional[str]:
    caption = raw.get("caption")
    if isinstance(caption, dict):
        return caption.get("text") or caption.get("caption_text")
    if isinstance(caption, str):
        return caption
    return None

def _normalize_story(raw: Dict[str, Any]) -> Story:
    if not isinstance(raw, dict):
        raise ValueError("Each story item must be a JSON object")

    story_id = str(raw.get("id") or raw.get("pk") or "")
    if not story_id:
        raise ValueError("Story item is missing an 'id' or 'pk' field")

    code = raw.get("code") or raw.get("shortcode")
    fbid = raw.get("fbid") or raw.get("facebook_id")
    media_type = int(raw.get("media_type", 1))
    product_type = str(raw.get("product_type") or "story")

    taken_at_ts = _ensure_unix_timestamp(raw.get("taken_at"))
    if taken_at_ts is None:
        # If we really don't have a timestamp, fall back to "now"
        taken_at_ts = int(datetime.now(tz=timezone.utc).timestamp())
        logger.debug("No 'taken_at' found for story %s; defaulting to now()", story_id)

    taken_at_date = raw.get("taken_at_date")
    if not taken_at_date:
        taken_at_date = _format_iso(taken_at_ts)

    expiring_at_ts = _infer_expiring_at(taken_at_ts, raw)

    video_versions_raw = raw.get("video_versions") or []
    image_versions_raw = raw.get("image_versions2", {}).get("candidates") or raw.get("image_versions") or []

    video_versions = _normalize_media_versions(video_versions_raw)
    image_versions = _normalize_media_versions(image_versions_raw)

    thumbnail_url = raw.get("thumbnail_url")
    if not thumbnail_url and image_versions:
        best_image = choose_best_version(image_versions)
        thumbnail_url = best_image.get("url")

    video_url = raw.get("video_url")
    if not video_url and video_versions:
        best_video = choose_best_version(video_versions)
        video_url = best_video.get("url")

    video_duration = None
    if "video_duration" in raw:
        try:
            video_duration = float(raw.get("video_duration"))
        except (TypeError, ValueError):
            logger.debug("Invalid video_duration for story %s", story_id)

    video_codec = raw.get("video_codec")
    has_audio = bool(raw.get("has_audio", False))

    original_width = None
    original_height = None
    if raw.get("original_width") is not None:
        try:
            original_width = int(raw.get("original_width"))
        except (TypeError, ValueError):
            logger.debug("Invalid original_width for story %s", story_id)
    if raw.get("original_height") is not None:
        try:
            original_height = int(raw.get("original_height"))
        except (TypeError, ValueError):
            logger.debug("Invalid original_height for story %s", story_id)

    user_info = _extract_user(raw)
    user_dict = asdict(user_info)

    can_reply = bool(raw.get("can_reply", True))
    can_reshare = bool(raw.get("can_reshare", True))
    can_save = bool(raw.get("can_save", True))
    supports_reel_reactions = bool(raw.get("supports_reel_reactions", True))

    creative_config = raw.get("creative_config") or {}
    if not isinstance(creative_config, dict):
        creative_config = {}

    tagged_users = raw.get("tagged_users") or []
    if not isinstance(tagged_users, list):
        tagged_users = []

    crosspost = raw.get("crosspost") or []
    if not isinstance(crosspost, list):
        crosspost = []

    filter_type = None
    if raw.get("filter_type") is not None:
        try:
            filter_type = int(raw.get("filter_type"))
        except (TypeError, ValueError):
            logger.debug("Invalid filter_type for story %s", story_id)

    caption = _extract_caption(raw)

    story = Story(
        id=story_id,
        code=code,
        fbid=fbid,
        media_type=media_type,
        product_type=product_type,
        taken_at=taken_at_ts,
        taken_at_date=taken_at_date,
        expiring_at=expiring_at_ts,
        video_url=video_url,
        video_duration=video_duration,
        video_codec=video_codec,
        video_versions=video_versions,
        thumbnail_url=thumbnail_url,
        image_versions=image_versions,
        has_audio=has_audio,
        original_width=original_width,
        original_height=original_height,
        user=user_dict,
        owner=user_dict.copy(),
        can_reply=can_reply,
        can_reshare=can_reshare,
        can_save=can_save,
        supports_reel_reactions=supports_reel_reactions,
        creative_config=creative_config,
        caption=caption,
        tagged_users=tagged_users,
        crosspost=crosspost,
        filter_type=filter_type,
    )
    logger.debug("Normalized story %s", story_id)
    return story

def parse_stories(raw: Any) -> List[Dict[str, Any]]:
    """
    Parse a raw Instagram stories JSON payload into a normalized list
    of story dictionaries following the shape described in the README.
    """
    items: List[Dict[str, Any]]
    if isinstance(raw, dict):
        if "items" in raw and isinstance(raw["items"], list):
            items = raw["items"]
        else:
            # Treat dict as a single story object
            items = [raw]
    elif isinstance(raw, list):
        items = raw
    else:
        raise ValueError("Root JSON must be an object or an array")

    normalized: List[Dict[str, Any]] = []
    for idx, item in enumerate(items):
        try:
            story = _normalize_story(item)
            normalized.append(story.to_dict())
        except Exception as exc:
            logger.warning("Skipping invalid story at index %d: %s", idx, exc)
    return normalized