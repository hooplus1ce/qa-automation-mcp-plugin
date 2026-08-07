"""GLM-5V 视觉理解降级工具模块 (腾讯云 TokenHub OpenAI 兼容接口, 流式 + 思考过程)。"""

import asyncio
import base64
import json
import logging
import mimetypes
import os
from pathlib import Path
from typing import List, Optional, Tuple

from openai import OpenAI

from qa_mcp.config import EVIDENCE_DIR, PROJECT_DIR

logger = logging.getLogger("mcp_automation.vision")

API_BASE = "https://tokenhub.tencentmaas.com/v1"
MODEL = "glm-5v-turbo"
MAX_TOKENS = 2048
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
    """读取 VISION_API_KEY: 环境变量 > 用户项目 .env > 插件 .env。"""
    key = os.environ.get("VISION_API_KEY", "").strip()
    if key:
        return key
    bases: List[Path] = []
    for base in (Path(PROJECT_DIR), Path.cwd(), Path(__file__).resolve().parents[3]):
        if base not in bases:
            bases.append(base)
    for base in bases:
        env_file = base / ".env"
        if env_file.is_file():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("VISION_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def _resolve_image_url(image_arg: str) -> dict:
    """将图片文件路径或 URL 解析为 Base64 data URI 对象。

    相对路径优先基于用户项目根目录 (PROJECT_DIR, 插件化部署时由客户端注入的
    CLAUDE_PROJECT_DIR 指向用户项目) 解析, 其次回退进程 cwd (本地直跑),
    保证粘贴图片/截图等相对地址在任何部署形态下都能命中。
    """
    if image_arg.startswith(("http://", "https://")):
        return {"url": image_arg}

    expanded = os.path.expanduser(image_arg)
    path = Path(expanded)
    if not path.is_file():
        for base in (Path(PROJECT_DIR), Path.cwd()):
            candidate = base / expanded
            if candidate.is_file():
                path = candidate
                break

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
    """从 Claude Code 会话记录 jsonl 中提取最近一张粘贴的图片并保存到 EVIDENCE_DIR。

    会话目录名由用户项目路径 (PROJECT_DIR) 生成; 插件化部署时进程 cwd 是插件
    目录, 不能用作会话定位依据。
    """
    project_parts = Path(PROJECT_DIR).resolve().parts
    drive = project_parts[0][0]
    rest_path = "-".join(project_parts[1:])

    projects_base = Path.home() / ".claude" / "projects"
    session_dir = None
    for d_prefix in [drive.lower(), drive.upper()]:
        candidate = projects_base / f"{d_prefix}--{rest_path}"
        if candidate.is_dir():
            session_dir = candidate
            break

    if not session_dir:
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


def _stream_vision_completion(
    api_key: str,
    image_urls: List[dict],
    question: str,
    thinking: bool,
    reasoning_effort: str,
) -> Tuple[str, str]:
    """同步执行 GLM-5V 流式视觉理解 (在独立线程中运行), 返回 (reasoning, content)。

    与官方示例一致: stream=True 逐块收集 delta.reasoning_content (思考过程)
    与 delta.content (正式回答), thinking 开启时附带 reasoning_effort 控制思考深度。
    """
    client = OpenAI(api_key=api_key, base_url=API_BASE)

    user_content = [
        {"type": "image_url", "image_url": url_obj} for url_obj in image_urls
    ]
    if question:
        user_content.append({"type": "text", "text": question})

    messages = [
        {"role": "system", "content": "你是 GLM-5V 多模态视觉助手，请基于图片内容准确回答用户的问题。"},
        {"role": "user", "content": user_content},
    ]

    extra_body = {}
    if thinking:
        extra_body["thinking"] = {"type": "enabled"}
        extra_body["reasoning_effort"] = reasoning_effort

    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        max_tokens=MAX_TOKENS,
        stream=True,
        extra_body=extra_body,
    )

    reasoning_parts: List[str] = []
    content_parts: List[str] = []
    for chunk in response:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        reasoning = getattr(delta, "reasoning_content", None)
        if reasoning:
            reasoning_parts.append(reasoning)
        content = getattr(delta, "content", None)
        if content:
            content_parts.append(content)

    return "".join(reasoning_parts).strip(), "".join(content_parts).strip()


async def describe_image_impl(
    images: Optional[List[str]] = None,
    question: str = "请描述图片中的元素与数据信息内容",
    thinking: bool = True,
    reasoning_effort: str = "high",
    extract_pasted: bool = False,
) -> dict:
    """调用 GLM-5V (腾讯云 TokenHub) 对图片进行流式视觉理解。

    thinking=True (默认): 开启深度思考, 返回 reasoning (思考过程) 与 description (回答);
    reasoning_effort 控制思考深度 (max/high/medium/low), 仅在 thinking=True 时生效。
    """
    api_key = _load_api_key()
    if not api_key:
        return {
            "status": "error",
            "message": "未配置 VISION_API_KEY 环境变量，无法调起视觉识别接口。",
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

        reasoning, content = await asyncio.to_thread(
            _stream_vision_completion,
            api_key,
            image_urls,
            question,
            thinking,
            reasoning_effort,
        )

        return {
            "status": "success",
            "images_processed": target_images,
            "question": question,
            "model": MODEL,
            "provider": API_BASE,
            "thinking": thinking,
            "reasoning_effort": reasoning_effort if thinking else None,
            "reasoning": reasoning,
            "description": content,
        }

    except Exception as e:
        logger.error(f"GLM-5V 视觉识别异常: {e}")
        return {"status": "error", "message": f"视觉识别失败: {str(e)}"}
