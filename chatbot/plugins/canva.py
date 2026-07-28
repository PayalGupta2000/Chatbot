import frappe
import re
from chatbot.plugins import ChatbotPlugin, PluginRegistry


class CanvaPlugin(ChatbotPlugin):
	name = "canva"
	description = "Provides Canva integration context — graphic design, templates, presentations, and visual content"
	version = "1.0.0"

	_keywords = [
		"canva", "graphic design", "presentation", "template", "poster",
		"social media", "infographic", "visual", "banner", "flyer",
		"design", "creativity", "creative", "brand",
	]

	def on_chat_before(self, message, **kwargs):
		msg_lower = message.lower()
		if any(re.search(rf"\b{re.escape(kw)}\b", msg_lower) for kw in self._keywords):
			frappe.flags.chatbot_context_canva = True

	def on_chat_after(self, message, response, **kwargs):
		if getattr(frappe.flags, "chatbot_context_canva", False):
			tip = (
				"\n\n---\n*Canva-ready!* I can help you create marketing visuals, "
				"design business presentations, generate infographic content, "
				"or build brand assets for your business. "
				"Try: *\"Create a product catalogue presentation\"* or *\"Design a social media banner\"*."
			)
			response["reply"] += tip


PluginRegistry.register(CanvaPlugin())
