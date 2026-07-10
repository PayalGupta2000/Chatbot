import re

import frappe
import google.generativeai as genai

genai.configure(api_key=frappe.conf.get("gemini_api_key"))

model = genai.GenerativeModel("gemini-2.5-flash")


def is_lead_client_script_request(message):
	request = message.lower()
	action_words = ("add", "apply", "build", "create", "make", "set", "write")
	has_action = any(word in request for word in action_words)
	is_client_script = "client script" in request
	is_email_validation = "email" in request and "validation" in request
	return "lead" in request and has_action and (is_client_script or is_email_validation)


def extract_javascript(response):
	match = re.search(r"```(?:javascript|js)?\s*(.*?)```", response, flags=re.IGNORECASE | re.DOTALL)
	return (match.group(1) if match else response).strip()


def generate_lead_client_script(request):
	prompt = f"""
		Create a Frappe Client Script for the Lead DocType based on this request:
		{request}

		Return only executable JavaScript in a fenced ```javascript code block.
		Use frappe.ui.form.on("Lead", {{ ... }}). Use supported form events such as onload and validate.
		Do not include explanations, HTML, server-side code, imports, network requests, or destructive actions.
	"""
	response = model.generate_content(prompt)
	script = extract_javascript(response.text if response and response.text else "")
	if not script or "frappe.ui.form.on" not in script or "Lead" not in script:
		frappe.throw("The assistant could not generate a valid Lead Client Script.")
	return script


def create_lead_client_script(request):
	if frappe.session.user == "Guest" or not frappe.has_permission("Client Script", "create"):
		return None

	script = generate_lead_client_script(request)
	name = f"AI Lead Script {frappe.generate_hash(length=8)}"
	doc = frappe.get_doc(
		{
			"doctype": "Client Script",
			"name": name,
			"dt": "Lead",
			"view": "Form",
			"enabled": 1,
			"script": script,
		}
	)
	doc.insert()
	return doc


# ---------------- MEMORY ----------------
def save_memory(user, message, response, context=None, tool_used=None):

    frappe.get_doc({
        "doctype": "AI Chat Memory",
        "user": user,
        "message": message,
        "conversation": response,   # 👈 AI reply stored here
        "context": context,
        "tool_used": tool_used
    }).insert(ignore_permissions=True)

def get_memory(user):

    return frappe.get_all(
        "AI Chat Memory",
        filters={"user": user},
        fields=["message", "conversation", "context", "tool_used"],
        order_by="creation desc",
        limit=5
    )


@frappe.whitelist(allow_guest=True)
def chat(message):
	user = frappe.session.user or "Guest"
	message = (message or "").strip()
	if not message:
		frappe.throw("Please enter a message.")

	if is_lead_client_script_request(message):
		try:
			client_script = create_lead_client_script(message)
			if client_script:
				reply = (
					f"Created and enabled the Client Script **{client_script.name}** for the Lead form. "
					"Refresh the Lead form to use it."
				)
				save_memory(user=user, message=message, response=reply, tool_used="Create Client Script")
				return {
					"reply": reply,
					"action": {"type": "client_script_created", "name": client_script.name, "doctype": "Lead"},
				}
			return {"reply": "I need permission to create Client Script records before I can apply that change."}
		except Exception:
			frappe.log_error(frappe.get_traceback(), "AI Client Script Creation Error")
			return {"reply": "I couldn't create the Lead Client Script. Please try again or check your permissions."}

	memory = get_memory(user)

	prompt = """
		You are an AI Assistant inside ERPNext system.

		Rules:
		- Start long answers with a short summary
		- Use Markdown headings (##) for each major section or step group
		- Use bullet points or numbered lists below headings
		- Keep paragraphs short and avoid long single blocks of text
		- For ERPNext how-to questions, separate navigation, required fields, and next steps

		Use memory to answer correctly.

		Conversation history:
		"""

	for row in reversed(memory):
		prompt += f"\nUser: {row.message}"
		prompt += f"\nAssistant: {row.conversation}"

	prompt += f"\nUser: {message}\nAssistant:"

	response = model.generate_content(prompt)

	reply = response.text if response and response.text else "No response"

	try:
		save_memory(
			user=user,
			message=message,
			response=reply,
		)
	except Exception as error:
		frappe.log_error(str(error), "AI Memory Save Error")

	return {"reply": reply}
