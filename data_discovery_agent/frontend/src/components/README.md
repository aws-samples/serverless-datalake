# AI-Powered Widget Creation

This feature allows users to create dashboard widgets by describing what they want in natural language. The system uses the MCP (Model Context Protocol) orchestrator agent to understand the request and generate appropriate widgets.

## How It Works

1. Click the "Create with AI" button in the dashboard
2. Describe the widget you want to create (e.g., "Show me a pie chart of sales by region")
3. The agent will process your request and create an appropriate widget

## Examples of Prompts

- "Create a pie chart showing the distribution of products by category"
- "Show me a table of the top 10 customers by revenue"
- "Display monthly sales trends for the past year"
- "Create a dashboard widget showing active users by region"

## Technical Implementation

The feature uses WebSockets to communicate with the backend orchestrator agent, which:

1. Processes the natural language request
2. Determines which data sources to query
3. Retrieves the appropriate data
4. Creates a widget with the right visualization type
5. Adds the widget to the dashboard

## Benefits

- Create widgets without knowing SQL or database structure
- Get insights quickly without manual data exploration
- Leverage the power of AI to suggest appropriate visualizations