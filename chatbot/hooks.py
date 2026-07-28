app_name = "chatbot"
app_title = "Chatbot"
app_publisher = "Heatbot"
app_description = "Chatbot"
app_email = "test@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "chatbot",
# 		"logo": "/assets/chatbot/logo.png",
# 		"title": "Chatbot",
# 		"route": "/chatbot",
# 		"has_permission": "chatbot.api.permission.has_app_permission"
# 	}
# ]
app_include_js = ["/assets/chatbot/js/field_quick_edit.js"]

patches = [
    "chatbot.patches.add_allow_quick_edit.execute"
]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/chatbot/css/chatbot.css"
# app_include_js = "/assets/chatbot/js/chatbot.js"

# include js, css files in header of web template
# web_include_css = "/assets/chatbot/css/chatbot.css"
# web_include_js = "/assets/chatbot/js/chatbot.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "chatbot/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views



# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "chatbot/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "chatbot.utils.jinja_methods",
# 	"filters": "chatbot.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "chatbot.install.before_install"
# after_install = "chatbot.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "chatbot.uninstall.before_uninstall"
# after_uninstall = "chatbot.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "chatbot.utils.before_app_install"
# after_app_install = "chatbot.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "chatbot.utils.before_app_uninstall"
# after_app_uninstall = "chatbot.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "chatbot.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

scheduler_events = {
	"hourly": [
		"chatbot.proactive_engine.scheduled_insight_check"
	],
	"daily": [
		"chatbot.proactive_engine.scheduled_insight_check"
	],
}

# Testing
# -------

# before_tests = "chatbot.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "chatbot.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "chatbot.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["chatbot.utils.before_request"]
# after_request = ["chatbot.utils.after_request"]

# Job Events
# ----------
# before_job = ["chatbot.utils.before_job"]
# after_job = ["chatbot.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"chatbot.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Chatbot Plugin Hooks
# --------------------
# Other apps can register chatbot tools and plugins via these hooks.
#
# chatbot_tools — list of Tool subclasses to register with the chatbot
# 	Example: ["myapp.my_module.MyTool"]
# 	Your class must extend chatbot.tools.Tool and set name/description/parameters.
#
# chatbot_plugins — list of ChatbotPlugin subclasses for lifecycle hooks
# 	Example: ["myapp.my_module.MyPlugin"]
# 	Your class must extend chatbot.plugins.ChatbotPlugin and set name.
# 	Available lifecycle hooks:
# 	  - on_register()
# 	  - on_chat_before(message, document_content, image_data, image_mime_type, target_language, memory)
# 	  - on_chat_after(message, response, tool_used)
# 	  - on_tool_before(tool_name, **kwargs)
# 	  - on_tool_after(tool_name, result, **kwargs)

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []
