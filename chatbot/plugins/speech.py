import re

import frappe
from chatbot.plugins import ChatbotPlugin, PluginRegistry

SHORTCUTS = [
	{"keys": "Ctrl + Alt + R", "action": "Read the last assistant reply aloud"},
	{"keys": "Ctrl + Alt + S", "action": "Stop speaking"},
]

ACCESSIBILITY_KEYWORDS = [
	"read aloud", "read it", "speak", "text to speech", "text-to-speech", "tts",
	"listen", "hear", "accessibility", "accessible", "screen reader",
	"shortcut", "keyboard shortcut", "read the reply", "audio",
]


class SpeechAccessibilityPlugin(ChatbotPlugin):
	name = "speech"
	description = "Adds read-aloud (text-to-speech), accessibility keyboard shortcuts, and reply tips"
	version = "1.0.0"

	def on_chat_before(self, message, **kwargs):
		msg_lower = (message or "").lower()
		if any(re.search(rf"\b{re.escape(kw)}\b", msg_lower) for kw in ACCESSIBILITY_KEYWORDS):
			frappe.flags.chatbot_context_speech = True

	def on_chat_after(self, message, response, **kwargs):
		if not getattr(frappe.flags, "chatbot_context_speech", False):
			return
		shortcuts = "".join(
			f"\n  - **{s['keys']}** — {s['action']}" for s in SHORTCUTS
		)
		response["reply"] += (
			"\n\n---\n*♿ Accessibility:* every assistant reply now has a **Read aloud** "
			"button, and you can use these shortcuts:"
			f"{shortcuts}\n"
			'\nTry: *"Read the last reply aloud"*.'
		)


@frappe.whitelist()
def get_shortcuts():
	return SHORTCUTS


PluginRegistry.register(SpeechAccessibilityPlugin())
