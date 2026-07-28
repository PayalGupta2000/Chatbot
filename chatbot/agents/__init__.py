import frappe
import google.generativeai as genai
from typing import Protocol


class Agent(Protocol):
	name: str
	description: str
	capabilities: list[str]

	def run(self, message: str, context: dict) -> str:
		...


class BaseAgent:
	def __init__(self, name: str, description: str, capabilities: list[str], system_prompt: str):
		self.name = name
		self.description = description
		self.capabilities = capabilities
		self._system_prompt = system_prompt
		api_key = frappe.conf.get("gemini_api_key")
		if not api_key:
			frappe.log_error("Gemini API key not configured", "Agent System")
		genai.configure(api_key=api_key)
		self._model = genai.GenerativeModel("gemini-2.5-flash")

	def _format_context(self, context: dict) -> str:
		parts = []
		if context.get("document_content"):
			parts.append(f"## Uploaded Document\n{context['document_content'][:6000]}")
		if context.get("memory"):
			for row in context["memory"]:
				parts.append(f"User: {row.message}\nAssistant: {row.conversation}")
		if context.get("schema_context"):
			parts.append(f"## ERPNext Schema Info\n{context['schema_context'][:4000]}")
		if context.get("data_context"):
			parts.append(f"## Live Data\n{context['data_context'][:3000]}")
		if context.get("target_language"):
			parts.append(f"## Language\nRespond in {context['target_language']}")
		return "\n\n".join(parts)

	def run(self, message: str, context: dict, tools: list | None = None) -> str:
		ctx_text = self._format_context(context)
		prompt = f"{self._system_prompt}\n\n{ctx_text}\n\nUser: {message}\nAssistant:"
		try:
			if tools:
				resp = self._model.generate_content(prompt, tools=tools)
			else:
				resp = self._model.generate_content(prompt)
			return resp.text if resp and resp.text else ""
		except Exception as e:
			frappe.log_error(frappe.get_traceback(), f"Agent {self.name} Error")
			return ""
