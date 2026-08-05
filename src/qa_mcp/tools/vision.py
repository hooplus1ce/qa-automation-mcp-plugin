"""小米 MiMo-V2.5 视觉理解降级工具模块。"""

import base64
import json
import logging
import mimetypes
import os
from pathlib import Path
from typing import List, Optional

from openai import OpenAI

from qa_mcp.config import EVIDENCE_DIR

logger = logging.getLogger("mcp_automation.vision")

API_BASE = "https://api.xiaomimimo.com/v1"
MODEL = "mimo-v2.5"
MAX_IMAGE_BYTES = 50 * 1024 * 1024
SUPPORTED_MIME = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/bmp",
}
MIME_EXT = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/gif": "gif",
    "image/webp": "webp",
    "image/bmp": "bmp",
}


def _load_api_key() -> str:
    """读取 MIMO_API_KEY: 环境变量 > 项目 .env。"""
    key = os.environ.get("MIMO_API_KEY", "").strip()
    if key:
        return key
    for base in (Path.cwd(), Path(__file__).resolve().parents[3]):
        env_file = base / ".env"
        if env_file.is_file():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("MIMO_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def _resolve_image_url(image_arg: str) -> dict:
    """将图片文件路径或 URL 解析为 Base64 data URI 对象。"""
    if image_arg.startswith(("http://", "https://")):
        return {"url": image_arg}

    path = Path(image_arg)
    if not path.is_file():
        raise RuntimeError(f"图片文件不存在: {image_arg}")

    if path.stat().st_size > MAX_IMAGE_BYTES:
        raise RuntimeError(f"图片 {image_arg} 超过 50MB 限制")

    mime = mimetypes.guess_type(path.name)[0] or ""
    if mime not in SUPPORTED_MIME and not mime.startswith("image/"):
        raise RuntimeError(f"不支持的图片格式: {path.name}")

    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return {"url": f"data:{mime};base64,{b64}"}


def _extract_latest_pasted_image() -> Optional[Path]:
    """从 Claude Code 会话记录 jsonl 中提取最近一张粘贴的图片并保存到 EVIDENCE_DIR。"""
    project_parts = Path.cwd().resolve().parts
    drive = project_parts[0][0].lower()
    proj_dir_name = f"{drive}--" + "-".join(project_parts[1:])

    session_dir = Path.home() / ".claude" / "projects" / proj_dir_name
    if not session_dir.is_dir():
        return None

    session_files = sorted(
        session_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    if not session_files:
        return None

    for s_file in session_files:
        with open(s_file, encoding="utf-8") as fh:
            lines = fh.readlines()
            for line in reversed(lines):
                line = line.strip()
                if not line or '"type":"image"' not in line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("type") != "user":
                    continue
                content = (rec.get("message") or {}).get("content") or []
                if not isinstance(content, list):
                    continue
                for blk in content:
                    if isinstance(blk, dict) and blk.get("type") == "image":
                        src = blk.get("source") or {}
                        if src.get("type") == "base64" and src.get("data"):
                            media_type = src.get("media_type", "image/png")
                            ext = MIME_EXT.get(media_type, "png")
                            out_dir = Path(EVIDENCE_DIR)
                            out_dir.mkdir(parents=True, exist_ok=True)
                            out_path = out_dir / f"pasted_image_latest.{ext}"
                            out_path.write_bytes(base64.b64decode(src["data"]))
                            return out_path
    return None


async def mimo_describe_image_impl(
    images: Optional[List[str]] = None,
    question: str = "请描述图片中的元素与数据信息内容",
    thinking: bool = False,
    extract_pasted: bool = False,
) -> dict:
    """调用小米 MiMo-V2.5 API 对图片进行视觉理解与描述。"""
    api_key = _load_api_key()
    if not api_key:
        return {
            "status": "error",
            "message": "未配置 MIMO_API_KEY 环境变量，无法调起视觉识别接口。",
        }

    target_images: List[str] = list(images) if images else []

    if extract_pasted or not target_images:
        pasted_path = _extract_latest_pasted_image()
        if pasted_path:
            target_images.append(str(pasted_path))

    if not target_images:
        return {
            "status": "error",
            "message": "未指定图片路径/URL，且未找到会话中提取的粘贴图片。",
        }

    try:
        image_urls = [_resolve_image_url(img) for img in target_images]

        client = OpenAI(api_key=api_key, base_url=API_BASE)

        user_content = [
            {"type": "image_url", "image_url": url_obj} for url_obj in image_urls
        ]
        if question:
            user_content.append({"type": "text", "text": question})

        messages = [
            {"role": "system", "content": "你是小米开发的 AI 助手 MiMo。"},
            {"role": "user", "content": user_content},
        ]

        completion = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            max_completion_tokens=4096,
            extra_body={
                "thinking": {"type": "enabled" if thinking else "disabled"}
            },
        )

        result_text = completion.choices[0].message.content or ""
        return {
            "status": "success",
            "images_processed": target_images,
            "question": question,
            "description": result_text.strip(),
        }

    except Exception as e:
        logger.error(f"MiMo 视觉识别异常: {e}")
        return {"status": "error", "message": f"视觉识别失败: {str(e)}"}
