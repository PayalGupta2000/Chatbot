import frappe
from google.generativeai import protos


class Tool:
	name: str
	description: str
	parameters: dict

	def execute(self, **kwargs) -> dict:
		raise NotImplementedError


class ToolRegistry:
	_tools: list[Tool] = []

	@classmethod
	def register(cls, tool: Tool):
		cls._tools.append(tool)

	@classmethod
	def get_all(cls) -> list[Tool]:
		ensure_hooks_discovered()
		return list(cls._tools)

	@classmethod
	def get_by_name(cls, name: str) -> Tool | None:
		ensure_hooks_discovered()
		for tool in cls._tools:
			if tool.name == name:
				return tool
		return None

	@classmethod
	def get_function_declarations(cls) -> list[protos.Tool]:
		if not cls._tools:
			return []

		declarations = []
		for tool in cls._tools:
			try:
				fd = _build_function_declaration(tool)
				declarations.append(fd)
			except Exception as e:
				frappe.log_error(f"Failed to build declaration for {tool.name}: {e}", "Tool Registry")

		return [protos.Tool(function_declarations=declarations)] if declarations else []

	@classmethod
	def execute(cls, name: str, **kwargs) -> dict:
		tool = cls.get_by_name(name)
		if not tool:
			return {"reply": f"Unknown tool: {name}"}

		if frappe.session.user == "Guest":
			return {"reply": "I need you to be logged in to perform that action."}

		return tool.execute(**kwargs)


_TYPE_MAP = {
	"string": protos.Type.STRING,
	"integer": protos.Type.INTEGER,
	"boolean": protos.Type.BOOLEAN,
	"number": protos.Type.NUMBER,
	"array": protos.Type.ARRAY,
	"object": protos.Type.OBJECT,
}


def _build_schema(value: dict) -> protos.Schema:
	field_type = _TYPE_MAP.get(value.get("type", "string"), protos.Type.STRING)
	schema_kwargs = {
		"type": field_type,
		"description": value.get("description", ""),
	}
	if "enum" in value:
		schema_kwargs["enum"] = value["enum"]
	if "items" in value:
		schema_kwargs["items"] = _build_schema(value["items"])
	if "properties" in value:
		properties = {}
		for prop_key, prop_value in value["properties"].items():
			properties[prop_key] = _build_schema(prop_value)
		schema_kwargs["properties"] = properties
	if "required" in value:
		schema_kwargs["required"] = value["required"]
	return protos.Schema(**schema_kwargs)


def _build_function_declaration(tool: Tool) -> protos.FunctionDeclaration:
	params = tool.parameters or {}
	properties = {}

	for key, value in params.get("properties", {}).items():
		properties[key] = _build_schema(value)

	schema = protos.Schema(
		type=protos.Type.OBJECT,
		properties=properties,
		required=params.get("required", []),
	)

	return protos.FunctionDeclaration(
		name=tool.name,
		description=tool.description,
		parameters=schema,
	)


def extract_function_call(response):
	for candidate in response.candidates:
		for part in candidate.content.parts:
			if hasattr(part, "function_call") and part.function_call:
				return part.function_call
	return None


import chatbot.tools.import_data
import chatbot.tools.create_api
import chatbot.tools.client_script
import chatbot.tools.generate_image
import chatbot.tools.report_builder
import chatbot.tools.workflow_creator
import chatbot.tools.email_agent
import chatbot.tools.data_query
import chatbot.tools.doc_automation
import chatbot.tools.todo_tool
import chatbot.tools.currency_converter
import chatbot.tools.calculator
import chatbot.tools.holiday_events


def discover_from_hooks():
	from chatbot.plugins import discover_plugin_tools
	discover_plugin_tools()


_hooks_discovered = False


def ensure_hooks_discovered():
	global _hooks_discovered
	if not _hooks_discovered:
		_hooks_discovered = True
		discover_from_hooks()
