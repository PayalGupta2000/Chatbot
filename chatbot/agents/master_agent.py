import base64
import json
import re

import frappe
import google.generativeai as genai
from google.generativeai import protos

from chatbot.agents import BaseAgent
from chatbot.tools import ToolRegistry, extract_function_call

MAX_STEPS = 6
MAX_TOOL_RESULT_CHARS = 8000

MASTER_AGENT_PROMPT = """You are the Master Agent — a fully autonomous AI assistant embedded inside ERPNext. You handle EVERYTHING on your own: general questions, data queries and analytics, reports and charts, code and customizations, documents and images, workflows, emails, notifications, data imports, and proactive business insights. You do not delegate — you plan, call tools, observe results, and keep going until the job is done.

## How you work (agentic loop)
You have access to tools. When the user's request needs an action or real data, call the appropriate tool. You will receive the tool's result and continue reasoning. You may call multiple tools in sequence — for example, query data, then build a chart, then refine a filter — until the task is fully complete. When you are done, stop calling tools and produce your final answer to the user.

## Capabilities
### Data, Reports & Charts
- Query any ERPNext data with `query_data` (supports filters, grouping, aggregation, sorting, charts)
- Build structured reports with `build_report`
- Export data as CSV, Excel, or JSON with `export_data`
- Present findings with markdown tables, totals, and notable insights; include a chart when visual data helps
### Code & Customization
- Create/edit client scripts, server scripts, REST API endpoints, custom fields, and DocTypes
- Follow Frappe best practices (tabs, double quotes, whitelisted methods, parameterized SQL, error handling)
### Business Operations (Admin)
- Create workflows with states, transitions, and role approvals via `create_workflow`
- Draft/send emails and create reusable email templates
- Create or update documents in any DocType
- Set up notifications on document events
### Documents & Images
- Summarize, extract tables, and answer questions about uploaded documents (PDF, DOCX, Excel, CSV, PPT)
- OCR and describe images; analyze charts and screenshots
- Generate images when requested
### Data Import
- Import Excel/CSV files into any DocType with `import_data`
### Proactive Intelligence
- Use available insights (low stock, overdue invoices, pending approvals, anomalies) to surface issues proactively

## Guidelines
- Use sensible defaults when details are missing (last 30 days, top 10, current user, etc.) instead of blocking on questions — unless the missing info is truly essential.
- Call the tool, WAIT for its result, then decide the next step. Never invent data.
- When a tool fails, inspect the error and try a corrected attempt or explain the issue clearly.
- For data questions, query first, then present findings with a clear summary.
- Start long answers with a brief summary.
- Use Markdown formatting in replies.
- Never expose secrets, API keys, or credentials.

## Final Answer Format
When finished, respond with ONLY a JSON object:
{"reply": "your markdown answer to the user", "action": {"type": "...", ...}, "data": {"columns": [...], "rows": [...], "total_rows": n}, "chart": {"type": "bar|line|pie|doughnut", "title": "...", "labels": [...], "datasets": [...]}}
- "reply" is always required — the text shown to the user.
- Include "action" only for UI action cards: workflow_created, email_drafted, email_sent, data_imported, api_created, api_updated, client_script_created, image_generated, report_created, data_exported, document_created, notification_created, and similar.
- Include "data"/"chart" when you produced structured data or a visualization.
- If a step produced nothing actionable, still respond with a clear "reply".

## Conversation History
"""


def _truncate(result) -> str:
	try:
		text = json.dumps(result, default=str)
	except (TypeError, ValueError):
		text = str(result)
	if len(text) > MAX_TOOL_RESULT_CHARS:
		text = text[:MAX_TOOL_RESULT_CHARS] + "\n...(truncated)"
	return text


def _parse_final(text: str) -> dict:
	clean = text.strip()
	match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", clean, re.S)
	if match:
		clean = match.group(1).strip()
	try:
		parsed = json.loads(clean)
		if isinstance(parsed, dict) and "reply" in parsed:
			parsed.setdefault("reply", "")
			return parsed
		if isinstance(parsed, dict):
			return {"reply": text}
	except (json.JSONDecodeError, ValueError):
		pass
	return {"reply": text}


class MasterAgent(BaseAgent):
	def __init__(self):
		super().__init__(
			name="master_agent",
			description="Autonomous agent that handles every ERPNext request end-to-end by itself",
			capabilities=[
				"data_query",
				"report_builder",
				"chart_gen",
				"data_export",
				"schema_explore",
				"code_gen",
				"client_script",
				"server_script",
				"api_gen",
				"custom_field",
				"workflow_create",
				"email_send",
				"email_template",
				"doc_automation",
				"notification",
				"document_analysis",
				"image_ocr",
				"image_generation",
				"data_import",
				"general_chat",
				"proactive_insights",
			],
			system_prompt=MASTER_AGENT_PROMPT,
		)

	def run(
		self,
		message: str,
		context: dict | None = None,
		tools: list | None = None,
		image_data: str | None = None,
		image_mime_type: str | None = None,
		plugins: list | None = None,
	) -> dict:
		context = context or {}
		chat = self._model.start_chat()

		parts = [self._system_prompt]
		ctx_text = self._format_context(context)
		if ctx_text:
			parts.append(ctx_text)
		parts.append(f"User: {message}")
		if image_data and image_mime_type:
			try:
				image_bytes = base64.b64decode(image_data)
				parts.append(
					protos.Part(inline_data=protos.Blob(mime_type=image_mime_type, data=image_bytes))
				)
			except Exception:
				frappe.log_error(frappe.get_traceback(), "Master Agent Image Decode Error")
		parts.append("Assistant:")

		response = chat.send_message(parts, tools=tools or None)
		tool_uses = []

		for _ in range(MAX_STEPS):
			function_call = extract_function_call(response)
			if not function_call:
				break

			tool_name = function_call.name
			tool_args = {key: value for key, value in function_call.args.items()}
			tool_uses.append(tool_name)

			if plugins:
				for plugin in plugins:
					plugin.on_tool_before(tool_name, **tool_args)

			try:
				result = ToolRegistry.execute(tool_name, **tool_args)
			except Exception as e:
				frappe.log_error(frappe.get_traceback(), f"Master Agent Tool Error: {tool_name}")
				result = {"reply": f"Error executing {tool_name}: {e}", "error": str(e)}

			if plugins:
				for plugin in plugins:
					plugin.on_tool_after(tool_name, result=result, **tool_args)

			response = chat.send_message(
				protos.Content(
					parts=[
						protos.Part(
							function_response=protos.FunctionResponse(
								name=tool_name,
								response={"result": _truncate(result)},
							)
						)
					]
				)
			)

		text = response.text if response and response.text else ""
		if not text:
			text = "I couldn't complete that task. Please try again with a bit more detail."

		final = _parse_final(text)
		final["tools_used"] = tool_uses
		return final


master_agent = MasterAgent()
