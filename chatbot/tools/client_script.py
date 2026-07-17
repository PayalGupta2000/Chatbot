import re

import frappe
import google.generativeai as genai
from chatbot.tools import Tool, ToolRegistry

_genai_configured = False

def _get_model():
	global _genai_configured
	if not _genai_configured:
		genai.configure(api_key=frappe.conf.get("gemini_api_key"))
		_genai_configured = True
	return genai.GenerativeModel("gemini-2.5-flash")


def extract_javascript(response):
	match = re.search(r"```(?:javascript|js)?\s*(.*?)```", response, flags=re.IGNORECASE | re.DOTALL)
	return (match.group(1) if match else response).strip()


class ClientScriptTool(Tool):
	name = "create_client_script"
	description = (
		"Create or modify a Client Script for any DocType in ERPNext. "
		"Use this when the user asks to add form behavior, validation, "
		"field automation, or custom UI logic on any form. "
		"The user must specify which DocType."
	)
	parameters = {
		"type": "object",
		"properties": {
			"doctype": {
				"type": "string",
				"description": (
					"The target DocType name (e.g., Lead, Customer, Sales Invoice, "
					"Purchase Order, Item, Contact, Address, Quotation, etc.)"
				),
			},
			"request": {
				"type": "string",
				"description": (
					"Description of what the client script should do. "
					"For example: 'validate email format on the Lead form', "
					"'auto-set customer territory based on country', "
					"'hide discount field when total < 1000'"
				),
			},
		},
		"required": ["doctype", "request"],
	}

	def execute(self, doctype, request, **kwargs):
		if not frappe.has_permission("Client Script", "create"):
			return {"reply": "I need permission to create Client Script records."}

		if not frappe.db.exists("DocType", doctype):
			return {"reply": f"DocType **{doctype}** does not exist in the system."}

		try:
			script = self._generate_script(doctype, request)
			name = f"AI Script {doctype} {frappe.generate_hash(length=6)}"
			doc = frappe.get_doc(
				{
					"doctype": "Client Script",
					"name": name,
					"dt": doctype,
					"view": "Form",
					"enabled": 1,
					"script": script,
				}
			)
			doc.insert()
			frappe.db.commit()

			reply = (
				f"Created and enabled the Client Script **{name}** for the **{doctype}** form.\n\n"
				f"Refresh the {doctype} form to see it in action."
			)

			return {
				"reply": reply,
				"action": {
					"type": "client_script_created",
					"name": name,
					"doctype": doctype,
				},
			}

		except Exception as e:
			frappe.log_error(frappe.get_traceback(), f"AI Client Script Error ({doctype})")
			return {"reply": f"Failed to create the Client Script for **{doctype}**: {str(e)}"}

	def _generate_script(self, doctype, request):
		prompt = f"""
			Create a Frappe Client Script for the {doctype} DocType based on this request:
			{request}

			Return only executable JavaScript in a fenced ```javascript code block.
			Use frappe.ui.form.on("{doctype}", {{ ... }}). Use supported form events such as onload and validate.
			Do not include explanations, HTML, server-side code, imports, network requests, or destructive actions.
		"""
		response = _get_model().generate_content(prompt)
		script = extract_javascript(response.text if response and response.text else "")
		expected_pattern = f'frappe.ui.form.on("{doctype}"'
		if not script or expected_pattern not in script:
			frappe.throw(
				f"The assistant could not generate a valid Client Script for {doctype}."
			)
		return script


ToolRegistry.register(ClientScriptTool())
