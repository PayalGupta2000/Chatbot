import frappe
import re
from chatbot.plugins import ChatbotPlugin, PluginRegistry


class GitHubPlugin(ChatbotPlugin):
	name = "github"
	description = "Provides GitHub integration context — repos, commits, issues, CI/CD, and code management"
	version = "1.0.0"

	_keywords = [
		"github", "git ", "repo", "repository", "commit", "push", "pull request",
		"pr ", "branch", "merge", "code review", "issue", "ci/cd", "devops",
		"deploy", "version control", "source code",
	]

	def on_chat_before(self, message, **kwargs):
		msg_lower = message.lower()
		if any(re.search(rf"\b{re.escape(kw)}\b", msg_lower) for kw in self._keywords):
			frappe.flags.chatbot_context_github = True

	def on_chat_after(self, message, response, **kwargs):
		if getattr(frappe.flags, "chatbot_context_github", False):
			tip = (
				"\n\n---\n*GitHub integration available!* I can help you connect ERPNext with GitHub — "
				"track code changes, automate deployments, link issues to customer tickets, "
				"or set up CI/CD pipelines. "
				"Try: *\"Connect my GitHub repo to track deployments\"*."
			)
			response["reply"] += tip


PluginRegistry.register(GitHubPlugin())
