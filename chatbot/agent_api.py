"""Bridge between the chatbot UI and the local opencode (frappe-developer) agent.

Flow:
1. ``agent_chat`` (fast, < 1s): validates, creates opencode session, enqueues
   background RQ job, returns ``{status: "processing", conversation_id}``.
2. ``_run_agent_background`` (RQ worker): POSTs to opencode, stores result on
   the ``OpenCode Session`` row.
3. ``agent_result`` (polling): reads the row and returns the result.
"""

import json
import os

import frappe
import requests


# ---------------------------------------------------------------------------
# Configuration helpers (read lazily so the module loads even if conf is empty)
# ---------------------------------------------------------------------------

def _server_url():
	return frappe.conf.get("opencode_server_url") or "http://127.0.0.1:4100"


def _agent_name():
	return frappe.conf.get("opencode_agent") or "frappe-developer"


def _request_timeout():
	return frappe.conf.get("opencode_timeout") or 600


def _server_available() -> bool:
	try:
		resp = requests.get(f"{_server_url()}/global/health", timeout=3)
		return resp.ok
	except Exception:
		return False


# ---------------------------------------------------------------------------
# OpenCode Session helpers
# ---------------------------------------------------------------------------

def get_or_create_opencode_session(conversation_id) -> str:
	row = frappe.db.get_value(
		"OpenCode Session", {"conversation_id": conversation_id}, "opencode_session"
	)
	# A row created early by attach_files uses a "pending-..." placeholder that
	# is not a real opencode session, so we must still create a real one.
	if row and not row.startswith("pending-"):
		return row

	resp = requests.post(
		f"{_server_url()}/session",
		json={"title": f"chatbot conversation {conversation_id}"},
		timeout=10,
	)
	resp.raise_for_status()
	session_id = resp.json()["id"]

	existing = frappe.db.exists("OpenCode Session", {"conversation_id": conversation_id})
	if existing:
		frappe.db.set_value("OpenCode Session", existing, "opencode_session", session_id)
	else:
		frappe.get_doc(
			{
				"doctype": "OpenCode Session",
				"conversation_id": conversation_id,
				"opencode_session": session_id,
			}
		).insert(ignore_permissions=True)
	frappe.db.commit()

	return session_id


def _set_session_state(conversation_id, status, result=None, error=None):
	result_payload = {}
	if result:
		result_payload["reply"] = result.get("reply", "")
		if result.get("action"):
			result_payload["action"] = result["action"]
	if error:
		result_payload["error"] = str(error)

	filters = {"conversation_id": conversation_id}
	existing = frappe.db.exists("OpenCode Session", filters)
	if existing:
		update_fields = {"status": status}
		if result_payload:
			update_fields["result"] = json.dumps(result_payload, default=str)
		frappe.db.set_value("OpenCode Session", existing, update_fields)
		frappe.db.commit()


# ---------------------------------------------------------------------------
# Opencode message helpers
# ---------------------------------------------------------------------------

def _extract_reply(payload: dict) -> str:
	texts = []
	for part in payload.get("parts") or []:
		if part.get("type") == "text" and part.get("text"):
			texts.append(part["text"])
	return "\n".join(texts).strip()


def _collect_file_changes(payload: dict) -> list:
	paths = set()
	for part in payload.get("parts") or []:
		if part.get("type") == "file" and part.get("file"):
			paths.add(part["file"].get("path"))
	return sorted(paths)


# ---------------------------------------------------------------------------
# Background agent runner (executes in an RQ worker)
# ---------------------------------------------------------------------------

def _get_attached_files(conversation_id):
	"""Return the list of uploaded file paths registered for a conversation."""
	raw = frappe.db.get_value(
		"OpenCode Session", {"conversation_id": conversation_id}, "attached_files"
	)
	if not raw:
		return []
	try:
		files = json.loads(raw)
		return files if isinstance(files, list) else []
	except (json.JSONDecodeError, TypeError):
		return []


def _build_upload_note(message, conversation_id):
	"""Append a note about currently uploaded files so the agent is aware of them.

	Returns ``(prompt_text, note_text)`` where ``prompt_text`` is what is sent to
	the agent and ``note_text`` is a human-readable summary ("" when no files).
	"""
	files = _get_attached_files(conversation_id)
	if not files:
		return message, ""

	lines = ["The following files were uploaded by the user in the current chat context. "
		"You can read them directly from disk at the given absolute paths if needed:",
		""]
	for f in files:
		name = f.get("file_name", "")
		path = f.get("file_path", "")
		notes = f.get("notes", "")
		lines.append(f"- {name}" + (f"  ({notes})" if notes else ""))
		if path:
			lines.append(f"    path: {path}")
	lines.append("")
	lines.append("If the user asks about an uploaded file (e.g. summarise this file/screenshot), "
		"use these paths to read/inspect the file rather than claiming you have no such file.")

	note = "\n".join(lines).strip()
	# Only give the agent a compact pointer (paths), not full content, to avoid
	# bloating the prompt; the agent reads the file on demand from disk.
	pointer = "\n".join(f"- {f.get('file_name','')}: {f.get('file_path','')}" for f in files if f.get("file_path"))
	return f"{message}\n\n## Uploaded files (available on disk)\n{pointer}\n", note


def _run_agent_background(conversation_id, message, session_id, user):
	"""Run the opencode agent in a background RQ worker."""
	try:
		_set_session_state(conversation_id, "processing")

		prompt, _note = _build_upload_note(message, conversation_id)

		msg_resp = requests.post(
			f"{_server_url()}/session/{session_id}/message",
			json={
				"parts": [{"type": "text", "text": prompt}],
				"agent": _agent_name(),
			},
			timeout=_request_timeout(),
		)
		msg_resp.raise_for_status()
		payload = msg_resp.json()

		reply = _extract_reply(payload) or "The developer agent produced no response."
		files = _collect_file_changes(payload)

		result = {"reply": reply}
		if files:
			result["action"] = {"type": "files_modified", "files": files}

		_set_session_state(conversation_id, "done", result=result)

	except Exception as exc:
		frappe.log_error(frappe.get_traceback(), "Agent API background error")
		_set_session_state(conversation_id, "failed", error=str(exc))


# ---------------------------------------------------------------------------
# Whitelisted HTTP endpoints
# ---------------------------------------------------------------------------

@frappe.whitelist()
def agent_chat(message, conversation_id=None, client_id=None):
	"""Enqueue the agent prompt and return immediately (< 1s)."""
	user = frappe.session.user or "Guest"
	message = (message or "").strip()
	if not message:
		frappe.throw("Please enter a message.")

	if not _server_available():
		frappe.throw(
			"opencode_server_unavailable: The developer agent is not running. "
			"Please ensure the opencode server is started (opencode serve) and try again."
		)

	if conversation_id:
		session_id = get_or_create_opencode_session(conversation_id)
	else:
		conversation_id = f"adhoc-{frappe.utils.now_datetime().strftime('%Y%m%d%H%M%S')}"
		resp = requests.post(
			f"{_server_url()}/session", json={"title": "ad-hoc chatbot run"}, timeout=10
		)
		resp.raise_for_status()
		session_id = resp.json()["id"]

	_set_session_state(conversation_id, "processing")

	frappe.enqueue(
		"chatbot.agent_api._run_agent_background",
		queue="default",
		conversation_id=conversation_id,
		message=message,
		session_id=session_id,
		user=user,
		timeout=_request_timeout(),
		enqueue_after_commit=True,
	)
	frappe.db.commit()

	return {"status": "processing", "conversation_id": conversation_id}


@frappe.whitelist()
def attach_files(conversation_id=None, files=None):
	"""Register uploaded files for a conversation so the agent knows about them.

	``files`` is a list of ``{"file_name", "file_path", "notes"}`` dicts (paths
	are absolute on-disk locations the agent can read).  Stored on the
	``OpenCode Session`` row and injected into the agent prompt on the next run.
	"""
	if not conversation_id:
		frappe.throw("conversation_id is required.")
	if not files:
		files = []

	normalized = []
	for f in files or []:
		if not isinstance(f, dict):
			continue
		# The File DocType name (e.g. the doc.name from upload) is the most
		# reliable way to resolve the on-disk path.
		file_doc_name = f.get("name")
		file_name = f.get("file_name") or f.get("name") or ""
		path = _resolve_file_path(file_doc_name) or _resolve_file_path(file_name)
		normalized.append({
			"file_name": file_name,
			"file_path": path,
			"notes": f.get("notes", ""),
		})

	existing = frappe.db.exists("OpenCode Session", {"conversation_id": conversation_id})
	if existing:
		frappe.db.set_value("OpenCode Session", existing, "attached_files", json.dumps(normalized))
	else:
		frappe.get_doc({
			"doctype": "OpenCode Session",
			"conversation_id": conversation_id,
			"opencode_session": f"pending-{conversation_id}",
			"status": "pending",
			"attached_files": json.dumps(normalized),
		}).insert(ignore_permissions=True)
	frappe.db.commit()

	return {"attached": len(normalized)}


def _resolve_file_path(file_name_or_url):
	"""Best-effort: return an absolute on-disk path for a Frappe File.

	The private files live under ``sites/<site>/private/files`` and public files
	under ``sites/<site>/public/files``.  We try the File doc first, then fall
	back to matching the filename in those directories.
	"""
	try:
		if not file_name_or_url:
			return ""
		file_doc = frappe.get_doc("File", file_name_or_url)
		path = file_doc.get_full_path() or ""
		if path and os.path.exists(path):
			return os.path.abspath(path)
	except Exception:
		pass

	# Fallback: match against this site's public/private files dirs.
	base_names = [frappe.get_site_path("private", "files"), frappe.get_site_path("public", "files")]
	# Also consider the bench-root referenced form "./mysite.local/private/files/..."
	bench = frappe.utils.get_bench_path()
	stem = file_name_or_url.split("/")[-1]
	for base in base_names:
		guess = os.path.join(base, stem)
		if os.path.exists(guess):
			return os.path.abspath(guess)
	# ./mysite.local/... style path
	if os.path.exists(os.path.join(bench, file_name_or_url)):
		return os.path.abspath(os.path.join(bench, file_name_or_url))
	return ""


@frappe.whitelist()
def agent_result(conversation_id):
	"""Poll endpoint: return the current status."""
	if not conversation_id:
		frappe.throw("conversation_id is required.")

	row = frappe.db.get_value(
		"OpenCode Session",
		{"conversation_id": conversation_id},
		["status", "result"],
		as_dict=True,
	)

	if not row:
		return {"status": "done", "reply": "No agent task found for this conversation."}

	status = row.status or "processing"

	if status == "done" and row.result:
		try:
			result = json.loads(row.result)
		except (json.JSONDecodeError, TypeError):
			result = {"reply": row.result or ""}
		return {"status": "done", **result}

	if status == "failed" and row.result:
		try:
			result = json.loads(row.result)
		except (json.JSONDecodeError, TypeError):
			result = {}
		return {"status": "failed", "error": result.get("error", "Unknown error")}

	return {"status": status}


@frappe.whitelist()
def agent_status():
	"""Returns whether the local developer agent server is reachable."""
	return {
		"available": _server_available(),
		"server_url": _server_url(),
		"agent": _agent_name(),
	}
