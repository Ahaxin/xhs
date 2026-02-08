"""
Automated Workflow Module.

Orchestrates the complete content generation and publishing pipeline:
1. Generate content using BannaFlow
2. Import content into local database
3. (Optional) Auto-approve content
4. Publish to Xiaohongshu

This creates a seamless flow from content idea to published post.
"""
import time
from datetime import datetime
from typing import List, Optional, Callable
from dataclasses import dataclass
from enum import Enum
from loguru import logger

from .bannaflow import BannaFlowIntegration, GeneratedContent, create_content_from_bannaflow
from ..content.database import Database, ContentStatus, ContentSource, PublishMode
from ..content.manager import ContentManager
from ..auth.xhs_auth import XHSAuthManager
from ..publisher.publisher import XHSPublisher
from ..utils.config import get_config


class WorkflowStatus(str, Enum):
    """Workflow step status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class WorkflowStep:
    """Represents a step in the workflow."""
    name: str
    status: WorkflowStatus
    message: str = ""
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class ContentWorkflow:
    """
    Orchestrates the complete content generation and publishing pipeline.

    Workflow Steps:
    1. Initialize - Set up all required components
    2. Generate Content - Use BannaFlow to create content
    3. Import Content - Save to local database
    4. Approve Content - Auto or manual approval
    5. Login to XHS - Authenticate with Xiaohongshu
    6. Publish Content - Post to Xiaohongshu

    Usage:
        workflow = ContentWorkflow()
        result = workflow.run_interactive()
        # or
        result = workflow.run_automated(auto_approve=True)
    """

    def __init__(
        self,
        db_path: str = "data/xhs.db",
        session_file: str = "data/xhs_session.json",
    ):
        """
        Initialize the workflow.

        Args:
            db_path: Path to database file
            session_file: Path to XHS session file
        """
        self.config = get_config()

        # Components
        self.db = Database(db_path)
        self.content_manager = ContentManager(self.db)
        self.bannaflow: Optional[BannaFlowIntegration] = None
        self.auth_manager: Optional[XHSAuthManager] = None
        self.publisher: Optional[XHSPublisher] = None

        # Session file
        self.session_file = session_file

        # Workflow state
        self.steps: List[WorkflowStep] = []
        self.current_step: int = 0
        self.generated_content: Optional[GeneratedContent] = None
        self.content_id: Optional[int] = None

        # Callbacks
        self.on_step_start: Optional[Callable[[WorkflowStep], None]] = None
        self.on_step_complete: Optional[Callable[[WorkflowStep], None]] = None
        self.on_step_error: Optional[Callable[[WorkflowStep, Exception], None]] = None

    def _init_steps(self):
        """Initialize workflow steps."""
        self.steps = [
            WorkflowStep(name="Initialize Components", status=WorkflowStatus.PENDING),
            WorkflowStep(name="Generate Content (BannaFlow)", status=WorkflowStatus.PENDING),
            WorkflowStep(name="Import to Database", status=WorkflowStatus.PENDING),
            WorkflowStep(name="Approve Content", status=WorkflowStatus.PENDING),
            WorkflowStep(name="Login to Xiaohongshu", status=WorkflowStatus.PENDING),
            WorkflowStep(name="Publish to Xiaohongshu", status=WorkflowStatus.PENDING),
        ]
        self.current_step = 0

    def _update_step(self, status: WorkflowStatus, message: str = ""):
        """Update current step status."""
        if self.current_step < len(self.steps):
            step = self.steps[self.current_step]
            step.status = status
            step.message = message

            if status == WorkflowStatus.IN_PROGRESS:
                step.started_at = datetime.now()
                if self.on_step_start:
                    self.on_step_start(step)
            elif status in [WorkflowStatus.COMPLETED, WorkflowStatus.FAILED, WorkflowStatus.SKIPPED]:
                step.completed_at = datetime.now()
                if self.on_step_complete:
                    self.on_step_complete(step)

            logger.info(f"[Step {self.current_step + 1}/{len(self.steps)}] {step.name}: {status.value} - {message}")

    def _next_step(self):
        """Move to next step."""
        self.current_step += 1

    def _step_initialize(self) -> bool:
        """Step 1: Initialize all components."""
        self._update_step(WorkflowStatus.IN_PROGRESS, "Initializing components...")

        try:
            # BannaFlow integration
            self.bannaflow = BannaFlowIntegration(headless=False)

            # XHS Auth Manager
            self.auth_manager = XHSAuthManager(
                creator_url=self.config.xiaohongshu.creator_center_url,
                session_file=self.session_file,
                login_method=self.config.xiaohongshu.login_method,
                phone_number=self.config.xiaohongshu.phone_number,
            )

            self._update_step(WorkflowStatus.COMPLETED, "All components initialized")
            return True

        except Exception as e:
            self._update_step(WorkflowStatus.FAILED, f"Initialization failed: {e}")
            return False

    def _step_generate_content(self, interactive: bool = True) -> bool:
        """Step 2: Generate content using BannaFlow."""
        self._update_step(WorkflowStatus.IN_PROGRESS, "Opening BannaFlow for content generation...")

        try:
            if interactive:
                # Interactive mode - user generates content manually
                self.generated_content = self.bannaflow.generate_content_interactive()
            else:
                # Automated mode - import from existing BannaFlow content
                contents = self.bannaflow.import_from_bannaflow()
                if contents:
                    self.generated_content = contents[0]  # Get most recent
                else:
                    self._update_step(WorkflowStatus.FAILED, "No content found in BannaFlow")
                    return False

            if self.generated_content:
                self._update_step(
                    WorkflowStatus.COMPLETED,
                    f"Content generated: {self.generated_content.title[:50]}..."
                )
                return True
            else:
                self._update_step(WorkflowStatus.FAILED, "No content was generated")
                return False

        except Exception as e:
            self._update_step(WorkflowStatus.FAILED, f"Content generation failed: {e}")
            return False

    def _step_import_content(self, publish_mode: PublishMode = PublishMode.IMAGE_TEXT_UPLOAD) -> bool:
        """Step 3: Import generated content to database."""
        self._update_step(WorkflowStatus.IN_PROGRESS, "Importing content to database...")

        if not self.generated_content:
            self._update_step(WorkflowStatus.FAILED, "No generated content to import")
            return False

        try:
            # Convert BannaFlow content format
            title, body, images = create_content_from_bannaflow(self.generated_content)

            # Create in database
            self.content_id = self.content_manager.create_content(
                title=title,
                body=body,
                images=images,
                source=ContentSource.FETCHED,  # Mark as fetched/generated
                publish_mode=publish_mode,
            )

            self._update_step(
                WorkflowStatus.COMPLETED,
                f"Content imported as #{self.content_id}"
            )
            return True

        except Exception as e:
            self._update_step(WorkflowStatus.FAILED, f"Import failed: {e}")
            return False

    def _step_approve_content(self, auto_approve: bool = False) -> bool:
        """Step 4: Approve content for publishing."""
        self._update_step(WorkflowStatus.IN_PROGRESS, "Approving content...")

        if not self.content_id:
            self._update_step(WorkflowStatus.FAILED, "No content ID to approve")
            return False

        try:
            if auto_approve:
                # Auto-approve
                self.content_manager.approve_content(self.content_id)
                self._update_step(WorkflowStatus.COMPLETED, "Content auto-approved")
                return True
            else:
                # Manual approval required
                logger.info("=" * 60)
                logger.info("CONTENT REVIEW REQUIRED")
                logger.info("=" * 60)

                content = self.content_manager.get_content(self.content_id)
                if content:
                    logger.info(f"Title: {content.title}")
                    logger.info(f"Body ({len(content.body)} chars):")
                    logger.info(content.body[:500] + "..." if len(content.body) > 500 else content.body)
                    logger.info(f"Images: {len(content.images)}")

                logger.info("=" * 60)

                # Wait for user approval
                while True:
                    response = input("Approve this content? (y/n/e for edit): ").strip().lower()
                    if response == 'y':
                        self.content_manager.approve_content(self.content_id)
                        self._update_step(WorkflowStatus.COMPLETED, "Content approved by user")
                        return True
                    elif response == 'n':
                        self.content_manager.reject_content(self.content_id, "Rejected by user")
                        self._update_step(WorkflowStatus.SKIPPED, "Content rejected by user")
                        return False
                    elif response == 'e':
                        logger.info("Edit mode not implemented - please approve or reject")
                    else:
                        logger.info("Invalid input. Enter y, n, or e.")

        except Exception as e:
            self._update_step(WorkflowStatus.FAILED, f"Approval failed: {e}")
            return False

    def _step_login_xhs(self) -> bool:
        """Step 5: Login to Xiaohongshu."""
        self._update_step(WorkflowStatus.IN_PROGRESS, "Logging in to Xiaohongshu...")

        try:
            success = self.auth_manager.login()

            if success:
                # Initialize publisher
                driver = self.auth_manager.get_driver()
                if driver:
                    self.publisher = XHSPublisher(driver)
                    self._update_step(WorkflowStatus.COMPLETED, "Logged in to Xiaohongshu")
                    return True
                else:
                    self._update_step(WorkflowStatus.FAILED, "Could not get driver after login")
                    return False
            else:
                self._update_step(WorkflowStatus.FAILED, "Login failed")
                return False

        except Exception as e:
            self._update_step(WorkflowStatus.FAILED, f"Login error: {e}")
            return False

    def _step_publish(self) -> bool:
        """Step 6: Publish content to Xiaohongshu."""
        self._update_step(WorkflowStatus.IN_PROGRESS, "Publishing to Xiaohongshu...")

        if not self.publisher or not self.content_id:
            self._update_step(WorkflowStatus.FAILED, "Publisher or content not ready")
            return False

        try:
            content = self.content_manager.get_content(self.content_id)
            if not content:
                self._update_step(WorkflowStatus.FAILED, "Content not found")
                return False

            if content.status != ContentStatus.APPROVED:
                self._update_step(WorkflowStatus.FAILED, "Content not approved")
                return False

            # Publish with retry
            success = self.publisher.publish_with_retry(
                content,
                max_attempts=self.config.publishing.retry_attempts,
                retry_delay=self.config.publishing.retry_delay,
            )

            if success:
                self.content_manager.mark_published(self.content_id)
                self._update_step(WorkflowStatus.COMPLETED, "Content published successfully!")
                return True
            else:
                self.content_manager.mark_failed(self.content_id, "Publishing failed after retries")
                self._update_step(WorkflowStatus.FAILED, "Publishing failed")
                return False

        except Exception as e:
            self._update_step(WorkflowStatus.FAILED, f"Publishing error: {e}")
            return False

    def run_interactive(
        self,
        publish_mode: PublishMode = PublishMode.IMAGE_TEXT_UPLOAD,
        auto_approve: bool = False,
    ) -> bool:
        """
        Run the complete workflow in interactive mode.

        User will manually generate content in BannaFlow, then the workflow
        handles import, approval, and publishing.

        Args:
            publish_mode: XHS publishing mode
            auto_approve: Automatically approve content without review

        Returns:
            True if workflow completed successfully
        """
        logger.info("=" * 60)
        logger.info("Starting Interactive Content Workflow")
        logger.info("=" * 60)

        self._init_steps()

        try:
            # Step 1: Initialize
            self._next_step() if self._step_initialize() else None
            if self.steps[0].status != WorkflowStatus.COMPLETED:
                return False

            # Step 2: Generate content (interactive)
            self._next_step()
            if not self._step_generate_content(interactive=True):
                return False

            # Step 3: Import to database
            self._next_step()
            if not self._step_import_content(publish_mode):
                return False

            # Step 4: Approve
            self._next_step()
            if not self._step_approve_content(auto_approve):
                return False

            # Close BannaFlow - we don't need it anymore
            if self.bannaflow:
                self.bannaflow.close()

            # Step 5: Login to XHS
            self._next_step()
            if not self._step_login_xhs():
                return False

            # Step 6: Publish
            self._next_step()
            return self._step_publish()

        finally:
            self._print_summary()

    def run_import_and_publish(
        self,
        publish_mode: PublishMode = PublishMode.IMAGE_TEXT_UPLOAD,
        auto_approve: bool = True,
    ) -> bool:
        """
        Import existing content from BannaFlow and publish.

        This is useful when you've already generated content in BannaFlow
        and want to publish it to Xiaohongshu.

        Args:
            publish_mode: XHS publishing mode
            auto_approve: Automatically approve content

        Returns:
            True if workflow completed successfully
        """
        logger.info("=" * 60)
        logger.info("Starting Import & Publish Workflow")
        logger.info("=" * 60)

        self._init_steps()

        try:
            # Step 1: Initialize
            if not self._step_initialize():
                return False
            self._next_step()

            # Step 2: Import from BannaFlow (non-interactive)
            if not self._step_generate_content(interactive=False):
                return False
            self._next_step()

            # Step 3: Import to database
            if not self._step_import_content(publish_mode):
                return False
            self._next_step()

            # Step 4: Approve
            if not self._step_approve_content(auto_approve):
                return False
            self._next_step()

            # Close BannaFlow
            if self.bannaflow:
                self.bannaflow.close()

            # Step 5: Login to XHS
            if not self._step_login_xhs():
                return False
            self._next_step()

            # Step 6: Publish
            return self._step_publish()

        finally:
            self._print_summary()

    def _print_summary(self):
        """Print workflow summary."""
        logger.info("=" * 60)
        logger.info("WORKFLOW SUMMARY")
        logger.info("=" * 60)

        for i, step in enumerate(self.steps):
            status_icon = {
                WorkflowStatus.COMPLETED: "✓",
                WorkflowStatus.FAILED: "✗",
                WorkflowStatus.SKIPPED: "○",
                WorkflowStatus.IN_PROGRESS: "→",
                WorkflowStatus.PENDING: "-",
            }.get(step.status, "?")

            logger.info(f"  [{status_icon}] Step {i + 1}: {step.name}")
            if step.message:
                logger.info(f"      {step.message}")

        logger.info("=" * 60)

    def cleanup(self):
        """Cleanup resources."""
        if self.bannaflow:
            self.bannaflow.close()
        if self.auth_manager:
            self.auth_manager.close()


def run_full_workflow(
    publish_mode: str = "image_text_upload",
    auto_approve: bool = False,
    interactive: bool = True,
):
    """
    Convenience function to run the full workflow.

    Args:
        publish_mode: Publishing mode (image_text_upload, image_text_compose, long_article)
        auto_approve: Auto-approve content without review
        interactive: Use interactive mode (user generates content)
    """
    mode = PublishMode(publish_mode)
    workflow = ContentWorkflow()

    try:
        if interactive:
            success = workflow.run_interactive(publish_mode=mode, auto_approve=auto_approve)
        else:
            success = workflow.run_import_and_publish(publish_mode=mode, auto_approve=auto_approve)

        return success
    finally:
        workflow.cleanup()
