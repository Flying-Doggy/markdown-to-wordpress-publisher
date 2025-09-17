'''
Autor: Flying-Doggy
Date: 2025-09-17 13:58:11
title: 
'''
"""项目配置常量定义

包含日志格式、支持的媒体类型、默认参数等全局配置，便于统一修改。
"""

# 默认日志格式（时间、级别、模块、消息）
DEFAULT_LOG_FORMAT = "%(asctime)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s"
# 默认日志级别
DEFAULT_LOG_LEVEL = "INFO"

# 支持的图片媒体类型（用于MIME类型校验）
SUPPORTED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/svg+xml"
}

# WordPress文章默认状态
DEFAULT_POST_STATUS = "draft"  # 默认为草稿，避免误发布
# WordPress默认博客ID（多博客环境下需调整，单博客默认0）
DEFAULT_BLOG_ID = 0

# WordPress用户信息配置
WP_URL = ''
WP_USERNAME = ''
WP_PASSWD = ''
