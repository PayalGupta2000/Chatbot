import frappe
from frappe.utils import flt
from chatbot.tools import Tool, ToolRegistry

CURRENCY_NAMES = {
	"USD": "US Dollar", "EUR": "Euro", "GBP": "British Pound", "INR": "Indian Rupee",
	"AUD": "Australian Dollar", "CAD": "Canadian Dollar", "JPY": "Japanese Yen",
	"CNY": "Chinese Yuan", "AED": "UAE Dirham", "SAR": "Saudi Riyal", "SGD": "Singapore Dollar",
	"MYR": "Malaysian Ringgit", "THB": "Thai Baht", "PHP": "Philippine Peso", "NZD": "New Zealand Dollar",
	"CHF": "Swiss Franc", "SEK": "Swedish Krona", "NOK": "Norwegian Krone", "DKK": "Danish Krone",
	"ZAR": "South African Rand", "BRL": "Brazilian Real", "MXN": "Mexican Peso", "HKD": "Hong Kong Dollar",
	"KRW": "South Korean Won", "IDR": "Indonesian Rupiah", "LKR": "Sri Lankan Rupee",
	"BDT": "Bangladeshi Taka", "PKR": "Pakistani Rupee", "NPR": "Nepalese Rupee",
}


class CurrencyConverterTool(Tool):
	name = "convert_currency"
	description = (
		"Convert an amount from one currency to another using the Currency Exchange rates "
		"configured in the system. Use this when the user says 'how much is X in USD', "
		"'convert 5000 EUR to INR', or asks about exchange rates."
	)
	parameters = {
		"type": "object",
		"properties": {
			"amount": {
				"type": "number",
				"description": "The amount to convert",
			},
			"from_currency": {
				"type": "string",
				"description": "ISO currency code to convert from (e.g., USD, EUR, INR)",
			},
			"to_currency": {
				"type": "string",
				"description": "ISO currency code to convert to (e.g., USD, EUR, INR)",
			},
			"date": {
				"type": "string",
				"description": "Optional rate date (YYYY-MM-DD). Defaults to the latest available rate",
			},
		},
		"required": ["amount", "from_currency", "to_currency"],
	}

	def execute(self, amount, from_currency, to_currency, date=None, **kwargs):
		from_currency = (from_currency or "").strip().upper()
		to_currency = (to_currency or "").strip().upper()

		if not from_currency or not to_currency:
			return {"reply": "I need both a source and a target currency code (e.g., USD, EUR, INR)."}

		if from_currency == to_currency:
			return {
				"reply": f"**{flt(amount, 2)} {from_currency}** is the same currency, so no conversion needed — it stays **{flt(amount, 2)} {to_currency}**."
			}

		try:
			amount = flt(amount)
			filters = {"from_currency": from_currency, "to_currency": to_currency}
			if date:
				filters["date"] = ("<=", date)

			rate = frappe.db.get_value(
				"Currency Exchange",
				filters,
				"exchange_rate",
				order_by="date desc",
			)

			if not rate:
				return {
					"reply": (
						f"I couldn't find a configured exchange rate from **{from_currency}** to **{to_currency}**. "
						f"Please add one under **Accounts > Currency Exchange**, or try a different pair."
					)
				}

			converted = flt(amount * flt(rate), 2)
			from_name = CURRENCY_NAMES.get(from_currency, "")
			to_name = CURRENCY_NAMES.get(to_currency, "")

			reply = (
				f"**{flt(amount, 2)} {from_currency}** ({from_name}) = "
				f"**{converted:,.2f} {to_currency}** ({to_name})\n\n"
				f"- Rate used: 1 {from_currency} = {flt(rate, 4)} {to_currency}\n"
				f"- Based on the configured Currency Exchange record."
			)
			return {
				"reply": reply,
				"data": {
					"columns": ["from", "to", "amount", "rate", "converted"],
					"rows": [[from_currency, to_currency, flt(amount, 2), flt(rate, 4), converted]],
					"total_rows": 1,
				},
			}

		except Exception as e:
			frappe.log_error(frappe.get_traceback(), "Currency Converter Tool Error")
			return {"reply": f"I ran into an error converting currencies: {str(e)}"}


ToolRegistry.register(CurrencyConverterTool())
