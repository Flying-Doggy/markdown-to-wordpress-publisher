<!--
 * @Autor: Flying-Doggy
 * @Date: 2025-09-17 13:53:41
 * @title: 
-->
# markdown-to-wordpress-publisher
 A simple  tool for automatically uploading local Markdown files (including images and other resources) to WordPress and publishing them as posts.

## 核心功能
1. **自动解析**：提取Markdown中的本地资源（图片/文件）和外部链接
2. **资源上传**：批量上传本地资源到WordPress媒体库，支持文件名前缀防覆盖
3. **链接替换**：自动将Markdown中的本地路径替换为WordPress资源URL
4. **封面设置**：支持通过Markdown标记（`<!-- cover: 路径 -->`）或命令行指定封面图
5. **一键发布**：整合解析、上传、替换、发布流程，支持草稿/发布状态切换


## 环境要求
- Python 3.8+
- WordPress 5.0+（需启用XML-RPC功能）


## 安装步骤
1. **克隆项目**
   ```bash
   git clone https://github.com/Flying-Doggy/markdown-to-wordpress-publisher.git
   cd markdown-to-wordpress-publisher
   ```

2.  **安装依赖**
```bash
pip install -r requirements.txt
```

3. **使用方法**
```bash
# 发布Markdown文件为草稿（默认状态）
python -m src.main ./my_article.md \
  --url https://your-wordpress-site.com \
  --username your-wp-username \
  --password your-wp-password \
  --category 技术博客 \
  --tag Python \
  --tag Markdown

```
