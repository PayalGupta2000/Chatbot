import json
import frappe
from chatbot.tools import Tool, ToolRegistry


class DataQueryTool(Tool):
	name = "query_data"
	description = (
		"Query ERPNext data in real-time using natural language. "
		"Returns structured data with optional chart configuration. "
		"Use this when the user asks 'how many', 'show me', 'list', "
		"'get data', 'what is the total', 'find records', or any data question."
	)
	parameters = {
		"type": "object",
		"properties": {
			"doctype": {
				"type": "string",
				"description": "The DocType to query (e.g., Sales Invoice, Customer, Item, Purchase Order, Lead, Opportunity)",
			},
			"fields": {
				"type": "array",
				"description": "Fields to return (e.g., ['name', 'customer', 'grand_total', 'posting_date'])",
				"items": {"type": "string"},
			},
			"filters": {
				"type": "string",
				"description": "JSON filter object (e.g., {'docstatus': 1, 'company': 'My Company'})",
			},
			"group_by": {
				"type": "string",
				"description": "Field to group results by for aggregation",
			},
			"aggregate_field": {
				"type": "string",
				"description": "Numeric field to aggregate (sum, count, average)",
			},
			"aggregate_function": {
				"type": "string",
				"enum": ["sum", "count", "avg", "max", "min"],
				"description": "Aggregation function",
			},
			"order_by": {
				"type": "string",
				"description": "Sort field and direction (e.g., 'creation desc')",
			},
			"limit": {
				"type": "integer",
				"description": "Maximum records to return (max 200)",
			},
		},
		"required": ["doctype", "fields"],
	}

	def execute(self, doctype, fields, filters=None, group_by=None, aggregate_field=None, aggregate_function=None, order_by=None, limit=50, **kwargs):
		if not frappe.has_permission(doctype, "read"):
			return {"reply": f"I don't have permission to read **{doctype}**."}

		try:
			if isinstance(fields, str):
				fields = json.loads(fields)
			parsed_filters = {}
			if filters:
				parsed_filters = json.loads(filters) if isinstance(filters, str) else filters

			limit = min(int(limit), 200)

			if group_by and aggregate_field and aggregate_function:
				query_fields = [f"`tab{doctype}`.`{group_by}`"]
				agg_op = {"sum": "SUM", "count": "COUNT", "avg": "AVG", "max": "MAX", "min": "MIN"}
				op = agg_op.get(aggregate_function, "SUM")
				query_fields.append(f"{op}(`tab{doctype}`.`{aggregate_field}`) as {aggregate_function}_{aggregate_field}")
				query_fields.extend([f"`tab{doctype}`.`{f}`" for f in fields if f != group_by])

				sql = f"SELECT {', '.join(query_fields)} FROM `tab{doctype}`"
				where_clauses = []
				params = []
				for key, val in parsed_filters.items():
					where_clauses.append(f"`tab{doctype}`.`{key}` = %s")
					params.append(val)
				if where_clauses:
					sql += " WHERE " + " AND ".join(where_clauses)
				sql += f" GROUP BY `{group_by}`"
				if order_by:
					sql += f" ORDER BY {order_by}"
				sql += f" LIMIT {limit}"

				data = frappe.db.sql(sql, params, as_dict=True)
				total_rows = len(data)

				chart_labels = [row.get(group_by, "") for row in data]
				chart_values = [row.get(f"{aggregate_function}_{aggregate_field}", 0) for row in data]

				chart = {
					"type": "bar" if len(data) < 15 else "line",
					"title": f"{aggregate_function.upper()} of {aggregate_field} by {group_by}",
					"labels": chart_labels[:20],
					"datasets": [{"label": f"{aggregate_function.title()} {aggregate_field}", "values": chart_values[:20]}],
				}
			else:
				data = frappe.get_all(doctype, fields=fields, filters=parsed_filters, order_by=order_by or "creation desc", limit=limit)
				total_rows = len(data)
				chart = None

			if not data:
				return {"reply": f"No **{doctype}** records match the given criteria."}

			numeric_fields = [f for f in fields if f in ("grand_total", "total", "amount", "net_total", "base_grand_total", "rate", "qty", "price")]

			lines = [f"Found **{total_rows}** **{doctype}** records."]
			if total_rows > 10:
				lines.append(f"Showing top **{min(total_rows, limit)}** results.")

			if numeric_fields and total_rows <= 20:
				for row in data[:10]:
					parts = []
					for f in fields[:5]:
						val = row.get(f, "")
						if val:
							parts.append(f"{f.replace('_', ' ').title()}: {val}")
					lines.append("• " + " | ".join(parts))

			reply = "\n".join(lines)

			result = {
				"reply": reply,
				"data": {
					"columns": [{"fieldname": f, "label": f.replace("_", " ").title(), "fieldtype": "Data"} for f in fields],
					"rows": data[:50],
					"total_rows": total_rows,
				},
			}

			if chart:
				result["chart"] = chart
				result["action"] = {
					"type": "data_chart",
					"chart_type": chart["type"],
					"title": chart["title"],
				}

			if not chart and numeric_fields and total_rows > 1:
				result["action"] = {
					"type": "data_queried",
					"doctype": doctype,
					"count": total_rows,
				}

			return result

		except Exception as e:
			frappe.log_error(frappe.get_traceback(), "Data Query Error")
			return {"reply": f"I tried to query **{doctype}** data: {str(e)}"}


ToolRegistry.register(DataQueryTool())
