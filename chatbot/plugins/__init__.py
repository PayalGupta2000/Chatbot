import frappe
from chatbot.tools import ToolRegistry


class ChatbotPlugin:
	name: str = ""
	description: str = ""
	version: str = "0.0.1"

	def on_register(self):
		pass

	def on_chat_before(self, message, document_content=None, image_data=None, image_mime_type=None, target_language=None, memory=None):
		pass

	def on_chat_after(self, message, response, tool_used=None):
		pass

	def on_tool_before(self, tool_name, **kwargs):
		pass

	def on_tool_after(self, tool_name, result, **kwargs):
		pass


def _upsert_doctype_record(plugin: ChatbotPlugin):
	try:
		if frappe.db.exists("Chatbot Plugin", plugin.name):
			doc = frappe.get_doc("Chatbot Plugin", plugin.name)
			if doc.description != plugin.description or doc.version != plugin.version:
				doc.description = plugin.description
				doc.version = plugin.version
				doc.save(ignore_permissions=True)
		else:
			frappe.get_doc(
				{
					"doctype": "Chatbot Plugin",
					"plugin_name": plugin.name,
					"enabled": 1,
					"description": plugin.description,
					"version": plugin.version,
				}
			).insert(ignore_permissions=True)
	except Exception:
		pass


def _is_enabled(plugin_name: str) -> bool:
	try:
		enabled = frappe.db.get_value("Chatbot Plugin", plugin_name, "enabled")
		if enabled is None:
			return True
		return bool(enabled)
	except Exception:
		return True


class PluginRegistry:
	_plugins: dict[str, ChatbotPlugin] = {}

	@classmethod
	def register(cls, plugin: ChatbotPlugin):
		if not plugin.name:
			frappe.log_error("Plugin registered without a name", "Plugin Registry")
			return
		cls._plugins[plugin.name] = plugin
		_upsert_doctype_record(plugin)
		plugin.on_register()

	@classmethod
	def get_all(cls) -> list[ChatbotPlugin]:
		return [p for p in cls._plugins.values() if _is_enabled(p.name)]

	@classmethod
	def get(cls, name: str) -> ChatbotPlugin | None:
		p = cls._plugins.get(name)
		if p and _is_enabled(p.name):
			return p
		return None

	@classmethod
	def get_all_raw(cls) -> list[ChatbotPlugin]:
		return list(cls._plugins.values())


def discover_plugins():
	plugins = frappe.get_hooks("chatbot_plugins") or []
	for plugin_class in plugins:
		if isinstance(plugin_class, str):
			plugin_class = frappe.get_attr(plugin_class)
		name = getattr(plugin_class, "name", None) or plugin_class.__name__
		if name not in PluginRegistry._plugins:
			plugin = plugin_class()
			PluginRegistry.register(plugin)


def discover_plugin_tools():
	tools = frappe.get_hooks("chatbot_tools") or []
	for tool_class in tools:
		if isinstance(tool_class, str):
			tool_class = frappe.get_attr(tool_class)
		name = getattr(tool_class, "name", None) or tool_class.__name__
		if not ToolRegistry.get_by_name(name):
			ToolRegistry.register(tool_class())


# Auto-discover and register default plugins
import chatbot.plugins.audit_log  # noqa: F401, E402
import chatbot.plugins.greeting  # noqa: F401, E402
import chatbot.plugins.rate_limiter  # noqa: F401, E402
import chatbot.plugins.data_analytics  # noqa: F401, E402
import chatbot.plugins.slack  # noqa: F401, E402
import chatbot.plugins.github  # noqa: F401, E402
import chatbot.plugins.notion  # noqa: F401, E402
import chatbot.plugins.dropbox  # noqa: F401, E402
import chatbot.plugins.figma  # noqa: F401, E402
import chatbot.plugins.canva  # noqa: F401, E402
import chatbot.plugins.product_design  # noqa: F401, E402
