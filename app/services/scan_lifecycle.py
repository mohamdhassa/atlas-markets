from datetime import datetime, timezone

from app.db.models.automation import AutomationScan


def interrupt_scan(db, scan_id):
    """Finish only this worker's scan; never infer broker order outcomes."""
    db.rollback()
    scan = db.get(AutomationScan, scan_id)
    if scan is not None and scan.status == 'RUNNING':
        scan.status = 'INTERRUPTED'
        scan.error_message = 'WORKER_CANCELLED_BROKER_RECONCILIATION_REQUIRED'
        scan.finished_at = datetime.now(timezone.utc)
        db.commit()
