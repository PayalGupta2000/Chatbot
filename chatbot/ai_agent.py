import frappe
import google.generativeai as genai
import base64
import json

from chatbot.tools import ToolRegistry, extract_function_call
from chatbot.plugins import PluginRegistry, discover_plugins
from chatbot.agents.supervisor import route_message
from chatbot.agents.code_agent import code_agent
from chatbot.agents.admin_agent import admin_agent
from chatbot.proactive_engine import get_proactive_insights

genai.configure(api_key=frappe.conf.get("gemini_api_key"))
model = genai.GenerativeModel("gemini-2.5-flash")

SYSTEM_PROMPT = """You are an advanced AI assistant inside the ERPNext system with multi-agent orchestration, proactive intelligence, and deep system integration.

## Core Capabilities
You can answer questions, perform actions, analyze documents, generate code, build reports, create workflows, send emails, and proactively monitor business health.

## Multi-Agent System
Your system has specialized sub-agents for complex tasks:
- **Data Agent**: Queries data, builds reports, generates charts, analyzes trends
- **Code Agent**: Generates code, scripts, APIs, and customizations
- **Admin Agent**: Creates workflows, sends emails, manages documents and notifications
When tasks are complex, you coordinate across these capabilities.

## Data & Reports
- Query any ERPNext data using the `query_data` tool
- Build structured reports with the `build_report` tool
- Export data as CSV, Excel, or JSON with `export_data`
- Data results can include auto-generated charts (bar, line, pie, doughnut)
- You can group, aggregate, filter, and sort data in real-time

## Document Processing
You can analyze uploaded documents (PDF, DOCX, Excel, CSV, PPT, images):
- Summarize documents, extract tables, find specific info
- Extract text from images (OCR)
- Analyze charts, graphs, and data visualizations in images
- Read and extract data from invoices, receipts, and forms
- Describe screenshots and answer questions about image contents

## Workflow Automation
- Create complete business workflows with states, transitions, and role-based approvals
- Set up notifications for document events
- Create email templates with Jinja for recurring communications
- Automate document creation from natural language

## Proactive Intelligence
You can check for:
- Low stock alerts on inventory items
- Overdue sales invoices needing follow-up
- Pending leave applications awaiting approval
- Business anomalies and trends
Use the `get_insights` endpoint to proactively surface issues.

## Tool Usage
- **import_data**: Import Excel/CSV files into any DocType
- **create_api**: Create/edit REST API endpoints via Server Script
- **create_client_script**: Generate form validation and UI logic
- **generate_image**: Create images via DALL-E 3
- **query_data**: Query ERPNext data in real-time with chart support
- **build_report**: Create structured Report Builder reports
- **export_data**: Export data as CSV, Excel, or JSON files
- **create_workflow**: Build business process workflows
- **send_email**: Draft and send emails through ERPNext
- **create_email_template**: Create reusable email templates
- **create_document**: Create or update records in any DocType
- **create_notification**: Set up alerts on document events

## Guidelines
- Always ask for missing required info before calling tools
- Use Markdown formatting in replies
- For data questions, query first then present findings
- For complex tasks, explain the steps you'll take
- For ERPNext how-to questions, include navigation paths
- Offer proactive insights when appropriate (stock alerts, overdue items)
- Start responses with a brief summary for long answers
- When creating workflows or reports, suggest refinements
- Keep code blocks clean with proper syntax highlighting
- For images, offer to refine or regenerate

## Conversation History
"""


def save_memory(user, message, response, context=None, tool_used=None):
	frappe.get_doc(
		{
			"doctype": "AI Chat Memory",
			"user": user,
			"message": message,
			"conversation": response,
			"context": context,
			"tool_used": tool_used,
		}
	).insert(ignore_permissions=True)


def get_memory(user):
	return frappe.get_all(
		"AI Chat Memory",
		filters={"user": user},
		fields=["message", "conversation", "context", "tool_used"],
		order_by="creation desc",
		limit=10,
	)


def _build_prompt(message, document_content, memory, target_language=None, schema_context=None, data_context=None, insights=None):
	prompt = SYSTEM_PROMPT

	if target_language:
		prompt += f"\n## Language Instruction\nRespond in {target_language}. The user wrote their message in their preferred language — always reply in {target_language} regardless of the language they used.\n"

	if insights:
		insights_text = "\n".join(f"- [{i['type']}] {i['title']}" for i in insights)
		prompt += f"\n## Proactive Insights\nThe following business insights are available:\n{insights_text}\nAddress these if relevant to the user's question.\n"

	if document_content:
		doc_preview = document_content[:8000]
		prompt += f"\n## Uploaded Document Content\nThe user has uploaded a document:\n{doc_preview}\n\n"

	if schema_context:
		prompt += f"\n## ERPNext Schema Context\n{schema_context[:3000]}\n"

	if data_context:
		prompt += f"\n## Live Data Context\n{data_context[:3000]}\n"

	for row in reversed(memory):
		prompt += f"\nUser: {row.message}"
		prompt += f"\nAssistant: {row.conversation}"

	prompt += f"\nUser: {message}\nAssistant:"
	return prompt


def _build_multimodal_content(message, image_data, image_mime_type, document_content, memory, target_language=None, schema_context=None, data_context=None, insights=None):
	parts = []
	parts.append(SYSTEM_PROMPT)

	if target_language:
		parts.append(f"\n## Language Instruction\nRespond in {target_language}...\n")

	if insights:
		insights_text = "\n".join(f"- [{i['type']}] {i['title']}" for i in insights)
		parts.append(f"\n## Proactive Insights\n{insights_text}\n")

	if document_content:
		doc_preview = document_content[:8000]
		parts.append(f"\n## Uploaded Document Content\n{doc_preview}\n\n")

	if schema_context:
		parts.append(f"\n## ERPNext Schema Context\n{schema_context[:3000]}\n")

	if data_context:
		parts.append(f"\n## Live Data Context\n{data_context[:3000]}\n")

	for row in reversed(memory):
		parts.append(f"\nUser: {row.message}")
		parts.append(f"\nAssistant: {row.conversation}")

	parts.append(f"\nUser: {message}")

	if image_data and image_mime_type:
		from google.generativeai import protos
		image_bytes = base64.b64decode(image_data)
		parts.append(protos.Part(inline_data=protos.Blob(mime_type=image_mime_type, data=image_bytes)))

	parts.append("\nAssistant:")
	return parts


def _try_agent_execution(message, document_content, image_data, image_mime_type, memory, target_language):
	agent_name, reason = route_message(message)

	if agent_name == "default":
		return None

	context = {
		"document_content": document_content,
		"memory": memory,
		"target_language": target_language,
	}

	agent_map = {
		"data_agent": code_agent,
		"code_agent": code_agent,
		"admin_agent": admin_agent,
	}

	agent = agent_map.get(agent_name)
	if not agent:
		return None

	tools = ToolRegistry.get_function_declarations()
	agent_response = agent.run(message, context, tools=tools)

	if agent_response:
		reply = agent_response
		try:
			parsed = json.loads(agent_response)
			if isinstance(parsed, dict) and "reply" in parsed:
				reply = parsed["reply"]
		except (json.JSONDecodeError, ValueError):
			pass

		return {
			"reply": reply,
			"agent_used": agent_name,
			"raw": agent_response,
		}

	return None


@frappe.whitelist(allow_guest=True)
def chat(message, document_content=None, image_data=None, image_mime_type=None, target_language=None):
	user = frappe.session.user or "Guest"
	message = (message or "").strip()
	if not message:
		frappe.throw("Please enter a message.")

	memory = get_memory(user)

	discover_plugins()
	plugins = PluginRegistry.get_all()
	for plugin in plugins:
		plugin.on_chat_before(
			message=message,
			document_content=document_content,
			image_data=image_data,
			image_mime_type=image_mime_type,
			target_language=target_language,
			memory=memory,
		)

	insights = get_proactive_insights(user)
	if insights:
		pass

	agent_result = _try_agent_execution(message, document_content, image_data, image_mime_type, memory, target_language)
	if agent_result:
		save_memory(
			user=user,
			message=message,
			response=agent_result["reply"],
			context=f"Handled by agent: {agent_result.get('agent_used', 'unknown')}",
		)
		final = {"reply": agent_result["reply"]}
		if hasattr(frappe.flags, "chatbot_greeting") and frappe.flags.chatbot_greeting:
			final["reply"] = frappe.flags.chatbot_greeting + final["reply"]
		for plugin in plugins:
			plugin.on_chat_after(message=message, response=final)
		return final

	tools = ToolRegistry.get_function_declarations()
	has_image = bool(image_data and image_mime_type)

	try:
		if has_image:
			contents = _build_multimodal_content(message, image_data, image_mime_type, document_content, memory, target_language)
			response = model.generate_content(contents, tools=tools or None)
		else:
			prompt = _build_prompt(message, document_content, memory, target_language)
			if tools:
				response = model.generate_content(prompt, tools=tools)
			else:
				response = model.generate_content(prompt)
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "AI Chat Generation Error")
		return {"reply": "I encountered an error processing your request. Please try again."}

	function_call = extract_function_call(response)

	if function_call:
		tool_name = function_call.name
		tool_args = {key: value for key, value in function_call.args.items()}

		for plugin in plugins:
			plugin.on_tool_before(tool_name, **tool_args)

		try:
			result = ToolRegistry.execute(tool_name, **tool_args)
			reply = result.get("reply", "Action completed.")
			action = result.get("action")

			for plugin in plugins:
				plugin.on_tool_after(tool_name, result=result, **tool_args)

			save_memory(
				user=user,
				message=message,
				response=reply,
				tool_used=tool_name,
			)

			final = {"reply": reply, "action": action}

			if "data" in result:
				final["data"] = result["data"]
			if "chart" in result:
				final["chart"] = result["chart"]

			if hasattr(frappe.flags, "chatbot_greeting") and frappe.flags.chatbot_greeting:
				final["reply"] = frappe.flags.chatbot_greeting + final["reply"]

			for plugin in plugins:
				plugin.on_chat_after(message=message, response=final, tool_used=tool_name)

			return final

		except Exception as e:
			frappe.log_error(frappe.get_traceback(), f"AI Tool Execution Error: {tool_name}")
			return {"reply": f"I tried to {tool_name.replace('_', ' ')} but ran into an error: {str(e)}"}

	reply = response.text if response and response.text else "No response"

	save_memory(user=user, message=message, response=reply)

	final = {"reply": reply}

	if hasattr(frappe.flags, "chatbot_greeting") and frappe.flags.chatbot_greeting:
		final["reply"] = frappe.flags.chatbot_greeting + reply

	for plugin in plugins:
		plugin.on_chat_after(message=message, response=final)

	return final


@frappe.whitelist()
def get_all_insights():
	return get_proactive_insights(frappe.session.user)
