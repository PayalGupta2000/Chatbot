import json
import frappe
from chatbot.tools import Tool, ToolRegistry


class DocumentAutomationTool(Tool):
	name = "create_document"
	description = (
		"Create or update records in any ERPNext DocType. "
		"Use this when the user says 'create a', 'make a new', "
		"'add a record', 'save this as', or 'register a'."
	)
	parameters = {
		"type": "object",
		"properties": {
			"doctype": {
				"type": "string",
				"description": "The DocType to create a record in (e.g., Customer, Lead, Contact, Address, Note, ToDo, Opportunity)",
			},
			"data": {
				"type": "string",
				"description": "JSON object with field values to set on the new document",
			},
			"update_existing": {
				"type": "boolean",
				"description": "If true, will update existing records matching the data instead of creating new ones",
			},
		},
		"required": ["doctype", "data"],
	}

	def execute(self, doctype, data, update_existing=False, **kwargs):
		if isinstance(data, str):
			data = json.loads(data)

		perm_type = "write" if update_existing else "create"
		if not frappe.has_permission(doctype, perm_type):
			return {"reply": f"I need {perm_type} permission for **{doctype}**."}

		try:
			if update_existing and data.get("name"):
				if not frappe.has_permission(doctype, "write"):
					return {"reply": f"I need write permission for **{doctype}**."}
				doc = frappe.get_doc(doctype, data["name"])
				for key, val in data.items():
					if key != "name":
						doc.set(key, val)
				doc.save(ignore_permissions=True)
				frappe.db.commit()
				verb = "updated"
				name = doc.name
			else:
				doc = frappe.get_doc({"doctype": doctype, **data})
				doc.insert(ignore_permissions=True)
				frappe.db.commit()
				verb = "created"
				name = doc.name

			reply = (
				f"**{doctype}** '{name}' has been {verb}.\n\n"
				f"View it at: `/app/{frappe.scrub(doctype)}/{name}`"
			)

			return {
				"reply": reply,
				"action": {
					"type": "document_created" if verb == "created" else "document_updated",
					"doctype": doctype,
					"name": name,
					"url": f"/app/{frappe.scrub(doctype)}/{name}",
				},
			}

		except Exception as e:
			frappe.log_error(frappe.get_traceback(), f"Doc Automation Error ({doctype})")
			return {"reply": f"I tried to create the **{doctype}** but hit an error: {str(e)}"}


class CreateNotificationTool(Tool):
	name = "create_notification"
	description = (
		"Create an ERPNext Notification to alert users on document events. "
		"When the user says 'notify me when', 'send alert when', "
		"'set up notification', or 'email me when'."
	)
	parameters = {
		"type": "object",
		"properties": {
			"doctype": {
				"type": "string",
				"description": "The DocType to watch for events",
			},
			"event": {
				"type": "string",
				"enum": ["New", "Save", "Submit", "Cancel", "Days Before", "Days After"],
				"description": "When to trigger the notification",
			},
			"recipients": {
				"type": "string",
				"description": "Comma-separated email addresses or roles like 'HR Manager'",
			},
			"subject": {
				"type": "string",
				"description": "Email subject template (supports Jinja like {{ doc.name }})",
			},
			"message": {
				"type": "string",
				"description": "Email message template (supports Jinja)",
			},
		},
		"required": ["doctype", "event", "recipients", "subject", "message"],
	}

	def execute(self, doctype, event, recipients, subject, message, **kwargs):
		if not frappe.has_permission("Notification", "create"):
			return {"reply": "I need permission to create Notification records."}

		try:
			existing = frappe.db.get_value(
				"Notification",
				{"document_type": doctype, "event": event, "subject": subject},
				"name",
			)

			if existing:
				doc = frappe.get_doc("Notification", existing)
				doc.subject = subject
				doc.message = message
				doc.recipients = recipients
				doc.save(ignore_permissions=True)
				verb = "updated"
			else:
				doc = frappe.get_doc({
					"doctype": "Notification",
					"document_type": doctype,
					"event": event,
					"subject": subject,
					"message": message,
					"recipients": recipients,
					"enabled": 1,
					"send_system_notification": 0,
					"send_email_alert": 1,
				})
				doc.insert(ignore_permissions=True)
				verb = "created"

			frappe.db.commit()

			reply = (
				f"Notification **{verb}** for **{doctype}** on **{event}**.\n\n"
				f"- Subject: {subject}\n"
				f"- Recipients: {recipients}"
			)

			return {
				"reply": reply,
				"action": {
					"type": "notification_created" if not existing else "notification_updated",
					"doctype": doctype,
					"event": event,
				},
			}

		except Exception as e:
			frappe.log_error(frappe.get_traceback(), "Notification Creation Error")
			return {"reply": f"Failed to create notification: {str(e)}"}


ToolRegistry.register(DocumentAutomationTool())
ToolRegistry.register(CreateNotificationTool())
