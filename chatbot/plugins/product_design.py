import frappe
import re
from chatbot.plugins import ChatbotPlugin, PluginRegistry


class ProductDesignPlugin(ChatbotPlugin):
	name = "product_design"
	description = "Provides product design context — UX research, prototyping, design thinking, and product strategy"
	version = "1.0.0"

	_keywords = [
		"product design", "product strategy", "ux research", "user research",
		"design thinking", "prototype", "user testing", "usability",
		"product roadmap", "feature", "sprint", "agile design",
		"creativity", "creative", "innovation",
	]

	def on_chat_before(self, message, **kwargs):
		msg_lower = message.lower()
		if any(re.search(rf"\b{re.escape(kw)}\b", msg_lower) for kw in self._keywords):
			frappe.flags.chatbot_context_product_design = True

	def on_chat_after(self, message, response, **kwargs):
		if getattr(frappe.flags, "chatbot_context_product_design", False):
			tip = (
				"\n\n---\n*Product Design helper!* I can assist with design thinking exercises, "
				"user story creation, feature prioritisation, wireframing concepts, "
				"or product strategy documentation. "
				"Try: *\"Help me brainstorm features for a customer portal\"* or "
				"*\"Create a product requirements document\"*."
			)
			response["reply"] += tip


PluginRegistry.register(ProductDesignPlugin())
