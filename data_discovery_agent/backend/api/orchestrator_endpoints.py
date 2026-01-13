"""
API endpoints for the graph-based MCP chatbot system
"""

from flask import Blueprint, request, jsonify
from datetime import datetime
import logging
import sys
import os
import asyncio

# Add the parent directory to the path to import from database module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.graph_integration import (
    process_graph_query, 
    continue_graph_plan,
    continue_graph_tool_approval,
    get_graph_info, 
    get_graph_status,
    initialize_graph_system
)

logger = logging.getLogger(__name__)

# Create Blueprint for graph-based chatbot endpoints
orchestrator_bp = Blueprint('orchestrator', __name__, url_prefix='/api/orchestrator')

@orchestrator_bp.route('/query', methods=['POST'])
def handle_graph_query():
    """
    Handle queries through the graph-based MCP chatbot system
    
    Expected JSON payload:
    {
        "query": "What databases are available in AWS Glue?",
        "user_id": "user123",  // optional
        "session_id": "session456"  // optional
    }
    """
    try:
        data = request.get_json()
        
        if not data or 'query' not in data:
            return jsonify({
                "error": "Query is required",
                "timestamp": datetime.now().isoformat()
            }), 400
        
        query = data['query'].strip()
        user_id = data.get('user_id', 'default')
        session_id = data.get('session_id', 'default')
        
        if not query:
            return jsonify({
                "error": "Query cannot be empty",
                "timestamp": datetime.now().isoformat()
            }), 400
        
        logger.info(f"Processing graph query: {query[:100]}... for user {user_id}, session {session_id}")
        
        # Process the query using the graph system
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                process_graph_query(query, user_id, session_id)
            )
        finally:
            loop.close()
        
        # Add timestamp to response
        result['timestamp'] = datetime.now().isoformat()
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error processing graph query: {e}")
        return jsonify({
            "status": "error",
            "response": f"An error occurred while processing your query: {str(e)}",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@orchestrator_bp.route('/continue-plan', methods=['POST'])
def handle_continue_plan():
    """
    Continue processing with a confirmed plan
    
    Expected JSON payload:
    {
        "plan": [{"agent_name": "athena", "query": "List databases"}],
        "original_query": "What databases are available?",
        "user_id": "user123",  // optional
        "session_id": "session456"  // optional
    }
    """
    try:
        data = request.get_json()
        
        if not data or 'plan' not in data or 'original_query' not in data:
            return jsonify({
                "error": "Plan and original_query are required",
                "timestamp": datetime.now().isoformat()
            }), 400
        
        plan = data['plan']
        original_query = data['original_query']
        user_id = data.get('user_id', 'default')
        session_id = data.get('session_id', 'default')
        
        logger.info(f"Continuing with plan for user {user_id}, session {session_id}")
        
        # Continue with the confirmed plan
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                continue_graph_plan(plan, original_query, user_id, session_id)
            )
        finally:
            loop.close()
        
        # Add timestamp to response
        result['timestamp'] = datetime.now().isoformat()
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error continuing with plan: {e}")
        return jsonify({
            "status": "error",
            "response": f"An error occurred while executing the plan: {str(e)}",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@orchestrator_bp.route('/continue-tool-approval', methods=['POST'])
def handle_continue_tool_approval():
    """
    Continue processing after tool approval
    
    Expected JSON payload:
    {
        "agent_name": "athena",
        "interrupt_ids": ["interrupt_123"],
        "approval_responses": ["approve"],
        "original_query": "List databases",  // optional
        "user_id": "user123",  // optional
        "session_id": "session456"  // optional
    }
    """
    try:
        data = request.get_json()
        
        required_fields = ['agent_name', 'interrupt_ids', 'approval_responses']
        if not data or not all(field in data for field in required_fields):
            return jsonify({
                "error": "agent_name, interrupt_ids, and approval_responses are required",
                "timestamp": datetime.now().isoformat()
            }), 400
        
        agent_name = data['agent_name']
        interrupt_ids = data['interrupt_ids']
        approval_responses = data['approval_responses']
        original_query = data.get('original_query')
        user_id = data.get('user_id', 'default')
        session_id = data.get('session_id', 'default')
        
        logger.info(f"Continuing with tool approval for agent {agent_name}, user {user_id}, session {session_id}")
        
        # Continue with tool approval
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                continue_graph_tool_approval(
                    agent_name, interrupt_ids, approval_responses, 
                    original_query, user_id, session_id
                )
            )
        finally:
            loop.close()
        
        # Add timestamp to response
        result['timestamp'] = datetime.now().isoformat()
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error continuing with tool approval: {e}")
        return jsonify({
            "status": "error",
            "response": f"An error occurred while processing tool approval: {str(e)}",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

logger = logging.getLogger(__name__)

@orchestrator_bp.route('/info', methods=['GET'])
def get_system_info():
    """Get information about the graph-based chatbot system"""
    try:
        info = get_graph_info()
        info['timestamp'] = datetime.now().isoformat()
        return jsonify(info)
        
    except Exception as e:
        logger.error(f"Error getting graph system info: {e}")
        return jsonify({
            "error": "Failed to get system information",
            "details": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@orchestrator_bp.route('/status', methods=['GET'])
def get_system_status():
    """Get connection status of the graph-based system"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            status = loop.run_until_complete(get_graph_status())
        finally:
            loop.close()
            
        status['timestamp'] = datetime.now().isoformat()
        return jsonify(status)
        
    except Exception as e:
        logger.error(f"Error getting graph system status: {e}")
        return jsonify({
            "error": "Failed to get system status",
            "details": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@orchestrator_bp.route('/agents', methods=['GET'])
def get_agents_info():
    """Get detailed information about available MCP agents"""
    try:
        info = get_graph_info()
        agents = info.get('available_agents', [])
        
        return jsonify({
            "agents": agents,
            "count": len(agents),
            "system_type": info.get('system_type', 'unknown'),
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting agents info: {e}")
        return jsonify({
            "error": "Failed to get agents information",
            "details": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@orchestrator_bp.route('/test', methods=['POST'])
def test_graph_system():
    """
    Test endpoint for the graph-based chatbot system
    
    Expected JSON payload:
    {
        "test_case": "athena_query"  // optional, runs all tests if not specified
    }
    """
    try:
        data = request.get_json() or {}
        test_case = data.get('test_case')
        
        # Define test cases for data discovery
        test_cases = {
            "athena_query": {
                "query": "List all databases in AWS Athena",
                "expected_agents": ["athena"],
                "description": "Simple Athena database listing"
            },
            "glue_tables": {
                "query": "Show me tables in the default database in AWS Glue",
                "expected_agents": ["glue"],
                "description": "Glue table discovery"
            },
            "s3_analysis": {
                "query": "Analyze S3 buckets for data processing usage",
                "expected_agents": ["s3"],
                "description": "S3 bucket analysis"
            },
            "multi_service": {
                "query": "List databases in Athena and tables in Glue, then summarize the findings",
                "expected_agents": ["athena", "glue"],
                "description": "Multi-service data discovery"
            }
        }
        
        # Run specific test case or all test cases
        if test_case:
            if test_case not in test_cases:
                return jsonify({
                    "error": f"Unknown test case: {test_case}",
                    "available_tests": list(test_cases.keys()),
                    "timestamp": datetime.now().isoformat()
                }), 400
            
            test_to_run = {test_case: test_cases[test_case]}
        else:
            test_to_run = test_cases
        
        results = {}
        
        for name, test_config in test_to_run.items():
            logger.info(f"Running test case: {name}")
            
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(
                        process_graph_query(test_config['query'])
                    )
                finally:
                    loop.close()
                
                test_result = {
                    "status": result['status'],
                    "query": test_config['query'],
                    "description": test_config['description'],
                    "response": result['response'][:200] + "..." if len(result['response']) > 200 else result['response'],
                    "expected_agents": test_config['expected_agents'],
                    "type": result.get('type', 'unknown')
                }
                
                results[name] = test_result
                
            except Exception as e:
                logger.error(f"Error in test case {name}: {e}")
                results[name] = {
                    "status": "error",
                    "query": test_config['query'],
                    "description": test_config['description'],
                    "error": str(e),
                    "expected_agents": test_config['expected_agents'],
                    "type": "error"
                }
        
        # Calculate summary statistics
        total_tests = len(results)
        successful_tests = sum(1 for r in results.values() if r['status'] == 'success')
        
        return jsonify({
            "test_results": results,
            "summary": {
                "total_tests": total_tests,
                "successful_tests": successful_tests,
                "failed_tests": total_tests - successful_tests,
                "success_rate": f"{(successful_tests/total_tests)*100:.1f}%" if total_tests > 0 else "0%"
            },
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error running graph system tests: {e}")
        return jsonify({
            "error": "Failed to run tests",
            "details": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@orchestrator_bp.route('/health', methods=['GET'])
def graph_health():
    """Health check for the graph-based chatbot system"""
    try:
        # Try to get system info to verify everything is working
        info = get_graph_info()
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            status = loop.run_until_complete(get_graph_status())
        finally:
            loop.close()
        
        return jsonify({
            "status": "healthy" if info['status'] == 'initialized' else "unhealthy",
            "system_available": info['initialized'],
            "agents_count": info.get('agent_count', 0),
            "connected_clients": status.get('connected_clients', 0),
            "total_clients": status.get('total_clients', 0),
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Graph system health check failed: {e}")
        return jsonify({
            "status": "unhealthy",
            "system_available": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

# Error handlers for the blueprint
@orchestrator_bp.errorhandler(404)
def not_found(error):
    return jsonify({
        "error": "Endpoint not found",
        "available_endpoints": [
            "/api/orchestrator/query",
            "/api/orchestrator/continue-plan",
            "/api/orchestrator/continue-tool-approval",
            "/api/orchestrator/info", 
            "/api/orchestrator/status",
            "/api/orchestrator/agents",
            "/api/orchestrator/test",
            "/api/orchestrator/health"
        ],
        "timestamp": datetime.now().isoformat()
    }), 404

@orchestrator_bp.errorhandler(500)
def internal_error(error):
    return jsonify({
        "error": "Internal server error",
        "details": str(error),
        "timestamp": datetime.now().isoformat()
    }), 500