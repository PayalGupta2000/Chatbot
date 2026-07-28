import frappe
from frappe.model.meta import get_meta


@frappe.whitelist()
def get_all_doctypes(include_singles=False):
	doctypes = frappe.get_all("DocType", pluck="name", order_by="name asc")
	if include_singles:
		singles = frappe.get_all("Singles", pluck="doctype", distinct=True)
		doctypes = list(set(doctypes + singles))
	return sorted(doctypes)


@frappe.whitelist()
def get_doctype_info(doctype: str):
	meta = get_meta(doctype)
	if not meta:
		return {}
	fields = []
	for df in meta.fields:
		fields.append({
			"fieldname": df.fieldname,
			"label": df.label or df.fieldname,
			"fieldtype": df.fieldtype,
			"reqd": bool(df.reqd),
			"unique": bool(df.unique),
			"options": df.options,
			"default": df.default,
			"idx": df.idx,
		})
	table_fields = [f for f in fields if f["fieldtype"] in ("Table", "Table MultiSelect")]
	return {
		"name": meta.name,
		"module": meta.module,
		"fields": fields,
		"table_fields": table_fields,
		"is_submittable": bool(meta.is_submittable),
		"is_child": bool(meta.istable),
		"track_changes": bool(meta.track_changes),
		"track_views": bool(meta.track_views),
		"has_workflow": bool(meta.workflow),
	}


@frappe.whitelist()
def search_doctypes(query: str):
	all_dt = frappe.get_all("DocType", pluck="name", order_by="name asc")
	query = query.lower()
	matches = []
	for dt in all_dt:
		if query in dt.lower():
			matches.append(dt)
	meta_matches = frappe.db.sql("""
		SELECT DISTINCT dt.name
		FROM tabDocField df
		JOIN tabDocType dt ON dt.name = df.parent
		WHERE LOWER(df.label) LIKE %s OR LOWER(df.fieldname) LIKE %s
		LIMIT 20
	""", (f"%{query}%", f"%{query}%"))
	for (dt_name,) in meta_matches:
		if dt_name not in matches:
			matches.append(dt_name)
	return matches[:20]


@frappe.whitelist()
def get_field_options(doctype: str, fieldname: str):
	meta = get_meta(doctype)
	df = meta.get_field(fieldname)
	if not df:
		return []
	if df.fieldtype == "Select" and df.options:
		return [o.strip() for o in df.options.split("\n") if o.strip()]
	return []


@frappe.whitelist()
def get_related_doctypes(doctype: str):
	meta = get_meta(doctype)
	relations = []
	for df in meta.fields:
		if df.fieldtype == "Link":
			relations.append({"type": "link", "field": df.fieldname, "target": df.options})
		elif df.fieldtype == "Table":
			relations.append({"type": "table", "field": df.fieldname, "child": df.options})
		elif df.fieldtype in ("Dynamic Link", "Dynamic Table"):
			relations.append({"type": "dynamic", "field": df.fieldname, "options_field": df.options})
	return relations


@frappe.whitelist()
def find_doctype_by_label(label: str):
	results = frappe.db.sql("""
		SELECT DISTINCT parent
		FROM tabDocField
		WHERE label = %s OR fieldname = %s
		LIMIT 5
	""", (label, label))
	return [r[0] for r in results]


@frappe.whitelist()
def get_business_modules():
	modules = frappe.get_all("Module Def", pluck="name", order_by="name asc")
	mod_doctypes = {}
	for mod in modules:
		dts = frappe.get_all("DocType", filters={"module": mod}, pluck="name", limit=5)
		if dts:
			mod_doctypes[mod] = dts
	return mod_doctypes


@frappe.whitelist()
def get_schema_context_for_llm(doctype: str) -> str:
	meta = get_meta(doctype)
	if not meta:
		return ""
	fields_str = []
	for df in meta.fields:
		if df.fieldtype in ("Section Break", "Column Break", "Tab Break", "HTML", "Fold"):
			continue
		parts = [f"{df.fieldname} ({df.fieldtype})"]
		if df.label:
			parts.insert(0, f"{df.label}:")
		if df.reqd:
			parts.append("[REQUIRED]")
		if df.options:
			parts.append(f"options={df.options}")
		fields_str.append(" ".join(parts))
	return f"DocType: {doctype}\nModule: {meta.module}\nFields:\n" + "\n".join(fields_str[:100])
