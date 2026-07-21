import frappe
import google.generativeai as genai
import base64

from chatbot.tools import ToolRegistry, extract_function_call

genai.configure(api_key=frappe.conf.get("gemini_api_key"))

model = genai.GenerativeModel("gemini-2.5-flash")


SYSTEM_PROMPT = """You are an AI assistant inside the ERPNext system.

## Your Capabilities
You can answer questions about ERPNext, help users with tasks, and perform
actions by calling tools when the user asks you to do something.

You can also work with uploaded documents (PDF, DOCX, Excel, CSV, PPT,
images). When the user asks questions about a document they've uploaded,
use the document content provided in the prompt to answer.
You can summarise documents, extract tables, find specific information,
or answer questions based on the document content.

When you receive an image you can:
- Extract and read text in any language (OCR)
- Analyse charts, graphs, and data visualisations
- Read and extract data from invoices, receipts, and forms
- Describe and interpret screenshots
- Answer questions about the image contents

## When to Use Tools
- **Import data**: If the user says "import this excel", "import data",
  "import this file", or provides a file to import — use the `import_data` tool.
- **Create an API**: If the user says "create an api", "make an endpoint",
  "expose this as an api" — use the `create_api` tool.
- **Client Script**: If the user asks to add, edit, or update form behavior,
  validation, field automation, or custom UI logic on any DocType form — use
  the `create_client_script` tool. If a script for that DocType already exists,
  this tool will update it. The user must specify which DocType.

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
- When the user asks you to generate, draw, or create an image, do NOT
  say you cannot generate images. Instead, offer realistic alternatives:
  generate SVG code they can view in a browser, write detailed
  descriptions, create ASCII art, produce HTML/CSS for a visual layout,
  or generate Mermaid diagram code. Frame it positively ("I can create
  that as SVG code for you" rather than "I cannot generate images").

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


def _build_prompt(message, document_content, memory, target_language=None):
	prompt = SYSTEM_PROMPT

	if target_language:
		prompt += f"\n## Language Instruction\nRespond in {target_language}. The user wrote their message in their preferred language — always reply in {target_language} regardless of the language they used.\n"

	if document_content:
		doc_preview = document_content[:8000]
		prompt += f"\n## Uploaded Document Content\nThe user has uploaded a document with the following content:\n{doc_preview}\n\n"

	for row in reversed(memory):
		prompt += f"\nUser: {row.message}"
		prompt += f"\nAssistant: {row.conversation}"

	prompt += f"\nUser: {message}\nAssistant:"
	return prompt


def _build_multimodal_content(message, image_data, image_mime_type, document_content, memory, target_language=None):
	parts = []
	parts.append(SYSTEM_PROMPT)

	if target_language:
		parts.append(f"\n## Language Instruction\nRespond in {target_language}. The user wrote their message in their preferred language — always reply in {target_language} regardless of the language they used.\n")

	if document_content:
		doc_preview = document_content[:8000]
		parts.append(f"\n## Uploaded Document Content\nThe user has uploaded a document with the following content:\n{doc_preview}\n\n")

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


@frappe.whitelist(allow_guest=True)
def chat(message, document_content=None, image_data=None, image_mime_type=None, target_language=None):
	user = frappe.session.user or "Guest"
	message = (message or "").strip()
	if not message:
		frappe.throw("Please enter a message.")

	memory = get_memory(user)
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
