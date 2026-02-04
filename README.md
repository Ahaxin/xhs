# Xiaohongshu Auto-Publishing Agent

An automated agent for publishing content to Xiaohongshu (Little Red Book) Creator Center.

## Features

- 🔐 **Automated Login**: SMS and QR code authentication support
- ✍️ **Manual Input**: Rich text editor with image upload
- ✅ **Approval Workflow**: Review and approve content before publishing
- 🤖 **Auto-publish Mode**: Future support for automated publishing
- 📊 **Content Queue**: Track pending, approved, and published content
- 🛡️ **Rate Limiting**: Configurable posting limits (default: 2-3 posts/day)

## Project Structure

```
xhs/
├── src/
│   ├── auth/              # Authentication module
│   ├── content/           # Content management
│   ├── publisher/         # Publishing logic
│   ├── ui/               # Web interface
│   └── utils/            # Shared utilities
├── config/               # Configuration files
├── data/                # Content queue & storage
├── logs/                # Application logs
├── tests/               # Unit & integration tests
├── requirements.txt     # Python dependencies
└── main.py             # Application entry point
```

## Setup

1. **Create virtual environment**:
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

3. **Configure settings**:
   - Edit `config/config.yaml`
   - Set your phone number for SMS login (optional)

4. **Run the application**:
   ```bash
   python main.py
   ```

5. **Access the UI**:
   - Open browser: `http://localhost:5000`

## Usage

### Manual Content Publishing

1. Navigate to the web UI
2. Create new content with text and images
3. Preview the content
4. Submit for approval
5. Review in approval queue
6. Approve to publish to Xiaohongshu

### Configuration

Edit `config/config.yaml` to customize:
- Login method (SMS or QR code)
- Publishing mode (approval or auto)
- Rate limits
- UI settings

## Development Status

- [x] Phase 1: Foundation & Setup
- [x] Phase 2: Authentication System (SMS/QR)
- [x] Phase 3: Database & Content Management
- [x] Phase 4: Web UI - Manual Input
- [x] Phase 5: Approval Workflow
- [x] Phase 6: Publishing Engine
- [ ] Phase 7: Testing & Polish
- [ ] Phase 8: Website Fetching (Future)

## License

MIT
