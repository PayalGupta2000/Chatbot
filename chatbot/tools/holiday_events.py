import frappe
from frappe.utils import add_days, date_diff, getdate
from chatbot.tools import Tool, ToolRegistry


def _get_company_holiday_list():
	company = frappe.defaults.get_global_default("company") or frappe.defaults.get_user_default("Company")
	if company:
		hl = frappe.db.get_value("Company", company, "default_holiday_list")
		if hl:
			return hl

	employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, ["name", "holiday_list"])
	if employee:
		return employee[1]

	hl = frappe.db.get_value("Holiday List", None, "name", order_by="creation desc")
	return hl


class CompanyHolidaysTool(Tool):
	name = "company_holidays"
	description = (
		"List upcoming public holidays from the company's Holiday List. "
		"Use this when the user says 'upcoming holidays', 'holiday list', 'which days are holidays', "
		"or 'when is the next holiday'."
	)
	parameters = {
		"type": "object",
		"properties": {
			"days": {
				"type": "integer",
				"description": "How many days ahead to look for holidays (default 90)",
			},
			"limit": {
				"type": "integer",
				"description": "Max holidays to return (default 10)",
			},
		},
	}

	def execute(self, days=90, limit=10, **kwargs):
		try:
			holiday_list = _get_company_holiday_list()
			if not holiday_list:
				return {"reply": "No default company or Holiday List found. Please set a default company in System Settings."}

			today = getdate()
			end_date = add_days(today, days)

			holidays = frappe.get_all(
				"Holiday",
				filters={
					"parent": holiday_list,
					"holiday_date": ["between", [today, end_date]],
				},
				fields=["holiday_date", "description", "weekly_off"],
				order_by="holiday_date asc",
				limit=limit,
			)

			if not holidays:
				return {"reply": f"No upcoming holidays in the next **{days}** days for **{holiday_list}**."}

			rows = []
			for h in holidays:
				d = getdate(h["holiday_date"])
				days_away = date_diff(d, today)
				label = "Today!" if days_away == 0 else (f"in {days_away} day{'s' if days_away > 1 else ''}" if days_away > 0 else "past")
				desc = h.get("description") or ("Weekly off" if h.get("weekly_off") else "Holiday")
				rows.append([d.strftime("%Y-%m-%d"), desc, label, h["holiday_date"]])

			lines = [f"- **{r[0]}** — {r[1]} ({r[2]})" for r in rows]
			reply = f"Upcoming holidays from **{holiday_list}**:\n\n" + "\n".join(lines)

			return {
				"reply": reply,
				"data": {
					"columns": ["date", "holiday", "when"],
					"rows": [[r[0], r[1], r[2]] for r in rows],
					"total_rows": len(rows),
				},
			}

		except Exception as e:
			frappe.log_error(frappe.get_traceback(), "Company Holidays Tool Error")
			return {"reply": f"I ran into an error fetching holidays: {str(e)}"}


class TodayEventsTool(Tool):
	name = "today_events"
	description = (
		"Show today's and upcoming calendar events and reminders. "
		"Use this when the user says 'what's on my calendar', 'today's events', "
		"'my schedule', 'upcoming meetings', or 'what's happening this week'."
	)
	parameters = {
		"type": "object",
		"properties": {
			"days": {
				"type": "integer",
				"description": "How many days ahead to include (default 7)",
			},
			"limit": {
				"type": "integer",
				"description": "Max events to return (default 10)",
			},
		},
	}

	def execute(self, days=7, limit=10, **kwargs):
		try:
			today = getdate()
			end_date = add_days(today, days)

			events = frappe.get_all(
				"Event",
				filters=[
					["status", "=", "Open"],
					["starts_on", ">=", f"{today} 00:00:00"],
					["starts_on", "<=", f"{end_date} 23:59:59"],
				],
				fields=["subject", "starts_on", "event_category", "event_type"],
				order_by="starts_on asc",
				limit=limit,
			)

			if not events:
				return {"reply": f"No upcoming events in the next **{days}** days on your calendar."}

			rows = []
			for e in events:
				starts = e["starts_on"]
				date_part = str(starts)[:10]
				time_part = str(starts)[11:16] if len(str(starts)) > 10 else ""
				when = "Today" if date_part == str(today) else f"in {date_diff(getdate(date_part), today)} day(s)"
				rows.append([date_part, time_part, e["subject"], when, e.get("event_type", "")])

			lines = [f"- **{r[0]}**{f' {r[1]}' if r[1] else ''} — {r[2]} ({r[3]})" for r in rows]
			reply = f"Upcoming events:\n\n" + "\n".join(lines)

			return {
				"reply": reply,
				"data": {
					"columns": ["date", "time", "subject", "when"],
					"rows": [[r[0], r[1], r[2], r[3]] for r in rows],
					"total_rows": len(rows),
				},
			}

		except Exception as e:
			frappe.log_error(frappe.get_traceback(), "Today Events Tool Error")
			return {"reply": f"I ran into an error fetching your events: {str(e)}"}


ToolRegistry.register(CompanyHolidaysTool())
ToolRegistry.register(TodayEventsTool())
