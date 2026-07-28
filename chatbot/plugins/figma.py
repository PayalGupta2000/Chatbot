import frappe
import re
from chatbot.plugins import ChatbotPlugin, PluginRegistry


class FigmaPlugin(ChatbotPlugin):
	name = "figma"
	description = "Provides Figma integration context — UI/UX design, prototyping, design systems, and collaboration"
	version = "1.0.0"

	_keywords = [
		"figma", "design", "ui ", "ux ", "prototype", "wireframe", "mockup",
		"design system", "component", "layout", "interface", "user experience",
		"user interface", "creativity", "creative",
	]

	def on_chat_before(self, message, **kwargs):
		msg_lower = message.lower()
		if any(re.search(rf"\b{re.escape(kw)}\b", msg_lower) for kw in self._keywords):
			frappe.flags.chatbot_context_figma = True

	def on_chat_after(self, message, response, **kwargs):
		if getattr(frappe.flags, "chatbot_context_figma", False):
			tip = (
				"\n\n---\n*Figma integration available!* I can help you design ERPNext UI mockups, "
				"create design system components, plan user flows, or generate SVG prototypes. "
				"Try: *\"Design a sales dashboard layout\"* or *\"Create a wireframe for the customer form\"*."
			)
			response["reply"] += tip


PluginRegistry.register(FigmaPlugin())
