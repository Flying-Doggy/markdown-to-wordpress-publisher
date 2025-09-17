"""WordPress上传与发布模块

负责将本地资源（图片/文件）上传到WordPress媒体库，
并将处理后的Markdown内容发布为WordPress文章，支持封面图设置。
"""

import os
import mimetypes
from typing import List, Dict, Optional, Tuple
import xmlrpc.client
from xmlrpc.client import Binary
import logging
from wordpress_xmlrpc.methods.posts import NewPost
from wordpress_xmlrpc.methods.media import UploadFile
from .markdown_parser import Asset, MD_ParsedResult
from .utils import setup_logging
from .config import DEFAULT_BLOG_ID, DEFAULT_POST_STATUS, SUPPORTED_IMAGE_TYPES


class WordPressUploader:
    """WordPress资源上传与文章发布器

    核心功能：
    1. 连接WordPress XML-RPC接口
    2. 批量上传本地资源到媒体库（支持文件名前缀，避免覆盖）
    3. 发布Markdown内容为WordPress文章
    4. 为文章设置封面图（特色图片）
    """

    def __init__(
        self,
        wp_url: str,
        username: str,
        password: str,
        logger: Optional[logging.Logger] = None
    ) -> None:
        """初始化WordPress上传器

        注意：
        - 需确保WordPress已启用XML-RPC功能（后台→设置→写作→远程发布）
        - 若开启两步验证，需使用「应用密码」（而非登录密码）

        Args:
            wp_url: WordPress网站根URL（如"https://example.com"）
            username: WordPress登录用户名（需具备「发布文章」和「上传媒体」权限）
            password: WordPress登录密码或应用密码
            logger: 日志实例，若为None则自动初始化默认日志

        Raises:
            ValueError: 若wp_url格式无效（不含http/https）
            ConnectionError: 若无法连接到WordPress XML-RPC接口
        """
        self.logger = logger or setup_logging()
        self.wp_url = self._validate_wp_url(wp_url)
        self.username = username
        self.password = password
        self.blog_id = DEFAULT_BLOG_ID

        # 初始化WordPress XML-RPC客户端
        self.server = self._init_xmlrpc_client()

    def _validate_wp_url(self, wp_url: str) -> str:
        """内部方法：验证WordPress URL格式（确保含http/https）

        Args:
            wp_url: 输入的WordPress URL

        Returns:
            验证后的URL（去除末尾斜杠，统一格式）

        Raises:
            ValueError: 若URL不含http/https
        """
        if not wp_url.startswith(("http://", "https://")):
            self.logger.error(f"WordPress URL格式无效（需含http/https）：{wp_url}")
            raise ValueError("WordPress URL必须以http://或https://开头")
        # 去除末尾斜杠，避免拼接XML-RPC路径时出现重复斜杠
        return wp_url.rstrip("/")

    def _init_xmlrpc_client(self) -> xmlrpc.client.ServerProxy:
        """内部方法：初始化WordPress XML-RPC客户端

        Returns:
            初始化完成的XML-RPC客户端实例

        Raises:
            ConnectionError: 若无法连接到XML-RPC接口
        """
        xmlrpc_path = f"{self.wp_url}/xmlrpc.php"
        try:
            server = xmlrpc.client.ServerProxy(xmlrpc_path, use_builtin_types=True)
            # 简单验证连接（调用system.listMethods，无需权限）
            server.system.listMethods()
            self.logger.debug(f"成功连接到WordPress XML-RPC接口：{xmlrpc_path}")
            return server
        except Exception as e:
            self.logger.error(f"连接WordPress XML-RPC接口失败：{str(e)}")
            raise ConnectionError(f"无法连接到{xmlrpc_path}，请检查URL或XML-RPC启用状态") from e

    def upload_assets(
        self,
        assets: List[Asset],
        file_prefix: str = ""
    ) -> Tuple[Dict[str, str], Dict[str, int]]:
        """批量上传本地资源到WordPress媒体库

        上传逻辑：
        1. 为每个资源生成唯一文件名（支持前缀，避免覆盖）
        2. 读取文件内容并上传到媒体库
        3. 返回「原路径→URL」映射和「原路径→媒体ID」映射

        Args:
            assets: 本地资源列表（Asset对象列表）
            file_prefix: 文件名前缀（如"202409_"，用于分类和防覆盖）

        Returns:
            二元组：
            - link_map: 资源链接映射（{原本地路径: WordPress资源URL}）
            - asset_id_map: 资源ID映射（{原本地路径: WordPress媒体ID}）

        Raises:
            Exception: 单个文件上传失败不会中断批量上传，仅日志报错
        """
        if not assets:
            self.logger.info("无本地资源需要上传")
            return {}, {}

        link_map: Dict[str, str] = {}
        asset_id_map: Dict[str, int] = {}
        total = len(assets)
        success_count = 0

        self.logger.info(f"开始上传{total}个本地资源到WordPress媒体库（前缀：{file_prefix or '无'}）")

        for idx, asset in enumerate(assets, 1):
            self.logger.debug(f"正在上传资源（{idx}/{total}）：{asset.file_name}")
            try:
                # 上传单个资源，获取URL和媒体ID
                url, media_id = self._upload_single_asset(asset, file_prefix)
                if url and media_id:
                    link_map[asset.original_path] = url
                    asset_id_map[asset.original_path] = media_id
                    success_count += 1
                    self.logger.info(f"上传成功（{idx}/{total}）：{asset.file_name} → URL: {url}, ID: {media_id}")
            except Exception as e:
                self.logger.error(f"上传失败（{idx}/{total}）：{asset.file_name}，错误：{str(e)}")

        self.logger.info(f"资源上传完成：成功{success_count}/{total}个")
        return link_map, asset_id_map

    def _file_path_to_Asset(self, file_path: str) -> Optional[Asset]:
        """将文件路径转换为Asset对象"""
        if not os.path.exists(file_path):
            self.logger.error(f"文件不存在: {file_path}")
            return None
            
        if not os.path.isfile(file_path):
            self.logger.error(f"不是有效的文件: {file_path}")
            return None
            
        asset = Asset(
            original_path=file_path,
            absolute_path=os.path.abspath(file_path),
            is_image=True
        )
        return asset

    def _upload_single_asset(self, asset: Asset, file_prefix: str) -> Tuple[Optional[str], Optional[int]]:
        """内部方法：上传单个本地资源到WordPress媒体库

        Args:
            asset: 本地资源对象（Asset）
            file_prefix: 文件名前缀（用于防覆盖）

        Returns:
            二元组：(资源URL, 媒体ID)，若上传失败则为(None, None)

        Raises:
            Exception: 若文件读取失败或XML-RPC调用出错
        """
        # 1. 检查输入文件是否为Asset
        if not isinstance(asset, Asset):
            self.logger.error("上传方法需要Asset对象作为参数")
            return None, None

        # 2. 生成上传文件名（前缀+原文件名，防覆盖）
        upload_file_name = f"{file_prefix}{asset.file_name}"

        # 3. 读取文件内容（二进制模式）
        try:
            with open(asset.absolute_path, "rb") as f:
                file_content = f.read()
        except Exception as e:
            raise Exception(f"文件读取失败：{str(e)}") from e

        # 4. 自动识别MIME类型（若无法识别则用默认值）
        mime_type, _ = mimetypes.guess_type(asset.absolute_path)
        if not mime_type:
            mime_type = "application/octet-stream"  # 默认MIME类型
            self.logger.warning(f"无法识别文件MIME类型，使用默认值：{mime_type}（文件：{asset.file_name}）")
        # 验证图片MIME类型（避免非图片被误判为图片）
        if asset.is_image and mime_type not in SUPPORTED_IMAGE_TYPES:
            self.logger.warning(f"文件类型不是支持的图片（MIME：{mime_type}），仍尝试上传（文件：{asset.file_name}）")

        # 5. 准备上传参数（符合WordPress XML-RPC要求）
        upload_data = {
            "name": upload_file_name,
            "type": mime_type,
            "bits": Binary(file_content),
            "overwrite": False  # 不覆盖已存在的文件（若同名则自动加后缀）
        }

        # 6. 调用XML-RPC接口上传
        try:
            response = self.server.wp.uploadFile(
                0,  
                self.username,
                self.password,
                upload_data
            )

            # 提取返回结果（response含id、url、file等字段）
            media_id = response["id"]
            media_url = response["url"]
            return media_url, media_id
        except Exception as e:
            raise Exception(f"XML-RPC上传失败：{str(e)}") from e

    def publish_post(
        self,
        content: str,
        title: str,
        categories: List[str] = None,
        tags: List[str] = None,
        thumbnail_id: Optional[int] = None,
        status: str = DEFAULT_POST_STATUS
    ) -> Optional[int]:
        """发布Markdown内容为WordPress文章

        执行流程：
        1. 准备文章数据（标题、内容、分类、标签、状态）
        2. 调用XML-RPC接口创建文章
        3. 若提供封面图ID，为文章设置封面图

        Args:
            content: 处理后的Markdown内容（链接已替换为WordPress资源URL）
            title: 文章标题
            categories: 文章分类列表（如["技术博客", "Python"]），默认空列表
            tags: 文章标签列表（如["Markdown", "WordPress"]），默认空列表
            thumbnail_id: 封面图媒体ID（从upload_assets返回的asset_id_map获取），默认None
            status: 文章状态，可选值："publish"（发布）、"draft"（草稿）、"pending"（待审核）

        Returns:
            文章ID（int），若发布失败则为None

        Raises:
            Exception: 若文章创建或封面图设置失败
        """
        # 处理默认参数（避免None）
        categories = categories or []
        tags = tags or []

        self.logger.info(f"开始发布WordPress文章：{title}（状态：{status}，分类：{categories}，标签：{tags}）")

        post_data = {
            "post_title": title,
            "post_content": content,
            "post_status": status,
            "post_type": "post",
            "terms_names": {
                "category": categories,
                "post_tag": tags
            }
        }
        
        if thumbnail_id:
            post_data['post_thumbnail'] = thumbnail_id
            
        try:
            # 调用XML-RPC接口创建文章
            post_id = self.server.wp.newPost(
                0,
                self.username,
                self.password,
                post_data
            )
            self.logger.info(f"文章创建成功：ID={post_id}")
            
            # # 修改：在这里调用设置封面图的方法
            # if thumbnail_id:
            #     try:
            #         self._set_featured_image(post_id, thumbnail_id)
            #     except Exception as e:
            #         self.logger.warning(f"封面图设置失败，但不影响文章发布：{str(e)}")
            
            # self.logger.info(f"文章链接：{self.wp_url}/?p={post_id}")
            return post_id

        except Exception as e:
            self.logger.error(f"文章发布失败：{str(e)}")
            raise

    def _set_featured_image(self, post_id: int, thumbnail_id: int) -> None:
        """内部方法：为WordPress文章设置封面图（特色图片）

        Args:
            post_id: 文章ID（从publish_post返回）
            thumbnail_id: 封面图媒体ID（从upload_assets返回）

        Raises:
            Exception: 若封面图设置失败（如媒体ID无效、权限不足）
        """
        try:
            # 调用wp.setPostThumbnail接口设置封面图
            result = self.server.wp.setPostThumbnail(
                self.blog_id,
                self.username,
                self.password,
                post_id,
                thumbnail_id
            )
            if not result:
                raise Exception("接口返回失败（无错误信息）")
            self.logger.info(f"成功为文章{post_id}设置封面图（媒体ID：{thumbnail_id}）")
        except Exception as e:
            # 封面图设置失败不中断文章发布，仅抛出警告级错误
            error_msg = f"封面图设置失败（文章ID：{post_id}，媒体ID：{thumbnail_id}）：{str(e)}"
            self.logger.warning(error_msg)
            raise Exception(error_msg) from e

    def publish_from_parsed_result(
        self,
        parsed_result: MD_ParsedResult,
        title: Optional[str] = None,
        categories: List[str] = None,
        tags: List[str] = None,
        file_prefix: str = "",
        status: str = DEFAULT_POST_STATUS,
    ) -> Optional[int]:
        """一站式发布：从解析结果直接完成上传、链接替换、发布

        整合流程：
        1. 上传解析结果中的本地资源
        2. 替换Markdown内容中的链接
        3. 提取封面图ID（若存在）
        4. 发布文章

        Args:
            parsed_result: Markdown解析结果（MD_ParsedResult对象）
            title: 文章标题，默认使用Markdown文件名（不含扩展名）
            categories: 文章分类列表，默认空列表
            tags: 文章标签列表，默认空列表
            file_prefix: 资源文件名前缀，默认空字符串
            status: 文章状态，默认草稿

        Returns:
            文章ID，若发布失败则为None
        """
        """一站式发布：从解析结果直接完成上传、链接替换、发布"""
        if not title:
            title = os.path.splitext(os.path.basename(parsed_result.file_path))[0]
            self.logger.debug(f"未指定文章标题，使用Markdown文件名：{title}")

        # 1. 创建一个列表，包含所有需要上传的资源，包括封面图
        assets_to_upload = list(parsed_result.local_assets)
        if parsed_result.cover_image and parsed_result.cover_image not in assets_to_upload:
            assets_to_upload.append(parsed_result.cover_image)

        # 2. 上传所有本地资源
        link_map, asset_id_map = self.upload_assets(assets_to_upload, file_prefix)

        # 3. 替换Markdown链接
        from .utils import replace_markdown_links
        updated_content = replace_markdown_links(parsed_result.content, link_map)

        # 4. 提取封面图ID（若存在）
        thumbnail_id = None
        if parsed_result.cover_image:
            thumbnail_id = asset_id_map.get(parsed_result.cover_image.original_path)
            if not thumbnail_id:
                self.logger.warning("封面图已识别但未上传成功，跳过封面图设置")
                
        # 5. 发布文章
        return self.publish_post(
            content=updated_content,
            title=title,
            categories=categories,
            tags=tags,
            thumbnail_id=thumbnail_id,
            status=status
        )