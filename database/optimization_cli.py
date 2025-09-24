#!/usr/bin/env python3
"""
Database optimization CLI tool for SAT Report Generator.
"""

import click
import json
import logging
from datetime import datetime, timedelta
from flask import Flask
from flask.cli import with_appcontext

from models import db
from database.performance import (
    query_monitor, pool_monitor, QueryOptimizer, 
    DatabaseIndexManager, DatabaseMaintenanceManager
)
from database.pooling import pool_manager
from database.query_cache import get_cache_manager
from database.query_analyzer import get_query_analyzer

logger = logging.getLogger(__name__)


@click.group()
def db_optimize():
    """Database optimization commands."""
    pass


@db_optimize.command()
@with_appcontext
def analyze_queries():
    """Analyze slow queries and provide optimization recommendations."""
    click.echo("🔍 Analyzing database queries...")
    
    # Get analyzer instance
    analyzer = get_query_analyzer()
    
    # Get performance summary
    summary = analyzer.get_performance_summary()
    
    if 'message' in summary:
        click.echo(f"⚠️ {summary['message']}")
        return
    
    # Display summary
    click.echo(f"\n📊 Query Performance Summary")
    click.echo(f"Total queries executed: {summary['total_queries']}")
    click.echo(f"Unique query patterns: {summary['unique_queries']}")
    click.echo(f"Total execution time: {summary['total_execution_time']:.2f}s")
    click.echo(f"Average execution time: {summary['avg_execution_time']:.3f}s")
    click.echo(f"Slow queries: {summary['slow_queries']} ({summary['slow_query_percentage']:.1f}%)")
    click.echo(f"Query errors: {summary['error_queries']} ({summary['error_percentage']:.1f}%)")
    
    # Display percentiles
    click.echo(f"\n⏱️ Response Time Percentiles:")
    click.echo(f"50th percentile: {summary['percentiles']['p50']:.3f}s")
    click.echo(f"95th percentile: {summary['percentiles']['p95']:.3f}s")
    click.echo(f"99th percentile: {summary['percentiles']['p99']:.3f}s")
    
    # Display most accessed tables
    if summary['most_accessed_tables']:
        click.echo(f"\n🔥 Most Accessed Tables:")
        for table, count in list(summary['most_accessed_tables'].items())[:5]:
            click.echo(f"   • {table}: {count} accesses")
    
    # Get slow queries
    slow_queries = analyzer.get_slow_queries(5)
    if slow_queries:
        click.echo(f"\n🐌 Slowest Queries:")
        for i, query in enumerate(slow_queries, 1):
            click.echo(f"\n{i}. Performance Score: {query['performance_score']:.1f}/100")
            click.echo(f"   Average Time: {query['avg_time']:.3f}s (Max: {query['max_time']:.3f}s)")
            click.echo(f"   Executions: {query['execution_count']} (Slow: {query['slow_executions']})")
            click.echo(f"   Query: {query['normalized_query'][:100]}...")
            
            if query['recommendations']:
                click.echo(f"   Recommendations:")
                for rec in query['recommendations']:
                    click.echo(f"     • {rec['description']}")
    
    # Get optimization recommendations
    recommendations = analyzer.generate_optimization_recommendations()
    if recommendations:
        click.echo(f"\n💡 Optimization Recommendations:")
        for rec in recommendations:
            priority_icon = "🚨" if rec['priority'] == 'high' else "⚠️" if rec['priority'] == 'medium' else "💡"
            click.echo(f"\n{priority_icon} {rec['title']} [{rec['priority'].upper()}]")
            click.echo(f"   {rec['description']}")
            click.echo(f"   Impact: {rec['impact']}")
            click.echo(f"   Actions:")
            for action in rec['actions']:
                click.echo(f"     • {action}")
    
    # Save detailed report
    report = {
        'generated_at': datetime.now().isoformat(),
        'performance_summary': summary,
        'slow_queries': slow_queries,
        'recommendations': recommendations,
        'table_performance': analyzer.get_table_performance()
    }
    
    report_file = f"query_analysis_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    click.echo(f"\n📄 Detailed report saved to: {report_file}")


@db_optimize.command()
@with_appcontext
def check_indexes():
    """Check for missing indexes and create recommendations."""
    click.echo("🔍 Analyzing database indexes...")
    
    # Create recommended indexes
    created, failed = DatabaseIndexManager.create_recommended_indexes()
    
    if created:
        click.echo(f"✅ Created {len(created)} new indexes:")
        for index_name in created:
            click.echo(f"   • {index_name}")
    
    if failed:
        click.echo(f"❌ Failed to create {len(failed)} indexes:")
        for index_name, error in failed:
            click.echo(f"   • {index_name}: {error}")
    
    # Analyze missing indexes
    suggestions = DatabaseIndexManager.analyze_missing_indexes()
    
    if suggestions:
        click.echo(f"\n💡 Additional index suggestions:")
        for suggestion in suggestions[:10]:  # Show top 10
            click.echo(f"   • {suggestion['table']}.{suggestion['column']} "
                      f"({suggestion['type']}): {suggestion['reason']}")
    else:
        click.echo("✅ No additional index suggestions found")


@db_optimize.command()
@with_appcontext
def pool_status():
    """Check database connection pool status and optimization recommendations."""
    click.echo("🔍 Checking connection pool status...")
    
    try:
        status = pool_manager.get_pool_status(db.engine)
        health = pool_manager.health_check(db.engine)
        
        # Display pool status
        click.echo(f"\n📊 Connection Pool Status:")
        click.echo(f"Pool size: {status.get('pool_size', 'N/A')}")
        click.echo(f"Checked out: {status.get('checked_out', 'N/A')}")
        click.echo(f"Checked in: {status.get('checked_in', 'N/A')}")
        click.echo(f"Overflow: {status.get('overflow', 'N/A')}")
        click.echo(f"Utilization: {status.get('utilization', 0):.1f}%")
        
        # Display health status
        health_icon = "✅" if health['status'] == 'healthy' else "⚠️" if health['status'] == 'warning' else "❌"
        click.echo(f"\n{health_icon} Pool Health: {health['status'].upper()}")
        
        if health['issues']:
            click.echo("Issues found:")
            for issue in health['issues']:
                click.echo(f"   • {issue}")
        
        # Display recommendations
        if health['recommendations']:
            click.echo(f"\n💡 Optimization Recommendations:")
            for rec in health['recommendations']:
                priority_icon = "🚨" if rec.get('priority') == 'high' else "⚠️" if rec.get('priority') == 'medium' else "💡"
                click.echo(f"{priority_icon} {rec['setting']}: {rec['reason']}")
                click.echo(f"   Current: {rec['current']} → Recommended: {rec['recommended']}")
                if 'impact' in rec:
                    click.echo(f"   Impact: {rec['impact']}")
        
    except Exception as e:
        click.echo(f"❌ Error checking pool status: {e}")


@db_optimize.command()
@click.option('--hours', default=24, help='Number of hours to analyze')
@with_appcontext
def query_trends(hours):
    """Analyze query performance trends over time."""
    click.echo(f"📈 Analyzing query trends for the last {hours} hours...")
    
    analyzer = get_query_analyzer()
    trends = analyzer.get_query_trends(hours)
    
    if 'message' in trends:
        click.echo(f"⚠️ {trends['message']}")
        return
    
    click.echo(f"\n📊 Query Trends Summary ({hours} hours):")
    click.echo(f"Total executions: {trends['total_executions']}")
    
    if trends['trends']:
        click.echo(f"\n⏰ Hourly Breakdown:")
        for trend in trends['trends'][-12:]:  # Show last 12 hours
            hour = datetime.fromisoformat(trend['hour']).strftime('%H:%M')
            click.echo(f"   {hour}: {trend['query_count']} queries "
                      f"(avg: {trend['avg_time']:.3f}s, slow: {trend['slow_queries']}, "
                      f"errors: {trend['errors']})")
        
        # Find peak hours
        peak_hour = max(trends['trends'], key=lambda x: x['query_count'])
        slowest_hour = max(trends['trends'], key=lambda x: x['avg_time'])
        
        click.echo(f"\n🔍 Key Insights:")
        peak_time = datetime.fromisoformat(peak_hour['hour']).strftime('%H:%M')
        click.echo(f"   Peak activity: {peak_time} ({peak_hour['query_count']} queries)")
        
        slowest_time = datetime.fromisoformat(slowest_hour['hour']).strftime('%H:%M')
        click.echo(f"   Slowest hour: {slowest_time} (avg: {slowest_hour['avg_time']:.3f}s)")


@db_optimize.command()
@with_appcontext
def table_analysis():
    """Analyze performance by database table."""
    click.echo("🔍 Analyzing performance by table...")
    
    analyzer = get_query_analyzer()
    table_performance = analyzer.get_table_performance()
    
    if not table_performance:
        click.echo("⚠️ No table performance data available")
        return
    
    click.echo(f"\n📊 Table Performance Analysis:")
    
    # Sort tables by total time
    sorted_tables = sorted(
        table_performance.items(),
        key=lambda x: x[1]['total_time'],
        reverse=True
    )
    
    for table, stats in sorted_tables[:10]:  # Top 10 tables
        click.echo(f"\n📋 Table: {table}")
        click.echo(f"   Total queries: {stats['query_count']}")
        click.echo(f"   Total time: {stats['total_time']:.2f}s")
        click.echo(f"   Average time: {stats['avg_time']:.3f}s")
        click.echo(f"   Slow queries: {stats['slow_queries']}")
        
        if stats['queries']:
            click.echo(f"   Slowest queries:")
            for query in stats['queries'][:3]:  # Top 3 slowest
                click.echo(f"     • {query['avg_time']:.3f}s (x{query['execution_count']})")


@db_optimize.command()
@with_appcontext
def cache_stats():
    """Display query cache statistics."""
    click.echo("🔍 Checking query cache statistics...")
    
    cache_manager = get_cache_manager()
    if not cache_manager:
        click.echo("❌ Query cache not initialized")
        return
    
    stats = cache_manager.get_cache_stats()
    
    # Display cache status
    status_icon = "✅" if stats['available'] else "❌"
    click.echo(f"\n{status_icon} Cache Status: {'Available' if stats['available'] else 'Unavailable'}")
    click.echo(f"Enabled: {'Yes' if stats['enabled'] else 'No'}")
    
    if stats['available']:
        click.echo(f"\n📊 Cache Statistics:")
        click.echo(f"Hit rate: {stats['hit_rate']:.1f}%")
        click.echo(f"Total requests: {stats['total_requests']}")
        click.echo(f"Cache hits: {stats['hit_count']}")
        click.echo(f"Cache misses: {stats['miss_count']}")
        click.echo(f"Cached queries: {stats.get('cached_queries', 'N/A')}")
        click.echo(f"Default TTL: {stats['default_ttl']}s")
        
        # Show sample entries
        if stats.get('sample_entries'):
            click.echo(f"\n📝 Sample Cache Entries:")
            for entry in stats['sample_entries'][:5]:
                click.echo(f"   • {entry['key'][:50]}... (TTL: {entry['ttl']}s, Size: {entry['size_bytes']} bytes)")


@db_optimize.command()
@click.option('--clear-cache', is_flag=True, help='Clear query cache')
@click.option('--vacuum', is_flag=True, help='Vacuum database')
@click.option('--update-stats', is_flag=True, help='Update database statistics')
@click.option('--cleanup-old', is_flag=True, help='Clean up old records')
@with_appcontext
def maintenance(clear_cache, vacuum, update_stats, cleanup_old):
    """Perform database maintenance tasks."""
    click.echo("🔧 Performing database maintenance...")
    
    if clear_cache:
        cache_manager = get_cache_manager()
        if cache_manager:
            cleared = cache_manager.clear_all_cache()
            click.echo(f"✅ Cleared {cleared} cached queries")
        else:
            click.echo("⚠️ Query cache not available")
    
    if vacuum:
        click.echo("🧹 Vacuuming database...")
        success = DatabaseMaintenanceManager.vacuum_database()
        if success:
            click.echo("✅ Database vacuum completed")
        else:
            click.echo("❌ Database vacuum failed")
    
    if update_stats:
        click.echo("📊 Updating database statistics...")
        success = DatabaseMaintenanceManager.update_statistics()
        if success:
            click.echo("✅ Database statistics updated")
        else:
            click.echo("❌ Statistics update failed")
    
    if cleanup_old:
        click.echo("🗑️ Cleaning up old records...")
        cleaned = DatabaseMaintenanceManager.cleanup_old_records()
        click.echo(f"✅ Cleaned up {cleaned} old records")
    
    if not any([clear_cache, vacuum, update_stats, cleanup_old]):
        click.echo("No maintenance tasks specified. Use --help to see available options.")


@db_optimize.command()
@click.option('--days', default=7, help='Number of days to analyze')
@with_appcontext
def performance_report(days):
    """Generate comprehensive database performance report."""
    click.echo(f"📊 Generating {days}-day performance report...")
    
    # Get query statistics
    query_stats = query_monitor.get_query_stats(20)
    slow_queries = query_monitor.get_slow_queries(10)
    
    # Get pool statistics
    pool_stats = pool_monitor.get_stats()
    
    # Get cache statistics
    cache_manager = get_cache_manager()
    cache_stats = cache_manager.get_cache_stats() if cache_manager else {}
    
    # Generate report
    report = {
        'generated_at': datetime.utcnow().isoformat(),
        'period_days': days,
        'query_performance': {
            'total_queries_tracked': len(query_stats),
            'slow_queries_count': len(slow_queries),
            'top_slow_queries': [
                {
                    'query': q['query'][:100] + '...' if len(q['query']) > 100 else q['query'],
                    'duration': q['duration'],
                    'timestamp': q['timestamp'].isoformat() if q['timestamp'] else None
                }
                for q in slow_queries[:5]
            ],
            'top_time_consuming': [
                {
                    'query': query[:100] + '...' if len(query) > 100 else query,
                    'total_time': stats['total_time'],
                    'avg_time': stats['avg_time'],
                    'count': stats['count']
                }
                for query, stats in query_stats[:5]
            ]
        },
        'connection_pool': {
            'connections_created': pool_stats.get('connections_created', 0),
            'connections_closed': pool_stats.get('connections_closed', 0),
            'connections_checked_out': pool_stats.get('connections_checked_out', 0),
            'connections_checked_in': pool_stats.get('connections_checked_in', 0),
            'pool_overflows': pool_stats.get('pool_overflows', 0),
            'connection_errors': pool_stats.get('connection_errors', 0)
        },
        'query_cache': cache_stats
    }
    
    # Display summary
    click.echo(f"\n📊 Performance Summary ({days} days):")
    click.echo(f"Queries tracked: {report['query_performance']['total_queries_tracked']}")
    click.echo(f"Slow queries: {report['query_performance']['slow_queries_count']}")
    click.echo(f"Connection errors: {report['connection_pool']['connection_errors']}")
    click.echo(f"Pool overflows: {report['connection_pool']['pool_overflows']}")
    
    if cache_stats.get('available'):
        click.echo(f"Cache hit rate: {cache_stats.get('hit_rate', 0):.1f}%")
    
    # Show top slow queries
    if report['query_performance']['top_slow_queries']:
        click.echo(f"\n🐌 Slowest Queries:")
        for i, query in enumerate(report['query_performance']['top_slow_queries'], 1):
            click.echo(f"{i}. {query['duration']:.2f}s - {query['query']}")
    
    # Save detailed report
    report_file = f"performance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    click.echo(f"\n📄 Detailed report saved to: {report_file}")


@db_optimize.command()
@click.option('--auto-apply', is_flag=True, help='Automatically apply safe optimizations')
@with_appcontext
def optimize_all(auto_apply):
    """Run comprehensive database optimization."""
    click.echo("🚀 Running comprehensive database optimization...")
    
    results = {
        'indexes_created': 0,
        'cache_cleared': False,
        'vacuum_completed': False,
        'stats_updated': False,
        'optimizations_found': 0
    }
    
    # 1. Create recommended indexes
    click.echo("\n1. Creating recommended indexes...")
    created, failed = DatabaseIndexManager.create_recommended_indexes()
    results['indexes_created'] = len(created)
    
    if created:
        click.echo(f"✅ Created {len(created)} indexes")
    if failed:
        click.echo(f"⚠️ Failed to create {len(failed)} indexes")
    
    # 2. Analyze queries
    click.echo("\n2. Analyzing query performance...")
    optimizer = QueryOptimizer()
    optimization_report = optimizer.generate_optimization_report()
    results['optimizations_found'] = optimization_report.get('total_queries_analyzed', 0)
    
    if optimization_report.get('high_priority_optimizations', 0) > 0:
        click.echo(f"⚠️ Found {optimization_report['high_priority_optimizations']} high-priority optimizations")
    
    # 3. Check connection pool
    click.echo("\n3. Optimizing connection pool...")
    try:
        recommendations = pool_manager.optimize_pool_settings(db.engine)
        if recommendations:
            click.echo(f"💡 Found {len(recommendations)} pool optimization recommendations")
            for rec in recommendations[:3]:  # Show top 3
                click.echo(f"   • {rec['setting']}: {rec['reason']}")
    except Exception as e:
        click.echo(f"⚠️ Pool optimization failed: {e}")
    
    # 4. Maintenance tasks (if auto-apply is enabled)
    if auto_apply:
        click.echo("\n4. Performing maintenance tasks...")
        
        # Clear cache
        cache_manager = get_cache_manager()
        if cache_manager:
            cache_manager.clear_all_cache()
            results['cache_cleared'] = True
            click.echo("✅ Cache cleared")
        
        # Update statistics
        if DatabaseMaintenanceManager.update_statistics():
            results['stats_updated'] = True
            click.echo("✅ Database statistics updated")
        
        # Vacuum (only for SQLite in development)
        if 'sqlite' in str(db.engine.url):
            if DatabaseMaintenanceManager.vacuum_database():
                results['vacuum_completed'] = True
                click.echo("✅ Database vacuumed")
    
    # Summary
    click.echo(f"\n🎯 Optimization Summary:")
    click.echo(f"Indexes created: {results['indexes_created']}")
    click.echo(f"Queries analyzed: {results['optimizations_found']}")
    click.echo(f"Cache cleared: {'Yes' if results['cache_cleared'] else 'No'}")
    click.echo(f"Statistics updated: {'Yes' if results['stats_updated'] else 'No'}")
    click.echo(f"Database vacuumed: {'Yes' if results['vacuum_completed'] else 'No'}")
    
    if not auto_apply:
        click.echo("\n💡 Use --auto-apply to automatically perform safe maintenance tasks")


def register_cli_commands(app: Flask):
    """Register database optimization CLI commands."""
    app.cli.add_command(db_optimize)