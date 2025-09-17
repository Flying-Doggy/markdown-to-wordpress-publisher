'''
Autor: Flying-Doggy
Date: 2025-09-17 13:59:03
title: 
'''
"""通用工具函数

包含链接替换、日志初始化等跨模块复用功能。
"""

import re
import logging
from typing import Dict, Optional ,List
from .config import DEFAULT_LOG_FORMAT, DEFAULT_LOG_LEVEL



def setup_logging(
    log_level: str = DEFAULT_LOG_LEVEL,
    log_format: str = DEFAULT_LOG_FORMAT
) -> logging.Logger:
    """初始化日志配置

    配置全局日志的输出格式、级别，支持控制台输出。
    可在不同模块中调用此函数获取统一配置的日志实例。

    Args:
        log_level: 日志级别，可选值：DEBUG, INFO, WARNING, ERROR, CRITICAL
        log_format: 日志输出格式

    Returns:
        配置完成的日志实例
    """
    # 设置日志级别（转换为logging模块的常量）
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    # 避免重复添加处理器
    logger = logging.getLogger(__name__.split(".")[0])  # 获取根包日志实例
    if logger.handlers:
        return logger
    
    # 配置控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(log_format))
    logger.addHandler(console_handler)
    logger.setLevel(level)
    
    return logger


def replace_markdown_links(md_content: str, link_map: Dict[str, str]) -> str:
    """批量替换Markdown文本中的链接

    同时支持两种Markdown链接格式：
    1. 图片链接：![alt_text](old_link "title")
    2. 普通文本链接：[link_text](old_link)
    
    若链接不在link_map中，保持原链接不变，避免破坏外部链接。

    Args:
        md_content: 原始Markdown文本内容
        link_map: 链接映射字典，格式：{原本地路径: WordPress资源URL}

    Returns:
        链接替换后的Markdown文本
    """
    if not link_map:
        return md_content

    def _replace_link(match: re.Match) -> str:
        """正则匹配回调函数：替换单个链接"""
        # match.group(0)：完整匹配内容（如"![alt](old.jpg)"）
        # match.group(1)：链接部分（如"old.jpg"）
        old_link = match.group(1).strip()
        new_link = link_map.get(old_link, old_link)  # 无匹配则保留原链接
        return match.group(0).replace(old_link, new_link)

    # 1. 匹配图片链接：![任意内容](链接 "可选标题")
    image_pattern = r'!\[.*?\]\((.*?)(\s+"[^"]+")?\)'
    md_content = re.sub(image_pattern, _replace_link, md_content)

    # 2. 匹配普通文本链接：[任意内容](链接)
    text_link_pattern = r'\[.*?\]\((.*?)\)'
    md_content = re.sub(text_link_pattern, _replace_link, md_content)

    return md_content

def process_list_args(args_list: List[str]) -> List[str]:
    """处理列表类型的参数，支持逗号分隔的字符串

    Args:
        args_list: 命令行参数列表

    Returns:
        处理后的列表，将逗号分隔的项拆分为多个元素
    """
    result = []
    for item in args_list:
        # 分割逗号并去除空白
        if ',' in item:
            parts = [p.strip() for p in item.split(',') if p.strip()]
            result.extend(parts)
        else:
            if item.strip():
                result.append(item.strip())
    return result