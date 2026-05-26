import asyncio
import atexit
import base64
import json
import os
import time
from pathlib import Path

import aiohttp

from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register, StarTools
from astrbot.api import logger
from astrbot.api.all import *
from astrbot.api.message_components import Image, Video, Record
from astrbot.core.utils.astrbot_path import get_astrbot_plugin_data_path


@register(
    "astrbot_plugin_minimax_media",
    "angela-hykt",
    "对接 MiniMax Token Plan API 实现文生图、图生图、文生视频、图生视频、音乐生成",
    "1.0.0",
    "https://github.com/angela-hykt/astrbot_plugin_minimax_media",
)
class MiniMaxMediaPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config

        mm_config = config.get("minimax_config", {})
        self.token_plan_key = mm_config.get("token_plan_key", "")
        self.base_url = mm_config.get("base_url", "https://api.minimaxi.com").rstrip("/")

        img_config = config.get("image_config", {})
        self.image_model = img_config.get("image_model", "image-01")
        self.aspect_ratio = img_config.get("aspect_ratio", "16:9")
        self.image_width = max(0, int(img_config.get("width", 0)))
        self.image_height = max(0, int(img_config.get("height", 0)))
        self.image_n = min(max(int(img_config.get("image_n", 1)), 1), 9)

        vid_config = config.get("video_config", {})
        self.video_model = vid_config.get("video_model", "MiniMax-Hailuo-2.3")
        self.video_duration = int(vid_config.get("duration", 6))
        self.video_resolution = vid_config.get("resolution", "768P")

        mus_config = config.get("music_config", {})
        self.music_model = mus_config.get("music_model", "music-2.6")
        self.lyrics_optimizer = bool(mus_config.get("lyrics_optimizer", True))
        self.audio_format = mus_config.get("audio_format", "mp3")
        self.audio_sample_rate = int(mus_config.get("sample_rate", 44100))
        self.audio_bitrate = int(mus_config.get("bitrate", 128000))

        ref_config = config.get("reference_config", {})
        self.default_persona = ref_config.get("default_persona", "")
        self.default_reference_image = ref_config.get("default_reference_image", "")
        self._reference_images_cache = None
        self._uploaded_reference_images: list[str] = []
        uploaded_raw = ref_config.get("uploaded_reference_images", []) or []
        if uploaded_raw:
            plugin_data_dir = Path(get_astrbot_plugin_data_path()) / "astrbot_plugin_minimax_media"
            for rel_path in uploaded_raw:
                full_path = plugin_data_dir / rel_path
                if os.path.exists(full_path):
                    self._uploaded_reference_images.append(str(full_path))
        self._last_generated_images: list[str] = []

        self._download_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "downloads"
        )
        os.makedirs(self._download_dir, exist_ok=True)

        if not self.token_plan_key:
            logger.warning("MiniMax token_plan_key is empty! Please configure it in the plugin settings.")

        self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60))
        atexit.register(self._cleanup_session)

    def _cleanup_session(self):
        """Synchronously close the aiohttp session at exit."""
        if hasattr(self, "_session") and self._session and not self._session.closed:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._close_session())
                else:
                    loop.run_until_complete(self._close_session())
            except Exception:
                pass

    async def _close_session(self):
        """Close the aiohttp session safely."""
        if hasattr(self, "_session") and self._session and not self._session.closed:
            try:
                await self._session.close()
            except Exception:
                pass

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token_plan_key}",
            "Content-Type": "application/json",
        }

    def _get_download_path(self, prefix: str, ext: str) -> str:
        ts = int(time.time() * 1000)
        return os.path.join(self._download_dir, f"{prefix}_{ts}.{ext}")

    async def _download_file(self, url: str, dest: str) -> str:
        async with self._session.get(url) as resp:
            resp.raise_for_status()
            with open(dest, "wb") as f:
                f.write(await resp.read())
        return dest

    async def _async_post(self, endpoint: str, json_data: dict = None) -> dict:
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers()
        async with self._session.post(url, headers=headers, json=json_data) as resp:
            if not resp.ok:
                return {"base_resp": {"status_code": resp.status, "status_msg": f"HTTP {resp.status}"}}
            return await resp.json()

    async def _async_get(self, url: str) -> dict:
        headers = self._get_headers()
        async with self._session.get(url, headers=headers) as resp:
            if not resp.ok:
                return {"base_resp": {"status_code": resp.status, "status_msg": f"HTTP {resp.status}"}}
            return await resp.json()

    async def _read_image_as_base64(self, image_path: str) -> str:
        if image_path.startswith(("http://", "https://")):
            async with self._session.get(image_path) as resp:
                data = await resp.read()
        elif os.path.exists(image_path):
            with open(image_path, "rb") as f:
                data = f.read()
        else:
            raise FileNotFoundError(f"图片文件不存在: {image_path}")
        return base64.b64encode(data).decode("utf-8")

    async def _poll_video_task(self, task_id: str, interval: int = 5, timeout: int = 300) -> dict:
        url = f"{self.base_url}/v1/video_generation/query/{task_id}"
        deadline = time.time() + timeout
        while time.time() < deadline:
            result = await self._async_get(url)
            status = result.get("status", "")
            if status == "Success":
                return result
            if status == "Failed":
                raise Exception(f"视频生成失败: {result.get('msg', '未知错误')}")
            await asyncio.sleep(interval)
        raise TimeoutError("视频生成超时")

    async def _send_image_result(self, event: AstrMessageEvent, image_urls: list[str], image_base64s: list[str] = None):
        components = []
        generated = []
        if image_urls:
            for url in image_urls:
                ext = url.rsplit(".", 1)[-1].split("?")[0] if "." in url else "png"
                dest = self._get_download_path("minimax_img", ext)
                await self._download_file(url, dest)
                components.append(Image(file=dest))
                generated.append(dest)
        if image_base64s:
            for b64 in image_base64s:
                dest = self._get_download_path("minimax_img", "png")
                with open(dest, "wb") as f:
                    f.write(base64.b64decode(b64))
                components.append(Image(file=dest))
                generated.append(dest)
        self._last_generated_images = generated
        if components:
            yield event.chain_result(components)

    def _find_image_in_message(self, event: AstrMessageEvent):
        for comp in event.message_obj.message:
            if isinstance(comp, Image):
                path = comp.file
                if os.path.exists(path):
                    return path
                if os.sep not in path and not path.startswith("."):
                    fallback = os.path.join(self._download_dir, path)
                    if os.path.exists(fallback):
                        return fallback
                    for root, dirs, files in os.walk(self._download_dir):
                        if path in files:
                            return os.path.join(root, path)
                if path.startswith("http"):
                    return path
                return None
        if self._last_generated_images:
            return self._last_generated_images[-1]
        return None

    def _get_reference_images(self) -> list:
        if self._reference_images_cache is not None:
            return self._reference_images_cache
        raw = self.config.get("reference_config", {}).get("reference_images_json", "[]")
        try:
            refs = json.loads(raw) if isinstance(raw, str) else raw
            if isinstance(refs, list):
                self._reference_images_cache = refs
                return refs
        except (json.JSONDecodeError, TypeError):
            pass
        return []

    def _build_prompt_with_persona(self, prompt: str, use_persona: bool = True) -> str:
        if use_persona and self.default_persona:
            return f"{self.default_persona}\n{prompt}"
        return prompt

    def _is_private_url(self, url: str) -> bool:
        if not url.startswith("http"):
            return False
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            host = parsed.hostname or ""
            if host in ("localhost", "127.0.0.1", "::1"):
                return True
            if host.startswith(("192.168.", "10.", "172.16.", "172.17.", "172.18.", "172.19.",
                               "172.20.", "172.21.", "172.22.", "172.23.", "172.24.",
                               "172.25.", "172.26.", "172.27.", "172.28.", "172.29.",
                               "172.30.", "172.31.")):
                return True
            if host == "0.0.0.0":
                return True
        except Exception:
            pass
        return False

    async def _url_to_local_file(self, url: str) -> str:
        dest = self._get_download_path("ref_img", "png")
        await self._download_file(url, dest)
        return dest

    async def _resolve_reference_image(self, event: AstrMessageEvent, ref_name: str = "") -> str:
        image_file = self._find_image_in_message(event)
        if image_file:
            return image_file

        if ref_name:
            refs = self._get_reference_images()
            for r in refs:
                if r.get("name", "") == ref_name:
                    url = r.get("url", "")
                    if self._is_private_url(url):
                        return await self._url_to_local_file(url)
                    return url
            return ""

        if self.default_reference_image:
            url = self.default_reference_image
            if self._is_private_url(url):
                return await self._url_to_local_file(url)
            return url

        if self._uploaded_reference_images:
            return self._uploaded_reference_images[0]

        return ""

    def _maybe_add_size(self, payload: dict):
        if self.image_width > 0 and self.image_height > 0:
            w = (self.image_width // 8) * 8
            h = (self.image_height // 8) * 8
            payload["width"] = min(max(w, 512), 2048)
            payload["height"] = min(max(h, 512), 2048)

    async def _image_to_subject_ref(self, image_file: str) -> list:
        image_b64 = await self._read_image_as_base64(image_file)
        if image_file.startswith(("http://", "https://")):
            mime_type = "image/jpeg"
        else:
            ext = os.path.splitext(image_file)[-1].lower()
            if ext in (".png",):
                mime_type = "image/png"
            elif ext in (".gif",):
                mime_type = "image/gif"
            elif ext in (".webp",):
                mime_type = "image/webp"
            else:
                mime_type = "image/jpeg"
        return [{"type": "character", "image_file": f"data:{mime_type};base64,{image_b64}"}]

    async def _upload_image_for_video(self, image_file: str) -> str:
        if image_file.startswith(("http://", "https://")):
            return image_file
        if not os.path.exists(image_file):
            raise FileNotFoundError(f"图片文件不存在: {image_file}")
        upload_url = f"{self.base_url}/v1/files/upload"
        headers = self._get_headers()
        data = aiohttp.FormData()
        ext = os.path.splitext(image_file)[-1].lower() or ".png"
        filename = f"frame{ext}"
        with open(image_file, "rb") as f:
            data.add_field("file", f, filename=filename)
        async with self._session.post(upload_url, headers=headers, data=data) as resp:
            upload_result = await resp.json()
        if upload_result.get("base_resp", {}).get("status_code") != 0:
            raise Exception("图片上传失败")
        return upload_result.get("data", {}).get("file_url", "")

    # ==================== 命令处理器 ====================

    @filter.command("minimax_t2i")
    async def text_to_image_cmd(self, event: AstrMessageEvent, prompt: str = ""):
        """文生图。用法：/minimax_t2i <提示词> [--no-persona]"""
        if not prompt:
            yield event.plain_result("请输入提示词，例如: /minimax_t2i 一只可爱的猫咪")
            return

        use_persona = True
        tokens = prompt.split()
        cleaned = []
        for t in tokens:
            if t == "--no-persona":
                use_persona = False
            else:
                cleaned.append(t)
        prompt = " ".join(cleaned)

        final_prompt = self._build_prompt_with_persona(prompt, use_persona)
        yield event.plain_result("🎨 MiniMax 文生图中...")
        try:
            payload = {
                "model": self.image_model,
                "prompt": final_prompt,
                "aspect_ratio": self.aspect_ratio,
            }
            self._maybe_add_size(payload)
            result = await self._async_post("/v1/image_generation", payload)
            if result.get("base_resp", {}).get("status_code") != 0:
                msg = result.get("base_resp", {}).get("status_msg", "未知错误")
                yield event.plain_result(f"❌ 文生图失败: {msg}")
                return
            image_urls = result.get("data", {}).get("image_urls", [])
            image_base64s = result.get("data", {}).get("image_base64s", [])
            if not image_urls and not image_base64s:
                yield event.plain_result("❌ 未生成图片")
                return
            async for chain in self._send_image_result(event, image_urls, image_base64s):
                yield chain
        except Exception as e:
            yield event.plain_result(f"❌ 文生图出错: {e}")

    @filter.command("minimax_i2i")
    async def image_to_image_cmd(self, event: AstrMessageEvent, prompt: str = ""):
        """图生图。用法：/minimax_i2i <提示词> [--ref <图库名>] [--no-persona]"""
        if not prompt:
            yield event.plain_result("请输入提示词并附带一张参考图片")
            return

        ref_name = ""
        use_persona = True
        tokens = prompt.split()
        rest = []
        skip_next = False
        for i, t in enumerate(tokens):
            if skip_next:
                skip_next = False
                continue
            if t == "--ref" and i + 1 < len(tokens):
                ref_name = tokens[i + 1]
                skip_next = True
            elif t == "--no-persona":
                use_persona = False
            else:
                rest.append(t)
        prompt = " ".join(rest)

        image_file = await self._resolve_reference_image(event, ref_name)
        if not image_file:
            yield event.plain_result("未找到参考图片，请附带一张图片、设置默认参考图 URL，或指定图库名称")
            return

        final_prompt = self._build_prompt_with_persona(prompt, use_persona)
        yield event.plain_result("🎨 MiniMax 图生图中...")
        try:
            subject_ref = await self._image_to_subject_ref(image_file)
            payload = {
                "model": self.image_model,
                "prompt": final_prompt,
                "aspect_ratio": self.aspect_ratio,
                "subject_reference": subject_ref,
            }
            self._maybe_add_size(payload)
            result = await self._async_post("/v1/image_generation", payload)
            if result.get("base_resp", {}).get("status_code") != 0:
                msg = result.get("base_resp", {}).get("status_msg", "未知错误")
                yield event.plain_result(f"❌ 图生图失败: {msg}")
                return
            image_urls = result.get("data", {}).get("image_urls", [])
            image_base64s = result.get("data", {}).get("image_base64s", [])
            if not image_urls and not image_base64s:
                yield event.plain_result("❌ 未生成图片")
                return
            async for chain in self._send_image_result(event, image_urls, image_base64s):
                yield chain
        except Exception as e:
            yield event.plain_result(f"❌ 图生图出错: {e}")

    @filter.command("minimax_t2v")
    async def text_to_video_cmd(self, event: AstrMessageEvent, prompt: str = ""):
        """文生视频。用法：/minimax_t2v <提示词>"""
        if not prompt:
            yield event.plain_result("请输入提示词，例如: /minimax_t2v 一只在草地上奔跑的狗")
            return

        yield event.plain_result("🎬 MiniMax 文生视频中，请耐心等待...")
        try:
            result = await self._async_post("/v1/video_generation", {
                "model": self.video_model,
                "prompt": prompt,
                "duration": self.video_duration,
                "resolution": self.video_resolution,
            })
            if result.get("base_resp", {}).get("status_code") != 0:
                msg = result.get("base_resp", {}).get("status_msg", "未知错误")
                yield event.plain_result(f"❌ 视频生成失败: {msg}")
                return

            task_id = result.get("data", {}).get("task_id", "")
            if not task_id:
                yield event.plain_result("❌ 未获取到任务 ID")
                return

            yield event.plain_result(f"⏳ 视频生成中 (任务ID: {task_id})...")
            poll_result = await self._poll_video_task(task_id)
            video_url = poll_result.get("data", {}).get("video_url", "")
            if not video_url:
                yield event.plain_result("❌ 未获取到视频链接")
                return

            dest = self._get_download_path("minimax_video", "mp4")
            await self._download_file(video_url, dest)
            yield event.chain_result([Video(file=dest)])
        except Exception as e:
            yield event.plain_result(f"❌ 文生视频出错: {e}")

    @filter.command("minimax_i2v")
    async def image_to_video_cmd(self, event: AstrMessageEvent, prompt: str = ""):
        """图生视频。用法：/minimax_i2v <提示词> [--ref <图库名>]"""
        if not prompt:
            yield event.plain_result("请输入提示词并附带一张参考图片")
            return

        ref_name = ""
        tokens = prompt.split()
        rest = []
        skip_next = False
        for i, t in enumerate(tokens):
            if skip_next:
                skip_next = False
                continue
            if t == "--ref" and i + 1 < len(tokens):
                ref_name = tokens[i + 1]
                skip_next = True
            else:
                rest.append(t)
        prompt = " ".join(rest)

        image_file = await self._resolve_reference_image(event, ref_name)
        if not image_file:
            yield event.plain_result("未找到参考图片，请附带一张图片、设置默认参考图 URL，或指定图库名称")
            return

        yield event.plain_result("🎬 MiniMax 图生视频中，请耐心等待...")
        try:
            first_frame_url = await self._upload_image_for_video(image_file)
            result = await self._async_post("/v1/video_generation", {
                "model": self.video_model,
                "prompt": prompt,
                "duration": self.video_duration,
                "resolution": self.video_resolution,
                "first_frame_image": first_frame_url,
            })
            if result.get("base_resp", {}).get("status_code") != 0:
                msg = result.get("base_resp", {}).get("status_msg", "未知错误")
                yield event.plain_result(f"❌ 图生视频失败: {msg}")
                return

            task_id = result.get("data", {}).get("task_id", "")
            if not task_id:
                yield event.plain_result("❌ 未获取到任务 ID")
                return

            yield event.plain_result(f"⏳ 视频生成中 (任务ID: {task_id})...")
            poll_result = await self._poll_video_task(task_id)
            video_url = poll_result.get("data", {}).get("video_url", "")
            if not video_url:
                yield event.plain_result("❌ 未获取到视频链接")
                return

            dest = self._get_download_path("minimax_video", "mp4")
            await self._download_file(video_url, dest)
            yield event.chain_result([Video(file=dest)])
        except Exception as e:
            yield event.plain_result(f"❌ 图生视频出错: {e}")

    @filter.command("minimax_refs")
    async def list_references_cmd(self, event: AstrMessageEvent):
        """查看配置的参考图库和默认人设。用法：/minimax_refs"""
        lines = ["📚 MiniMax 参考配置\n"]

        if self.default_persona:
            persona_preview = self.default_persona[:100]
            if len(self.default_persona) > 100:
                persona_preview += "..."
            lines.append(f"👤 默认人设: {persona_preview}\n")
        else:
            lines.append("👤 默认人设: (未设置)\n")

        if self.default_reference_image:
            lines.append(f"🖼️ 默认参考图: {self.default_reference_image}\n")
        else:
            lines.append("🖼️ 默认参考图: (未设置)\n")

        refs = self._get_reference_images()
        if refs:
            lines.append(f"\n📖 参考图库 ({len(refs)} 个):\n")
            for r in refs:
                name = r.get("name", "未命名")
                desc = r.get("desc", "")
                url = r.get("url", "")
                url_short = url[:60] + "..." if len(url) > 60 else url
                line = f"  · {name}"
                if desc:
                    line += f" - {desc}"
                line += f"\n    {url_short}\n"
                lines.append(line)
        else:
            lines.append("\n📖 参考图库: (空，可在设置中配置 reference_images_json)\n")

        lines.append("\n提示:")
        lines.append("  /minimax_i2i 提示词 --ref 名称  — 使用图库中的参考图")
        lines.append("  /minimax_i2v 提示词 --ref 名称  — 使用图库中的参考图")
        yield event.plain_result("\n".join(lines))

    # ==================== LLM 工具 ====================

    @filter.llm_tool(name="minimax_t2i")
    async def llm_text_to_image(
        self, event: AstrMessageEvent, prompt: str, aspect_ratio: str = "16:9", n: int = 1,
        prompt_optimizer: bool = False, seed: int = 0
    ) -> MessageEventResult:
        """使用 MiniMax image-01 模型根据文本描述生成图片。适合需要生成插画、设计图、概念图等场景。
        如果配置了默认人设，会自动拼接到提示词中。

        Args:
            prompt(string): 图片描述提示词，用英文或中文详细描述想要的画面内容
            aspect_ratio(string): 图片宽高比，可选 16:9, 1:1, 9:16, 4:3, 3:4, 21:9，默认 16:9
            n(int): 生成图片数量，1-9 张，默认 1
            prompt_optimizer(bool): 是否自动优化提示词，默认 false
            seed(int): 随机种子，相同种子可复现相近结果，默认 0 表示不指定
        """
        try:
            n = max(1, min(int(n) if n else 1, 9))
            final_prompt = self._build_prompt_with_persona(prompt)
            payload = {
                "model": self.image_model,
                "prompt": final_prompt,
                "aspect_ratio": aspect_ratio,
                "n": n,
            }
            if prompt_optimizer:
                payload["prompt_optimizer"] = True
            if seed > 0:
                payload["seed"] = seed
            self._maybe_add_size(payload)
            result = await self._async_post("/v1/image_generation", payload)
            if result.get("base_resp", {}).get("status_code") != 0:
                msg = result.get("base_resp", {}).get("status_msg", "未知错误")
                return event.plain_result(f"文生图失败: {msg}")

            image_urls = result.get("data", {}).get("image_urls", [])
            image_base64s = result.get("data", {}).get("image_base64s", [])

            if not image_urls and not image_base64s:
                return event.plain_result("未生成图片")

            async for chain in self._send_image_result(event, image_urls[:n], image_base64s[:n]):
                await event.send(chain)
            return event.plain_result("图片已生成")
        except Exception as e:
            return event.plain_result(f"文生图出错: {e}")

    @filter.llm_tool(name="minimax_i2i")
    async def llm_image_to_image(
        self, event: AstrMessageEvent, prompt: str, image: str = "", n: int = 1,
        aspect_ratio: str = "", prompt_optimizer: bool = False, seed: int = 0
    ) -> MessageEventResult:
        """使用 MiniMax image-01 模型基于参考图片进行图生图。适合对已有图片进行风格变换、修饰等。

        Args:
            prompt(string): 对参考图片的修改描述或风格变换提示词
            image(string): 参考图片路径，传入后优先使用此图片作为参考。可传本地路径或URL
            n(int): 生成图片数量，1-9 张，默认 1
            aspect_ratio(string): 图片宽高比，可选 16:9, 1:1, 9:16, 4:3, 3:4, 21:9，默认使用配置值
            prompt_optimizer(bool): 是否自动优化提示词，默认 false
            seed(int): 随机种子，相同种子可复现相近结果，默认 0 表示不指定
        """
        image_file = image if image else await self._resolve_reference_image(event)
        if not image_file:
            return event.plain_result("需要提供一张参考图片，请附带一张图片或配置默认参考图 URL")

        try:
            n = max(1, min(int(n) if n else 1, 9))
            final_prompt = self._build_prompt_with_persona(prompt)
            subject_ref = await self._image_to_subject_ref(image_file)
            payload = {
                "model": self.image_model,
                "prompt": final_prompt,
                "aspect_ratio": aspect_ratio or self.aspect_ratio,
                "subject_reference": subject_ref,
                "n": n,
            }
            if prompt_optimizer:
                payload["prompt_optimizer"] = True
            if seed > 0:
                payload["seed"] = seed
            self._maybe_add_size(payload)
            result = await self._async_post("/v1/image_generation", payload)
            if result.get("base_resp", {}).get("status_code") != 0:
                msg = result.get("base_resp", {}).get("status_msg", "未知错误")
                return event.plain_result(f"图生图失败: {msg}")

            image_urls = result.get("data", {}).get("image_urls", [])
            image_base64s = result.get("data", {}).get("image_base64s", [])

            if not image_urls and not image_base64s:
                return event.plain_result("未生成图片")

            async for chain in self._send_image_result(event, image_urls[:n], image_base64s[:n]):
                await event.send(chain)
            return event.plain_result("图片已生成")
        except Exception as e:
            return event.plain_result(f"图生图出错: {e}")

    @filter.llm_tool(name="minimax_t2v")
    async def llm_text_to_video(
        self, event: AstrMessageEvent, prompt: str, duration: int = 0, resolution: str = ""
    ) -> MessageEventResult:
        """使用 MiniMax Hailuo 模型根据文本描述生成视频。适合需要生成短视频、动画片段、动态视觉内容等场景。

        Args:
            prompt(string): 视频描述提示词，详细描述想要的视频画面内容和动作
            duration(int): 视频时长秒数，可选 6 或 10，默认使用配置值
            resolution(string): 分辨率，可选 768P 或 1080P，默认使用配置值
        """
        try:
            d = duration if duration in (6, 10) else self.video_duration
            r = resolution if resolution in ("768P", "1080P") else self.video_resolution
            result = await self._async_post("/v1/video_generation", {
                "model": self.video_model,
                "prompt": prompt,
                "duration": d,
                "resolution": r,
            })
            if result.get("base_resp", {}).get("status_code") != 0:
                msg = result.get("base_resp", {}).get("status_msg", "未知错误")
                return event.plain_result(f"视频生成失败: {msg}")

            task_id = result.get("data", {}).get("task_id", "")
            if not task_id:
                return event.plain_result("未获取到任务 ID")

            poll_result = await self._poll_video_task(task_id)
            video_url = poll_result.get("data", {}).get("video_url", "")
            if not video_url:
                return event.plain_result("未获取到视频链接")

            dest = self._get_download_path("t2v", "mp4")
            await self._download_file(video_url, dest)
            return event.chain_result([Video(file=dest)])
        except Exception as e:
            return event.plain_result(f"文生视频出错: {e}")

    @filter.llm_tool(name="minimax_i2v")
    async def llm_image_to_video(
        self, event: AstrMessageEvent, prompt: str, duration: int = 0, resolution: str = ""
    ) -> MessageEventResult:
        """使用 MiniMax Hailuo 模型基于参考图片生成视频。优先使用用户消息中附带的图片作为参考，否则使用配置的默认参考图。
        调用前需先说明需要用户提供参考图片。

        Args:
            prompt(string): 视频描述提示词，描述图片中内容应该发生的动作和变化
            duration(int): 视频时长秒数，可选 6 或 10，默认使用配置值
            resolution(string): 分辨率，可选 768P 或 1080P，默认使用配置值
        """
        image_file = await self._resolve_reference_image(event)
        if not image_file:
            return event.plain_result("需要提供一张参考图片，请附带一张图片或配置默认参考图 URL")

        try:
            first_frame_url = await self._upload_image_for_video(image_file)
            d = duration if duration in (6, 10) else self.video_duration
            r = resolution if resolution in ("768P", "1080P") else self.video_resolution
            result = await self._async_post("/v1/video_generation", {
                "model": self.video_model,
                "prompt": prompt,
                "duration": d,
                "resolution": r,
                "first_frame_image": first_frame_url,
            })
            if result.get("base_resp", {}).get("status_code") != 0:
                msg = result.get("base_resp", {}).get("status_msg", "未知错误")
                return event.plain_result(f"图生视频失败: {msg}")

            task_id = result.get("data", {}).get("task_id", "")
            if not task_id:
                return event.plain_result("未获取到任务 ID")

            poll_result = await self._poll_video_task(task_id)
            video_url = poll_result.get("data", {}).get("video_url", "")
            if not video_url:
                return event.plain_result("未获取到视频链接")

            dest = self._get_download_path("i2v", "mp4")
            await self._download_file(video_url, dest)
            return event.chain_result([Video(file=dest)])
        except Exception as e:
            return event.plain_result(f"图生视频出错: {e}")

    @filter.command("minimax_music")
    async def music_generation_cmd(self, event: AstrMessageEvent, prompt: str = ""):
        """音乐生成。用法：/minimax_music <描述> [-l <歌词>] [-inst]"""
        if not prompt:
            yield event.plain_result("请输入音乐描述，例如: /minimax_music 流行、忧伤、适合雨夜的钢琴曲")
            return

        lyrics = None
        is_instrumental = False
        tokens = prompt.split()
        lyrics_start = -1
        rest = []
        for i, t in enumerate(tokens):
            if lyrics_start >= 0:
                continue
            if t == "-l":
                lyrics_start = i + 1
            elif t in ("-inst", "--instrumental"):
                is_instrumental = True
            else:
                rest.append(t)
        if lyrics_start > 0 and lyrics_start < len(tokens):
            lyrics_tokens = [t for t in tokens[lyrics_start:] if t not in ("-inst", "--instrumental")]
            lyrics = " ".join(lyrics_tokens) if lyrics_tokens else None
        remaining = " ".join(rest)

        yield event.plain_result("🎵 MiniMax 音乐生成中...")
        try:
            payload = {
                "model": self.music_model,
                "prompt": remaining,
                "output_format": "url",
                "audio_setting": {
                    "format": self.audio_format,
                    "sample_rate": self.audio_sample_rate,
                    "bitrate": self.audio_bitrate,
                },
            }
            if is_instrumental:
                payload["is_instrumental"] = True
            elif lyrics:
                payload["lyrics"] = lyrics
            else:
                payload["lyrics_optimizer"] = True

            result = await self._async_post("/v1/music_generation", payload)
            if result.get("base_resp", {}).get("status_code") != 0:
                msg = result.get("base_resp", {}).get("status_msg", "未知错误")
                yield event.plain_result(f"❌ 音乐生成失败: {msg}")
                return

            audio_url = result.get("data", {}).get("audio_url", "")
            if not audio_url:
                yield event.plain_result("❌ 未获取到音频链接")
                return

            ext = "wav" if self.audio_format == "pcm" else self.audio_format
            dest = self._get_download_path("minimax_music", ext)
            await self._download_file(audio_url, dest)
            yield event.chain_result([Record(file=dest)])
        except Exception as e:
            yield event.plain_result(f"❌ 音乐生成出错: {e}")

    @filter.llm_tool(name="minimax_music")
    async def llm_music_generation(
        self, event: AstrMessageEvent, prompt: str, lyrics: str = "", is_instrumental: bool = False
    ) -> MessageEventResult:
        """使用 MiniMax Music-2.6 模型根据文本描述生成音乐。适合需要生成背景音乐、歌曲、配乐等场景。

        Args:
            prompt(string): 音乐描述，指定风格、情绪、场景等，例如 "流行、忧伤、适合雨夜的钢琴曲"
            lyrics(string): 可选。歌词内容，多行用 \\n 分隔。为空时由 AI 自动生成
            is_instrumental(bool): 是否纯音乐（无人声），默认 false
        """
        try:
            payload = {
                "model": self.music_model,
                "prompt": prompt,
                "output_format": "url",
                "audio_setting": {
                    "format": self.audio_format,
                    "sample_rate": self.audio_sample_rate,
                    "bitrate": self.audio_bitrate,
                },
            }
            if is_instrumental:
                payload["is_instrumental"] = True
            elif lyrics and lyrics.strip():
                payload["lyrics"] = lyrics
            else:
                payload["lyrics_optimizer"] = True

            result = await self._async_post("/v1/music_generation", payload)
            if result.get("base_resp", {}).get("status_code") != 0:
                msg = result.get("base_resp", {}).get("status_msg", "未知错误")
                return event.plain_result(f"音乐生成失败: {msg}")

            audio_url = result.get("data", {}).get("audio_url", "")
            if not audio_url:
                return event.plain_result("未获取到音频链接")

            ext = "wav" if self.audio_format == "pcm" else self.audio_format
            dest = self._get_download_path("music", ext)
            await self._download_file(audio_url, dest)
            return event.chain_result([Record(file=dest)])
        except Exception as e:
            return event.plain_result(f"音乐生成出错: {e}")
