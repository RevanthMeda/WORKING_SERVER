"""
Advanced database query performance analysis and optimization.
"""
import time
import logging
import threading
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from sqlalchemy import text, event
from sqlalchemy.engine import Engine
from flask import current_app, g, request
import hashlib
import re

logger = logging.getLogger(__name__)


@dataclass
class QueryMetrics:
    """Query performance metrics."""
    query_hash: str
    normalized_query: str
    execution_count: int
    total_time: float
    avg_time: float
    min_time: float
    max_time: float
    last_executed: datetime
    slow_executions: int
    error_count: int
    tables_accessed: List[str]
    index_usage: Dict[str, int]
    
    @property
    def performance_score(self) -> float:
        """Calculate performance score (0-100, higher is better)."""
        # Base score on average execution time
        if self.avg_time < 0.1:
            time_score = 100
        elif self.avg_time < 0.5:
            time_score = 80
        elif self.avg_time < 1.0:
            time_score = 60
        elif self.avg_time < 2.0:
            time_score = 40
        else:
            time_score = 20
        
        # Penalty for slow executions
        slow_penalty = min(30, (self.slow_executions / max(1, self.execution_count)) * 100)
        
        # Penalty for errors
        error_penalty = min(20, (self.error_count / max(1, self.execution_count)) * 100)
        
        return max(0, time_score - slow_penalty - error_penalty)


class QueryAnalyzer:
    """Advanced query performance analyzer."""
    
    def __init__(self, slow_query_threshold: float = 1.0):
        self.slow_query_threshold = slow_query_threshold
        self.query_metrics: Dict[str, QueryMetrics] = {}
        self.query_patterns = defaultdict(list)
        self.table_access_patterns = defaultdict(int)
        self.lock = threading.Lock()
        
        # Query execution history for trend analysis
        self.execution_history = deque(maxlen=10000)
        
        # Index usage tracking
        self.index_recommendations = {}
        
        # Performance baselines
        self.performance_baselines = {}
    
    def analyze_query(self, query: str, execution_time: float, 
                     error: Optional[str] = None, 
                     explain_plan: Optional[Dict] = None) -> None:
        """Analyze query execution and update metrics."""
        
        normalized_query = self._normalize_query(query)
        query_hash = hashlib.md5(normalized_query.encode()).hexdigest()
        
        with self.lock:
            # Update or create metrics
            if query_hash in self.query_metrics:
                metrics = self.query_metrics[query_hash]
                metrics.execution_count += 1
                metrics.total_time += execution_time
                metrics.avg_time = metrics.total_time / metrics.execution_count
                metrics.min_time = min(metrics.min_time, execution_time)
                metrics.max_time = max(metrics.max_time, execution_time)
                metrics.last_executed = datetime.utcnow()
                
                if execution_time > self.slow_query_threshold:
                    metrics.slow_executions += 1
                
                if error:
                    metrics.error_count += 1
            else:
                # Extract tables from query
                tables = self._extract_tables(query)
                
                metrics = QueryMetrics(
                    query_hash=query_hash,
                    normalized_query=normalized_query,
                    execution_count=1,
                    total_time=execution_time,
                    avg_time=execution_time,
                    min_time=execution_time,
                    max_time=execution_time,
                    last_executed=datetime.utcnow(),
                    slow_executions=1 if execution_time > self.slow_query_threshold else 0,
                    error_count=1 if error else 0,
                    tables_accessed=tables,
                    index_usage={}
                )
                
                self.query_metrics[query_hash] = metrics
            
            # Track execution history
            self.execution_history.append({
                'query_hash': query_hash,
                'execution_time': execution_time,
                'timestamp': datetime.utcnow(),
                'error': error is not None,
                'endpoint': getattr(request, 'endpoint', None) if request else None
            })
            
            # Update table access patterns
            for table in metrics.tables_accessed:
                self.table_access_patterns[table] += 1
            
            # Analyze explain plan if provided
            if explain_plan:
                self._analyze_explain_plan(query_hash, explain_plan)
    
    def _normalize_query(self, query: str) -> str:
        """Normalize query for pattern matching."""
        # Remove comments
        query = re.sub(r'--.*$', '', query, flags=re.MULTILINE)
        query = re.sub(r'/\*.*?\*/', '', query, flags=re.DOTALL)
        
        # Replace parameter placeholders
        query = re.sub(r'\$\d+|\?|%\([^)]+\)s', '?', query)
        
        # Replace quoted strings and numbers
        query = re.sub(r"'[^']*'", "'?'", query)
        query = re.sub(r'"[^"]*"', '"?"', query)
        query = re.sub(r'\b\d+\b', '?', query)
        
        # Normalize whitespace
        query = ' '.join(query.split())
        
        return query.lower()
    
    def _extract_tables(self, query: str) -> List[str]:
        """Extract table names from query."""
        tables = []
        query_lower = query.lower()
        
        # Simple regex patterns for common table references
        patterns = [
            r'from\s+([a-zA-Z_][a-zA-Z0-9_]*)',
            r'join\s+([a-zA-Z_][a-zA-Z0-9_]*)',
            r'update\s+([a-zA-Z_][a-zA-Z0-9_]*)',
            r'insert\s+into\s+([a-zA-Z_][a-zA-Z0-9_]*)',
            r'delete\s+from\s+([a-zA-Z_][a-zA-Z0-9_]*)'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, query_lower)
            tables.extend(matches)
        
        return list(set(tables))  # Remove duplicates
    
    def _analyze_explain_plan(self, query_hash: str, explain_plan: Dict) -> None:
        """Analyze query execution plan for optimization opportunities."""
        if query_hash not in self.query_metrics:
            return
        
        metrics = self.query_metrics[query_hash]
        
        # Extract index usage information
        if 'index_usage' in explain_plan:
            for index_info in explain_plan['index_usage']:
                index_name = index_info.get('index_name', 'unknown')
                metrics.index_usage[index_name] = metrics.index_usage.get(index_name, 0) + 1
        
        # Check for table scans and missing indexes
        if 'execution_plan' in explain_plan:
            self._check_for_optimization_opportunities(query_hash, explain_plan['execution_plan'])
    
    def _check_for_optimization_opportunities(self, query_hash: str, execution_plan: Dict) -> None:
        """Check execution plan for optimization opportunities."""
        # Look for table scans
        if 'table_scan' in str(execution_plan).lower():
            if query_hash not in self.index_recommendations:
                self.index_recommendations[query_hash] = []
            
            self.index_recommendations[query_hash].append({
                'type': 'missing_index',
                'severity': 'high',
                'description': 'Query performs table scan, consider adding index',
                'recommendation': 'Analyze WHERE clauses and add appropriate indexes'
            })
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary."""
        with self.lock:
            if not self.query_metrics:
                return {'message': 'No query data available'}
            
            total_queries = sum(m.execution_count for m in self.query_metrics.values())
            total_time = sum(m.total_time for m in self.query_metrics.values())
            slow_queries = sum(m.slow_executions for m in self.query_metrics.values())
            error_queries = sum(m.error_count for m in self.query_metrics.values())
            
            # Calculate percentiles
            all_times = []
            for metrics in self.query_metrics.values():
                all_times.extend([metrics.avg_time] * metrics.execution_count)
            
            all_times.sort()
            if all_times:
                p50 = all_times[len(all_times) // 2]
                p95 = all_times[int(len(all_times) * 0.95)]
                p99 = all_times[int(len(all_times) * 0.99)]
            else:
                p50 = p95 = p99 = 0
            
            return {
                'total_queries': total_queries,
                'unique_queries': len(self.query_metrics),
                'total_execution_time': total_time,
                'avg_execution_time': total_time / total_queries if total_queries > 0 else 0,
                'slow_queries': slow_queries,
                'error_queries': error_queries,
                'slow_query_percentage': (slow_queries / total_queries * 100) if total_queries > 0 else 0,
                'error_percentage': (error_queries / total_queries * 100) if total_queries > 0 else 0,
                'percentiles': {
                    'p50': p50,
                    'p95': p95,
                    'p99': p99
                },
                'most_accessed_tables': dict(sorted(
                    self.table_access_patterns.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:10])
            }
    
    def get_slow_queries(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get slowest queries with detailed analysis."""
        with self.lock:
            # Sort by average execution time
            sorted_queries = sorted(
                self.query_metrics.values(),
                key=lambda m: m.avg_time,
                reverse=True
            )
            
            slow_queries = []
            for metrics in sorted_queries[:limit]:
                slow_queries.append({
                    'query_hash': metrics.query_hash,
                    'normalized_query': metrics.normalized_query[:500] + '...' if len(metrics.normalized_query) > 500 else metrics.normalized_query,
                    'execution_count': metrics.execution_count,
                    'avg_time': metrics.avg_time,
                    'max_time': metrics.max_time,
                    'total_time': metrics.total_time,
                    'slow_executions': metrics.slow_executions,
                    'error_count': metrics.error_count,
                    'performance_score': metrics.performance_score,
                    'tables_accessed': metrics.tables_accessed,
                    'last_executed': metrics.last_executed.isoformat(),
                    'recommendations': self.index_recommendations.get(metrics.query_hash, [])
                })
            
            return slow_queries
    
    def get_query_trends(self, hours: int = 24) -> Dict[str, Any]:
        """Get query performance trends over time."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        with self.lock:
            recent_executions = [
                exec_info for exec_info in self.execution_history
                if exec_info['timestamp'] > cutoff_time
            ]
            
            if not recent_executions:
                return {'message': 'No recent execution data'}
            
            # Group by hour
            hourly_stats = defaultdict(lambda: {
                'count': 0,
                'total_time': 0,
                'slow_count': 0,
                'error_count': 0
            })
            
            for exec_info in recent_executions:
                hour_key = exec_info['timestamp'].replace(minute=0, second=0, microsecond=0)
                stats = hourly_stats[hour_key]
                
                stats['count'] += 1
                stats['total_time'] += exec_info['execution_time']
                
                if exec_info['execution_time'] > self.slow_query_threshold:
                    stats['slow_count'] += 1
                
                if exec_info['error']:
                    stats['error_count'] += 1
            
            # Convert to list format
            trends = []
            for hour, stats in sorted(hourly_stats.items()):
                trends.append({
                    'hour': hour.isoformat(),
                    'query_count': stats['count'],
                    'avg_time': stats['total_time'] / stats['count'] if stats['count'] > 0 else 0,
                    'slow_queries': stats['slow_count'],
                    'errors': stats['error_count']
                })
            
            return {
                'period_hours': hours,
                'total_executions': len(recent_executions),
                'trends': trends
            }
    
    def get_table_performance(self) -> Dict[str, Any]:
        """Get performance analysis by table."""
        with self.lock:
            table_stats = defaultdict(lambda: {
                'query_count': 0,
                'total_time': 0,
                'slow_queries': 0,
                'avg_time': 0,
                'queries': []
            })
            
            for metrics in self.query_metrics.values():
                for table in metrics.tables_accessed:
                    stats = table_stats[table]
                    stats['query_count'] += metrics.execution_count
                    stats['total_time'] += metrics.total_time
                    stats['slow_queries'] += metrics.slow_executions
                    stats['queries'].append({
                        'query_hash': metrics.query_hash,
                        'avg_time': metrics.avg_time,
                        'execution_count': metrics.execution_count
                    })
            
            # Calculate averages and sort
            for table, stats in table_stats.items():
                if stats['query_count'] > 0:
                    stats['avg_time'] = stats['total_time'] / stats['query_count']
                
                # Sort queries by average time
                stats['queries'] = sorted(
                    stats['queries'],
                    key=lambda q: q['avg_time'],
                    reverse=True
                )[:5]  # Top 5 slowest queries per table
            
            return dict(table_stats)
    
    def generate_optimization_recommendations(self) -> List[Dict[str, Any]]:
        """Generate comprehensive optimization recommendations."""
        recommendations = []
        
        with self.lock:
            # Analyze slow queries
            slow_queries = [m for m in self.query_metrics.values() if m.avg_time > self.slow_query_threshold]
            
            if slow_queries:
                recommendations.append({
                    'category': 'slow_queries',
                    'priority': 'high',
                    'title': f'{len(slow_queries)} slow queries detected',
                    'description': f'Found {len(slow_queries)} queries with average execution time > {self.slow_query_threshold}s',
                    'impact': 'High - directly affects user experience',
                    'actions': [
                        'Review and optimize slow queries',
                        'Add appropriate database indexes',
                        'Consider query restructuring',
                        'Implement result caching for frequently executed slow queries'
                    ]
                })
            
            # Analyze frequently executed queries
            frequent_queries = [m for m in self.query_metrics.values() if m.execution_count > 100]
            if frequent_queries:
                recommendations.append({
                    'category': 'frequent_queries',
                    'priority': 'medium',
                    'title': f'{len(frequent_queries)} frequently executed queries',
                    'description': f'Found {len(frequent_queries)} queries executed more than 100 times',
                    'impact': 'Medium - optimization can provide cumulative benefits',
                    'actions': [
                        'Implement caching for frequently executed queries',
                        'Optimize database indexes for common query patterns',
                        'Consider materialized views for complex aggregations'
                    ]
                })
            
            # Analyze table access patterns
            hot_tables = [table for table, count in self.table_access_patterns.items() if count > 500]
            if hot_tables:
                recommendations.append({
                    'category': 'hot_tables',
                    'priority': 'medium',
                    'title': f'{len(hot_tables)} heavily accessed tables',
                    'description': f'Tables {", ".join(hot_tables)} are accessed very frequently',
                    'impact': 'Medium - optimizing these tables affects many queries',
                    'actions': [
                        'Ensure proper indexing on heavily accessed tables',
                        'Consider partitioning for very large tables',
                        'Implement table-level caching strategies',
                        'Monitor for lock contention'
                    ]
                })
            
            # Check for error-prone queries
            error_queries = [m for m in self.query_metrics.values() if m.error_count > 0]
            if error_queries:
                recommendations.append({
                    'category': 'error_queries',
                    'priority': 'high',
                    'title': f'{len(error_queries)} queries with errors',
                    'description': f'Found {len(error_queries)} queries that have failed at least once',
                    'impact': 'High - errors affect application reliability',
                    'actions': [
                        'Review and fix queries with errors',
                        'Add proper error handling',
                        'Validate query parameters',
                        'Check for data consistency issues'
                    ]
                })
        
        return recommendations
    
    def reset_metrics(self) -> None:
        """Reset all collected metrics."""
        with self.lock:
            self.query_metrics.clear()
            self.query_patterns.clear()
            self.table_access_patterns.clear()
            self.execution_history.clear()
            self.index_recommendations.clear()
            
        logger.info("Query analyzer metrics reset")


# Global analyzer instance
query_analyzer = QueryAnalyzer()


def setup_query_analysis(app):
    """Set up query analysis monitoring."""
    
    @event.listens_for(Engine, "before_cursor_execute")
    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        """Record query start time."""
        context._query_start_time = time.time()
        context._query_statement = statement
    
    @event.listens_for(Engine, "after_cursor_execute")
    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        """Analyze completed query."""
        if hasattr(context, '_query_start_time'):
            execution_time = time.time() - context._query_start_time
            query_analyzer.analyze_query(statement, execution_time)
    
    @event.listens_for(Engine, "handle_error")
    def handle_error(exception_context):
        """Analyze failed queries."""
        if hasattr(exception_context, 'statement'):
            query_analyzer.analyze_query(
                exception_context.statement,
                0,  # No execution time for failed queries
                error=str(exception_context.original_exception)
            )
    
    logger.info("Query analysis monitoring enabled")


def get_query_analyzer() -> QueryAnalyzer:
    """Get the global query analyzer instance."""
    return query_analyzer