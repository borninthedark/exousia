"""Ticket sync workflow — Paperless ↔ Forgejo issue bidirectional sync.

Flow:
1. Poll Paperless for docs tagged "actionable"
2. Create Forgejo issues for new actionable docs
3. Check for closed Forgejo issues that reference Paperless docs
4. Re-tag completed docs from "actionable" to "completed"
"""

from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from src.activities.paperless import PaperlessActivities


@workflow.defn
class TicketSyncWorkflow:
    """Bidirectional sync between Paperless docs and Forgejo issues.

    Schedule every 15 minutes:
        spec=ScheduleSpec(cron_expressions=["*/15 * * * *"])
    """

    @workflow.run
    async def run(self) -> dict:
        activities = PaperlessActivities.__new__(PaperlessActivities)
        timeout = timedelta(seconds=30)
        created = 0
        completed = 0

        # 1. Get actionable documents from Paperless
        actionable_docs = await workflow.execute_activity_method(
            activities.get_documents_by_tag,
            "actionable",
            start_to_close_timeout=timeout,
        )

        workflow.logger.info(f"Found {len(actionable_docs)} actionable documents")

        # 2. Create Forgejo issues for each (idempotent — check if issue exists)
        for doc in actionable_docs:
            try:
                issue_url = await workflow.execute_activity_method(
                    activities.create_forgejo_issue_from_doc,
                    doc,
                    start_to_close_timeout=timeout,
                )
                if issue_url:
                    # Tag as "in-progress" so we don't create duplicate issues
                    await workflow.execute_activity_method(
                        activities.update_document_tags,
                        args=[doc["id"], ["in-progress"], ["actionable"]],
                        start_to_close_timeout=timeout,
                    )
                    created += 1
                    workflow.logger.info(f"Created issue for doc {doc['title']}: {issue_url}")
            except Exception as e:
                workflow.logger.warning(f"Failed to create issue for {doc['title']}: {e}")

        # 3. Check for closed issues referencing Paperless docs
        closed = await workflow.execute_activity_method(
            activities.check_closed_issues_for_docs,
            start_to_close_timeout=timeout,
        )

        # 4. Re-tag completed docs
        for item in closed:
            try:
                await workflow.execute_activity_method(
                    activities.update_document_tags,
                    args=[item["doc_id"], ["completed"], ["in-progress"]],
                    start_to_close_timeout=timeout,
                )
                completed += 1
                workflow.logger.info(f"Completed doc {item['doc_id']} (issue: {item['issue_url']})")
            except Exception as e:
                workflow.logger.warning(f"Failed to update doc {item['doc_id']}: {e}")

        return {"created": created, "completed": completed}
