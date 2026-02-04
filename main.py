"""
Main application entry point.
"""
import sys
import asyncio
import uvicorn
from src.utils.config import get_config

# Fix for Windows asyncio subprocess issues with Playwright
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

if __name__ == "__main__":
    config = get_config()
    
    uvicorn.run(
        "src.ui.api:app",
        host=config.ui.host,
        port=config.ui.port,
        reload=config.ui.debug,
        log_level="info",
    )
