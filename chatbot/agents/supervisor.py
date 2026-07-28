import frappe
import json
import google.generativeai as genai

SUPERVISOR_PROMPT = """You are the Supervisor Agent — the central routing intelligence for the ERPNext AI assistant.
Your ONLY job is to analyze the user's message and select the BEST agent to handle it.

Available agents:
{catalogue}

## Routing Rules
- If the user wants a DATA QUERY, REPORT, CHART, or ANALYSIS → data_agent
- If the user wants CODE, SCRIPTS, APIs, or AUTOMATION → code_agent
- If the user wants WORKFLOWS, EMAILS, DOCUMENTS, or ADMIN → admin_agent
- If the user wants CONVERSATION, HELP, EXPLANATION, or GENERAL → use the default chat

## Output Format
Respond with ONLY a JSON object:
{{"agent": "agent_name", "reason": "brief reason"}}
If the request can be handled by the default chat, return:
{{"agent": "default", "reason": "..."}}

Do NOT include markdown, explanation, or anything else."""

SUPERVISOR_CATALOGUE = [
	{
		"name": "data_agent",
		"description": "Handles data queries, report building, chart generation, data analysis, trends, aggregations, and schema exploration. Use when user asks about ERPNext data, wants reports or charts, queries for records, or needs analytics.",
	},
	{
		"name": "code_agent",
		"description": "Handles code generation, script creation, API endpoints, client scripts, server scripts, customizations, and automation code. Use when user asks to create/edit/update code, scripts, APIs, or technical customizations.",
	},
	{
		"name": "admin_agent",
		"description": "Handles workflow creation, email composition, document generation, system configuration, user management, and business process automation. Use when user asks about workflows, emails, documents, or system settings.",
	},
]


def route_message(message: str) -> tuple[str, str]:
	api_key = frappe.conf.get("gemini_api_key")
	if not api_key:
		return "default", "No AI configured"
	genai.configure(api_key=api_key)
	model = genai.GenerativeModel("gemini-2.5-flash")
	catalogue_text = "\n".join(
		f"- {a['name']}: {a['description']}" for a in SUPERVISOR_CATALOGUE
	)
	prompt = SUPERVISOR_PROMPT.format(catalogue=catalogue_text)
	full = f"{prompt}\n\nUser message: {message}\n\nResponse:"
	try:
		resp = model.generate_content(full)
		text = resp.text.strip() if resp and resp.text else ""
		text = text.replace("```json", "").replace("```", "").strip()
		result = json.loads(text)
		agent = result.get("agent", "default")
		reason = result.get("reason", "")
		for a in SUPERVISOR_CATALOGUE:
			if a["name"] == agent:
				return agent, reason
		return "default", reason
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Supervisor Routing Error")
		return "default", "Routing failed, falling back to default"
