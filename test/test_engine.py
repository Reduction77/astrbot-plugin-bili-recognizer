"""Run with python -m unittest discover -s test -p test_engine.py."""
import asyncio
import logging
from pathlib import Path
import tempfile
import unittest

from engine import Engine


class EngineTest(unittest.IsolatedAsyncioTestCase):
    async def test_onebot_roundtrip_web_config_and_reload(self):
        messages = []

        async def action(method, params):
            if method == "get_group_list":
                return [{"group_id": 17, "group_name": "test"}]
            self.assertEqual(method, "send_msg")
            messages.append(params)
            return {"message_id": 1}

        with tempfile.TemporaryDirectory() as directory:
            for first in (True, False):
                engine = Engine(action, logging.getLogger("test"))
                try:
                    routes = await engine.start(Path(directory))
                    self.assertIn("GET /downloads/file/:id", routes)

                    async def web(route, body=None):
                        result = await engine.call("web", {"route": route, "body": body, "params": {}})
                        return result["body"]["data"]

                    groups, config = await asyncio.gather(web("GET /groups"), web("GET /config"))
                    self.assertEqual(groups["groups"][0]["id"], "17")
                    if first:
                        await web("POST /config", {"config": {"showCover": False}, "revision": config["revision"]})
                        await engine.call("message", {
                            "post_type": "message", "message_type": "group", "group_id": 17,
                            "user_id": 11, "self_id": 42, "message_id": 10,
                            "message": [{"type": "text", "data": {"text": "/bili下载"}}],
                        })
                        self.assertEqual(messages[0]["group_id"], "17")
                        self.assertIn("用法", messages[0]["message"][0]["data"]["text"])
                    else:
                        self.assertFalse(config["config"]["showCover"])
                finally:
                    await engine.close()
                self.assertEqual(engine.process.returncode, 0)
