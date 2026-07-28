import frappe
import re
from chatbot.plugins import ChatbotPlugin, PluginRegistry


class NotionPlugin(ChatbotPlugin):
	name = "notion"
	description = "Provides Notion integration context — notes, wikis, project docs, and knowledge management"
	version = "1.0.0"

	_keywords = [
		"notion", "note", "documentation", "wiki", "knowledge base",
		"project doc", "meeting notes", "write", "draft", "document",
		"productivity", "task", "to-do", "todo", "organize",
	]

	def on_chat_before(self, message, **kwargs):
		msg_lower = message.lower()
		if any(re.search(rf"\b{re.escape(kw)}\b", msg_lower) for kw in self._keywords):
			frappe.flags.chatbot_context_notion = True

	def on_chat_after(self, message, response, **kwargs):
		if getattr(frappe.flags, "chatbot_context_notion", False):
			tip = (
				"\n\n---\n*Notion-friendly!* I can help you draft documentation, "
				"create structured notes, build project wikis, or sync ERPNext data "
				"with your Notion workspace. "
				"Try: *\"Create a project plan in Notion format\"* or *\"Draft release notes\"*."
			)
			response["reply"] += tip


PluginRegistry.register(NotionPlugin())
