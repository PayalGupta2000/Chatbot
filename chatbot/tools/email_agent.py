import json
import frappe
from chatbot.tools import Tool, ToolRegistry


class EmailAgentTool(Tool):
	name = "send_email"
	description = (
		"Draft and send emails through ERPNext. "
		"Use this when the user says 'send an email', 'draft an email', "
		"'compose a message', 'notify someone', or 'send a communication'."
	)
	parameters = {
		"type": "object",
		"properties": {
			"recipients": {
				"type": "array",
				"description": "List of recipient email addresses",
				"items": {"type": "string"},
			},
			"subject": {
				"type": "string",
				"description": "Email subject line",
			},
			"content": {
				"type": "string",
				"description": "Email body content (can include HTML)",
			},
			"doctype": {
				"type": "string",
				"description": "Optional: Link this email to a specific DocType record (e.g., 'Customer')",
			},
			"docname": {
				"type": "string",
				"description": "Optional: Name of the document to link this email to",
			},
			"send_now": {
				"type": "boolean",
				"description": "Send immediately (true) or save as draft (false)",
			},
		},
		"required": ["recipients", "subject", "content"],
	}

	def execute(self, recipients, subject, content, doctype=None, docname=None, send_now=True, **kwargs):
		if not frappe.has_permission("Communication", "create"):
			return {"reply": "I need permission to create Communication records."}

		try:
			if isinstance(recipients, str):
				recipients = json.loads(recipients)

			recipient_str = ", ".join(recipients) if isinstance(recipients, list) else recipients

			comm = frappe.get_doc({
				"doctype": "Communication",
				"communication_type": "Communication",
				"communication_medium": "Email",
				"subject": subject,
				"content": content,
				"recipients": recipient_str,
				"sent_or_received": "Sent" if send_now else "Draft",
				"email_status": "Sent" if send_now else "Draft",
				"reference_doctype": doctype,
				"reference_name": docname,
			})
			comm.insert(ignore_permissions=True)

			if send_now:
				try:
					comm.send(print_format=None)
					status = "sent"
				except Exception as send_err:
					frappe.log_error(frappe.get_traceback(), "Email Send Error")
					status = "saved but sending failed"
			else:
				status = "saved as draft"

			frappe.db.commit()

			reply = (
				f"Email **{status}**.\n\n"
				f"- To: {recipient_str}\n"
				f"- Subject: {subject}\n"
				f"- Status: {status}\n"
			)
			if doctype and docname:
				reply += f"- Linked to: {doctype} {docname}\n"

			return {
				"reply": reply,
				"action": {
					"type": "email_sent" if send_now else "email_drafted",
					"recipients": recipient_str,
					"subject": subject,
					"status": status,
					"communication_id": comm.name,
				},
			}

		except Exception as e:
			frappe.log_error(frappe.get_traceback(), "Email Agent Error")
			return {"reply": f"Failed to process email: {str(e)}"}


class EmailTemplateTool(Tool):
	name = "create_email_template"
	description = (
		"Create a reusable Email Template in ERPNext. "
		"Use this when the user says 'create an email template', "
		"'make a template for emails', or 'save this as a template'."
	)
	parameters = {
		"type": "object",
		"properties": {
			"template_name": {
				"type": "string",
				"description": "Name for the email template",
			},
			"subject": {
				"type": "string",
				"description": "Email subject template (can include Jinja like {{ doc.name }})",
			},
			"content": {
				"type": "string",
				"description": "HTML body template with Jinja (use {{ doc.fieldname }} for document fields)",
			},
			"doctype": {
				"type": "string",
				"description": "DocType this template is for (e.g., 'Sales Invoice', 'Customer', 'Lead')",
			},
		},
		"required": ["template_name", "subject", "content", "doctype"],
	}

	def execute(self, template_name, subject, content, doctype, **kwargs):
		if not frappe.has_permission("Email Template", "create"):
			return {"reply": "I need permission to create Email Template records."}

		try:
			existing = frappe.db.get_value("Email Template", {"name": template_name}, "name")
			if existing:
				doc = frappe.get_doc("Email Template", existing)
				doc.subject = subject
				doc.response = content
				doc.doctype_name = doctype
				doc.save(ignore_permissions=True)
				verb = "updated"
			else:
				doc = frappe.get_doc({
					"doctype": "Email Template",
					"name": template_name,
					"subject": subject,
					"response": content,
					"doctype_name": doctype,
				})
				doc.insert(ignore_permissions=True)
				verb = "created"

			frappe.db.commit()

			reply = (
				f"Email template **{template_name}** {verb} for **{doctype}**.\n\n"
				f"- Subject: {subject}\n"
				f"- Use it with: `{{% raw %}}` in your emails"
			)

			return {
				"reply": reply,
				"action": {
					"type": "email_template_created" if not existing else "email_template_updated",
					"template_name": template_name,
					"doctype": doctype,
				},
			}

		except Exception as e:
			frappe.log_error(frappe.get_traceback(), "Email Template Error")
			return {"reply": f"Failed to create email template: {str(e)}"}


ToolRegistry.register(EmailAgentTool())
ToolRegistry.register(EmailTemplateTool())
