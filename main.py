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

NAME = "astrbot_plugin_bili_recognizer"


class BiliRecognizer(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.platform_id = str(config.get("platform_id", "")).strip()
        self.directory = StarTools.get_data_dir(NAME)
        self.engine = Engine(self._action, logger)
        self.handlers = set()

    async def initialize(self):
        try:
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
        client = self._platform().get_client()
        if method == "get_group_list":
            return await client.call_action(method)
        if method != "send_msg":
            raise ValueError("未知 OneBot 操作")
        for segment in params["message"]:
            if segment["type"] not in {"image", "video"}:
                continue
            data = segment["data"]
            source = data["file"]
            if source.startswith(("https://", "http://")):
                continue
            path = Path(url2pathname(source[7:]) if source.startswith("file://") else source).resolve()
            folder = "downloads" if segment["type"] == "video" else "live-cards"
            if not path.is_relative_to((self.directory / folder).resolve()):
                raise ValueError("媒体路径无效")
            # NapCat may run on another host and cannot read AstrBot's filesystem.
            def encode():
                return "base64://" + base64.b64encode(path.read_bytes()).decode("ascii")
            data["file"] = await asyncio.to_thread(encode)
        return await client.call_action(method, **params)

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent):
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
