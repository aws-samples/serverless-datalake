"""
Conversation History Rebuilder Utility

This utility class rebuilds conversation history from session files stored in the user_sessions directory.
It groups agents by their specialized agent name and provides the latest conversation for each.
"""

import json
import os
import pathlib
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class ConversationHistoryRebuilder:
    """
    Simplified utility class to rebuild conversation history grouped by specialized agents.
    
    This class reads session data and groups conversations by specialized agent name,
    returning only the latest conversation for each specialized agent.
    """
    
    def __init__(self, sessions_base_dir: str = None):
        """
        Initialize the conversation history rebuilder.
        
        Args:
            sessions_base_dir: Base directory for user sessions. If None, uses project default.
        """
        if sessions_base_dir is None:
            # Use project-relative path
            current_file = pathlib.Path(__file__)
            project_root = current_file.parent.parent.parent
            self.sessions_base_dir = project_root / "user_sessions"
        else:
            self.sessions_base_dir = pathlib.Path(sessions_base_dir)
            
        logger.info(f"ConversationHistoryRebuilder initialized with sessions dir: {self.sessions_base_dir}")
    
    def get_session_directory(self, session_id: str) -> pathlib.Path:
        """Get the session directory path for a given session ID."""
        return self.sessions_base_dir / f"session_{session_id}"
    
    def load_agent_info(self, session_id: str, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Load agent information from agent.json file.
        
        Args:
            session_id: The session ID
            agent_id: The agent ID
            
        Returns:
            Dictionary containing agent info or None if not found
        """
        try:
            session_dir = self.get_session_directory(session_id)
            agent_dir = session_dir / "agents" / f"agent_{agent_id}"
            agent_file = agent_dir / "agent.json"
            
            if not agent_file.exists():
                logger.warning(f"Agent file not found: {agent_file}")
                return None
                
            with open(agent_file, 'r', encoding='utf-8') as f:
                agent_data = json.load(f)
                
            return {
                "agent_id": agent_data["agent_id"],
                "specialized_agent": agent_data.get("state", {}).get("specialized_agent", "unknown"),
                "created_at": datetime.fromisoformat(agent_data["created_at"].replace('Z', '+00:00')),
                "updated_at": datetime.fromisoformat(agent_data["updated_at"].replace('Z', '+00:00')),
                "agent_dir": str(agent_dir)
            }
            
        except Exception as e:
            logger.error(f"Error loading agent info for {agent_id}: {e}")
            return None
    
    def load_agent_messages(self, session_id: str, agent_id: str) -> List[Dict[str, Any]]:
        """
        Load all messages for a specific agent.
        
        Args:
            session_id: The session ID
            agent_id: The agent ID
            
        Returns:
            List of message dictionaries in conversation format
        """
        messages = []
        
        try:
            session_dir = self.get_session_directory(session_id)
            agent_dir = session_dir / "agents" / f"agent_{agent_id}"
            messages_dir = agent_dir / "messages"
            
            if not messages_dir.exists():
                logger.warning(f"Messages directory not found: {messages_dir}")
                return messages
                
            # Get all message files and sort by message ID
            message_files = []
            for file_path in messages_dir.glob("message_*.json"):
                try:
                    # Extract message ID from filename
                    filename = file_path.name
                    message_id = int(filename.replace("message_", "").replace(".json", ""))
                    message_files.append((message_id, file_path))
                except ValueError:
                    logger.warning(f"Invalid message file format: {filename}")
                    continue
            
            # Sort by message ID to maintain chronological order
            message_files.sort(key=lambda x: x[0])
            
            # Load each message file and convert to conversation format
            for message_id, file_path in message_files:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        message_data = json.load(f)
                    
                    # Convert to simple conversation format
                    conversation_message = {
                        "role": message_data["message"]["role"],
                        "content": message_data["message"]["content"]
                    }
                    messages.append(conversation_message)
                        
                except Exception as e:
                    logger.error(f"Error loading message file {file_path}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error loading agent messages for session {session_id}, agent {agent_id}: {e}")
            
        return messages
    
    def get_specialized_agent_conversations(self, session_id: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get conversations grouped by specialized agent name.
        For each specialized agent, returns the conversation from the LATEST agent instance.
        
        Args:
            session_id: The session ID to process
            
        Returns:
            Dictionary mapping specialized agent names to their latest conversation:
            {
                "s3vectors": [
                    {"role": "user", "content": [{"text": "..."}]},
                    {"role": "assistant", "content": [{"text": "..."}]}
                ],
                "athena": [...]
            }
        """
        try:
            session_dir = self.get_session_directory(session_id)
            agents_dir = session_dir / "agents"
            
            if not agents_dir.exists():
                logger.warning(f"Agents directory not found: {agents_dir}")
                return {}
            
            # Step 1: Load all agent info and group by specialized agent
            specialized_agents = {}  # specialized_agent_name -> list of agent_info
            
            for agent_dir in agents_dir.iterdir():
                if agent_dir.is_dir() and agent_dir.name.startswith("agent_"):
                    # Extract agent ID from directory name
                    agent_id = agent_dir.name.replace("agent_", "")
                    
                    # Load agent info
                    agent_info = self.load_agent_info(session_id, agent_id)
                    if agent_info:
                        specialized_name = agent_info["specialized_agent"]
                        
                        if specialized_name not in specialized_agents:
                            specialized_agents[specialized_name] = []
                        
                        specialized_agents[specialized_name].append(agent_info)
            
            # Step 2: For each specialized agent, find the latest agent instance
            latest_agents = {}  # specialized_agent_name -> latest_agent_info
            
            for specialized_name, agent_list in specialized_agents.items():
                # Sort by updated_at to get the latest
                agent_list.sort(key=lambda x: x["updated_at"], reverse=True)
                latest_agents[specialized_name] = agent_list[0]
            
            # Step 3: Load conversations for the latest agents
            conversations = {}
            
            for specialized_name, agent_info in latest_agents.items():
                agent_id = agent_info["agent_id"]
                messages = self.load_agent_messages(session_id, agent_id)
                
                if messages:  # Only include if there are messages
                    conversations[specialized_name] = messages
                    logger.info(f"Loaded {len(messages)} messages for specialized agent '{specialized_name}' (agent {agent_id})")
            
            logger.info(f"Successfully loaded conversations for {len(conversations)} specialized agents")
            return conversations
            
        except Exception as e:
            logger.error(f"Error getting specialized agent conversations for {session_id}: {e}")
            return {}
    
    def test_specialized_conversations(self, session_id: str = "w8kmewFMPP_qoKs6AAAB_w8kmewFMPP_qoKs6AAAB") -> Dict[str, Any]:
        """
        Test method to load specialized agent conversations.
        
        Args:
            session_id: Session ID to test with
            
        Returns:
            Dictionary containing test results
        """
        print(f"\n{'='*60}")
        print(f"TESTING SPECIALIZED AGENT CONVERSATIONS")
        print(f"{'='*60}")
        print(f"Session ID: {session_id}")
        print(f"Sessions Directory: {self.sessions_base_dir}")
        
        # Check if session directory exists
        session_dir = self.get_session_directory(session_id)
        print(f"Session Directory: {session_dir}")
        print(f"Directory Exists: {session_dir.exists()}")
        
        if not session_dir.exists():
            return {
                "test_status": "FAILED",
                "error": f"Session directory does not exist: {session_dir}",
                "session_id": session_id
            }
        
        # Get specialized agent conversations
        print(f"\nLoading specialized agent conversations...")
        conversations = self.get_specialized_agent_conversations(session_id)
        
        print(conversations)
        
        print(f"\n{'='*60}")
        print(f"TEST COMPLETED SUCCESSFULLY")
        print(f"{'='*60}")
        
        return {
            "test_status": "SUCCESS",
            "session_id": session_id,
            "specialized_conversations": conversations,
            "specialized_agents": list(conversations.keys())
        }


# Convenience function for quick testing
def test_specialized_conversations(session_id: str = "w8kmewFMPP_qoKs6AAAB_w8kmewFMPP_qoKs6AAAB"):
    """
    Quick test function for specialized agent conversations.
    
    Args:
        session_id: Session ID to test with
        
    Returns:
        Test results
    """
    rebuilder = ConversationHistoryRebuilder()
    return rebuilder.test_specialized_conversations(session_id)


#if __name__ == "__main__":
    # Run test when script is executed directly
    #test_specialized_conversations('dfdsadd')