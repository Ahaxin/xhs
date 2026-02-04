# Quick Start Guide

## Installation

1. **Navigate to project directory**:
   ```bash
   cd f:\PROJECTS\xhs
   ```

2. **Create and activate virtual environment**:
   ```bash
   python -m venv venv
   ```

3. **Activate virtual environment**:
   
   **Option A - PowerShell (Recommended)**:
   ```powershell
   # If you get execution policy error, run this first (as Administrator):
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   
   # Then activate:
   venv\Scripts\Activate.ps1
   ```
   
   **Option B - Command Prompt**:
   ```cmd
   venv\Scripts\activate.bat
   ```
   
   **Option C - Bypass policy (one-time)**:
   ```powershell
   powershell -ExecutionPolicy Bypass -File venv\Scripts\Activate.ps1
   ```

4. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
   
   Note: Selenium will automatically download ChromeDriver when first used.

5. **Configure settings** (optional):
   - Edit `config/config.yaml`
   - Set your phone number for SMS login if desired

6. **Run the application**:
   ```bash
   python main.py
   ```

7. **Access the web interface**:
   - Open browser: http://localhost:5000

## Usage

### First Time Setup

1. **Login to Xiaohongshu**:
   - Click "登录小红书" tab
   - Choose login method (SMS or QR code)
   - Follow the prompts in the browser window
   - Session will be saved for future use

### Creating Content

1. **Go to "创建内容" tab**
2. **Fill in**:
   - Title (标题)
   - Content body (正文)
   - Upload images (optional)
3. **Click "提交内容"**
4. **Content will appear in "待审核" (Pending) queue**

### Approving & Publishing

1. **Go to "待审核" tab**
2. **Review content**
3. **Click "批准" (Approve) or "拒绝" (Reject)**
4. **Approved content appears in "所有内容" tab**
5. **Click "发布到小红书" to publish**

### Monitoring

- Dashboard shows statistics:
  - Pending content count
  - Approved content count
  - Published content count
  - Today's published count

## Troubleshooting

### PowerShell Execution Policy Error
If you get "cannot be loaded because running scripts is disabled":

**Solution 1 (Recommended)** - Enable for current user:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**Solution 2** - Use Command Prompt instead:
```cmd
venv\Scripts\activate.bat
```

**Solution 3** - Bypass for single session:
```powershell
powershell -ExecutionPolicy Bypass -File venv\Scripts\Activate.ps1
```

### Browser Issues
- Browser should open automatically using Selenium
- Chrome will be downloaded automatically if not installed
- If issues persist, ensure Chrome browser is installed on your system

### Windows Asyncio Error (FIXED)
- Switched from Playwright to Selenium to avoid Windows asyncio issues
- No action needed - this is now resolved

### Login Issues
- Clear saved session: delete `data/xhs_session.json`
- Try different login method
- Check internet connection

### Publishing Issues
- Ensure you're logged in (check status in header)
- Check daily limit (default: 3 posts/day)
- Review logs in `logs/xhs.log`

## Configuration

Edit `config/config.yaml` to customize:

```yaml
xiaohongshu:
  login_method: "sms"  # or "qr_code"
  phone_number: "your_phone"  # For SMS login

publishing:
  mode: "approval"  # or "auto" (future)
  max_posts_per_day: 3
  retry_attempts: 3
```

## Next Steps

- Test the full workflow
- Adjust selectors in `xhs_auth.py` and `publisher.py` if needed
- Implement website fetching (Phase 8) when ready
