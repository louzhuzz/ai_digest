# -*- coding: utf-8 -*-
"""
纯 Python Simhash 实现（无外部依赖）。

用于近似文本去重：相似标题（hamming distance ≤ 3）判定为重复。
基于 64-bit simhash + 4-gram tokenization。
"""
from __future__ import annotations

import re
import hashlib


def _tokenize(text: str) -> list[str]:
    """
    4-gram 滑动窗口分词（英文+中文混合）。
    小写化，保留字母和汉字，去除其他字符。
    """
    text = text.lower()
    # 提取中文字符和英文字符序列
    chars = re.findall(r'[\w\u4e00-\u9fff]', text)
    if not chars:
        return []
    joined = ''.join(chars)
    return [joined[i:i + 4] for i in range(max(len(joined) - 4 + 1, 1)) or [joined]]


def _string_hash(s: str, bits: int = 64) -> int:
    """将字符串哈希为指定位数的整数（使用 MD5 确保分布均匀）。"""
    h = hashlib.md5(s.encode('utf-8')).digest()
    if bits == 64:
        return int.from_bytes(h[:8], byteorder='big')
    elif bits == 128:
        return int.from_bytes(h[:16], byteorder='big')
    else:
        raise ValueError(f"Unsupported bits: {bits}")


class Simhash:
    """
    64-bit Simhash 计算器。

    用法：
        fp = Simhash("Hello world")  # 计算文本 simhash
        fp.value                    # 64-bit 整数指纹
        fp.hamming(other)           # 计算与另一个 Simhash 的汉明距离
        fp.distance(other)          # 同上（别名）
        Simhash.distance(fp1, fp2)  # 静态方法：计算两个指纹的距离
    """

    BITS = 64

    def __init__(self, text: str = '', tokens: list[str] | None = None) -> None:
        if tokens is None:
            tokens = _tokenize(text)
        self.value = self._compute(tokens)

    def _compute(self, tokens: list[str]) -> int:
        v = [0] * self.BITS
        for token in tokens:
            t = _string_hash(token, self.BITS)
            for i in range(self.BITS):
                bitmask = 1 << i
                if t & bitmask:
                    v[i] += 1
                else:
                    v[i] -= 1
        fingerprint = 0
        for i in range(self.BITS):
            if v[i] >= 0:
                fingerprint |= (1 << i)
        return fingerprint

    def hamming(self, other: "Simhash | int") -> int:
        """返回与另一个 Simhash 的汉明距离（0-64）。"""
        if isinstance(other, int):
            return bin(self.value ^ other).count('1')
        return bin(self.value ^ other.value).count('1')

    distance = hamming_distance = hamming  # 别名

    @staticmethod
    def distance(fp1: int, fp2: int) -> int:
        """静态方法：计算两个 64-bit 指纹的汉明距离。"""
        return bin(fp1 ^ fp2).count('1')

    def is_similar(self, other: "Simhash | int", max_hamming: int = 3) -> bool:
        """判断是否与另一个 Simhash 相似（hamming distance ≤ max_hamming）。"""
        return self.hamming(other) <= max_hamming

    def __repr__(self) -> str:
        return f"Simhash(0x{self.value:016x})"


def compute_text_simhash(title: str, body: str = "") -> int:
    """
    计算文本的 64-bit simhash 指纹。

    合并 title + body 进行分词，title 权重更高（重复时先看标题）。

    Args:
        title: 标题文本
        body: 正文/摘要文本

    Returns:
        64-bit 整数指纹
    """
    # title 分词（2x 权重）
    title_tokens = _tokenize(title)
    body_tokens = _tokenize(body) if body else []

    all_tokens = title_tokens * 2 + body_tokens
    return Simhash(tokens=all_tokens).value


def compute_title_simhash(title: str) -> int:
    """仅用标题计算 simhash（用于快速近似去重）。"""
    return Simhash(text=title).value