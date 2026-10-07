# Operations automation controls

The consolidated Operations page omitted the legacy Automation actions. ADMIN now gets
Run monitored scan, Pause automation, Enable automation / clear kill, and Activate kill switch
inside the existing Operations layout. No duplicate menu or page is added. USER remains read-only;
server ADMIN authorization is unchanged.

All actions call existing authenticated automation APIs. Pause preserves the latest simulation
execution setting, interval and symbols. Enable explicitly clears kill through the existing
restart workflow without changing simulation execution. Scan requires enabled automation,
clear kill and simulation execution on; existing certification, broker, ownership and risk
checks still apply. Confirmation describes simulation submission and kill effects.

Pending scans disable repeat scans across renders while keeping kill accessible. Request errors
ask the operator to refresh and inspect state before retrying. Completion does not redirect an
operator who left Operations. Responsive wrapping uses the existing action styles. The
operations asset cache version is 72.2.

Deploy app only after the container suite passes. Preserve the running image for rollback.
Check ADMIN and USER views, narrow-screen wrapping, cancelled confirmations, pending/error
states and a single monitored simulation scan after deployment. No schema or provider changes.
