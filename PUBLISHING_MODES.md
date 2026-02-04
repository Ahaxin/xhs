# Xiaohongshu Publishing Modes

## Supported Publishing Modes

The system now supports **three publishing modes** that match Xiaohongshu's Creator Center:

### 1. 上传图文 - 上传图片 (Image-Text Upload - Images First)
**Mode**: `IMAGE_TEXT_UPLOAD`

**Workflow**:
1. Upload images first
2. Then add title and text description
3. Publish

**Use case**: When you have images ready and want to add text descriptions

---

### 2. 上传图文 - 文字配图 (Image-Text Compose - Text First)
**Mode**: `IMAGE_TEXT_COMPOSE`

**Workflow**:
1. Write title and text content first
2. Then add images to complement the text
3. Publish

**Use case**: When you have text content ready and want to add supporting images

---

### 3. 写长文 (Long Article)
**Mode**: `LONG_ARTICLE`

**Workflow**:
1. Write long-form article content
2. Add images within the article (optional)
3. Publish with full-screen reading experience

**Use case**: For detailed articles, tutorials, or long-form content

---

## Implementation

### Database Schema
Added `publish_mode` column to content table:
```sql
ALTER TABLE content ADD COLUMN publish_mode TEXT DEFAULT 'image_text_upload'
```

### Content Model
```python
class PublishMode(str, Enum):
    IMAGE_TEXT_UPLOAD = "image_text_upload"
    IMAGE_TEXT_COMPOSE = "image_text_compose"
    LONG_ARTICLE = "long_article"

class Content:
    def __init__(self, ..., publish_mode: PublishMode = PublishMode.IMAGE_TEXT_UPLOAD):
        self.publish_mode = publish_mode
```

### API Usage
When creating content via API, specify the publish_mode:
```python
content_manager.create_content(
    title="My Post",
    body="Content here",
    images=[...],
    publish_mode=PublishMode.IMAGE_TEXT_UPLOAD  # or IMAGE_TEXT_COMPOSE or LONG_ARTICLE
)
```

---

## Publisher Behavior

The publisher will adapt its workflow based on the `publish_mode`:

- **IMAGE_TEXT_UPLOAD**: Navigate to "上传图文" → "上传图片", upload images first, then fill text
- **IMAGE_TEXT_COMPOSE**: Navigate to "上传图文" → "文字配图", fill text first, then upload images  
- **LONG_ARTICLE**: Navigate to "写长文", use long-form editor

---

## Migration

Existing content in the database will default to `IMAGE_TEXT_UPLOAD` mode. The database migration is automatic when the application starts.
