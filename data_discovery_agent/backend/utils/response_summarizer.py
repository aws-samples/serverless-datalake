"""
Response Summarization Utility

This module provides a reusable class for creating and managing Strands agents
that specialize in summarizing responses and generating business analysis reports.
"""

import logging
import uuid
from typing import Optional, Dict, Any
from strands import Agent
from strands.models import BedrockModel
import time

logger = logging.getLogger(__name__)


class ResponseSummarizer:
    """
    A utility class that provides response summarization capabilities using Strands agents.
    
    This class creates and manages specialized agents for:
    - General response summarization
    - Business analysis report generation
    - HTML report creation
    - Data analysis and insights
    """
    
    def __init__(self, model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"):
        """
        Initialize the ResponseSummarizer.
        
        Args:
            model_id: The model ID to use for the summarization agent
        """
        self.model_id = model_id
        self._agent = None
        
        logger.info(f"ResponseSummarizer initialized with model: {model_id}")
    
    @property
    def agent(self) -> Agent:
        """
        Lazy-loaded Strands agent for summarization tasks.
        
        Returns:
            Agent: Configured Strands agent for summarization
        """
        if self._agent is None:
            self._create_agent()
        return self._agent
    
    def _create_agent(self):
        """Create the summarization agent with proper configuration."""
        try:
            # Create model
            model = BedrockModel(model_id=self.model_id)
            
            # Create agent
            self._agent = Agent(
                model=model,
                agent_id=str(uuid.uuid4())
            )
            
            logger.info("Summarization agent created successfully")
            
        except Exception as e:
            logger.error(f"Error creating summarization agent: {e}")
            raise e
    
    def summarize_responses(self, responses: str, context: str = "") -> str:
        """
        Summarize a collection of responses with optional context.
        
        Args:
            responses: The responses to summarize
            context: Optional context to help with summarization
            
        Returns:
            str: Summarized content
        """
        prompt = f"""
        You are an expert at summarizing technical responses and data analysis results.
        
        **Task**: Provide a clear, concise summary of the following responses.
        
        **Context**: {context if context else "General response summarization"}
        
        **Responses to Summarize**:
        {responses}
        
        **Requirements**:
        1. Extract key findings and insights
        2. Highlight important data points
        3. Identify patterns or trends
        4. Provide actionable takeaways
        5. Keep the summary concise but comprehensive
        
        **Output**: Provide a well-structured markdown summary that captures the essence of the responses.
        """
        
        try:
            result = self.agent(prompt)
            return str(result)
        except Exception as e:
            logger.error(f"Error summarizing responses: {e}")
            return f"Error during summarization: {str(e)}"
    
    def generate_business_analysis_report(self, data: str, user_query: str) -> str:
        """
        Generate a comprehensive business analysis report in HTML format.
        
        Args:
            data: The data to analyze
            user_query: The original user query for context
            
        Returns:
            str: HTML formatted business analysis report
        """
        prompt = f"""
        You are a business analyst whose role is to provide actionable insights and recommendations based on data analysis.
        
        **YOUR TASK**: Analyze the following data and provide a clear, actionable summary: {data}
        
        **ORIGINAL USER QUERY**: {user_query}
        
        **OUTPUT REQUIREMENTS**:
        1. **Executive Summary**: Provide a concise overview of key findings.
        2. **Key Insights**: Extract the most important data points and what they mean for the business
        3. **Actionable Recommendations**: Specific steps the business can take based on the data
        4. **Risk Assessment**: Identify any concerning trends or issues that need attention
        
        **OUTPUT FORMAT**: Complete HTML document with the following specifications:
        
        **HTML STRUCTURE REQUIREMENTS**:
        - Complete HTML5 document with DOCTYPE, head, and body tags
        - Responsive design that works on desktop and mobile
        - Professional header with "Powered by AWS" small font positioned on the top-left
        - Clean, modern footer with contact information
        - Main content area with proper sections for each requirement
        
        **STYLING REQUIREMENTS**:
        - Use inline CSS or internal stylesheet (no external dependencies)
        - Color scheme: AWS orange (#FF9900) and dark blue (#232F3E) as primary colors
        - Clean, professional typography (Arial, Helvetica, or system fonts)
        - Proper spacing, margins, and padding for readability
        - Card-based layout for different sections
        - Responsive grid system for content organization
        
        **CHART/VISUALIZATION REQUIREMENTS**:
        - Include at least 2-3 data visualizations using Chart.js or similar library
        - Charts should be: bar charts for comparisons, line charts for trends, pie charts for distributions
        - Use CDN links for chart libraries
        - Ensure charts are responsive and mobile-friendly
        - Include proper labels, legends, and tooltips
        
        **CONTENT STRUCTURE**:
        1. Header with "Powered by AWS" small font and suitable report title based on report content
        2. Executive Summary section
        3. Key Findings with data visualizations
        4. Business Impact analysis
        5. Immediate Action Items (prioritized list)
        6. Risk Mitigation section
        7. Footer with metadata
        
        **STRICT GUIDELINES**:
        - DO NOT ask follow-up questions - work with the data provided
        - DO NOT request additional context - analyze what you have
        - FOCUS on actionable insights that can be implemented immediately
        - Be specific and direct in your recommendations
        - Quantify impact where possible using the available data
        - Prioritize recommendations by urgency or business impact
        - Generate complete, valid HTML that can be saved and opened in any browser
        - Include sample data in charts if actual data visualization is not possible from provided data
        
        Provide ONLY the complete HTML code - no explanatory text before or after.
        """
        
        try:
            result = self.agent(prompt)
            return str(result)
        except Exception as e:
            logger.error(f"Error generating business analysis report: {e}")
            return f"<html><body><h1>Error</h1><p>Error generating report: {str(e)}</p></body></html>"
    
    def analyze_data_insights(self, data: str, focus_area: str = "") -> str:
        """
        Analyze data and extract key insights with optional focus area.
        
        Args:
            data: The data to analyze
            focus_area: Optional area to focus the analysis on
            
        Returns:
            str: Analysis with key insights and recommendations
        """
        prompt = f"""
        You are a data analyst specializing in extracting actionable insights from complex data.
        
        **Task**: Analyze the following data and provide key insights.
        
        **Focus Area**: {focus_area if focus_area else "General data analysis"}
        
        **Data to Analyze**:
        {data}
        
        **Requirements**:
        1. **Data Overview**: Brief summary of what the data represents
        2. **Key Patterns**: Identify significant patterns, trends, or anomalies
        3. **Statistical Insights**: Highlight important metrics and their implications
        4. **Business Impact**: Explain what these insights mean for business decisions
        5. **Recommendations**: Provide specific, actionable recommendations
        6. **Next Steps**: Suggest follow-up analysis or actions
        
        **Output Format**: Structured analysis with clear sections and bullet points for easy reading.
        """
        
        try:
            result = self.agent(prompt)
            return str(result)
        except Exception as e:
            logger.error(f"Error analyzing data insights: {e}")
            return f"Error during data analysis: {str(e)}"
    
    def create_executive_summary(self, detailed_content: str, target_audience: str = "executives") -> str:
        """
        Create an executive summary from detailed content.
        
        Args:
            detailed_content: The detailed content to summarize
            target_audience: The target audience for the summary
            
        Returns:
            str: Executive summary tailored to the target audience
        """
        prompt = f"""
        You are an expert at creating executive summaries for {target_audience}.
        
        **Task**: Create a concise executive summary from the following detailed content.
        
        **Target Audience**: {target_audience}
        
        **Detailed Content**:
        {detailed_content}
        
        **Requirements**:
        1. **Length**: Keep it concise (2-3 paragraphs maximum)
        2. **Focus**: Highlight the most critical information
        3. **Clarity**: Use clear, jargon-free language appropriate for {target_audience}
        4. **Action-Oriented**: Include key decisions or actions needed
        5. **Impact**: Emphasize business impact and implications
        
        **Output**: A well-structured executive summary that captures the essence and key decisions needed.
        """
        
        try:
            result = self.agent(prompt)
            return str(result)
        except Exception as e:
            logger.error(f"Error creating executive summary: {e}")
            return f"Error creating executive summary: {str(e)}"
    

# Convenience functions for quick access
def create_summarizer(model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0") -> ResponseSummarizer:
    """
    Create a new ResponseSummarizer instance.
    
    Args:
        model_id: The model ID to use
        
    Returns:
        ResponseSummarizer: Configured summarizer instance
    """
    return ResponseSummarizer(model_id=model_id)


def quick_summarize(content: str, context: str = "", 
                   model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0") -> str:
    """
    Quick summarization function for one-off tasks.
    
    Args:
        content: Content to summarize
        context: Optional context
        model_id: Model ID to use
        
    Returns:
        str: Summarized content
    """
    summarizer = create_summarizer(model_id=model_id)
    try:
        return summarizer.summarize_responses(content, context)
    finally:
        logger.info(f"Summarized with model_id {model_id}")