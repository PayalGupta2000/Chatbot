import json

import frappe
from chatbot.tools import Tool, ToolRegistry


class ImportDataTool(Tool):
	name = "import_data"
	description = (
		"Import records into a DocType from an Excel or CSV file. "
		"Use this when the user says 'import this excel', 'import data', "
		"'upload and import', or provides a file to import into ERPNext."
	)
	parameters = {
		"type": "object",
		"properties": {
			"doctype": {
				"type": "string",
				"description": (
					"Target DocType to import into (e.g., Customer, Item, Lead, "
					"Sales Invoice, Purchase Order, Contact, Address)"
				),
			},
			"file_path": {
				"type": "string",
				"description": (
					"Full server path to the CSV or Excel file. "
					"If the user mentions an attached file, use the file URL from /files/."
				),
			},
			"import_type": {
				"type": "string",
				"enum": ["Insert New Records", "Update Existing Records"],
				"description": "Insert new records or update existing ones based on matching field",
			},
		},
		"required": ["doctype", "file_path"],
	}

	def execute(self, doctype, file_path, import_type="Insert New Records", **kwargs):
		if not frappe.has_permission(doctype, "create"):
			return {"reply": f"I don't have permission to create records in {doctype}."}

		if not frappe.has_permission("Data Import", "create"):
			return {"reply": "I need Data Import permission to run imports."}

		try:
			from frappe.core.doctype.data_import.importer import Importer

			data_import = frappe.new_doc("Data Import")
			data_import.submit_after_import = 0
			data_import.import_type = import_type
			data_import.reference_doctype = doctype
			data_import.insert()
			frappe.db.commit()

			i = Importer(
				doctype=doctype,
				file_path=file_path,
				data_import=data_import,
				console=False,
			)
			i.import_data()

			frappe.db.commit()

			logs = frappe.get_all(
				"Data Import Log",
				filters={"data_import": data_import.name},
				fields=["success"],
			)
			success = sum(1 for log in logs if log.success)
			failed = sum(1 for log in logs if not log.success)
			total = len(logs)

			if success and not failed:
				reply = (
					f"Successfully imported **{success}** records into **{doctype}**. "
					f"All {total} rows were processed without errors."
				)
			elif success and failed:
				reply = (
					f"Imported **{success}** records into **{doctype}**. "
					f"**{failed}** rows had errors — check the Data Import log for details."
				)
			else:
				reply = (
					f"The import completed but no records were imported into **{doctype}**. "
					"Please verify the file format and column headers match the DocType fields."
				)

			return {
				"reply": reply,
				"action": {
					"type": "data_imported",
					"doctype": doctype,
					"success": success,
					"failed": failed,
				},
			}

		except Exception:
			frappe.log_error(frappe.get_traceback(), "AI Data Import Error")
			return {
				"reply": (
					f"I tried to import into **{doctype}** but ran into an error. "
					"Please check that the file exists at the specified path "
					"and the column headers match the fields of the DocType."
				),
			}


ToolRegistry.register(ImportDataTool())
