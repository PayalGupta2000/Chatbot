import frappe
import re
from chatbot.plugins import ChatbotPlugin, PluginRegistry


class SlackPlugin(ChatbotPlugin):
	name = "slack"
	description = "Provides Slack integration context — notifications, messaging, and team collaboration"
	version = "1.0.0"

	_keywords = [
		"slack", "notification", "message", "channel", "team communication",
		"collaboration", "alert", "webhook", "integrate", "integration",
	]

	def on_chat_before(self, message, **kwargs):
		msg_lower = message.lower()
		if any(re.search(rf"\b{re.escape(kw)}\b", msg_lower) for kw in self._keywords):
			frappe.flags.chatbot_context_slack = True

	def on_chat_after(self, message, response, **kwargs):
		if getattr(frappe.flags, "chatbot_context_slack", False):
			tip = (
				"\n\n---\n*Need Slack integration?* I can help you set up Slack webhooks, "
				"send automated notifications for ERPNext events (new orders, payment alerts, "
				"approval requests), or build a custom Slack bot. "
				"Try: *\"Set up Slack notifications for new sales orders\"*."
			)
			response["reply"] += tip


PluginRegistry.register(SlackPlugin())
