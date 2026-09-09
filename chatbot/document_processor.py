import frappe
from pathlib import Path


def parse_file(file_path: str, ext: str) -> str:
	ext = ext.lower().lstrip(".")
	if ext == "pdf":
		return _parse_pdf(file_path)
	elif ext in ("docx", "doc"):
		return _parse_docx(file_path)
	elif ext in ("xlsx", "xls"):
		return _parse_xlsx(file_path)
	elif ext == "csv":
		return _parse_csv(file_path)
	elif ext in ("pptx", "ppt"):
		return _parse_pptx(file_path)
	elif ext in ("png", "jpg", "jpeg", "gif", "bmp", "webp"):
		return _parse_image(file_path)
	else:
		raise ValueError(f"Unsupported file type: {ext}")


def _parse_pdf(file_path: str) -> str:
	from pypdf import PdfReader
	reader = PdfReader(file_path)
	parts = []
	for i, page in enumerate(reader.pages, 1):
		text = page.extract_text() or ""
		if text.strip():
			parts.append(f"--- Page {i} ---\n{text.strip()}")
	return "\n\n".join(parts) if parts else ""


def _parse_docx(file_path: str) -> str:
	from docx import Document
	doc = Document(file_path)
	parts = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
	for table in doc.tables:
		rows = [" | ".join(cell.text.strip() for cell in row.cells) for row in table.rows]
		parts.append("\n".join(rows))
	return "\n\n".join(parts)


def _parse_xlsx(file_path: str) -> str:
	from openpyxl import load_workbook
	wb = load_workbook(file_path, read_only=True, data_only=True)
	parts = []
	for sheet_name in wb.sheetnames:
		ws = wb[sheet_name]
		rows = []
		for row in ws.iter_rows(values_only=True):
			cells = [str(c) if c is not None else "" for c in row]
			line = " | ".join(cells)
			if line.strip():
				rows.append(line)
		if rows:
			parts.append(f"## Sheet: {sheet_name}\n" + "\n".join(rows))
	wb.close()
	return "\n\n".join(parts)


def _parse_csv(file_path: str) -> str:
	import csv
	with open(file_path, newline="", encoding="utf-8-sig") as f:
		reader = csv.reader(f)
		rows = [" | ".join(row) for row in reader if any(cell.strip() for cell in row)]
	return "\n".join(rows)


def _parse_pptx(file_path: str) -> str:
	from pptx import Presentation
	prs = Presentation(file_path)
	parts = []
	for i, slide in enumerate(prs.slides, 1):
		slide_text = []
		for shape in slide.shapes:
			if shape.has_text_frame:
				for para in shape.text_frame.paragraphs:
					t = para.text.strip()
					if t:
						slide_text.append(t)
			if shape.has_table:
				table = shape.table
				for row in table.rows:
					slide_text.append(" | ".join(cell.text.strip() for cell in row.cells))
		if slide_text:
			parts.append(f"--- Slide {i} ---\n" + "\n".join(slide_text))
	return "\n\n".join(parts)


def _parse_image(file_path: str) -> str:
	from PIL import Image
	try:
		img = Image.open(file_path)
		return f"[Image: {Path(file_path).name} — {img.width}x{img.height}px, mode={img.mode}]"
	except Exception:
		return f"[Image: {Path(file_path).name} — could not read image metadata]"


@frappe.whitelist()
def upload_file():
	if "file" not in frappe.request.files:
		frappe.throw("No file provided")

	frappe_file = frappe.request.files["file"]
	content = frappe_file.read()
	file_name = frappe_file.filename or "uploaded_file"
	ext = Path(file_name).suffix

	file_doc = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": file_name,
			"is_private": 1,
			"content": content,
		}
	)
	file_doc.save(ignore_permissions=True)

	try:
		text = parse_file(file_doc.get_full_path(), ext)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Document Parse Error")
		text = ""

	return {
		"name": file_doc.name,
		"file_name": file_doc.file_name,
		"file_url": file_doc.file_url,
		"file_type": ext.lstrip(".").upper(),
		"content_length": len(text),
		"preview": text[:3000] if text else "",
		"uploaded_at": str(file_doc.creation),
	}


@frappe.whitelist()
def get_document_content(file_name: str):
	file_doc = frappe.get_doc("File", file_name)
	file_doc.check_permission("read")
	ext = Path(file_doc.file_name).suffix
	text = parse_file(file_doc.get_full_path(), ext)
	return {"content": text, "file_name": file_doc.file_name, "length": len(text)}


@frappe.whitelist()
def delete_document(file_name: str):
	file_doc = frappe.get_doc("File", file_name)
	file_doc.check_permission("delete")
	try:
		frappe.delete_doc("File", file_name)
	except frappe.exceptions.QueryTimeoutError:
		# Document is locked by another user; force delete after a brief wait
		frappe.db.rollback()
		import time
		time.sleep(1)
		frappe.delete_doc("File", file_name, force=True)
	return {"success": True}


def _is_image(ext: str) -> bool:
	return ext.lower().lstrip(".") in ("png", "jpg", "jpeg", "gif", "bmp", "webp")


@frappe.whitelist()
def get_image_data(file_name: str):
	import base64
	file_doc = frappe.get_doc("File", file_name)
	file_doc.check_permission("read")
	ext = Path(file_doc.file_name).suffix
	if not _is_image(ext):
		frappe.throw("Not an image file")
	mime_map = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "gif": "image/gif", "bmp": "image/bmp", "webp": "image/webp"}
	mime = mime_map.get(ext.lower().lstrip("."), "image/png")
	with open(file_doc.get_full_path(), "rb") as f:
		b64 = base64.b64encode(f.read()).decode("utf-8")
	return {"data": b64, "mime_type": mime, "file_name": file_doc.file_name}
