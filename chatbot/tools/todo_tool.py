import frappe
from chatbot.tools import Tool, ToolRegistry


class ManageToDoTool(Tool):
	name = "manage_todo"
	description = (
		"Create, complete, or list To-Do / task items in ERPNext. "
		"Use this when the user says 'add a to-do', 'create a task', 'remind me to', "
		"'mark my task done', 'complete the to-do', or 'what are my pending tasks'."
	)
	parameters = {
		"type": "object",
		"properties": {
			"action": {
				"type": "string",
				"enum": ["create", "complete", "list"],
				"description": "What to do: create a new to-do, mark an existing one complete, or list pending tasks",
			},
			"description": {
				"type": "string",
				"description": "The task text (required for 'create')",
			},
			"date": {
				"type": "string",
				"description": "Optional due date (YYYY-MM-DD) for 'create'",
			},
			"priority": {
				"type": "string",
				"enum": ["Low", "Medium", "High"],
				"description": "Priority for the new to-do",
			},
			"assigned_to": {
				"type": "string",
				"description": "User email to assign the task to (defaults to the current user)",
			},
			"todo_name": {
				"type": "string",
				"description": "The to-do name/id to complete (required for 'complete')",
			},
			"limit": {
				"type": "integer",
				"description": "Max tasks to return for 'list' (default 10)",
			},
		},
		"required": ["action"],
	}

	def execute(self, action, description=None, date=None, priority="Medium", assigned_to=None, todo_name=None, limit=10, **kwargs):
		action = (action or "list").lower()
		assigned_to = assigned_to or frappe.session.user

		try:
			if action == "create":
				if not description:
					return {"reply": "I need a description to create a to-do."}
				if not frappe.has_permission("ToDo", "create"):
					return {"reply": "I need permission to create To-Do items."}

				doc = frappe.get_doc({
					"doctype": "ToDo",
					"description": description,
					"priority": priority,
					"date": date,
					"allocated_to": assigned_to,
				})
				doc.insert(ignore_permissions=True)
				frappe.db.commit()

				reply = (
					f"To-Do created: **{description}**\n\n"
					f"- Priority: {priority}\n"
					f"- Due: {date or 'Not set'}\n"
					f"- Assigned to: {assigned_to}\n"
					f"- Status: Open"
				)
				return {
					"reply": reply,
					"action": {"type": "todo_created", "name": doc.name, "description": description},
				}

			if action == "complete":
				if not todo_name:
					return {"reply": "I need the to-do name to mark it complete."}
				if not frappe.has_permission("ToDo", "write"):
					return {"reply": "I need permission to update To-Do items."}

				if not frappe.db.exists("ToDo", todo_name):
					return {"reply": f"To-Do **{todo_name}** was not found."}

				doc = frappe.get_doc("ToDo", todo_name)
				doc.status = "Closed"
				doc.save(ignore_permissions=True)
				frappe.db.commit()

				return {
					"reply": f"To-Do **{doc.description}** marked as complete.",
					"action": {"type": "todo_completed", "name": doc.name},
				}

			tasks = frappe.get_all(
				"ToDo",
				filters={"status": ["!=", "Closed"], "allocated_to": assigned_to},
				fields=["name", "description", "priority", "date"],
				order_by="date asc",
				limit=limit,
			)

			if not tasks:
				return {"reply": "You have no pending to-dos. Great job!"}

			lines = [f"{t['description']} — {t['priority']} ({t['date'] or 'no due date'})" for t in tasks]
			reply = (
				f"You have **{len(tasks)}** pending to-do{'s' if len(tasks) > 1 else ''}:\n\n"
				+ "\n".join(f"- {line}" for line in lines)
			)
			return {
				"reply": reply,
				"data": {"columns": ["name", "description", "priority", "date"], "rows": tasks, "total_rows": len(tasks)},
			}

		except Exception as e:
			frappe.log_error(frappe.get_traceback(), "To-Do Tool Error")
			return {"reply": f"I ran into an error with the to-do: {str(e)}"}


ToolRegistry.register(ManageToDoTool())
