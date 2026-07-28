import frappe
from datetime import datetime
from chatbot.plugins import ChatbotPlugin, PluginRegistry


class GreetingPlugin(ChatbotPlugin):
	name = "greeting"
	description = "Sends personalized greetings based on time of day and user context"
	version = "1.0.0"

	def _get_greeting(self):
		hour = datetime.now().hour
		if hour < 12:
			return "Good morning"
		elif hour < 17:
			return "Good afternoon"
		else:
			return "Good evening"

	def _get_user_name(self):
		user = frappe.session.user
		if user and user != "Guest":
			full_name = frappe.db.get_value("User", user, "full_name")
			if full_name:
				return full_name.split()[0]
		return None

	def on_chat_before(self, message, memory=None, **kwargs):
		if memory and len(memory) > 0:
			return

		greeting = self._get_greeting()
		user_name = self._get_user_name()
		if user_name:
			prepend = f"{greeting}, {user_name}! "
		else:
			prepend = f"{greeting}! "

		if "hello" in message.lower() or "hi" in message.lower() or "hey" in message.lower():
			frappe.flags.chatbot_greeting = prepend


PluginRegistry.register(GreetingPlugin())
