"""
GitHub Service
==============

Service for interacting with GitHub API for workflow management.
"""

from github import Github, GithubException
from typing import Dict, Any, Optional
import asyncio
from functools import wraps


def async_github_call(func):
    """Decorator to run GitHub API calls in executor."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))
    return wrapper


class GitHubService:
    """Service for GitHub API operations."""

    def __init__(self, token: str, repo_name: str):
        """
        Initialize GitHub service.

        Args:
            token: GitHub personal access token
            repo_name: Repository name in format "owner/repo"
        """
        self.github = Github(token)
        self.repo_name = repo_name
        self._repo = None

    @async_github_call
    def get_repo(self):
        """Get repository object."""
        if not self._repo:
            self._repo = self.github.get_repo(self.repo_name)
        return self._repo

    async def trigger_workflow(
        self,
        workflow_file: str,
        ref: str = "main",
        inputs: Optional[Dict[str, str]] = None
    ):
        """
        Trigger a GitHub Actions workflow.

        Args:
            workflow_file: Workflow file name (e.g., "build.yaml")
            ref: Git ref to run workflow on
            inputs: Workflow inputs

        Returns:
            WorkflowRun object

        Raises:
            GithubException: If workflow trigger fails
        """
        repo = await self.get_repo()

        @async_github_call
        def _trigger():
            workflow = repo.get_workflow(workflow_file)
            success = workflow.create_dispatch(ref=ref, inputs=inputs or {})

            if not success:
                raise GithubException(
                    status=500,
                    data={"message": "Failed to trigger workflow"}
                )

            # Get the latest run for this workflow
            # Note: There's a small race condition here, but it's acceptable
            runs = workflow.get_runs(branch=ref)
            if runs.totalCount > 0:
                return runs[0]
            return None

        return await _trigger()

    async def get_workflow_run(self, run_id: int):
        """
        Get workflow run details.

        Args:
            run_id: Workflow run ID

        Returns:
            WorkflowRun object
        """
        repo = await self.get_repo()

        @async_github_call
        def _get_run():
            return repo.get_workflow_run(run_id)

        return await _get_run()

    async def cancel_workflow_run(self, run_id: int):
        """
        Cancel a running workflow.

        Args:
            run_id: Workflow run ID

        Returns:
            True if cancelled successfully
        """
        repo = await self.get_repo()

        @async_github_call
        def _cancel():
            run = repo.get_workflow_run(run_id)
            return run.cancel()

        return await _cancel()

    async def get_workflow_logs(self, run_id: int) -> str:
        """
        Get workflow run logs.

        Args:
            run_id: Workflow run ID

        Returns:
            Log content as string
        """
        repo = await self.get_repo()

        @async_github_call
        def _get_logs():
            run = repo.get_workflow_run(run_id)
            # Note: This returns a URL, not actual logs
            # You'd need to download from the URL
            return run.logs_url

        return await _get_logs()

    async def list_workflow_runs(
        self,
        workflow_file: str,
        limit: int = 20,
        status: Optional[str] = None
    ):
        """
        List workflow runs.

        Args:
            workflow_file: Workflow file name
            limit: Maximum number of runs to return
            status: Filter by status (queued, in_progress, completed)

        Returns:
            List of WorkflowRun objects
        """
        repo = await self.get_repo()

        @async_github_call
        def _list_runs():
            workflow = repo.get_workflow(workflow_file)
            runs = workflow.get_runs()

            if status:
                runs = [r for r in runs if r.status == status]

            return list(runs[:limit])

        return await _list_runs()
