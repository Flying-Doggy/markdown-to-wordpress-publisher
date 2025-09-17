"""主程序入口

提供命令行接口，支持用户通过命令行快速上传Markdown文件到WordPress。
"""

import argparse
import os
from .markdown_parser import MarkdownParser
from .uploader import WordPressUploader,Asset
from .utils import setup_logging, process_list_args
from .config import DEFAULT_POST_STATUS, WP_URL, WP_USERNAME, WP_PASSWD


def parse_args() -> argparse.Namespace:
    """解析命令行参数

    Returns:
        解析后的参数对象
    """
    parser = argparse.ArgumentParser(
        description="Markdown to WordPress 自动发布工具",
        epilog="示例：python -m src.main ./my_article.md --url https://example.com --username admin --password app_pass --category 技术 --tag Python"
    )

    # 必选参数
    parser.add_argument(
        "md_file",
        help="本地Markdown文件路径（如./article.md）"
    )

    parser.add_argument(
        "--url",
        default=WP_URL,
        help=f"WordPress网站根URL（如https://example.com，默认从配置文件获取：{WP_URL if WP_URL else '未设置'}）"
    )
    parser.add_argument(
        "--username",
        default=WP_USERNAME,
        help=f"WordPress登录用户名（默认从配置文件获取：{WP_USERNAME if WP_USERNAME else '未设置'}）"
    )
    parser.add_argument(
        "--password",
        default=WP_PASSWD,
        help=f"WordPress登录密码或应用密码（默认从配置文件获取：{'已设置' if WP_PASSWD else '未设置'}）"
    )

    # 可选参数
    parser.add_argument(
        "--title",
        help="文章标题（默认使用Markdown文件名）"
    )
    parser.add_argument(
        "--cover",
        help="手动指定封面图片路径（优先级高于Markdown中的cover标记）"
    )
    parser.add_argument(
        "--category",
        action="append",
        default=[],
        help="文章分类（可多次使用，如--category 技术 --category Python）"
    )
    parser.add_argument(
        "--tag",
        action="append",
        default=[],
        help="文章标签（可多次使用，如--tag Markdown --tag WordPress）"
    )
    parser.add_argument(
        "--prefix",
        default="",
        help="资源文件名前缀（防覆盖，如202409_）"
    )
    parser.add_argument(
        "--status",
        default=DEFAULT_POST_STATUS,
        choices=["publish", "draft", "pending"],
        help=f"文章状态（默认：{DEFAULT_POST_STATUS}）"
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="日志级别（默认：INFO）"
    )

    return parser.parse_args()


def main() -> None:
    """主程序逻辑"""
    # 1. 解析命令行参数
    args = parse_args()

     # 验证必要参数
    if not args.url:
        raise ValueError("WordPress URL未提供，请通过命令行参数或配置文件设置")
    if not args.username:
        raise ValueError("WordPress用户名未提供，请通过命令行参数或配置文件设置")
    if not args.password:
        raise ValueError("WordPress密码未提供，请通过命令行参数或配置文件设置")

    # 处理分类和标签参数（支持逗号分隔）
    categories = process_list_args(args.category)
    tags = process_list_args(args.tag)

    # 2. 初始化日志
    logger = setup_logging(log_level=args.log_level)
    logger.info("=" * 50)
    logger.info("Markdown to WordPress 自动发布工具启动")
    logger.info(f"命令行参数：{args}")

    try:
        # 3. 解析Markdown文件
        parser = MarkdownParser(logger=logger)
        parsed_result = parser.parse(args.md_file)

        # 4. 从Markdown头文件获取信息（如果用户未提供）
        front_matter = parsed_result.front_matter
        
        # 处理标题
        title = args.title
        if not title and 'title' in front_matter:
            title = front_matter['title']
            logger.info(f"从Markdown头文件获取标题：{title}")

        # 处理分类
        if not categories and 'categories' in front_matter:
            categories = process_list_args([front_matter['categories']])
            logger.info(f"从Markdown头文件获取分类：{categories}")

        # 处理标签
        if not tags and 'tags' in front_matter:
            tags = process_list_args([front_matter['tags']])
            logger.info(f"从Markdown头文件获取标签：{tags}")

        # 处理封面
        cover_path = args.cover
        if not cover_path and parsed_result.cover_path:
            cover_path = parsed_result.cover_path
            logger.info(f"从Markdown头文件获取标题：{cover_path}")

        # 处理前缀
        prefix = prefix if args.prefix else os.path.basename( parsed_result.file_path ).split('.')[0]
        
        # 如果命令行手动指定了封面图，则覆盖Markdown中的标记
        if args.cover:
            # 创建一个新的Asset对象来表示手动指定的封面图
            cover_asset = Asset(
                original_path=args.cover,
                absolute_path=os.path.abspath(os.path.join(os.path.dirname(args.md_file), args.cover)),
                is_image=True
            )
            parsed_result.cover_image = cover_asset
            logger.info(f"命令行手动指定封面图：{args.cover}")


        # 5. 初始化WordPress上传器
        uploader = WordPressUploader(
            wp_url=args.url,
            username=args.username,
            password=args.password,
            logger=logger
        )

        # 6. 发布
        post_id = uploader.publish_from_parsed_result(
            parsed_result=parsed_result,
            title=title,
            categories=categories,
            tags=tags,
            file_prefix=prefix,
            status=args.status,
        )

        if post_id:
            logger.info("=" * 50)
            logger.info(f"发布流程全部完成！文章ID：{post_id}")
            logger.info(f"文章链接：{args.url.rstrip('/')}/?p={post_id}")
        else:
            logger.error("=" * 50)
            logger.error("发布流程失败，未生成文章ID")

    except Exception as e:
        logger.error("=" * 50)
        logger.error(f"程序执行出错：{str(e)}", exc_info=True)
        exit(1)


if __name__ == "__main__":
    main()