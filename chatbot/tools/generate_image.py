import frappe
from openai import OpenAI
from chatbot.tools import Tool, ToolRegistry

client = OpenAI(api_key=frappe.conf.get("openai_api_key"))


class GenerateImageTool(Tool):
	name = "generate_image"
	description = "Generate an image using AI based on a text description. Use this when the user asks to create, draw, generate, or design an image, illustration, or visual."
	parameters = {
		"type": "object",
		"properties": {
			"prompt": {
				"type": "string",
				"description": "Detailed description of the image to generate. Be specific about style, colors, composition, and content.",
			},
			"size": {
				"type": "string",
				"enum": ["1024x1024", "1792x1024", "1024x1792"],
				"description": "Image size. Square (1024x1024), wide (1792x1024), or tall (1024x1792). Defaults to 1024x1024.",
			},
		},
		"required": ["prompt"],
	}

	def execute(self, prompt, size="1024x1024", **kwargs):
		if not frappe.conf.get("openai_api_key"):
			return {"reply": "Image generation is not configured — no OpenAI API key is set on this site."}

		try:
			response = client.images.generate(
				model="gpt-image-1",
				prompt=prompt,
				n=1,
			)

			result = response.data[0]
			image_url = result.url
			revised = getattr(result, "revised_prompt", None)

			reply = f"Here is the image I generated for **\"{prompt}\"**:"
			if revised and revised != prompt:
				reply += f"\n\n> *The AI refined your prompt to: {revised}*"

			return {
				"reply": reply,
				"action": {
					"type": "image_generated",
					"image_url": image_url,
					"prompt": prompt,
				},
			}

		except Exception as e:
			frappe.log_error(frappe.get_traceback(), "AI Image Generation Error")
			msg = str(e)
			if "billing_hard_limit_reached" in msg or "billing" in msg.lower():
				msg = "The image generation service has reached its billing limit. Please check your OpenAI account billing settings."
			elif "content_policy" in msg.lower():
				msg = "The image prompt was filtered by content policy. Please try a different description."
			return {"reply": f"I tried to generate an image but ran into an error: {msg}"}


ToolRegistry.register(GenerateImageTool())
