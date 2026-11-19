"""AstrBot host for the Bilibili recognizer."""
import asyncio
import base64
from pathlib import Path
from urllib.request import url2pathname

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, StarTools
from astrbot.api.web import error_response, json_response, request, stream_response

from .engine import Engine
from .qq_official import destination, send_official, unpack_destination

NAME = "astrbot_plugin_bili_recognizer"


class BiliRecognizer(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.platform_id = str(config.get("platform_id", "")).strip()
        self.directory = StarTools.get_data_dir(NAME)
        self.engine = Engine(self._action, logger)
        self.handlers = set()
        self.binding_lock = asyncio.Lock()
        self.official_groups = {}

    async def initialize(self):
        try:
            self.official_groups = await self.get_kv_data("official_groups", {}) or {}
            for route in await self.engine.start(self.directory):
                method, path = route.split(" ", 1)
                handler = self._handler(method, route)
                self.handlers.add(handler)
                self.context.register_web_api(
                    f"/{NAME}{path.replace(':id', '<id>')}",
                    handler, [method], "B站识别控制台",
                )
        except BaseException:
            await self.terminate()
            raise

    def _platform(self):
        if self.platform_id:
            platform = self.context.get_platform_inst(self.platform_id)
            if platform and platform.meta().name == "aiocqhttp":
                return platform
        else:
            platforms = [p for p in self.context.platform_manager.platform_insts
                         if p.meta().name == "aiocqhttp"]
            if len(platforms) == 1:
                return platforms[0]
        raise RuntimeError("请在插件配置中指定有效的 OneBot v11 平台实例 ID")

    async def _action(self, method, params):
        if method == "get_group_list":
            bound = self.official_groups
            groups = [
                {"group_id": key, "group_name": label}
                for key, label in bound.items()
                if self.context.get_platform_inst(unpack_destination(key)[0])
            ]
            onebots = [p for p in self.context.platform_manager.platform_insts if p.meta().name == "aiocqhttp"]
            if onebots:
                try:
                    rows = await self._platform().get_client().call_action(method)
                    groups.extend(rows if isinstance(rows, list) else rows["data"])
                except Exception:
                    if not groups:
                        raise
                    logger.warning("OneBot 群列表暂时不可用，仅显示已绑定的官方 QQ 群")
            return groups
        if method != "send_msg":
            raise ValueError("未知 QQ 操作")
        group = params["message_type"] == "group"
        key = params["group_id" if group else "user_id"]
        if key.startswith("qqo."):
            instance, openid = unpack_destination(key)
            platform = self.context.get_platform_inst(instance)
            if not platform or platform.meta().name != "qq_official":
                raise RuntimeError("目标 QQ 官方机器人实例不可用")
            await send_official(platform.get_client(), group, openid, params["message"],
                                params.get("reply_id"), self._media_path)
            return {"status": "ok"}
        client = self._platform().get_client()
        for segment in params["message"]:
            if segment["type"] not in {"image", "video"}:
                continue
            data = segment["data"]
            path = self._media_path(segment["type"], data["file"])
            if isinstance(path, str):
                continue
            # NapCat may run on another host and cannot read AstrBot's filesystem.
            def encode():
                return "base64://" + base64.b64encode(path.read_bytes()).decode("ascii")
            data["file"] = await asyncio.to_thread(encode)
        return await client.call_action(method, **params)

    def _media_path(self, kind, source):
        if source.startswith(("https://", "http://")):
            return source
        path = Path(url2pathname(source[7:]) if source.startswith("file://") else source).resolve()
        folder = "downloads" if kind == "video" else "live-cards"
        if not path.is_relative_to((self.directory / folder).resolve()):
            raise ValueError("媒体路径无效")
        return path

    async def _official_message(self, event):
        msg = event.message_obj
        raw = msg.raw_message
        raw_data = raw if isinstance(raw, dict) else getattr(raw, "raw_data", None)
        # Guild channels use a different QQ API from groups and C2C chats.
        if getattr(raw, "channel_id", None) or (isinstance(raw_data, dict) and raw_data.get("channel_id")):
            return
        group = event.get_group_id()
        sender = event.get_sender_id()
        content = (event.get_message_str() or "").strip()
        binding = content.lstrip("/") == "bili绑定"
        if not sender or sender == event.get_self_id():
            if binding:
                logger.warning("收到官方 QQ 绑定指令，但缺少可用的发送者身份")
            return
        instance = event.get_platform_id()
        target = destination(instance, group) if group else None
        if binding:
            logger.info("收到官方 QQ 绑定指令，平台=%s，群消息=%s", instance, bool(group))
            if not group:
                await event.send(event.plain_result("请在目标 QQ 群里 @机器人 并发送 /bili绑定。"))
                return
        if group:
            name = getattr(getattr(msg, "group", None), "group_name", None)
            label = f"{instance} · {name or group}"
            if target not in self.official_groups or (name and self.official_groups[target] != label):
                async with self.binding_lock:
                    if target not in self.official_groups or (name and self.official_groups[target] != label):
                        updated = {**self.official_groups, target: label}
                        await self.put_kv_data("official_groups", updated)
                        self.official_groups = updated
                        logger.info("已登记官方 QQ 群，平台=%s", instance)
        if group and binding:
            await event.send(event.plain_result("本群已绑定，可在直播订阅的群列表中选择。"))
            event.stop_event()
            return
        if content.split(maxsplit=1)[:1] in (["bili下载"], ["下载视频"]):
            content = "/" + content
        segments = [{"type": "text", "data": {"text": content}}]
        if isinstance(raw_data, dict):
            for key in ("ark", "json", "xml"):
                share = raw_data.get(key)
                if isinstance(share, (dict, str)):
                    segments.append({"type": "xml" if key == "xml" else "json", "data": {"data": share}})
        await self.engine.call("message", {
            "post_type": "message", "message_type": "group" if group else "private",
            "group_id": target, "user_id": destination(instance, sender),
            "message": segments, "message_id": msg.message_id, "reply_id": msg.message_id,
        })

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent):
        if event.get_platform_name() == "qq_official":
            await self._official_message(event)
            return
        if event.get_platform_name() != "aiocqhttp":
            return
        if self.platform_id and self.platform_id != event.get_platform_id():
            return
        if self._platform().meta().id != event.get_platform_id():
            return
        raw = event.message_obj.raw_message
        keys = ("post_type", "message_type", "sub_type", "self_id", "user_id",
                "group_id", "message_id", "raw_message", "message")
        await self.engine.call("message", {k: raw.get(k) for k in keys})

    def _handler(self, method, route):
        async def handle(**params):
            body = await request.json(default={}) if method == "POST" else None
            result = await self.engine.call("web", {"route": route, "params": params, "body": body})
            if "file" in result:
                async def chunks():
                    try:
                        with open(result["file"], "rb") as file:
                            while chunk := await asyncio.to_thread(file.read, 256 * 1024):
                                yield chunk
                    finally:
                        await self.engine.call("release", result["lease"])
                return stream_response(chunks(), content_type="video/mp4")
            reply = result["body"]
            if reply["code"]:
                return error_response(reply["message"], status_code=result.get("status", 400))
            return json_response(reply["data"], headers={"Cache-Control": "no-store"})
        return handle

    async def terminate(self):
        routes = self.context.registered_web_apis
        routes[:] = [entry for entry in routes if entry[1] not in self.handlers]
        self.handlers.clear()
        await self.engine.close()
