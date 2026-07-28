import frappe
from chatbot.plugins import ChatbotPlugin, PluginRegistry, discover_plugins

BASE_HOOKS = ["on_register", "on_chat_before", "on_chat_after", "on_tool_before", "on_tool_after"]

# In-memory fallback when Chatbot Plugin DocType table doesn't exist
_fallback_toggles: dict[str, bool] = {}


def _plugin_enabled(plugin_name: str) -> bool | None:
	try:
		return bool(frappe.db.get_value("Chatbot Plugin", plugin_name, "enabled"))
	except Exception:
		return _fallback_toggles.get(plugin_name)


def _set_plugin_enabled(plugin_name: str, value: bool):
	try:
		frappe.db.set_value("Chatbot Plugin", plugin_name, "enabled", 1 if value else 0)
	except Exception:
		_fallback_toggles[plugin_name] = value


def _get_implemented_hooks(plugin) -> list[str]:
	cls = type(plugin)
	return [name for name in BASE_HOOKS if getattr(cls, name, None) is not getattr(ChatbotPlugin, name, None)]


@frappe.whitelist()
def get_plugins():
	discover_plugins()
	result = []
	for plugin in PluginRegistry.get_all_raw():
		enabled = _plugin_enabled(plugin.name)
		if enabled is None:
			enabled = True
		result.append({
			"name": plugin.name,
			"description": plugin.description,
			"version": plugin.version,
			"enabled": enabled,
			"hooks": _get_implemented_hooks(plugin),
		})
	return result


@frappe.whitelist()
def toggle_plugin(plugin_name: str):
	if not plugin_name:
		frappe.throw("Plugin name is required")
	enabled = _plugin_enabled(plugin_name)
	current = True if enabled is None else enabled
	new_val = not current
	_set_plugin_enabled(plugin_name, new_val)
	return {"name": plugin_name, "enabled": new_val}
