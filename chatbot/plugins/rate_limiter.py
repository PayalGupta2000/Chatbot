import frappe
from datetime import timedelta
from chatbot.plugins import ChatbotPlugin, PluginRegistry

MAX_MESSAGES_PER_MINUTE = 10
MAX_TOOL_CALLS_PER_MINUTE = 5


class RateLimiterPlugin(ChatbotPlugin):
	name = "rate_limiter"
	description = "Prevents API abuse by limiting chat and tool usage frequency"
	version = "1.0.0"

	def _count_recent(self, doctype, field, user, minutes=1):
		since = frappe.utils.now_datetime() - timedelta(minutes=minutes)
		records = frappe.get_all(
			doctype,
			filters={
				field: user,
				"creation": (">=", since),
			},
			limit_page_length=0,
		)
		return len(records)

	def on_chat_before(self, message, **kwargs):
		user = frappe.session.user
		if user == "Guest":
			return

		count = self._count_recent("AI Chat Memory", "user", user, minutes=1)
		if count >= MAX_MESSAGES_PER_MINUTE:
			frappe.throw(
				f"You've sent {MAX_MESSAGES_PER_MINUTE} messages in the last minute. "
				"Please wait a moment before sending more messages."
			)

	def on_tool_before(self, tool_name, **kwargs):
		user = frappe.session.user
		if user == "Guest":
			return

		recent = self._count_recent("AI Chat Memory", "user", user, minutes=1)
		if recent >= MAX_TOOL_CALLS_PER_MINUTE:
			frappe.throw(
				f"Too many operations in a short time. "
				"Please wait a moment before performing more actions."
			)


PluginRegistry.register(RateLimiterPlugin())
