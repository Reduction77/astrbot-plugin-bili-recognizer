"""Routing and delivery for QQ Official group and C2C messages."""
import base64
import re
import secrets
from types import SimpleNamespace


def destination(platform_id, openid):
    platform = base64.urlsafe_b64encode(platform_id.encode()).decode().rstrip("=")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", platform) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", openid):
        raise ValueError("无效的官方 QQ 平台 ID 或 OpenID")
    return f"qqo.{platform}.{openid}"


def unpack_destination(value):
    _, encoded, openid = value.split(".")
    platform = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode()
    if destination(platform, openid) != value:
        raise ValueError("无效的官方 QQ 目标")
    return platform, openid


async def send_official(client, group, openid, segments, reply_id, media_path):
    # Import lazily so OneBot-only installations do not need the QQ SDK.
    from astrbot.core.platform.sources.qqofficial.qqofficial_message_event import QQOfficialMessageEvent as QQ

    helper = SimpleNamespace(bot=client)
    target = {"group_openid" if group else "openid": openid}
    text = "\n".join(s["data"]["text"] for s in segments if s["type"] == "text")
    files = [s for s in segments if s["type"] in {"video", "image"}]
    # QQ accepts one media object per message. Attach the caption to the last one.
    for index, segment in enumerate(files or [None]):
        payload = dict(target, msg_type=0, msg_seq=secrets.randbelow(999999) + 1)
        if reply_id:
            payload["msg_id"] = reply_id
        if segment:
            kind = segment["type"]
            source = media_path(kind, segment["data"]["file"])
            media_type = QQ.VIDEO_FILE_TYPE if kind == "video" else QQ.IMAGE_FILE_TYPE
            payload["media"] = await QQ.upload_group_and_c2c_media(helper, str(source), media_type, **target)
            payload["msg_type"] = 7
        if text and index == max(len(files) - 1, 0):
            payload["content"] = text
        if group:
            receipt = await client.api.post_group_message(**payload)
        else:
            receipt = await QQ.post_c2c_message(helper, **payload)
        if not receipt:
            raise RuntimeError("QQ 官方机器人未返回发送回执")
