import frappe
from datetime import datetime, timedelta


def check_low_stock():
	# The Item module / Stock Settings may not exist in this site
	if not frappe.db.table_exists("tabItem"):
		return []
	try:
		threshold = frappe.db.get_single_value("Stock Settings", "low_stock_threshold") or 10
	except (frappe.exceptions.ValidationError, Exception):
		threshold = 10
	low_items = frappe.db.sql("""
		SELECT i.name, i.item_name, i.item_code, i.actual_qty
		FROM `tabItem` i
		WHERE i.is_stock_item = 1
		AND i.disabled = 0
		AND i.actual_qty < %s
		ORDER BY i.actual_qty ASC
		LIMIT 20
	""", threshold, as_dict=True)
	return low_items


def check_overdue_invoices():
	today = datetime.now().date()
	# The Sales Invoice module may not be installed in this site
	if not frappe.db.table_exists("tabSales Invoice"):
		return []
	try:
		overdue = frappe.db.sql("""
			SELECT si.name, si.customer, si.grand_total, si.outstanding_amount,
				   si.due_date, si.posting_date
			FROM `tabSales Invoice` si
			WHERE si.docstatus = 1
			AND si.outstanding_amount > 0
			AND si.due_date < %s
			ORDER BY si.due_date ASC
			LIMIT 15
		""", today, as_dict=True)
	except Exception:
		overdue = []
	return overdue


def check_pending_approvals():
	today = datetime.now().date()
	# The Leave Application module may not be installed in this site
	if not frappe.db.table_exists("tabLeave Application"):
		return []
	try:
		pending = frappe.db.sql("""
			SELECT la.name, la.employee, la.employee_name,
				   la.leave_type, la.from_date, la.to_date,
				   la.total_leave_days, la.status
			FROM `tabLeave Application` la
			WHERE la.status = 'Open'
			AND la.from_date <= %s
			ORDER BY la.from_date ASC
			LIMIT 10
		""", today, as_dict=True)
	except Exception:
		pending = []
	return pending


def get_proactive_insights(user=None):
	insights = []

	try:
		low_stock = check_low_stock()
		if low_stock:
			items_list = "\n".join(
				f"- {i.item_name} ({i.item_code}): {i.actual_qty} remaining"
				for i in low_stock[:5]
			)
			insights.append({
				"type": "low_stock",
				"severity": "warning",
				"title": f"Low Stock Alert — {len(low_stock)} items below threshold",
				"detail": items_list,
				"count": len(low_stock),
			})
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Proactive: Low Stock Check")

	try:
		overdue = check_overdue_invoices()
		if overdue:
			total = sum(o["outstanding_amount"] or 0 for o in overdue)
			inv_lines = "\n".join(
				f"- {i.customer}: {i.outstanding_amount:,.2f} (due {i.due_date})"
				for i in overdue[:5]
			)
			insights.append({
				"type": "overdue_invoices",
				"severity": "critical",
				"title": f"Overdue Invoices — {len(overdue)} invoices totaling {total:,.2f}",
				"detail": inv_lines,
				"count": len(overdue),
				"total": total,
			})
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Proactive: Overdue Check")

	try:
		pending = check_pending_approvals()
		if pending:
			pending_lines = "\n".join(
				f"- {p.employee_name}: {p.leave_type} ({p.from_date} to {p.to_date})"
				for p in pending[:5]
			)
			insights.append({
				"type": "pending_approvals",
				"severity": "info",
				"title": f"Pending Leave Approvals — {len(pending)} requests awaiting action",
				"detail": pending_lines,
				"count": len(pending),
			})
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Proactive: Pending Approvals")

	return insights


@frappe.whitelist()
def get_insights():
	user = frappe.session.user
	if user == "Guest":
		return []
	return get_proactive_insights(user)


def scheduled_insight_check():
	users = frappe.get_all("User", filters={"enabled": 1, "user_type": "System User"}, pluck="name")
	for user in users:
		try:
			insights = get_proactive_insights(user)
			if insights:
				message_lines = ["**Proactive Insights from your ERPNext Assistant**\n"]
				for ins in insights:
					icon = {"warning": "⚠️", "critical": "🔴", "info": "ℹ️"}.get(ins["severity"], "📌")
					message_lines.append(f"{icon} **{ins['title']}**")
					message_lines.append(ins["detail"])
					message_lines.append("")
				message = "\n".join(message_lines)
				existing = frappe.db.exists("AI Chat Memory", {"user": user})
				if existing:
					frappe.db.set_value("AI Chat Memory", existing, {
						"message": "system:proactive_insights",
						"conversation": message,
						"context": "Proactive intelligence alert",
					})
				else:
					frappe.get_doc({
						"doctype": "AI Chat Memory",
						"user": user,
						"message": "system:proactive_insights",
						"conversation": message,
						"context": "Proactive intelligence alert",
					}).insert(ignore_permissions=True)
		except Exception:
			pass
