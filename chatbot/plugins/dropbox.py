import frappe
import re
from chatbot.plugins import ChatbotPlugin, PluginRegistry


class DropboxPlugin(ChatbotPlugin):
	name = "dropbox"
	description = "Provides Dropbox integration context — file sync, storage, sharing, and backup"
	version = "1.0.0"

	_keywords = [
		"dropbox", "file", "storage", "sync", "backup", "share", "upload",
		"download", "cloud storage", "file management", "attachment",
		"file sharing", "archive",
	]

	def on_chat_before(self, message, **kwargs):
		msg_lower = message.lower()
		if any(re.search(rf"\b{re.escape(kw)}\b", msg_lower) for kw in self._keywords):
			frappe.flags.chatbot_context_dropbox = True

	def on_chat_after(self, message, response, **kwargs):
		if getattr(frappe.flags, "chatbot_context_dropbox", False):
			tip = (
				"\n\n---\n*Dropbox integration ready!* I can help you auto-sync invoices, "
				"back up attachments, share reports via shared links, or connect ERPNext "
				"file uploads to your Dropbox. "
				"Try: *\"Sync all sales invoices to Dropbox\"*."
			)
			response["reply"] += tip


PluginRegistry.register(DropboxPlugin())
