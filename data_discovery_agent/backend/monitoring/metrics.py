"""
Monitoring and metrics collection for the MCP Chatbot system.
"""
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import threading
from pathlib import Path

@dataclass
class QueryMetrics:
    """Metrics for a single query."""
    query_id: str
    user_id: str
    session_id: str
    query_text: str
    start_time: datetime
    end_time: Optional[datetime] = None
    success: bool = False
    error_message: str = ""
    agents_used: List[str] = None
    iterations: int = 0
    total_tokens: int = 0
    response_time_ms: int = 0
    
    def __post_init__(self):
        if self.agents_used is None:
            self.agents_used = []
    
    def complete(self, success: bool, error_message: str = ""):
        """Mark query as complete."""
        self.end_time = datetime.now()
        self.success = success
        self.error_message = error_message
        if self.start_time and self.end_time:
            self.response_time_ms = int((self.end_time - self.start_time).total_seconds() * 1000)

@dataclass
class AgentMetrics:
    """Metrics for agent performance."""
    agent_name: str
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    avg_response_time_ms: float = 0.0
    total_response_time_ms: int = 0
    last_used: Optional[datetime] = None
    error_types: Dict[str, int] = None
    
    def __post_init__(self):
        if self.error_types is None:
            self.error_types = defaultdict(int)
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_calls == 0:
            return 0.0
        return (self.successful_calls / self.total_calls) * 100
    
    def add_call(self, success: bool, response_time_ms: int, error_type: str = ""):
        """Add a call to metrics."""
        self.total_calls += 1
        self.total_response_time_ms += response_time_ms
        self.last_used = datetime.now()
        
        if success:
            self.successful_calls += 1
        else:
            self.failed_calls += 1
            if error_type:
                self.error_types[error_type] += 1
        
        # Update average response time
        self.avg_response_time_ms = self.total_response_time_ms / self.total_calls

class MetricsCollector:
    """Collects and manages system metrics."""
    
    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        self.query_history: deque = deque(maxlen=max_history)
        self.agent_metrics: Dict[str, AgentMetrics] = {}
        self.system_metrics = {
            "total_queries": 0,
            "successful_queries": 0,
            "failed_queries": 0,
            "avg_query_time_ms": 0.0,
            "peak_concurrent_queries": 0,
            "current_concurrent_queries": 0
        }
        self._lock = threading.Lock()
        self._active_queries: Dict[str, QueryMetrics] = {}
    
    def start_query(self, query_id: str, user_id: str, session_id: str, query_text: str) -> QueryMetrics:
        """Start tracking a new query."""
        with self._lock:
            query_metrics = QueryMetrics(
                query_id=query_id,
                user_id=user_id,
                session_id=session_id,
                query_text=query_text,
                start_time=datetime.now()
            )
            
            self._active_queries[query_id] = query_metrics
            self.system_metrics["current_concurrent_queries"] = len(self._active_queries)
            
            # Update peak concurrent queries
            if self.system_metrics["current_concurrent_queries"] > self.system_metrics["peak_concurrent_queries"]:
                self.system_metrics["peak_concurrent_queries"] = self.system_metrics["current_concurrent_queries"]
            
            return query_metrics
    
    def complete_query(self, query_id: str, success: bool, error_message: str = "", agents_used: List[str] = None):
        """Complete query tracking."""
        with self._lock:
            if query_id not in self._active_queries:
                return
            
            query_metrics = self._active_queries.pop(query_id)
            query_metrics.complete(success, error_message)
            
            if agents_used:
                query_metrics.agents_used = agents_used
            
            # Add to history
            self.query_history.append(query_metrics)
            
            # Update system metrics
            self.system_metrics["total_queries"] += 1
            self.system_metrics["current_concurrent_queries"] = len(self._active_queries)
            
            if success:
                self.system_metrics["successful_queries"] += 1
            else:
                self.system_metrics["failed_queries"] += 1
            
            # Update average query time
            total_time = sum(q.response_time_ms for q in self.query_history if q.response_time_ms > 0)
            query_count = len([q for q in self.query_history if q.response_time_ms > 0])
            if query_count > 0:
                self.system_metrics["avg_query_time_ms"] = total_time / query_count
    
    def record_agent_call(self, agent_name: str, success: bool, response_time_ms: int, error_type: str = ""):
        """Record an agent call."""
        with self._lock:
            if agent_name not in self.agent_metrics:
                self.agent_metrics[agent_name] = AgentMetrics(agent_name=agent_name)
            
            self.agent_metrics[agent_name].add_call(success, response_time_ms, error_type)
    
    def get_system_summary(self) -> Dict[str, Any]:
        """Get system-wide metrics summary."""
        with self._lock:
            recent_queries = list(self.query_history)[-100:]  # Last 100 queries
            
            # Calculate success rate
            if self.system_metrics["total_queries"] > 0:
                success_rate = (self.system_metrics["successful_queries"] / self.system_metrics["total_queries"]) * 100
            else:
                success_rate = 0.0
            
            # Calculate recent performance
            recent_success_count = sum(1 for q in recent_queries if q.success)
            recent_success_rate = (recent_success_count / len(recent_queries) * 100) if recent_queries else 0.0
            
            return {
                "system_metrics": {
                    **self.system_metrics,
                    "success_rate": success_rate,
                    "recent_success_rate": recent_success_rate
                },
                "agent_summary": {
                    name: {
                        "success_rate": metrics.success_rate,
                        "total_calls": metrics.total_calls,
                        "avg_response_time_ms": metrics.avg_response_time_ms,
                        "last_used": metrics.last_used.isoformat() if metrics.last_used else None
                    }
                    for name, metrics in self.agent_metrics.items()
                },
                "recent_queries": len(recent_queries),
                "active_queries": len(self._active_queries)
            }
    
    def get_agent_details(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed metrics for a specific agent."""
        with self._lock:
            if agent_name not in self.agent_metrics:
                return None
            
            metrics = self.agent_metrics[agent_name]
            return {
                "agent_name": agent_name,
                "success_rate": metrics.success_rate,
                "total_calls": metrics.total_calls,
                "successful_calls": metrics.successful_calls,
                "failed_calls": metrics.failed_calls,
                "avg_response_time_ms": metrics.avg_response_time_ms,
                "last_used": metrics.last_used.isoformat() if metrics.last_used else None,
                "error_types": dict(metrics.error_types)
            }
    
    def get_query_history(self, limit: int = 50, user_id: str = None) -> List[Dict[str, Any]]:
        """Get query history with optional filtering."""
        with self._lock:
            queries = list(self.query_history)
            
            # Filter by user if specified
            if user_id:
                queries = [q for q in queries if q.user_id == user_id]
            
            # Sort by start time (most recent first)
            queries.sort(key=lambda x: x.start_time, reverse=True)
            
            # Limit results
            queries = queries[:limit]
            
            return [
                {
                    "query_id": q.query_id,
                    "user_id": q.user_id,
                    "session_id": q.session_id,
                    "query_text": q.query_text[:100] + "..." if len(q.query_text) > 100 else q.query_text,
                    "start_time": q.start_time.isoformat(),
                    "end_time": q.end_time.isoformat() if q.end_time else None,
                    "success": q.success,
                    "response_time_ms": q.response_time_ms,
                    "agents_used": q.agents_used,
                    "iterations": q.iterations
                }
                for q in queries
            ]
    
    def export_metrics(self, filepath: str):
        """Export metrics to JSON file."""
        with self._lock:
            data = {
                "export_time": datetime.now().isoformat(),
                "system_summary": self.get_system_summary(),
                "query_history": self.get_query_history(limit=1000),
                "agent_details": {
                    name: self.get_agent_details(name)
                    for name in self.agent_metrics.keys()
                }
            }
            
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2, default=str)
    
    def get_performance_trends(self, hours: int = 24) -> Dict[str, Any]:
        """Get performance trends over specified time period."""
        with self._lock:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            recent_queries = [
                q for q in self.query_history 
                if q.start_time >= cutoff_time and q.end_time is not None
            ]
            
            if not recent_queries:
                return {"message": "No data available for the specified time period"}
            
            # Group by hour
            hourly_stats = defaultdict(lambda: {"total": 0, "successful": 0, "avg_time": 0, "times": []})
            
            for query in recent_queries:
                hour_key = query.start_time.strftime("%Y-%m-%d %H:00")
                hourly_stats[hour_key]["total"] += 1
                if query.success:
                    hourly_stats[hour_key]["successful"] += 1
                hourly_stats[hour_key]["times"].append(query.response_time_ms)
            
            # Calculate averages
            for hour_data in hourly_stats.values():
                if hour_data["times"]:
                    hour_data["avg_time"] = sum(hour_data["times"]) / len(hour_data["times"])
                hour_data["success_rate"] = (hour_data["successful"] / hour_data["total"]) * 100
                del hour_data["times"]  # Remove raw times from output
            
            return {
                "time_period_hours": hours,
                "total_queries": len(recent_queries),
                "hourly_breakdown": dict(hourly_stats),
                "overall_success_rate": (sum(1 for q in recent_queries if q.success) / len(recent_queries)) * 100,
                "avg_response_time": sum(q.response_time_ms for q in recent_queries) / len(recent_queries)
            }

# Global metrics collector instance
metrics_collector = MetricsCollector()

# Decorator for automatic metrics collection
def track_agent_call(agent_name: str):
    """Decorator to automatically track agent calls."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            success = False
            error_type = ""
            
            try:
                result = await func(*args, **kwargs)
                success = True
                return result
            except Exception as e:
                error_type = type(e).__name__
                raise
            finally:
                response_time_ms = int((time.time() - start_time) * 1000)
                metrics_collector.record_agent_call(agent_name, success, response_time_ms, error_type)
        
        return wrapper
    return decorator

# Context manager for query tracking
class QueryTracker:
    """Context manager for tracking query metrics."""
    
    def __init__(self, query_id: str, user_id: str, session_id: str, query_text: str):
        self.query_id = query_id
        self.user_id = user_id
        self.session_id = session_id
        self.query_text = query_text
        self.agents_used = []
    
    def __enter__(self):
        metrics_collector.start_query(self.query_id, self.user_id, self.session_id, self.query_text)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        success = exc_type is None
        error_message = str(exc_val) if exc_val else ""
        metrics_collector.complete_query(self.query_id, success, error_message, self.agents_used)
    
    def add_agent(self, agent_name: str):
        """Add an agent to the list of agents used."""
        if agent_name not in self.agents_used:
            self.agents_used.append(agent_name)