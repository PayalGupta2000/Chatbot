import frappe
from chatbot.tools import Tool, ToolRegistry


class CreateAPITool(Tool):
	name = "create_api"
	description = (
		"Create or edit a custom API endpoint in ERPNext using Server Script. "
		"Use this when the user says 'create an api', 'make an endpoint', "
		"'expose this as api', 'create a rest endpoint', "
		"'edit api', or 'update endpoint'. "
		"If the endpoint already exists it will be updated."
	)
	parameters = {
		"type": "object",
		"properties": {
			"method_name": {
				"type": "string",
				"description": (
					"Name for the API endpoint (e.g., 'get_customer_summary'). "
					"It will be accessible at /api/method/<method_name>. "
					"Use snake_case and keep it short but descriptive."
				),
			},
			"description": {
				"type": "string",
				"description": "Short description of what this API endpoint does",
			},
			"script": {
				"type": "string",
				"description": (
					"Python code that runs when this API is called. "
					"Use frappe.response['message'] to return data. "
					"Example:\n"
					'```python\n'
					'data = frappe.get_all("Customer", limit=10)\n'
					'frappe.response["message"] = data\n'
					'```'
				),
			},
			"allow_guest": {
				"type": "boolean",
				"description": "Allow unauthenticated users to access this API",
			},
		},
		"required": ["method_name", "description", "script"],
	}

	def execute(self, method_name, description, script, allow_guest=False, **kwargs):
		api_method = method_name.strip().lower().replace(" ", "_")
		if not api_method:
			return {"reply": "Please provide a valid method name."}

		existing_name = frappe.db.get_value(
			"Server Script", {"api_method": api_method}, "name"
		)

		if existing_name:
			if not frappe.has_permission("Server Script", "write"):
				return {"reply": "I need write permission to edit Server Script records."}
		else:
			if not frappe.has_permission("Server Script", "create"):
				return {"reply": "I need permission to create Server Script records."}

		try:
			if existing_name:
				doc = frappe.get_doc("Server Script", existing_name)
				doc.script = script
				doc.title = description
				doc.allow_guest = 1 if allow_guest else 0
				doc.enabled = 1
				doc.save()
				frappe.db.commit()
				verb = "updated"
			else:
				doc = frappe.get_doc(
					{
						"doctype": "Server Script",
						"name": api_method,
						"title": description,
						"script_type": "API",
						"api_method": api_method,
						"script": script,
						"allow_guest": 1 if allow_guest else 0,
						"enabled": 1,
					}
				)
				doc.insert()
				frappe.db.commit()
				verb = "created and enabled"

			endpoint_url = f"/api/method/{api_method}"
			reply = (
				f"API endpoint **{api_method}** has been {verb}.\n\n"
				f"- **URL:** `{endpoint_url}`\n"
				f"- **Method:** `POST` (or `GET` if no side effects)\n"
				f"- **Guest access:** {'Yes' if allow_guest else 'No'}\n\n"
				f"You can test it by sending a request to `{endpoint_url}`."
			)

			return {
				"reply": reply,
				"action": {
					"type": "api_updated" if existing_name else "api_created",
					"method_name": api_method,
					"endpoint_url": endpoint_url,
					"allow_guest": allow_guest,
				},
			}

		except Exception as e:
			frappe.log_error(frappe.get_traceback(), "AI API Error")
			return {"reply": f"Failed to process API endpoint: {str(e)}"}


ToolRegistry.register(CreateAPITool())
