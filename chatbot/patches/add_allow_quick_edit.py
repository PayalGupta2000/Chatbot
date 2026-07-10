import frappe

def execute():
    if not frappe.db.exists("DocField", {"fieldname": "allow_quick_edit"}):
        frappe.get_doc({
            "doctype": "DocField",
            "dt": "DocField",
            "fieldname": "allow_quick_edit",
            "label": "Allow Quick Edit",
            "fieldtype": "Check",
            "insert_after": "read_only",
            "default": 0
        }).insert(ignore_permissions=True)