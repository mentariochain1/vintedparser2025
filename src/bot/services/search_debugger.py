"""Search debugging and logging infrastructure."""

import time
import uuid
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum

from monitoring import get_logger, StructuredLogger
from config import settings


class SearchStage(Enum):
    """Search operation stages for tracking."""
    INITIATED = "initiated"
    VALIDATED = "validated"
    PREMIUM_CHECKED = "premium_checked"
    VINTED_SEARCH = "vinted_search"
    ITEM_DETAILS = "item_details"
    RESULT_FORMATTING = "result_formatting"
    RESULT_SENDING = "result_sending"
    COMPLETED = "completed"
    FAILED = "failed"


class SearchErrorType(Enum):
    """Types of search errors for categorization."""
    VALIDATION_ERROR = "validation_error"
    PREMIUM_EXPIRED = "premium_expired"
    VINTED_API_ERROR = "vinted_api_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    NETWORK_ERROR = "network_error"
    FORMATTING_ERROR = "formatting_error"
    STATE_ERROR = "state_error"
    CALLBACK_ERROR = "callback_error"
    IMAGE_ERROR = "image_error"
    DATABASE_ERROR = "database_error"


@dataclass
class SearchContext:
    """Search operation context for debugging."""
    correlation_id: str
    user_id: int
    query: str
    item_count: int
    chat_id: int
    message_id: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    current_stage: SearchStage = SearchStage.INITIATED
    stages_completed: List[str] = None
    api_calls: List[Dict[str, Any]] = None
    errors: List[Dict[str, Any]] = None
    metrics: Dict[str, Any] = None

    def __post_init__(self):
        if self.stages_completed is None:
            self.stages_completed = []
        if self.api_calls is None:
            self.api_calls = []
        if self.errors is None:
            self.errors = []
        if self.metrics is None:
            self.metrics = {}
        if self.started_at is None:
            self.started_at = datetime.utcnow()


@dataclass
class SearchError:
    """Search error information for debugging."""
    error_type: SearchErrorType
    message: str
    stage: SearchStage
    timestamp: datetime
    details: Dict[str, Any]
    correlation_id: str
    user_id: Optional[int] = None
    query: Optional[str] = None
    traceback: Optional[str] = None


@dataclass
class APICallInfo:
    """API call information for debugging."""
    service: str
    endpoint: str
    method: str
    params: Dict[str, Any]
    response_status: Optional[int] = None
    response_time: Optional[float] = None
    error: Optional[str] = None
    timestamp: datetime = None
    correlation_id: str = ""

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


class SearchDebugger:
    """Comprehensive debugging utilities for search functionality."""

    def __init__(self):
        self.logger: StructuredLogger = get_logger(__name__)
        self._active_searches: Dict[str, SearchContext] = {}
        self._search_history: List[SearchContext] = []
        self._max_history_size = 1000

    def create_correlation_id(self) -> str:
        """Generate a unique correlation ID for tracking."""
        return str(uuid.uuid4())[:12]

    def start_search_debug(
        self,
        user_id: int,
        query: str,
        item_count: int,
        chat_id: int,
        message_id: Optional[int] = None
    ) -> str:
        """Start debugging a search operation."""
        correlation_id = self.create_correlation_id()
        
        context = SearchContext(
            correlation_id=correlation_id,
            user_id=user_id,
            query=query,
            item_count=item_count,
            chat_id=chat_id,
            message_id=message_id,
            started_at=datetime.utcnow()
        )
        
        self._active_searches[correlation_id] = context
        
        self.logger.info(
            "Search operation started",
            correlation_id=correlation_id,
            user_id=user_id,
            query=query,
            item_count=item_count,
            chat_id=chat_id,
            stage=SearchStage.INITIATED.value
        )
        
        return correlation_id

    def log_stage_completion(
        self,
        correlation_id: str,
        stage: SearchStage,
        duration_ms: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log completion of a search stage."""
        context = self._active_searches.get(correlation_id)
        if not context:
            self.logger.warning(
                "Attempted to log stage for unknown correlation ID",
                correlation_id=correlation_id,
                stage=stage.value
            )
            return

        context.current_stage = stage
        context.stages_completed.append(stage.value)
        
        if duration_ms:
            context.metrics[f"{stage.value}_duration_ms"] = duration_ms

        log_details = {
            "correlation_id": correlation_id,
            "user_id": context.user_id,
            "query": context.query,
            "stage": stage.value,
            "stage_count": len(context.stages_completed)
        }
        
        if duration_ms:
            log_details["duration_ms"] = duration_ms
        
        if details:
            log_details.update(details)

        self.logger.info(f"Search stage completed: {stage.value}", **log_details)

    def log_api_call(
        self,
        correlation_id: str,
        service: str,
        endpoint: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        response_status: Optional[int] = None,
        response_time: Optional[float] = None,
        error: Optional[str] = None
    ) -> None:
        """Log an API call with detailed information."""
        context = self._active_searches.get(correlation_id)
        
        api_call = APICallInfo(
            service=service,
            endpoint=endpoint,
            method=method,
            params=params or {},
            response_status=response_status,
            response_time=response_time,
            error=error,
            correlation_id=correlation_id
        )
        
        if context:
            context.api_calls.append(asdict(api_call))

        log_details = {
            "correlation_id": correlation_id,
            "service": service,
            "endpoint": endpoint,
            "method": method,
            "response_status": response_status,
        }
        
        if response_time:
            log_details["response_time_ms"] = round(response_time * 1000, 2)
        
        if error:
            log_details["error"] = error
            self.logger.error(f"API call failed: {service}{endpoint}", **log_details)
        else:
            self.logger.info(f"API call completed: {service}{endpoint}", **log_details)

    def log_search_error(
        self,
        correlation_id: str,
        error_type: SearchErrorType,
        message: str,
        stage: SearchStage,
        details: Optional[Dict[str, Any]] = None,
        exception: Optional[Exception] = None
    ) -> None:
        """Log a search error with full context."""
        context = self._active_searches.get(correlation_id)
        
        error_info = SearchError(
            error_type=error_type,
            message=message,
            stage=stage,
            timestamp=datetime.utcnow(),
            details=details or {},
            correlation_id=correlation_id,
            user_id=context.user_id if context else None,
            query=context.query if context else None,
            traceback=str(exception) if exception else None
        )
        
        if context:
            context.errors.append(asdict(error_info))

        log_details = {
            "correlation_id": correlation_id,
            "error_type": error_type.value,
            "stage": stage.value,
        }
        
        if context:
            log_details.update({
                "user_id": context.user_id,
                "query": context.query
            })
        
        if details:
            log_details.update(details)
        
        if exception:
            log_details["exception_type"] = type(exception).__name__

        self.logger.error(f"Search error: {error_type.value}", **log_details)

    def complete_search_debug(
        self,
        correlation_id: str,
        success: bool = True,
        final_stage: Optional[SearchStage] = None,
        results_count: Optional[int] = None
    ) -> Optional[SearchContext]:
        """Complete search debugging and move to history."""
        context = self._active_searches.get(correlation_id)
        if not context:
            self.logger.warning(
                "Attempted to complete unknown search",
                correlation_id=correlation_id
            )
            return None

        context.completed_at = datetime.utcnow()
        context.current_stage = final_stage or (SearchStage.COMPLETED if success else SearchStage.FAILED)
        
        # Calculate total duration
        if context.started_at and context.completed_at:
            total_duration = (context.completed_at - context.started_at).total_seconds()
            context.metrics["total_duration_ms"] = round(total_duration * 1000, 2)

        if results_count is not None:
            context.metrics["results_count"] = results_count

        log_details = {
            "correlation_id": correlation_id,
            "user_id": context.user_id,
            "query": context.query,
            "success": success,
            "final_stage": context.current_stage.value,
            "stages_completed": len(context.stages_completed),
            "api_calls_made": len(context.api_calls),
            "errors_encountered": len(context.errors)
        }
        
        if context.metrics.get("total_duration_ms"):
            log_details["total_duration_ms"] = context.metrics["total_duration_ms"]
        
        if results_count is not None:
            log_details["results_count"] = results_count

        self.logger.info(f"Search operation completed", **log_details)

        # Move to history
        self._search_history.append(context)
        if len(self._search_history) > self._max_history_size:
            self._search_history = self._search_history[-self._max_history_size:]

        # Remove from active searches
        del self._active_searches[correlation_id]
        
        return context

    def get_search_context(self, correlation_id: str) -> Optional[SearchContext]:
        """Get current search context."""
        return self._active_searches.get(correlation_id)

    def get_active_searches(self) -> Dict[str, SearchContext]:
        """Get all active search contexts."""
        return self._active_searches.copy()

    def get_search_history(self, limit: int = 100) -> List[SearchContext]:
        """Get recent search history."""
        return self._search_history[-limit:]

    def get_search_statistics(self) -> Dict[str, Any]:
        """Get search operation statistics."""
        active_count = len(self._active_searches)
        history_count = len(self._search_history)
        
        # Analyze recent searches
        recent_searches = self._search_history[-100:]
        
        success_count = sum(1 for s in recent_searches if s.current_stage == SearchStage.COMPLETED)
        error_count = sum(1 for s in recent_searches if s.current_stage == SearchStage.FAILED)
        
        # Calculate average duration
        completed_searches = [s for s in recent_searches if s.metrics.get("total_duration_ms")]
        avg_duration = 0
        if completed_searches:
            avg_duration = sum(s.metrics["total_duration_ms"] for s in completed_searches) / len(completed_searches)

        # Count error types
        error_types = {}
        for search in recent_searches:
            for error in search.errors:
                error_type = error.get("error_type", "unknown")
                error_types[error_type] = error_types.get(error_type, 0) + 1

        return {
            "active_searches": active_count,
            "total_history": history_count,
            "recent_success_rate": round(success_count / max(len(recent_searches), 1) * 100, 2),
            "recent_searches": len(recent_searches),
            "recent_successes": success_count,
            "recent_errors": error_count,
            "average_duration_ms": round(avg_duration, 2),
            "error_types": error_types,
            "timestamp": datetime.utcnow().isoformat()
        }

    async def health_check_search_flow(self) -> Dict[str, Any]:
        """Perform comprehensive health check of search flow."""
        health_status = {
            "status": "healthy",
            "checks": {},
            "timestamp": datetime.utcnow().isoformat()
        }

        # Check active searches
        active_searches = len(self._active_searches)
        health_status["checks"]["active_searches"] = {
            "status": "healthy" if active_searches < 50 else "warning",
            "count": active_searches,
            "threshold": 50
        }

        # Check for stuck searches (running > 10 minutes)
        stuck_searches = 0
        current_time = datetime.utcnow()
        for context in self._active_searches.values():
            if context.started_at:
                duration = (current_time - context.started_at).total_seconds()
                if duration > 600:  # 10 minutes
                    stuck_searches += 1

        health_status["checks"]["stuck_searches"] = {
            "status": "healthy" if stuck_searches == 0 else "unhealthy",
            "count": stuck_searches,
            "threshold": 0
        }

        # Check recent error rate
        recent_searches = self._search_history[-50:]
        if recent_searches:
            error_rate = sum(1 for s in recent_searches if s.errors) / len(recent_searches)
            health_status["checks"]["error_rate"] = {
                "status": "healthy" if error_rate < 0.1 else "warning" if error_rate < 0.3 else "unhealthy",
                "rate": round(error_rate * 100, 2),
                "threshold_warning": 10,
                "threshold_critical": 30
            }
        else:
            health_status["checks"]["error_rate"] = {
                "status": "unknown",
                "rate": 0,
                "message": "No recent searches to analyze"
            }

        # Overall status
        check_statuses = [check["status"] for check in health_status["checks"].values()]
        if "unhealthy" in check_statuses:
            health_status["status"] = "unhealthy"
        elif "warning" in check_statuses:
            health_status["status"] = "warning"

        return health_status

    def export_search_debug_data(self, correlation_id: str) -> Optional[Dict[str, Any]]:
        """Export complete debug data for a search operation."""
        context = self._active_searches.get(correlation_id)
        if not context:
            # Check history
            for historical_context in reversed(self._search_history):
                if historical_context.correlation_id == correlation_id:
                    context = historical_context
                    break
        
        if not context:
            return None

        return {
            "correlation_id": context.correlation_id,
            "user_id": context.user_id,
            "query": context.query,
            "item_count": context.item_count,
            "chat_id": context.chat_id,
            "message_id": context.message_id,
            "started_at": context.started_at.isoformat() if context.started_at else None,
            "completed_at": context.completed_at.isoformat() if context.completed_at else None,
            "current_stage": context.current_stage.value,
            "stages_completed": context.stages_completed,
            "api_calls": context.api_calls,
            "errors": context.errors,
            "metrics": context.metrics,
            "is_active": correlation_id in self._active_searches
        }


# Global search debugger instance
search_debugger = SearchDebugger()