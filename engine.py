"""Duplex RPC over the private stdin/stdout of the bundled JS engine."""
import asyncio
import json
from pathlib import Path



class Engine:
    def __init__(self, action, logger):
        self.logger = logger
        self.action = action
        self.process = None
        self.reader = None
        self.tasks = set()
        self.pending = {}
        self.serial = 0

    async def start(self, directory):
        directory.mkdir(parents=True, exist_ok=True)
        try:
            self.process = await asyncio.create_subprocess_exec(
                "node", str(Path(__file__).parent / "lib" / "worker.mjs"), str(directory),
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                limit=64 * 1024 * 1024,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("请在 AstrBot 运行环境安装 Node.js 20.3 或更高版本") from exc
        self.reader = asyncio.create_task(self._read())
        return await self.call("init")

    async def write(self, packet):
        pipe = self.process.stdin
        pipe.write(json.dumps(packet, ensure_ascii=False).encode() + b"\n")
        await pipe.drain()

    async def call(self, method, args=None):
        if not self.reader or self.reader.done():
            raise RuntimeError("B站插件引擎已停止，请重载插件")
        self.serial += 1
        key = self.serial
        future = asyncio.get_running_loop().create_future()
        self.pending[key] = future
        try:
            await self.write({"id": key, "method": method, "args": args})
            return await future
        finally:
            self.pending.pop(key, None)

    async def _action(self, packet):
        response = {"actionId": packet["actionId"]}
        try:
            response["result"] = await asyncio.wait_for(
                self.action(packet["method"], packet["params"]), 120
            )
        except Exception as exc:
            response["error"] = type(exc).__name__
        try:
            await self.write(response)
        except (BrokenPipeError, ConnectionResetError):
            pass

    async def _read(self):
        try:
            async for line in self.process.stdout:
                packet = json.loads(line)
                if "actionId" in packet:
                    task = asyncio.create_task(self._action(packet))
                    self.tasks.add(task)
                    task.add_done_callback(self.tasks.discard)
                elif "level" in packet:
                    level = {"warn": "warning"}.get(packet["level"], packet["level"])
                    getattr(self.logger, level)(packet["message"])
                else:
                    future = self.pending.get(packet["id"])
                    if future and not future.done():
                        if "error" in packet:
                            future.set_exception(RuntimeError(packet["error"]))
                        else:
                            future.set_result(packet["result"])
        finally:
            for future in self.pending.values():
                if not future.done():
                    future.set_exception(RuntimeError("B站插件引擎连接中断"))

    async def close(self):
        if not self.process:
            return
        try:
            await asyncio.wait_for(self.call("close"), 10)
        except (RuntimeError, TimeoutError, ConnectionError):
            pass
        self.process.stdin.close()
        try:
            await asyncio.wait_for(self.process.wait(), 5)
        except TimeoutError:
            self.process.kill()
            await self.process.wait()
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(self.reader, *self.tasks, return_exceptions=True)
