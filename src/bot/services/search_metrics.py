"""Search metrics collection and analysis."""

import time
from datetime import datetime, timedelta, date
from typing import Dict, Any, List, Optional
from collections import defaultdict, deque
from threading import Lock
from dataclasses import dataclass

from prometheus_client import Counter, Histogram, Gauge
from monitoring import get_logger


# Prometheus metrics for search operations
SEARCH_OPERATIONS_TOTAL = Counter(
    'search_operations_total',
    'Total search operations',
    ['stage', 'status', 'user_type']
)

SEARCH_DURATION = Histogram(
    'search_duration_seconds',
    'Search operation duration in seconds',
    ['stage', 'status']
)

SEARCH_RESULTS_COUNT = Histogram(
    'search_results_count',
    'Number of results returned by search',
    ['query_type']
)

SEARCH_ACTIVE_OPERATIONS = Gauge(
    'search_active_operations',
    'Number of currently active search operations'
)

SEARCH_CALLBACK_OPERATIONS_TOTAL = Counter(
    'search_callback_operations_total',
    'Total search callback operations',
    ['callback_type', 'status']
)

SEARCH_API_CALLS_TOTAL = Counter(
    'search_api_calls_total',
    'Total API calls made during search',
    ['service', 'endpoint', 'status']
)

SEARCH_ERRORS_TOTAL = Counter(
    'search_errors_total',
    'Total search errors',
    ['error_type', 'stage']
)

SEARCH_USER_SESSIONS = Gauge(
    'search_user_sessions_active',
    'Number of active user search sessions'
)


@dataclass
class SearchMetric:
    """Individual search operation metric."""
    correlation_id: str
    user_id: int
    query: str
    item_count: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    stage: str = "initiated"
    status: str = "active"
    results_count: Optional[int] = None
    api_calls_count: int = 0
    errors_count: int = 0
    duration_ms: Optional[float] = None
    user_type: str = "regular"  # regular, premium, trial


@dataclass
class StageMetric:
    """Metrics for a specific search stage."""
    stage_name: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_ms: Optional[float] = None
    status: str = "active"
    details: Dict[str, Any] = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}


class SearchMetrics:
    """Comprehensive metrics collection for search operations."""

    def __init__(self):
        self.logger = get_logger(__name__)
        self._metrics_lock = Lock()
        
        # Active search operations
        self._active_searches: Dict[str, SearchMetric] = {}
        
        # Stage metrics for active searches
        self._stage_metrics: Dict[str, List[StageMetric]] = defaultdict(list)
        
        # Recent completed searches (last 1000)
        self._recent_searches: deque = deque(maxlen=1000)
        
        # User session tracking
        self._user_sessions: Dict[int, datetime] = {}
        
        # Performance metrics
        self._performance_metrics = {
            'hourly_counts': defaultdict(int),
            'error_rates': defaultdict(float),
            'avg_durations': defaultdict(float),
            'success_rates': defaultdict(float)
        }

    def start_search_operation(
        self,
        correlation_id: str,
        user_id: int,
        query: str,
        item_count: int,
        user_type: str = "regular"
    ) -> None:
        """Start tracking a search operation."""
        with self._metrics_lock:
            metric = SearchMetric(
                correlation_id=correlation_id,
                user_id=user_id,
                query=query,
                item_count=item_count,
                started_at=datetime.utcnow(),
                user_type=user_type
            )
            
            self._active_searches[correlation_id] = metric
            self._user_sessions[user_id] = datetime.utcnow()
            
            # Update Prometheus metrics
            SEARCH_OPERATIONS_TOTAL.labels(
                stage="initiated",
                status="started",
                user_type=user_type
            ).inc()
            
            SEARCH_ACTIVE_OPERATIONS.set(len(self._active_searches))
            SEARCH_USER_SESSIONS.set(len(self._user_sessions))

        self.logger.info(
            "Search operation started",
            correlation_id=correlation_id,
            user_id=user_id,
            query=query,
            item_count=item_count,
            user_type=user_type
        )

    def record_stage_start(
        self,
        correlation_id: str,
        stage_name: str,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record the start of a search stage."""
        with self._metrics_lock:
            stage_metric = StageMetric(
                stage_name=stage_name,
                started_at=datetime.utcnow(),
                details=details or {}
            )
            
            self._stage_metrics[correlation_id].append(stage_metric)
            
            # Update active search stage
            if correlation_id in self._active_searches:
                self._active_searches[correlation_id].stage = stage_name

        self.logger.debug(
            f"Search stage started: {stage_name}",
            correlation_id=correlation_id,
            stage=stage_name
        )

    def record_stage_completion(
        self,
        correlation_id: str,
        stage_name: str,
        status: str = "success",
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record the completion of a search stage."""
        with self._metrics_lock:
            # Find the most recent stage metric for this stage
            stage_metrics = self._stage_metrics.get(correlation_id, [])
            stage_metric = None
            
            for metric in reversed(stage_metrics):
                if metric.stage_name == stage_name and metric.completed_at is None:
                    stage_metric = metric
                    break
            
            if stage_metric:
                stage_metric.completed_at = datetime.utcnow()
                stage_metric.status = status
                if details:
                    stage_metric.details.update(details)
                
                # Calculate duration
                duration = (stage_metric.completed_at - stage_metric.started_at).total_seconds()
                stage_metric.duration_ms = duration * 1000
                
                # Update Prometheus metrics
                user_type = "regular"
                if correlation_id in self._active_searches:
                    user_type = self._active_searches[correlation_id].user_type
                
                SEARCH_OPERATIONS_TOTAL.labels(
                    stage=stage_name,
                    status=status,
                    user_type=user_type
                ).inc()
                
                SEARCH_DURATION.labels(
                    stage=stage_name,
                    status=status
                ).observe(duration)

        self.logger.info(
            f"Search stage completed: {stage_name}",
            correlation_id=correlation_id,
            stage=stage_name,
            status=status,
            duration_ms=stage_metric.duration_ms if stage_metric else None
        )

    def record_api_call(
        self,
        correlation_id: str,
        service: str,
        endpoint: str,
        status: str = "success"
    ) -> None:
        """Record an API call made during search."""
        with self._metrics_lock:
            if correlation_id in self._active_searches:
                self._active_searches[correlation_id].api_calls_count += 1
            
            # Update Prometheus metrics
            SEARCH_API_CALLS_TOTAL.labels(
                service=service,
                endpoint=endpoint,
                status=status
            ).inc()

        self.logger.debug(
            f"Search API call recorded: {service}{endpoint}",
            correlation_id=correlation_id,
            service=service,
            endpoint=endpoint,
            status=status
        )

    def record_search_error(
        self,
        correlation_id: str,
        error_type: str,
        stage: str = "unknown"
    ) -> None:
        """Record a search error."""
        with self._metrics_lock:
            if correlation_id in self._active_searches:
                self._active_searches[correlation_id].errors_count += 1
            
            # Update Prometheus metrics
            SEARCH_ERRORS_TOTAL.labels(
                error_type=error_type,
                stage=stage
            ).inc()

        self.logger.warning(
            f"Search error recorded: {error_type}",
            correlation_id=correlation_id,
            error_type=error_type,
            stage=stage
        )

    def record_callback_operation(
        self,
        callback_type: str,
        status: str = "success"
    ) -> None:
        """Record a search-related callback operation."""
        SEARCH_CALLBACK_OPERATIONS_TOTAL.labels(
            callback_type=callback_type,
            status=status
        ).inc()

        self.logger.debug(
            f"Search callback recorded: {callback_type}",
            callback_type=callback_type,
            status=status
        )

    def complete_search_operation(
        self,
        correlation_id: str,
        status: str = "success",
        results_count: Optional[int] = None
    ) -> Optional[SearchMetric]:
        """Complete a search operation and move to history."""
        with self._metrics_lock:
            if correlation_id not in self._active_searches:
                self.logger.warning(
                    "Attempted to complete unknown search operation",
                    correlation_id=correlation_id
                )
                return None
            
            metric = self._active_searches[correlation_id]
            metric.completed_at = datetime.utcnow()
            metric.status = status
            metric.results_count = results_count
            
            # Calculate total duration
            if metric.started_at and metric.completed_at:
                duration = (metric.completed_at - metric.started_at).total_seconds()
                metric.duration_ms = duration * 1000
                
                # Update Prometheus metrics
                SEARCH_DURATION.labels(
                    stage="total",
                    status=status
                ).observe(duration)
            
            if results_count is not None:
                query_type = "short" if len(metric.query) < 10 else "long"
                SEARCH_RESULTS_COUNT.labels(query_type=query_type).observe(results_count)
            
            # Move to recent searches
            self._recent_searches.append(metric)
            
            # Clean up
            del self._active_searches[correlation_id]
            if correlation_id in self._stage_metrics:
                del self._stage_metrics[correlation_id]
            
            # Update active counts
            SEARCH_ACTIVE_OPERATIONS.set(len(self._active_searches))
            
            # Clean up old user sessions (older than 1 hour)
            current_time = datetime.utcnow()
            expired_users = [
                user_id for user_id, last_seen in self._user_sessions.items()
                if (current_time - last_seen).total_seconds() > 3600
            ]
            for user_id in expired_users:
                del self._user_sessions[user_id]
            
            SEARCH_USER_SESSIONS.set(len(self._user_sessions))

        self.logger.info(
            "Search operation completed",
            correlation_id=correlation_id,
            status=status,
            duration_ms=metric.duration_ms,
            results_count=results_count,
            api_calls=metric.api_calls_count,
            errors=metric.errors_count
        )
        
        return metric

    def get_search_metrics(self, correlation_id: str) -> Optional[Dict[str, Any]]:
        """Get metrics for a specific search operation."""
        with self._metrics_lock:
            if correlation_id in self._active_searches:
                metric = self._active_searches[correlation_id]
                stage_metrics = self._stage_metrics.get(correlation_id, [])
                
                return {
                    "correlation_id": correlation_id,
                    "user_id": metric.user_id,
                    "query": metric.query,
                    "item_count": metric.item_count,
                    "started_at": metric.started_at.isoformat(),
                    "current_stage": metric.stage,
                    "status": metric.status,
                    "api_calls_count": metric.api_calls_count,
                    "errors_count": metric.errors_count,
                    "user_type": metric.user_type,
                    "stages": [
                        {
                            "stage_name": sm.stage_name,
                            "started_at": sm.started_at.isoformat(),
                            "completed_at": sm.completed_at.isoformat() if sm.completed_at else None,
                            "duration_ms": sm.duration_ms,
                            "status": sm.status,
                            "details": sm.details
                        }
                        for sm in stage_metrics
                    ]
                }
        
        return None

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary of search operations."""
        with self._metrics_lock:
            current_time = datetime.utcnow()
            
            # Analyze recent searches (last 100)
            recent_searches = list(self._recent_searches)[-100:]
            
            if not recent_searches:
                return {
                    "status": "no_data",
                    "message": "No recent search operations to analyze",
                    "timestamp": current_time.isoformat()
                }
            
            # Calculate success rate
            successful_searches = [s for s in recent_searches if s.status == "success"]
            success_rate = len(successful_searches) / len(recent_searches) * 100
            
            # Calculate average duration
            completed_searches = [s for s in recent_searches if s.duration_ms is not None]
            avg_duration = 0
            if completed_searches:
                avg_duration = sum(s.duration_ms for s in completed_searches) / len(completed_searches)
            
            # Calculate average results count
            searches_with_results = [s for s in recent_searches if s.results_count is not None]
            avg_results = 0
            if searches_with_results:
                avg_results = sum(s.results_count for s in searches_with_results) / len(searches_with_results)
            
            # Analyze error patterns
            error_counts = defaultdict(int)
            for search in recent_searches:
                if search.errors_count > 0:
                    error_counts["searches_with_errors"] += 1
            
            # User type distribution
            user_type_counts = defaultdict(int)
            for search in recent_searches:
                user_type_counts[search.user_type] += 1
            
            return {
                "status": "healthy" if success_rate > 80 else "degraded" if success_rate > 50 else "unhealthy",
                "active_searches": len(self._active_searches),
                "active_user_sessions": len(self._user_sessions),
                "recent_searches_analyzed": len(recent_searches),
                "success_rate_percent": round(success_rate, 2),
                "average_duration_ms": round(avg_duration, 2),
                "average_results_count": round(avg_results, 2),
                "searches_with_errors": error_counts["searches_with_errors"],
                "user_type_distribution": dict(user_type_counts),
                "timestamp": current_time.isoformat()
            }

    def get_hourly_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """Get hourly search statistics."""
        with self._metrics_lock:
            current_time = datetime.utcnow()
            cutoff_time = current_time - timedelta(hours=hours)
            
            # Filter recent searches within time window
            recent_searches = [
                s for s in self._recent_searches
                if s.started_at >= cutoff_time
            ]
            
            # Group by hour
            hourly_stats = defaultdict(lambda: {
                'total': 0,
                'successful': 0,
                'failed': 0,
                'avg_duration': 0,
                'total_results': 0
            })
            
            for search in recent_searches:
                hour_key = search.started_at.strftime('%Y-%m-%d %H:00')
                stats = hourly_stats[hour_key]
                
                stats['total'] += 1
                if search.status == 'success':
                    stats['successful'] += 1
                else:
                    stats['failed'] += 1
                
                if search.duration_ms:
                    stats['avg_duration'] += search.duration_ms
                
                if search.results_count:
                    stats['total_results'] += search.results_count
            
            # Calculate averages
            for stats in hourly_stats.values():
                if stats['total'] > 0:
                    stats['avg_duration'] = stats['avg_duration'] / stats['total']
                    stats['success_rate'] = stats['successful'] / stats['total'] * 100
            
            return {
                "time_window_hours": hours,
                "total_searches": len(recent_searches),
                "hourly_breakdown": dict(hourly_stats),
                "timestamp": current_time.isoformat()
            }

    def get_user_daily_search_count(self, user_id: int, day: Optional[date] = None) -> int:
        """Return number of searches by a user for the given day (UTC)."""
        with self._metrics_lock:
            target_date = day or datetime.utcnow().date()
            count = 0
            # Completed searches
            for s in self._recent_searches:
                if s.user_id == user_id and s.started_at.date() == target_date:
                    count += 1
            # Active searches
            for s in self._active_searches.values():
                if s.user_id == user_id and s.started_at.date() == target_date:
                    count += 1
            return count

    def cleanup_old_data(self, max_age_hours: int = 24) -> None:
        """Clean up old metrics data."""
        with self._metrics_lock:
            current_time = datetime.utcnow()
            cutoff_time = current_time - timedelta(hours=max_age_hours)
            
            # Clean up old user sessions
            expired_users = [
                user_id for user_id, last_seen in self._user_sessions.items()
                if last_seen < cutoff_time
            ]
            for user_id in expired_users:
                del self._user_sessions[user_id]
            
            SEARCH_USER_SESSIONS.set(len(self._user_sessions))
            
            self.logger.info(
                f"Cleaned up {len(expired_users)} expired user sessions",
                expired_count=len(expired_users),
                remaining_sessions=len(self._user_sessions)
            )


# Global search metrics instance
search_metrics = SearchMetrics()