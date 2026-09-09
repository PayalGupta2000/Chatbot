import json

import frappe
from frappe import _

MAX_CONVERSATIONS = 12


def _resolve_owner(client_id=None):
	user = frappe.session.user
	if user and user != "Guest":
		return user
	return (client_id or "").strip() or "Guest"


def _get_owned_conversation(name, owner):
	doc = frappe.db.exists("AI Chat Conversation", name)
	if not doc:
		return None
	doc = frappe.get_doc("AI Chat Conversation", name, ignore_permissions=True)
	if doc.owner_key != owner:
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	return doc


def _decode_messages(value):
	try:
		messages = json.loads(value or "[]")
		return messages if isinstance(messages, list) else []
	except (ValueError, TypeError):
		return []


@frappe.whitelist()
def get_conversations(client_id=None):
	owner = _resolve_owner(client_id)
	conversations = frappe.get_all(
		"AI Chat Conversation",
		filters={"owner_key": owner},
		fields=["name", "title", "messages", "updated_at"],
		order_by="updated_at desc",
		limit=MAX_CONVERSATIONS,
		ignore_permissions=True,
	)
	for row in conversations:
		row["id"] = row["name"]
		row["messages"] = _decode_messages(row["messages"])
		row["updatedAt"] = row["updated_at"]
	return {"conversations": conversations}


@frappe.whitelist()
def save_conversation(name=None, title=None, messages=None, client_id=None):
	owner = _resolve_owner(client_id)
	if not name:
		frappe.throw(_("Conversation name is required"))

	if isinstance(messages, list):
		messages = json.dumps(messages[:MAX_CONVERSATIONS * 2])
	title = title or "New conversation"

	existing = frappe.db.exists("AI Chat Conversation", name)
	if existing:
		doc = frappe.get_doc("AI Chat Conversation", name, ignore_permissions=True)
		if doc.owner_key != owner:
			frappe.throw(_("Not permitted"), frappe.PermissionError)
		doc.title = title
		doc.messages = messages
		doc.updated_at = frappe.utils.now()
		doc.save(ignore_permissions=True)
	else:
		frappe.get_doc(
			{
				"doctype": "AI Chat Conversation",
				"name": name,
				"owner_key": owner,
				"title": title,
				"messages": messages,
				"updated_at": frappe.utils.now(),
			}
		).insert(ignore_permissions=True)

	return {"name": name}


@frappe.whitelist()
def delete_conversation(name, client_id=None):
	owner = _resolve_owner(client_id)
	doc = _get_owned_conversation(name, owner)
	if doc:
		doc.delete(ignore_permissions=True)
	return {"ok": True}


@frappe.whitelist()
def clear_all_conversations(client_id=None):
	owner = _resolve_owner(client_id)
	frappe.db.delete("AI Chat Conversation", {"owner_key": owner})
	return {"ok": True}