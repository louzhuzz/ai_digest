# -*- coding: utf-8 -*-
"""
通义万相文生图集成 - ai_digest

调用 DashScope wanx-v1 API 生成配图。
环境变量: DASHSCOPE_API_KEY

用法:
    from ai_digest.dashscope_image import generate_image, generate_infographic

    # 简单文生图（wan2.6-t2i，同步返回，无需轮询）
    url = generate_image("一只橘色的猫在阳光下打盹")

    # 指定模型
    url = generate_image("图表：GPT-5性能对比", model="qwen-image-2.0-pro")

    # 信息图（公众号配图推荐）
    url = generate_infographic(
        title="GPT-5 vs DeepSeek V4 基准测试对比",
        data={"GPT-5": 98, "DeepSeek V4": 95, "Claude 4": 93},
    )
"""

import os
import time
import requests
from typing import Optional

BASE_URL = "https://dashscope.aliyuncs.com/api/v1"
TIMEOUT_SECONDS = 120

# ---------------------------------------------------------------------------
# 支持的模型
# ---------------------------------------------------------------------------
# wan2.6-t2i         文生图旗舰，同步返回（一次请求即得结果），支持 1280-1440 像素，
#                      总像素 [1280*1280, 1440*1440]，宽高比 [1:4, 4:1]
# wan2.5-t2i-preview 文生图 preview，支持灵活尺寸如 768*2700
# wan2.2-t2i-flash   极速版，较 2.1 提速 50%
# wanx-v1            旧版，1024*1024，仅支持 <style> 风格
# qwen-image-2.0-pro 文本渲染强，适合图表/海报/PPT（中英文精准）
# z-image-turbo      速度快，成本低，人像/产品图效果好
MODEL_SYNC = "wan2.6-t2i"  # 同步模式默认模型
MODEL_ASYNC = "wan2.5-t2i-preview"  # 异步模式默认模型

# wan2.6 支持的分辨率（总像素 1280*1280~1440*1440，宽高比 1:4~4:1）
WAN2_6_SIZES = {
    "1:1": "1280*1280",
    "3:4": "1104*1472",
    "4:3": "1472*1104",
    "9:16": "960*1696",
    "16:9": "1696*960",
}


def _get_api_key() -> str:
    key = os.getenv("DASHSCOPE_API_KEY")
    if not key:
        raise ValueError("DASHSCOPE_API_KEY 环境变量未设置")
    return key


# ---------------------------------------------------------------------------
# wan2.6 同步接口（一次请求返回结果，无需轮询）
# ---------------------------------------------------------------------------
def _generate_sync_v2(prompt: str, model: str = MODEL_SYNC, size: str = "1280*1280",
                     n: int = 1, negative_prompt: str = "",
                     prompt_extend: bool = True, watermark: bool = False,
                     timeout: float = TIMEOUT_SECONDS) -> str:
    """wan2.6 同步接口：POST → 直接返回图片 URL"""
    url = f"{BASE_URL}/services/aigc/multimodal-generation/generation"
    headers = {
        "Authorization": f"Bearer {_get_api_key()}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "input": {
            "messages": [{"role": "user", "content": [{"text": prompt}]}]
        },
        "parameters": {
            "n": n,
            "size": size,
            "negative_prompt": negative_prompt,
            "prompt_extend": prompt_extend,
            "watermark": watermark,
        }
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    if data.get("code"):
        raise RuntimeError(f"DashScope API 错误: {data['code']} - {data.get('message', '')}")
    choices = data.get("output", {}).get("choices", [])
    if not choices:
        raise RuntimeError(f"DashScope 同步返回为空: {data}")
    # 取第一张图
    content = choices[0].get("message", {}).get("content", [])
    for item in content:
        if item.get("type") == "image":
            return item["image"]
    raise RuntimeError(f"DashScope 同步返回中无图片: {data}")


# ---------------------------------------------------------------------------
# 旧版异步接口（wanx-v1 / wan2.5 等，需要轮询）
# ---------------------------------------------------------------------------
def _create_task(prompt: str, model: str = "wanx-v1",
                 style: str = "<auto>", size: str = "1024*1024",
                 n: int = 1) -> str:
    """创建异步任务，返回 task_id"""
    url = f"{BASE_URL}/services/aigc/text2image/image-synthesis"
    headers = {
        "Authorization": f"Bearer {_get_api_key()}",
        "Content-Type": "application/json",
        "X-DashScope-Async": "enable",
    }
    payload = {
        "model": model,
        "input": {"prompt": prompt},
        "parameters": {"style": style, "size": size, "n": n},
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if data.get("code"):
        raise RuntimeError(f"DashScope API 错误: {data['code']} - {data.get('message', '')}")
    return data["output"]["task_id"]


def _wait_for_task(task_id: str, poll_interval: float = 2.0,
                   max_wait: float = 120.0) -> list[str]:
    """轮询异步任务状态，返回图片 URL 列表"""
    url = f"{BASE_URL}/tasks/{task_id}"
    headers = {"Authorization": f"Bearer {_get_api_key()}"}
    elapsed = 0.0
    while elapsed < max_wait:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        status = data["output"]["task_status"]
        if status == "SUCCEEDED":
            results = data["output"].get("results", [])
            return [r["url"] for r in results if "url" in r]
        elif status in ("FAILED", "CANCELED"):
            msg = data["output"].get("message", status)
            raise RuntimeError(f"任务失败: {msg}")
        time.sleep(poll_interval)
        elapsed += poll_interval
    raise TimeoutError(f"任务 {task_id} 等待超时（{max_wait}s）")


# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------

def generate_image(
    prompt: str,
    model: str = MODEL_SYNC,
    size: str = "1280*1280",
    n: int = 1,
    negative_prompt: str = "",
    prompt_extend: bool = True,
    watermark: bool = False,
    timeout: float = TIMEOUT_SECONDS,
) -> str:
    """
    文生图，返回第一张图片的 URL。

    Args:
        prompt: 正向提示词（中文，推荐）
        model: 模型选择
               - "wan2.6-t2i"      文生图旗舰，同步返回，推荐
               - "wan2.5-t2i-preview"  preview，支持 768*2700 等异形尺寸
               - "wan2.2-t2i-flash"  极速版，512-1440 像素
               - "qwen-image-2.0-pro" 文本渲染强，图表/海报/PPT 推荐
               - "z-image-turbo"    速度快，人像/产品图
               - "wanx-v1"          旧版（默认风格，不推荐）
        size: 分辨率
               - wan2.6: 1:1(1280*1280)/3:4(1104*1472)/4:3(1472*1104)/9:16(960*1696)/16:9(1696*960)
               - wan2.5: 同上
               - wan2.2/wanx: 1024*1024 / 720*1280 / 768*1152 / 1280*720
        n: 生成数量（1-4）
        negative_prompt: 反向提示词（wan2.6/wan2.5 支持）
        prompt_extend: 启用提示词智能改写（wan2.6/wan2.5 支持），默认开启
        watermark: 添加水印，默认 False
        timeout: 最大等待秒数

    Returns:
        第一张图片的 URL（有效期24小时）
    """
    if model in (MODEL_SYNC, "wan2.6-t2i"):
        return _generate_sync_v2(
            prompt=prompt, model=model, size=size, n=n,
            negative_prompt=negative_prompt,
            prompt_extend=prompt_extend, watermark=watermark, timeout=timeout,
        )
    else:
        # 旧版异步：只有 wanx-v1 用 <style> 参数
        style = "<flat illustration>" if model == "wanx-v1" else "<auto>"
        task_id = _create_task(prompt, model=model, style=style, size=size, n=n)
        urls = _wait_for_task(task_id, max_wait=timeout)
        return urls[0]


def generate_infographic(
    title: str,
    data: dict,
    model: str = "qwen-image-2.0-pro",
    size: str = "1280*1280",
) -> str:
    """
    生成信息图/数据对比图（公众号配图推荐）。

    qwen-image-2.0-pro 文本渲染精准，适合生成图表、海报。
    也可使用 wan2.6-t2i（同步）或 wan2.5-t2i-preview。

    Args:
        title: 图表标题
        data: 字典，key=标签，value=数值或描述
        model: 推荐 qwen-image-2.0-pro（文本渲染强）
        size: 分辨率

    Returns:
        图片 URL

    Example:
        generate_infographic(
            title="主流大模型 MMLU 基准对比",
            data={"GPT-5": "98分", "DeepSeek V4": "95分", "Qwen3": "91分"},
        )
    """
    items_text = " | ".join(f"{k}: {v}" for k, v in data.items())
    prompt = (
        f"{title}，{items_text}，"
        f"信息图风格，扁平矢量设计，网格布局，语义配色，"
        f"白色背景，充足留白，大字体标题，清晰数据标签，"
        f"专业商业图表风格，无复杂背景，高信息密度"
    )
    return generate_image(prompt=prompt, model=model, size=size, n=1)


def download_image(url: str, output_path: str) -> None:
    """下载图片到本地文件"""
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    path = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(resp.content)
