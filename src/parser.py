"""解析Markdown文件

负责读取本地Markdown文件，提取文本内容、本地资源链接（图片/文件）和外部链接，
并将解析结果封装为结构化数据，为后续上传步骤提供输入。
"""

import os
import re
from urllib.parse import urlparse
from dataclasses import dataclass, field
from typing import List, Optional, Dict
import logging
from .utils import setup_logging


@dataclass
class Asset:
    """本地资源文件信息封装

    存储单个本地资源的关键信息，用于后续上传和链接替换。

    Attributes:
        original_path: Markdown中记录的原始路径（相对/绝对路径）
        absolute_path: 资源的绝对路径（便于读取文件）
        is_image: 是否为图片资源（True=图片，False=其他文件如PDF）
        file_name: 资源文件名（含扩展名，如"cover.jpg"）
    """
    original_path: str
    absolute_path: str
    is_image: bool
    file_name: str = field(init=False)  # 自动推导，无需手动传入

    def __post_init__(self) -> None:
        """初始化后自动设置文件名（从绝对路径提取）"""
        self.file_name = os.path.basename(self.absolute_path)


@dataclass
class MD_ParsedResult:
    """Markdown解析结果封装

    结构化存储解析后的所有信息，作为模块输出。

    Attributes:
        content: Markdown原始文本内容
        file_path: Markdown文件的绝对路径
        dir_path: Markdown文件所在目录的绝对路径
        external_links: 外部链接列表（http/https开头的链接）
        local_assets: 本地资源列表（Asset对象列表）
        cover_image: 封面图资源（若Markdown中用<!-- cover: 路径 -->标记）
        front_matter: Markdown头文件信息文件
    """
    content: str
    file_path: str
    dir_path: str
    external_links: List[str] = field(default_factory=list)
    local_assets: List[Asset] = field(default_factory=list)
    cover_image: Optional[Asset] = None
    front_matter: Dict[str, str] = field(default_factory=dict)


class MarkdownParser:
    """Markdown文件解析器

    核心功能：
    1. 验证并读取本地Markdown文件
    2. 提取文本内容
    3. 分类提取外部链接和本地资源链接
    4. 识别Markdown中标记的封面图
    """

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        """初始化解析器

        Args:
            logger: 日志实例，若为None则自动初始化默认日志
        """
        self.logger = logger or setup_logging()

        # 封面图标记正则（格式：<!-- cover: 资源路径 -->）
        self._cover_pattern = r'<!--\s*cover:\s*(.*?)\s*-->'
        # 头文件正则（YAML Front Matter）
        self._front_matter_pattern = r'^---\s*\n(.*?)\n---\s*'

    def parse(self, md_file_path: str) -> MD_ParsedResult:
        """解析Markdown文件，返回结构化结果

        执行流程：
        1. 验证文件存在性
        2. 读取文件内容
        3. 提取文件路径信息
        4. 提取头文件信息
        5. 提取外部链接和本地资源
        6. 识别封面图（若存在）

        Args:
            md_file_path: 本地Markdown文件路径（相对/绝对路径均可）

        Returns:
            解析结果（MD_ParsedResult对象）

        Raises:
            FileNotFoundError: 若传入的Markdown文件不存在
            UnicodeDecodeError: 若文件编码不是UTF-8（无法读取）
        """
        # 1. 验证文件存在性
        if not os.path.exists(md_file_path):
            self.logger.error(f"Markdown文件不存在：{md_file_path}")
            raise FileNotFoundError(f"Markdown文件不存在: {md_file_path}")

        # 2. 处理文件路径（转为绝对路径，便于后续资源定位）
        file_path = os.path.abspath(md_file_path)
        dir_path = os.path.dirname(file_path)
        self.logger.debug(f"解析Markdown文件：{file_path}（所在目录：{dir_path}）")

        # 3. 读取文件内容（强制UTF-8编码，避免中文乱码）
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except UnicodeDecodeError as e:
            self.logger.error(f"文件编码错误（需UTF-8）：{file_path}，错误：{str(e)}")
            raise
        
        # 4. 提取头文件信息
        front_matter = self._extract_front_matter(content)

        # 5. 初始化解析结果
        parsed_result = MD_ParsedResult(
            content=content,
            file_path=file_path,
            dir_path=dir_path,
            front_matter=front_matter
        )

        # 6. 提取链接（外部链接 + 本地资源）
        self._extract_links(content, dir_path, parsed_result)

        # 7. 提取封面图（若Markdown中标记了封面）
        self._extract_cover_image(content, dir_path, parsed_result)

        # 7. 输出解析统计信息
        self.logger.info(
            f"Markdown解析完成："
            f"本地资源{len(parsed_result.local_assets)}个，"
            f"外部链接{len(parsed_result.external_links)}个，"
            f"封面图{'已识别' if parsed_result.cover_image else '未设置'}，"
            f"头文件信息{len(parsed_result.front_matter)}项"
        )

        return parsed_result

    def _extract_front_matter(self, content: str) -> Dict[str, str]:
        """提取Markdown头文件信息（YAML Front Matter）"""
        match = re.search(self._front_matter_pattern, content, re.DOTALL)
        if not match:
            return {}

        front_matter = {}
        matter_content = match.group(1)
        
        # 解析YAML格式的键值对
        for line in matter_content.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
                
            if ':' in line:
                key, value = line.split(':', 1)
                front_matter[key.strip().lower()] = value.strip()
                
        self.logger.debug(f"提取到头文件信息：{front_matter}")
        return front_matter

    def _extract_links(
        self, content: str, base_dir: str, result: MD_ParsedResult
    ) -> None:
        """内部方法：从Markdown内容中提取所有链接并分类

        分类逻辑：
        - 外部链接：http/https开头的链接，直接加入external_links
        - 本地资源：非http/https链接，转为绝对路径并验证存在性，加入local_assets

        Args:
            content: Markdown文本内容
            base_dir: Markdown文件所在目录（用于转换本地资源的相对路径）
            result: 解析结果对象（用于存储提取的链接）
        """
        # 匹配Markdown链接的正则：支持图片（![alt](link)）和普通链接（[text](link)）
        # 分组说明：
        # group 1: 链接类型标记（"!"表示图片，空表示普通链接）
        # group 2: 链接路径（核心提取目标）
        # group 3: 可选标题（如"title"，暂不处理）
        link_pattern = r'(!?)\[.*?\]\((.*?)(\s+"[^"]+")?\)'
        matches = re.findall(link_pattern, content)

        for link_mark, path, _ in matches:
            path = path.strip()
            if not path:  # 跳过空链接
                continue

            # 分类1：外部链接（http/https开头）
            parsed_url = urlparse(path)
            if parsed_url.scheme in ("http", "https"):
                result.external_links.append(path)
                self.logger.debug(f"识别外部链接：{path}")
                continue

            # 分类2：本地资源（非http/https链接）
            self._process_local_asset(link_mark, path, base_dir, result)

    def _process_local_asset(
        self, link_mark: str, path: str, base_dir: str, result: MD_ParsedResult
    ) -> None:
        """内部方法：处理本地资源链接，验证存在性并封装为Asset对象

        Args:
            link_mark: 链接类型标记（"!"表示图片，空表示普通文件）
            path: Markdown中记录的本地资源路径（相对/绝对路径）
            base_dir: Markdown文件所在目录（用于转换相对路径为绝对路径）
            result: 解析结果对象（用于存储本地资源）
        """
        # 转换为绝对路径（处理相对路径场景）
        absolute_path = os.path.abspath(os.path.join(base_dir, path))

        # 验证资源是否存在
        if not os.path.exists(absolute_path):
            self.logger.warning(f"本地资源不存在（跳过）：{absolute_path}（原路径：{path}）")
            return

        # 封装为Asset对象并加入结果
        is_image = bool(link_mark)  # "!"标记表示图片
        asset = Asset(
            original_path=path,
            absolute_path=absolute_path,
            is_image=is_image
        )
        result.local_assets.append(asset)
        self.logger.debug(
            f"识别本地资源：{asset.file_name}（类型：{'图片' if is_image else '文件'}，路径：{absolute_path}）"
        )

    def _extract_cover_image(
        self, content: str, base_dir: str, result: MD_ParsedResult
    ) -> None:
        """内部方法：从Markdown内容中提取封面图标记（<!-- cover: 路径 -->）

        若标记的封面图存在，将其封装为Asset对象并加入result.cover_image；
        同时确保封面图也在local_assets中（避免重复上传）。

        Args:
            content: Markdown文本内容
            base_dir: Markdown文件所在目录（用于转换封面图路径）
            result: 解析结果对象（用于存储封面图）
        """
        # 匹配封面图标记
        cover_match = re.search(self._cover_pattern, content)
        if not cover_match:
            self.logger.debug("未找到封面图标记（格式：<!-- cover: 路径 -->）")
            return

        cover_path = cover_match.group(1).strip()
        if not cover_path:
            self.logger.warning("封面图标记存在但路径为空（跳过）")
            return

        # 转换为绝对路径并验证存在性
        absolute_path = os.path.abspath(os.path.join(base_dir, cover_path))
        if not os.path.exists(absolute_path):
            self.logger.warning(f"封面图标记路径不存在（跳过）：{absolute_path}（原标记：{cover_path}）")
            return

        # 验证是否为图片（封面图必须是图片类型）
        if not self._is_image_file(absolute_path):
            self.logger.warning(f"封面图标记路径不是图片文件（跳过）：{absolute_path}")
            return

        self.cover_path = cover_path
        self.logger.debug(f"识别封面图：{self.cover_path}（路径：{absolute_path}）")
        return self.cover_path

    def _is_image_file(self, file_path: str) -> bool:
        """内部方法：判断文件是否为图片（通过扩展名）

        Args:
            file_path: 文件绝对路径

        Returns:
            True=图片文件，False=非图片文件
        """
        image_extensions = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg")
        return file_path.lower().endswith(image_extensions)