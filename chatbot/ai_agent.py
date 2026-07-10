import frappe
import google.generativeai as genai

genai.configure(api_key=frappe.conf.get("gemini_api_key"))

model = genai.GenerativeModel("gemini-2.5-flash")


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

    memory = get_memory(user)

    prompt = """
        You are an AI Assistant inside ERPNext system.

        Rules:
        - Use bullet points for long explanations
        - Keep answers structured
        - Use short paragraphs
        - Avoid long single blocks of text

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
            response=reply
        )
    except Exception as e:
        frappe.log_error(str(e), "AI Memory Save Error")

    return {
        "reply": reply
    }