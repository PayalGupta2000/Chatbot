import frappe
import google.generativeai as genai

from chatbot.tools import ToolRegistry, extract_function_call

genai.configure(api_key=frappe.conf.get("gemini_api_key"))

model = genai.GenerativeModel("gemini-2.5-flash")


SYSTEM_PROMPT = """You are an AI assistant inside the ERPNext system.

## Your Capabilities
You can answer questions about ERPNext, help users with tasks, and perform
actions by calling tools when the user asks you to do something.

## When to Use Tools
- **Import data**: If the user says "import this excel", "import data",
  "import this file", or provides a file to import — use the `import_data` tool.
- **Create an API**: If the user says "create an api", "make an endpoint",
  "expose this as an api" — use the `create_api` tool.
- **Client Script**: If the user asks to add form behavior, validation,
  field automation, or custom UI logic on any DocType form — use the
  `create_client_script` tool. The user must specify which DocType.

## Guidelines
- Always ask for missing required information before calling a tool.
- For import requests, ask for the DocType and file path if not specified.
- For API requests, help the user write the Python code if they are unsure.
- Keep explanations concise but informative.
- Use Markdown formatting in your replies.
- Start long answers with a short summary.
- Use headings (##) for major sections.
- Use bullet points or numbered lists.
- For ERPNext how-to questions, separate navigation, required fields,
  and next steps.

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
		limit=5,
	)


@frappe.whitelist(allow_guest=True)
def chat(message):
	user = frappe.session.user or "Guest"
	message = (message or "").strip()
	if not message:
		frappe.throw("Please enter a message.")

	memory = get_memory(user)

	prompt = SYSTEM_PROMPT

	for row in reversed(memory):
		prompt += f"\nUser: {row.message}"
		prompt += f"\nAssistant: {row.conversation}"

	prompt += f"\nUser: {message}\nAssistant:"

	tools = ToolRegistry.get_function_declarations()

	try:
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

		try:
			result = ToolRegistry.execute(tool_name, **tool_args)
			reply = result.get("reply", "Action completed.")
			action = result.get("action")

			save_memory(
				user=user,
				message=message,
				response=reply,
				tool_used=tool_name,
			)

			return {"reply": reply, "action": action}

		except Exception as e:
			frappe.log_error(frappe.get_traceback(), f"AI Tool Execution Error: {tool_name}")
			return {"reply": f"I tried to {tool_name.replace('_', ' ')} but ran into an error: {str(e)}"}

	reply = response.text if response and response.text else "No response"

	save_memory(user=user, message=message, response=reply)

	return {"reply": reply}
