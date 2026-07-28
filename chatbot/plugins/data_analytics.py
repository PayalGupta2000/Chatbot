import frappe
import re
from chatbot.plugins import ChatbotPlugin, PluginRegistry


class DataAnalyticsPlugin(ChatbotPlugin):
	name = "data_analytics"
	description = "Provides data analytics context — reports, dashboards, BI, and ERPNext analytics tools"
	version = "1.0.0"

	_keywords = [
		"analytics", "dashboard", "report", "kpi", "metric", "data analysis",
		"business intelligence", "bi ", "chart", "graph", "pivot", "trend",
		"insight", "statistics", "data visualization", "visualize",
	]

	def on_chat_before(self, message, **kwargs):
		msg_lower = message.lower()
		if any(re.search(rf"\b{re.escape(kw)}\b", msg_lower) for kw in self._keywords):
			frappe.flags.chatbot_context_data_analytics = True

	def on_chat_after(self, message, response, **kwargs):
		if getattr(frappe.flags, "chatbot_context_data_analytics", False):
			tip = (
				"\n\n---\n*Want to explore deeper?* I can help you build custom reports, "
				"set up dashboards, analyse trends, or export data for BI tools. "
				"Try: *\"Create a sales dashboard\"* or *\"Show me monthly revenue trends\"*."
			)
			response["reply"] += tip


PluginRegistry.register(DataAnalyticsPlugin())
