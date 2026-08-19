import ast
import operator
import frappe
from frappe.utils import flt
from chatbot.tools import Tool, ToolRegistry

_OPERATORS = {
	ast.Add: operator.add,
	ast.Sub: operator.sub,
	ast.Mult: operator.mul,
	ast.Div: operator.truediv,
	ast.FloorDiv: operator.floordiv,
	ast.Mod: operator.mod,
	ast.Pow: operator.pow,
	ast.USub: operator.neg,
	ast.UAdd: operator.pos,
}

_CONSTANTS = {
	"pi": 3.141592653589793,
	"e": 2.718281828459045,
}


def _eval_node(node):
	if isinstance(node, ast.Expression):
		return _eval_node(node.body)
	if isinstance(node, ast.Constant):
		if isinstance(node.value, (int, float, complex)):
			return node.value
		raise ValueError("Only numeric values are supported")
	if isinstance(node, ast.BinOp):
		return _OPERATORS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
	if isinstance(node, ast.UnaryOp):
		return _OPERATORS[type(node.op)](_eval_node(node.operand))
	if isinstance(node, ast.Name) and node.id in _CONSTANTS:
		return _CONSTANTS[node.id]
	raise ValueError(f"Unsupported expression part: {type(node).__name__}")


class CalculatorTool(Tool):
	name = "calculate"
	description = (
		"Perform a safe arithmetic calculation. Use this when the user asks for a calculation, "
		"e.g., 'compute 250 * 12 + 500', 'how much is 3^4', or '(120+80)/4'."
		"Supports + - * / // % ** and parentheses, plus the constants pi and e."
	)
	parameters = {
		"type": "object",
		"properties": {
			"expression": {
				"type": "string",
				"description": "The arithmetic expression to evaluate, e.g., '250 * 12 + 500' or '(120 + 80) / 4'",
			},
			"precision": {
				"type": "integer",
				"description": "Number of decimal places for the result (default 2)",
			},
		},
		"required": ["expression"],
	}

	def execute(self, expression, precision=2, **kwargs):
		expression = (expression or "").strip()
		if not expression:
			return {"reply": "I need an expression to calculate."}

		normalized = expression.replace("×", "*").replace("÷", "/").replace("^", "**")

		try:
			tree = ast.parse(normalized, mode="eval")
			result = _eval_node(tree)
			if isinstance(result, complex):
				return {"reply": f"The result of **{expression}** is **{result.real:,.{precision}f}**."}

			formatted = f"{result:,.{precision}f}"
			reply = f"The result of **{expression}** is **{formatted}**."
			return {
				"reply": reply,
				"data": {
					"columns": ["expression", "result"],
					"rows": [[expression, result]],
					"total_rows": 1,
				},
			}
		except ZeroDivisionError:
			return {"reply": f"I can't calculate **{expression}** because it divides by zero."}
		except (SyntaxError, ValueError, TypeError, KeyError, OverflowError) as e:
			return {
				"reply": f"I couldn't understand the expression **{expression}** as math ({str(e)}). "
				"Please use numbers and operators like + - * / ( ) ^."
			}
		except Exception as e:
			frappe.log_error(frappe.get_traceback(), "Calculator Tool Error")
			return {"reply": f"I ran into an error calculating **{expression}**: {str(e)}"}


ToolRegistry.register(CalculatorTool())
