# -*- coding: utf-8 -*-
"""
TTS Emotion Router - Emotion Marker Processor

情绪标记处理模块，负责解析、清理和归一化情绪标记。
"""

from __future__ import annotations

import re
import logging
from typing import Optional, Tuple, Pattern

logger = logging.getLogger(__name__)

from .constants import (
    EMOTIONS,
    EMOTION_SYNONYMS,
    INVISIBLE_CHARS,
    DEFAULT_EMO_MARKER_TAG,
    INLINE_AUDIO_TAG_RE,
    INLINE_AUDIO_KEYWORDS,
)


class EmotionMarkerProcessor:
    """
    情绪标记处理器。
    
    负责：
    1. 从文本中解析情绪标记（如 [EMO:happy]）
    2. 清理文本中的情绪标记
    3. 归一化情绪标签到标准四选一
    """
    
    def __init__(self, tag: str = DEFAULT_EMO_MARKER_TAG, enabled: bool = True):
        """
        初始化情绪标记处理器。
        
        Args:
            tag: 情绪标记标签（如 "EMO"）
            enabled: 是否启用标记处理
        """
        self.tag = tag
        self.enabled = enabled
        
        # 编译正则表达式
        self._compile_patterns()
    
    def _compile_patterns(self) -> None:
        """编译所有需要的正则表达式。"""
        try:
            escaped_tag = re.escape(self.tag)
            
            # 严格匹配：[EMO:happy] 格式，标签为四选一
            self._marker_strict_re: Optional[Pattern] = re.compile(
                rf"\[\s*{escaped_tag}\s*:\s*(happy|sad|angry|neutral)\s*\]",
                re.I
            )
            
            # 宽松匹配任意形态头部标记（用于清理）
            # 允许":[label]"可缺省label，接受半/全角冒号及连字符
            self._marker_any_re: Optional[Pattern] = re.compile(
                rf"^[\s\ufeff]*[\[\(【]\s*{escaped_tag}\s*(?:[:\uff1a-]\s*[a-z]*)?\s*[\]\)】]",
                re.I
            )
            
            # 头部 token：支持 [EMO] / [EMO:] / 【EMO：】 / emo / emo:happy / 等
            self._head_token_re: Optional[Pattern] = re.compile(
                rf"^[\s\ufeff]*(?:[\[\(【]\s*{escaped_tag}\s*(?:[:\uff1a-]\s*(?P<lbl>happy|sad|angry|neutral))?\s*[\]\)】]|(?:{escaped_tag}|emo)\s*(?:[:\uff1a-]\s*(?P<lbl2>happy|sad|angry|neutral))?)\s*[,，。:\uff1a-]*\s*",
                re.I
            )
            
            # 头部 token（英文任意标签）：如 [EMO:confused]
            self._head_anylabel_re: Optional[Pattern] = re.compile(
                rf"^[\s\ufeff]*[\[\(【]\s*{escaped_tag}\s*[:\uff1a-]\s*(?P<raw>[a-z][a-z_-]*)\s*[\]\)】]",
                re.I
            )

            # 激进清理 - 行首/段首（保留换行）
            self._marker_head_visible_re: Optional[Pattern] = re.compile(
                rf'(^|\n)\s*[\[\(【]\s*{escaped_tag}\s*(?:[:：-]\s*[^\]\)】\n]+)?\s*[\]\)】]\s*',
                re.I
            )
            
            # 激进清理 - 句中：直接全局删除
            self._marker_mid_visible_re: Optional[Pattern] = re.compile(
                rf'[\[\(【]\s*{escaped_tag}\s*(?:[:：-]\s*[^\]\)】\n]+)?\s*[\]\)】]',
                re.I
            )

            # 清理多余空白
            self._cleanup_spaces_re: Optional[Pattern] = re.compile(r'[ \t]{2,}')
            self._cleanup_newlines_re: Optional[Pattern] = re.compile(r'\n{3,}')
            
        except Exception as e:
            logger.warning(f"EmotionMarkerProcessor: pattern compile failed: {e}", exc_info=True)
            self._marker_strict_re = None
            self._marker_any_re = None
            self._head_token_re = None
            self._head_anylabel_re = None
            self._marker_head_visible_re = None
            self._marker_mid_visible_re = None
            self._cleanup_spaces_re = None
            self._cleanup_newlines_re = None
    
    def normalize_text(self, text: str) -> str:
        """
        移除不可见字符与 BOM。
        
        Args:
            text: 原始文本
            
        Returns:
            清理后的文本
        """
        if not text:
            return text
        for ch in INVISIBLE_CHARS:
            text = text.replace(ch, "")
        return text
    
    def normalize_label(self, label: Optional[str]) -> Optional[str]:
        """
        将任意英文/中文情绪词映射到四选一。
        
        Args:
            label: 原始情绪标签
            
        Returns:
            归一化后的情绪标签（happy/sad/angry/neutral）或 None
        """
        if not label:
            return None
        
        lbl = label.strip().lower()
        
        for emotion, synonyms in EMOTION_SYNONYMS.items():
            if lbl in synonyms:
                return emotion
        
        return None
    
    def strip_head(self, text: str) -> Tuple[str, Optional[str]]:
        """
        从文本开头剥离情绪标记。
        
        Args:
            text: 原始文本
            
        Returns:
            (清理后的文本, 解析到的情绪或 None)
        """
        if not text:
            return text, None
        
        # 优先用宽松的头部匹配（限定四选一）
        if self._head_token_re:
            m = self._head_token_re.match(text)
            if m:
                label = (m.group("lbl") or m.group("lbl2") or "").lower()
                if label not in EMOTIONS:
                    label = None  # type: ignore
                cleaned = self._head_token_re.sub("", text, count=1)
                return cleaned.strip(), label if label in EMOTIONS else None
        
        # 其次：捕获任意英文标签，再做同义词归一化
        if self._head_anylabel_re:
            m2 = self._head_anylabel_re.match(text)
            if m2:
                raw = (m2.group("raw") or "").lower()
                label = self.normalize_label(raw)
                cleaned = self._head_anylabel_re.sub("", text, count=1)
                return cleaned.strip(), label
        
        # 最后：去掉任何形态头部标记（即便无法识别标签含义也移除）
        if self._marker_any_re and text.lstrip().startswith(("[", "【", "(")):
            cleaned = self._marker_any_re.sub("", text, count=1)
            return cleaned.strip(), None
        
        return text, None
    
    def strip_head_many(self, text: str) -> Tuple[str, Optional[str]]:
        """
        连续剥离多枚开头的情绪标记，并清理全文中残留的任何可见标记。
        
        Args:
            text: 原始文本
            
        Returns:
            (清理后文本, 最后一次解析到的情绪)
        """
        last_label: Optional[str] = None
        
        # 1. 优先清理头部，并提取情绪
        while True:
            cleaned, label = self.strip_head(text)
            if label:
                last_label = label
            if cleaned == text:
                break
            text = cleaned
        
        # 2. 全局清理任何位置的残留标记（不提取情绪，仅清理）
        try:
            if self._marker_strict_re:
                text = self._marker_strict_re.sub("", text)
        except Exception as e:
            logger.debug(f"Failed to strip residual markers: {e}")
        
        return text.strip(), last_label
    
    def strip_all_visible_markers(self, text: str) -> str:
        """
        更激进地移除文本任意位置的隐藏情绪标记。
        
        匹配：[EMO:happy] / 【EMO：sad】 / (EMO:angry) 等
        无论在开头、行首或句中均清理。
        
        Args:
            text: 原始文本
            
        Returns:
            清理后的文本
        """
        try:
            # 1) 行首/段首（保留换行）
            if self._marker_head_visible_re:
                def _head_sub(m: re.Match) -> str:
                    return "\n" if m.group(1) == "\n" else ""
                
                text = self._marker_head_visible_re.sub(_head_sub, text)
            
            # 2) 句中：直接全局删除
            if self._marker_mid_visible_re:
                text = self._marker_mid_visible_re.sub('', text)
            
            # 3) 清理多余空白
            if self._cleanup_spaces_re:
                text = self._cleanup_spaces_re.sub(' ', text)
            if self._cleanup_newlines_re:
                text = self._cleanup_newlines_re.sub('\n\n', text)
            
            return text.strip()
        except Exception as e:
            logger.error(f"Failed to strip all visible markers: {e}", exc_info=True)
            return text
    
    def extract_emotion(self, text: str) -> Optional[str]:
        """
        从文本中提取情绪标签（不修改文本）。
        
        Args:
            text: 原始文本
            
        Returns:
            提取到的情绪标签或 None
        """
        if not text or not self._marker_strict_re:
            return None
        
        m = self._marker_strict_re.search(text)
        if m:
            label = m.group(1).lower()
            if label in EMOTIONS:
                return label
        else:
            logger.debug("No strict emotion marker found in text.")
        
        return None
    
    def build_injection_instruction(self) -> str:
        """
        构建要注入到 LLM 系统提示中的情绪标记指令。
        
        Returns:
            情绪标记指令文本
        """
        return (
            f"请在每次回复的最开头只输出一个隐藏情绪标记，格式严格为："
            f"[{self.tag}:happy] 或 [{self.tag}:sad] 或 [{self.tag}:angry] 或 [{self.tag}:neutral]。"
            "必须四选一；若无法判断请选择 neutral。该标记仅供系统解析，"
            "输出后立刻继续正常作答，不要解释或复述该标记。"
            "如你想到其它词，请映射到以上四类：happy(开心/喜悦/兴奋)、sad(伤心/难过/沮丧/upset)、"
            "angry(生气/愤怒/恼火/furious)、neutral(平静/普通/困惑/confused)。"
        )
    
    def is_marker_present(self, system_prompt: str, prompt: str) -> bool:
        """
        检查提示中是否已存在情绪标记标签。
        
        Args:
            system_prompt: 系统提示
            prompt: 用户提示
            
        Returns:
            如果已存在标记返回 True
        """
        return (self.tag in system_prompt) or (self.tag in prompt)
    
    def has_inline_audio_tags(self, text: str) -> bool:
        """
        检查文本中是否包含行内音频标签。
        
        行内音频标签格式: (调侃) (低声｜情绪塌陷般平静) (模仿自信，提高音量)
        
        Args:
            text: 待检查文本
            
        Returns:
            是否包含行内音频标签
        """
        if not text:
            return False
        for match in INLINE_AUDIO_TAG_RE.finditer(text):
            content = match.group(1).strip()
            if self._is_inline_audio_tag(content):
                return True
        return False
    
    def strip_inline_audio_tags(self, text: str) -> Tuple[str, int]:
        """
        移除文本中的行内音频标签。
        
        只移除被识别为音频标签的括号内容，保留普通括号文本。
        
        Args:
            text: 原始文本
            
        Returns:
            (清理后的文本, 移除的标签数量)
        """
        if not text:
            return text, 0
        
        count = 0
        
        def _replacer(match: re.Match) -> str:
            nonlocal count
            content = match.group(1).strip()
            if self._is_inline_audio_tag(content):
                count += 1
                return ""
            return match.group(0)
        
        cleaned = INLINE_AUDIO_TAG_RE.sub(_replacer, text)
        # 清理因移除标签产生的多余空格
        cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
        cleaned = re.sub(r"\n[ \t]+\n", "\n\n", cleaned)
        return cleaned.strip(), count
    
    @staticmethod
    def _is_inline_audio_tag(content: str) -> bool:
        """
        判断括号内容是否为行内音频标签（而非普通括号文本）。
        
        启发式规则：
        - 包含已知音频关键词
        - 包含 ｜ 分隔符（强指示）
        - 短纯中文文本（无数字、无英文）
        """
        if not content:
            return False
        
        # 包含全角竖线分隔符 -> 强指示为音频标签
        if "｜" in content:
            return True
        
        # 包含已知音频关键词
        for kw in INLINE_AUDIO_KEYWORDS:
            if kw in content:
                return True
        
        # 短纯中文文本（>=2个中文字符，无数字无英文）-> 可能是音频标签
        if len(content) <= 15:
            chinese_chars = re.findall(r"[\u4e00-\u9fff]", content)
            has_digit = bool(re.search(r"\d", content))
            has_ascii_letter = bool(re.search(r"[a-zA-Z]", content))
            if len(chinese_chars) >= 2 and not has_digit and not has_ascii_letter:
                return True
        
        return False
    
    def build_mimo_inline_tag_instruction(self) -> str:
        """
        构建 MiMo 行内音频标签的 LLM 指令。
        
        Returns:
            LLM 指令文本
        """
        from .constants import MIMO_INLINE_TAG_INSTRUCTION
        return MIMO_INLINE_TAG_INSTRUCTION
    
    def update_config(self, tag: str, enabled: bool) -> None:
        """
        更新配置并重新编译正则。
        
        Args:
            tag: 新的情绪标记标签
            enabled: 是否启用
        """
        self.tag = tag
        self.enabled = enabled
        self._compile_patterns()
