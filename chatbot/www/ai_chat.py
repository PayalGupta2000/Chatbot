no_cache = 1


def get_context(context):
    import frappe

    context.csrf_token = frappe.sessions.get_csrf_token()
    context.companies = frappe.get_all(
        "Customer",
        fields=["name"],
        order_by="name asc",
        ignore_permissions=True,
    )