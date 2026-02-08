"""
Integration tests for the complete BannaFlow -> XHS Publisher workflow.

These tests verify the end-to-end integration between:
1. BannaFlow content generation
2. Local content management
3. XHS publishing

Usage:
    python -m tests.test_integration --mode interactive
    python -m tests.test_integration --mode import
"""
import sys
import argparse
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger


def setup_logging():
    """Setup test logging."""
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO"
    )
    logger.add(
        "logs/test_integration.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG",
        rotation="10 MB"
    )


def test_bannaflow_connection():
    """Test connecting to BannaFlow."""
    logger.info("=" * 60)
    logger.info("Test 1: BannaFlow Connection")
    logger.info("=" * 60)

    from src.generator.bannaflow import BannaFlowIntegration

    integration = BannaFlowIntegration(headless=False)

    try:
        success = integration.open_bannaflow()
        if success:
            logger.info("✓ Successfully connected to BannaFlow")

            # Get history
            history = integration.get_published_history()
            logger.info(f"✓ Found {len(history)} items in BannaFlow history")

            return True
        else:
            logger.error("✗ Failed to connect to BannaFlow")
            return False

    finally:
        integration.close()


def test_content_import():
    """Test importing content from BannaFlow."""
    logger.info("=" * 60)
    logger.info("Test 2: Content Import")
    logger.info("=" * 60)

    from src.generator.bannaflow import BannaFlowIntegration
    from src.content.database import Database
    from src.content.manager import ContentManager

    integration = BannaFlowIntegration(headless=False)
    db = Database("data/test_integration.db")
    manager = ContentManager(db)

    try:
        # Import from BannaFlow
        contents = integration.import_from_bannaflow()

        if not contents:
            logger.warning("No content found in BannaFlow - this is OK if you haven't generated any")
            return True

        logger.info(f"✓ Imported {len(contents)} content items")

        # Show first item
        content = contents[0]
        logger.info(f"  Title: {content.title[:50]}...")
        logger.info(f"  Body length: {len(content.body)} chars")
        logger.info(f"  Tags: {content.tags}")
        logger.info(f"  Images: {len(content.images)}")

        return True

    finally:
        integration.close()


def test_workflow_dry_run():
    """Test workflow initialization without actually publishing."""
    logger.info("=" * 60)
    logger.info("Test 3: Workflow Dry Run")
    logger.info("=" * 60)

    from src.generator.workflow import ContentWorkflow
    from src.content.database import PublishMode

    workflow = ContentWorkflow(
        db_path="data/test_workflow.db",
        session_file="data/test_session.json",
    )

    try:
        # Initialize steps
        workflow._init_steps()
        logger.info(f"✓ Workflow initialized with {len(workflow.steps)} steps:")
        for i, step in enumerate(workflow.steps):
            logger.info(f"  {i + 1}. {step.name}")

        # Test initialization step
        success = workflow._step_initialize()
        if success:
            logger.info("✓ Components initialized successfully")
        else:
            logger.warning("✗ Component initialization failed")

        return success

    finally:
        workflow.cleanup()


def test_interactive_workflow():
    """Run interactive workflow for manual testing."""
    logger.info("=" * 60)
    logger.info("Interactive Workflow Test")
    logger.info("=" * 60)
    logger.info("This will:")
    logger.info("  1. Open BannaFlow in a browser")
    logger.info("  2. Wait for you to generate content")
    logger.info("  3. Import the content")
    logger.info("  4. Ask for approval")
    logger.info("  5. Login to XHS")
    logger.info("  6. Publish the content")
    logger.info("=" * 60)

    response = input("Continue? (y/n): ").strip().lower()
    if response != 'y':
        logger.info("Cancelled by user")
        return False

    from src.generator.workflow import ContentWorkflow
    from src.content.database import PublishMode

    workflow = ContentWorkflow()

    try:
        success = workflow.run_interactive(
            publish_mode=PublishMode.IMAGE_TEXT_UPLOAD,
            auto_approve=False,  # Manual approval
        )

        if success:
            logger.info("✓ Interactive workflow completed successfully!")
        else:
            logger.error("✗ Interactive workflow failed")

        return success

    finally:
        workflow.cleanup()


def test_import_workflow():
    """Run import-and-publish workflow."""
    logger.info("=" * 60)
    logger.info("Import & Publish Workflow Test")
    logger.info("=" * 60)
    logger.info("This will:")
    logger.info("  1. Import existing content from BannaFlow")
    logger.info("  2. Auto-approve the content")
    logger.info("  3. Login to XHS")
    logger.info("  4. Publish the content")
    logger.info("=" * 60)

    response = input("Continue? (y/n): ").strip().lower()
    if response != 'y':
        logger.info("Cancelled by user")
        return False

    from src.generator.workflow import ContentWorkflow
    from src.content.database import PublishMode

    workflow = ContentWorkflow()

    try:
        success = workflow.run_import_and_publish(
            publish_mode=PublishMode.IMAGE_TEXT_UPLOAD,
            auto_approve=True,  # Auto approve
        )

        if success:
            logger.info("✓ Import workflow completed successfully!")
        else:
            logger.error("✗ Import workflow failed")

        return success

    finally:
        workflow.cleanup()


def run_all_tests():
    """Run all non-interactive tests."""
    logger.info("=" * 60)
    logger.info("Running All Integration Tests")
    logger.info("=" * 60)

    results = []

    # Test 1: BannaFlow connection
    try:
        results.append(("BannaFlow Connection", test_bannaflow_connection()))
    except Exception as e:
        logger.error(f"Test failed with exception: {e}")
        results.append(("BannaFlow Connection", False))

    # Test 2: Content import
    try:
        results.append(("Content Import", test_content_import()))
    except Exception as e:
        logger.error(f"Test failed with exception: {e}")
        results.append(("Content Import", False))

    # Test 3: Workflow dry run
    try:
        results.append(("Workflow Dry Run", test_workflow_dry_run()))
    except Exception as e:
        logger.error(f"Test failed with exception: {e}")
        results.append(("Workflow Dry Run", False))

    # Summary
    logger.info("=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)

    passed = 0
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        logger.info(f"  {status}: {name}")
        if result:
            passed += 1

    logger.info("=" * 60)
    logger.info(f"Total: {passed}/{len(results)} tests passed")
    logger.info("=" * 60)

    return passed == len(results)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Integration tests for BannaFlow -> XHS workflow")
    parser.add_argument(
        "--mode",
        choices=["all", "interactive", "import", "connection", "dry-run"],
        default="all",
        help="Test mode to run"
    )
    args = parser.parse_args()

    setup_logging()

    logger.info("=" * 60)
    logger.info("XHS Auto-Publisher Integration Tests")
    logger.info(f"Mode: {args.mode}")
    logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    # Ensure directories exist
    Path("logs").mkdir(exist_ok=True)
    Path("data").mkdir(exist_ok=True)

    if args.mode == "all":
        success = run_all_tests()
    elif args.mode == "interactive":
        success = test_interactive_workflow()
    elif args.mode == "import":
        success = test_import_workflow()
    elif args.mode == "connection":
        success = test_bannaflow_connection()
    elif args.mode == "dry-run":
        success = test_workflow_dry_run()
    else:
        logger.error(f"Unknown mode: {args.mode}")
        success = False

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
