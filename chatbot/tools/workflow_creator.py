import json
import frappe
from chatbot.tools import Tool, ToolRegistry


class WorkflowCreatorTool(Tool):
	name = "create_workflow"
	description = (
		"Create or update a Workflow for a DocType in ERPNext. "
		"Use this when the user says 'create a workflow', 'set up approval process', "
		"'add states to', or 'make a business process'."
	)
	parameters = {
		"type": "object",
		"properties": {
			"doctype": {
				"type": "string",
				"description": "The DocType to apply the workflow to (e.g., Leave Application, Expense Claim, Purchase Order, Sales Invoice)",
			},
			"workflow_name": {
				"type": "string",
				"description": "Name for the workflow (e.g., 'Leave Approval Workflow', 'Expense Reimbursement Process')",
			},
			"states": {
				"type": "array",
				"description": "List of workflow states. Each is a dict with: state_name (string), doc_status (0=Draft,1=Pending,2=Approved)",
				"items": {
					"type": "object",
					"properties": {
						"state": {"type": "string", "description": "State name (e.g., 'Pending Approval', 'Approved', 'Rejected')"},
						"doc_status": {"type": "string", "description": "Document status: 'Draft', 'Pending', or 'Approved'"},
					},
					"required": ["state", "doc_status"],
				},
			},
			"transitions": {
				"type": "array",
				"description": "List of transitions between states. Each is a dict with: from_state, to_state, role (who can perform), condition (optional Python expression)",
				"items": {
					"type": "object",
					"properties": {
						"from_state": {"type": "string"},
						"to_state": {"type": "string"},
						"role": {"type": "string", "description": "Role that can perform this transition (e.g., 'HR Manager', 'Accounts User', 'Expense Approver')"},
						"condition": {"type": "string", "description": "Optional Python expression as a condition"},
					},
					"required": ["from_state", "to_state", "role"],
				},
			},
			"field": {
				"type": "string",
				"description": "Field name that stores the workflow state (default: 'workflow_state')",
			},
		},
		"required": ["doctype", "workflow_name", "states", "transitions"],
	}

	def execute(self, doctype, workflow_name, states, transitions, field="workflow_state", **kwargs):
		if not frappe.has_permission("Workflow", "create"):
			return {"reply": "I need permission to create Workflow records."}

		if not frappe.db.exists("DocType", doctype):
			return {"reply": f"DocType **{doctype}** does not exist."}

		try:
			if isinstance(states, str):
				states = json.loads(states)
			if isinstance(transitions, str):
				transitions = json.loads(transitions)

			status_map = {"Draft": 0, "Pending": 1, "Approved": 2, "Cancelled": 2}
			workflow_states = []
			for s in states:
				workflow_states.append({
					"state": s["state"],
					"doc_status": status_map.get(s.get("doc_status", "Draft"), 0),
					"update_field": field,
					"update_value": s["state"],
				})

			workflow_transitions = []
			for t in transitions:
				transition = {
					"state": t["from_state"],
					"action": f"Approve to {t['to_state']}",
					"next_state": t["to_state"],
					"allowed": t["role"],
					"allow_self_approval": 1,
				}
				if t.get("condition"):
					transition["condition"] = t["condition"]
				workflow_transitions.append(transition)

			existing = frappe.db.get_value("Workflow", {"document_type": doctype, "workflow_name": workflow_name}, "name")

			if existing:
				doc = frappe.get_doc("Workflow", existing)
				doc.states = workflow_states
				doc.transitions = workflow_transitions
				doc.save(ignore_permissions=True)
				verb = "updated"
			else:
				doc = frappe.get_doc({
					"doctype": "Workflow",
					"workflow_name": workflow_name,
					"document_type": doctype,
					"workflow_state_field": field,
					"is_active": 1,
					"send_email_alert": 0,
					"states": workflow_states,
					"transitions": workflow_transitions,
				})
				doc.insert(ignore_permissions=True)
				verb = "created"

			frappe.db.commit()

			state_names = [s["state"] for s in states]
			transition_count = len(transitions)

			reply = (
				f"Workflow **{workflow_name}** {verb} for **{doctype}**.\n\n"
				f"- States: {', '.join(state_names)}\n"
				f"- Transitions: {transition_count} steps defined\n"
				f"- Workflow field: `{field}`\n\n"
				f"Users can now transition {doctype} records through this workflow."
			)

			return {
				"reply": reply,
				"action": {
					"type": "workflow_created" if not existing else "workflow_updated",
					"workflow_name": workflow_name,
					"doctype": doctype,
					"states": state_names,
					"transitions": transition_count,
				},
			}

		except Exception as e:
			frappe.log_error(frappe.get_traceback(), "Workflow Creator Error")
			return {"reply": f"I tried to create the workflow but ran into an error: {str(e)}"}


ToolRegistry.register(WorkflowCreatorTool())
