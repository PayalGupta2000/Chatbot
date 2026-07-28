import frappe
from chatbot.plugins import ChatbotPlugin, PluginRegistry

AUDIT_DOCTYPE = "AI Chat Memory"


class AuditLogPlugin(ChatbotPlugin):
	name = "audit_log"
	description = "Logs all chat interactions and tool usage for auditing purposes"
	version = "1.0.0"

	def on_chat_before(self, message, **kwargs):
		log = frappe.get_doc({
			"doctype": AUDIT_DOCTYPE,
			"user": frappe.session.user,
			"message": message,
			"context": "Started",
		})
		log.insert(ignore_permissions=True)
		frappe.db.commit()

	def on_chat_after(self, message, response, tool_used=None, **kwargs):
		logs = frappe.get_all(
			AUDIT_DOCTYPE,
			filters={
				"user": frappe.session.user,
				"message": message,
				"context": "Started",
			},
			order_by="creation desc",
			limit=1,
		)
		if logs:
			log = frappe.get_doc(AUDIT_DOCTYPE, logs[0].name)
			log.conversation = str(response.get("reply", ""))[:5000]
			log.tool_used = tool_used
			log.context = "Completed"
			log.save(ignore_permissions=True)
			frappe.db.commit()

	def on_tool_after(self, tool_name, result, **kwargs):
		log = frappe.get_doc({
			"doctype": AUDIT_DOCTYPE,
			"user": frappe.session.user,
			"message": f"Tool executed: {tool_name}",
			"conversation": str(result.get("reply", ""))[:5000],
			"tool_used": tool_name,
			"context": "Tool Executed",
		})
		log.insert(ignore_permissions=True)
		frappe.db.commit()


PluginRegistry.register(AuditLogPlugin())
