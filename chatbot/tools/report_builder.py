import json
import frappe
from chatbot.tools import Tool, ToolRegistry


class ReportBuilderTool(Tool):
	name = "build_report"
	description = (
		"Build a report from natural language. Generates a Report document in ERPNext "
		"with columns, filters, chart, and optional script. "
		"Use this when the user asks to 'create a report', 'build a report', "
		"'show me a report of', or needs structured data visualization."
	)
	parameters = {
		"type": "object",
		"properties": {
			"doctype": {
				"type": "string",
				"description": "The DocType to build the report on (e.g., Sales Invoice, Purchase Order, Item, Customer, Lead)",
			},
			"report_name": {
				"type": "string",
				"description": "Name for the report (e.g., 'Monthly Sales by Customer', 'Top Selling Items')",
			},
			"columns": {
				"type": "array",
				"description": "List of columns to show. Each is a fieldname from the DocType.",
				"items": {"type": "string"},
			},
			"filters": {
				"type": "string",
				"description": "JSON string of default filters as {fieldname: value} pairs",
			},
			"chart_type": {
				"type": "string",
				"enum": ["Bar", "Line", "Pie", "Percentage", "Donut"],
				"description": "Type of chart to include (optional)",
			},
			"group_by": {
				"type": "string",
				"description": "Field to group results by for aggregation",
			},
			"aggregation": {
				"type": "string",
				"enum": ["Sum", "Count", "Average", "Max", "Min"],
				"description": "Aggregation function for numeric columns",
			},
		},
		"required": ["doctype", "report_name", "columns"],
	}

	def execute(self, doctype, report_name, columns, filters=None, chart_type=None, group_by=None, aggregation=None, **kwargs):
		if not frappe.has_permission("Report", "create"):
			return {"reply": "I need permission to create Report records."}
		if not frappe.db.exists("DocType", doctype):
			return {"reply": f"DocType **{doctype}** does not exist."}

		try:
			if isinstance(columns, str):
				columns = json.loads(columns)

			parsed_filters = {}
			if filters:
				if isinstance(filters, str):
					parsed_filters = json.loads(filters)
				elif isinstance(filters, dict):
					parsed_filters = filters

			report_ref = frappe.scrub(report_name)
			if frappe.db.exists("Report", report_ref):
				return {"reply": f"A report named **{report_name}** already exists."}

			report_columns = []
			for col in columns:
				report_columns.append({"fieldname": col, "label": col.replace("_", " ").title(), "fieldtype": "Data", "width": 150})

			chart_spec = None
			if chart_type:
				chart_field = columns[-1] if len(columns) > 1 else columns[0]
				chart_spec = {
					"chart_type": chart_type,
					"field": chart_field,
					"group_by_type": "Count",
					"based_on": group_by or columns[0],
					"type": chart_type,
					"value": chart_field,
				}

			doc = frappe.get_doc({
				"doctype": "Report",
				"report_name": report_name,
				"ref_doctype": doctype,
				"report_type": "Report Builder",
				"is_standard": "No",
				"columns": report_columns,
				"filters": parsed_filters,
				"chart": chart_spec,
			})
			doc.insert(ignore_permissions=True)
			frappe.db.commit()

			parts = [f"Report **{report_name}** created for **{doctype}**."]
			parts.append(f"- Columns: {', '.join(columns)}")
			if group_by:
				parts.append(f"- Grouped by: {group_by}")
			if aggregation:
				parts.append(f"- Aggregation: {aggregation}")
			if chart_type:
				parts.append(f"- Chart: {chart_type}")
			parts.append(f"\nView at: `/app/report/{doc.name}`")

			reply = "\n".join(parts)

			return {
				"reply": reply,
				"action": {
					"type": "report_created",
					"report_name": report_name,
					"doctype": doctype,
					"report_url": f"/app/report/{doc.name}",
					"chart_type": chart_type,
				},
			}

		except Exception as e:
			frappe.log_error(frappe.get_traceback(), "Report Builder Error")
			return {"reply": f"I tried to build the report but ran into an error: {str(e)}"}


class DataExportTool(Tool):
	name = "export_data"
	description = (
		"Export ERPNext data to a downloadable file (CSV, Excel, or JSON). "
		"Use this when the user says 'export data', 'download data', "
		"'get me this data as a file', or wants structured data output."
	)
	parameters = {
		"type": "object",
		"properties": {
			"doctype": {
				"type": "string",
				"description": "The DocType to export data from (e.g., Customer, Item, Sales Invoice, Lead)",
			},
			"fields": {
				"type": "array",
				"description": "Fields to export (e.g., ['name', 'customer_name', 'email_id'])",
				"items": {"type": "string"},
			},
			"filters": {
				"type": "string",
				"description": "JSON filters to apply (e.g., {'status': 'Active'})",
			},
			"format": {
				"type": "string",
				"enum": ["CSV", "Excel", "JSON"],
				"description": "Output format",
			},
			"limit": {
				"type": "integer",
				"description": "Maximum records to export (default 1000)",
			},
		},
		"required": ["doctype", "fields"],
	}

	def execute(self, doctype, fields, filters=None, format="CSV", limit=1000, **kwargs):
		if not frappe.has_permission(doctype, "read"):
			return {"reply": f"I don't have permission to read {doctype}."}

		try:
			if isinstance(fields, str):
				fields = json.loads(fields)

			parsed_filters = {}
			if filters:
				if isinstance(filters, str):
					parsed_filters = json.loads(filters)
				elif isinstance(filters, dict):
					parsed_filters = filters

			data = frappe.get_all(doctype, fields=fields, filters=parsed_filters, limit=limit)
			total = len(data)

			if not data:
				return {"reply": f"No records found in **{doctype}** matching the given filters."}

			from frappe.utils.csvutils import to_csv
			import io, json as json_mod

			if format == "CSV":
				content = to_csv(data)
				ext = "csv"
				mime = "text/csv"
			elif format == "Excel":
				from frappe.utils.xlsxutils import make_xlsx
				xlsx = make_xlsx(data, doctype)
				content = xlsx.getvalue()
				ext = "xlsx"
				mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
			else:
				content = json_mod.dumps(data, indent=2, default=str)
				ext = "json"
				mime = "application/json"

			file_name = f"{frappe.scrub(doctype)}_export.{ext}"
			_file = frappe.get_doc({
				"doctype": "File",
				"file_name": file_name,
				"is_private": 1,
				"content": content if isinstance(content, str) else None,
			})
			if not isinstance(content, str):
				_file.content = content.decode() if isinstance(content, bytes) else str(content)
			_file.save(ignore_permissions=True)

			reply = (
				f"Exported **{total}** records from **{doctype}** as **{format}**.\n\n"
				f"- File: `{file_name}`\n"
				f"- Download: {_file.file_url}"
			)

			return {
				"reply": reply,
				"action": {
					"type": "data_exported",
					"doctype": doctype,
					"count": total,
					"format": format,
					"file_url": _file.file_url,
				},
			}

		except Exception as e:
			frappe.log_error(frappe.get_traceback(), "Data Export Error")
			return {"reply": f"Failed to export data: {str(e)}"}


ToolRegistry.register(ReportBuilderTool())
ToolRegistry.register(DataExportTool())
