import sys
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from qq_official import destination, send_official, unpack_destination


class OfficialDeliveryTest(unittest.IsolatedAsyncioTestCase):
    async def test_account_routing_and_media(self):
        key = destination("官方", "group123")
        self.assertEqual(unpack_destination(key), ("官方", "group123"))
        self.assertNotEqual(key, destination("备用", "group123"))
        api = SimpleNamespace(post_group_message=AsyncMock(return_value={"id": "ok"}))
        client = SimpleNamespace(api=api)
        qq = SimpleNamespace(IMAGE_FILE_TYPE=1, VIDEO_FILE_TYPE=2,
                             upload_group_and_c2c_media=AsyncMock(return_value={"file_info": "ok"}),
                             post_c2c_message=AsyncMock(return_value={"id": "ok"}))
        module = "astrbot.core.platform.sources.qqofficial.qqofficial_message_event"
        with patch.dict(sys.modules, {module: SimpleNamespace(QQOfficialMessageEvent=qq)}):
            await send_official(client, True, "group123", [
                {"type": "image", "data": {"file": "cover"}},
                {"type": "text", "data": {"text": "开播"}},
            ], None, lambda kind, source: source)
            params = api.post_group_message.await_args.kwargs
            self.assertEqual(params["group_openid"], "group123")
            self.assertNotIn("msg_id", params)
            self.assertEqual(params["content"], "开播")
            self.assertEqual(params["msg_type"], 7)
            await send_official(client, False, "user123", [
                {"type": "video", "data": {"file": "video.mp4"}},
            ], "message123", lambda kind, source: source)
            self.assertEqual(qq.post_c2c_message.await_args.kwargs["msg_id"], "message123")
            self.assertEqual(qq.post_c2c_message.await_args.kwargs["openid"], "user123")
            api.post_group_message.return_value = None
            with self.assertRaises(RuntimeError):
                await send_official(client, True, "group123", [
                    {"type": "text", "data": {"text": "下播"}},
                ], None, None)
