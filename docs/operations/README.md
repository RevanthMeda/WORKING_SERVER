# SAT Report Generator - Operations Guide

## Overview

This operations guide provides comprehensive instructions for managing, monitoring, and maintaining the SAT Report Generator application in production environments. It covers day-to-day operational tasks, monitoring procedures, troubleshooting, and maintenance activities.

## Table of Contents

1. [System Monitoring](#system-monitoring)
2. [Performance Management](#performance-management)
3. [Security Operations](#security-operations)
4. [Backup and Recovery](#backup-and-recovery)
5. [Maintenance Procedures](#maintenance-procedures)
6. [Incident Response](#incident-response)
7. [Capacity Planning](#capacity-planning)
8. [Troubleshooting Guide](#troubleshooting-guide)
9. [Runbooks](#runbooks)
10. [Alerting and Notifications](#alerting-and-notifications)

## System Monitoring

### Health Checks

**Application Health Endpoint:**
```bash
# Basic health check
curl -f http://localhost:5000/health

# Detailed health check with dependencies
curl -f http://localhost:5000/health/detailed
```

**Expected Response:**
```json
{
  "status": "healthy",
  "timestamp": "2023-01-01T00:00:00Z",
  "version": "1.0.0",
  "checks": {
    "database": "healthy",
    "redis": "healthy",
    "disk_space": "healthy",
    "memory": "healthy"
  },
  "metrics": {
    "uptime": 86400,
    "active_connections": 25,
    "memory_usage": "512MB",
    "disk_usage": "45%"
  }
}
```

### Monitoring Dashboards

**Key Metrics to Monitor:**

1. **Application Metrics:**
   - Request rate (requests/second)
   - Response time (95th percentile)
   - Error rate (4xx/5xx responses)
   - Active users
   - Report generation time

2. **Infrastructure Metrics:**
   - CPU utilization
   - Memory usage
   - Disk I/O
   - Network traffic
   - Database connections

3. **Business Metrics:**
   - Reports created per day
   - User registrations
   - Approval workflow times
   - File upload volumes

**Grafana Dashboard Queries:**

```promql
# Request rate
rate(http_requests_total[5m])

# Response time 95th percentile
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# Error rate
rate(http_requests_total{status=~"4..|5.."}[5m]) / rate(http_requests_total[5m])

# Active database connections
pg_stat_activity_count

# Memory usage
process_resident_memory_bytes / 1024 / 1024
```

### Log Monitoring

**Log Levels and Patterns:**

```bash
# Critical errors
grep -i "CRITICAL\|FATAL" /app/logs/app.log

# Authentication failures
grep "authentication failed\|login failed" /app/logs/app.log

# Database errors
grep -i "database\|postgresql\|connection" /app/logs/app.log | grep -i error

# Performance issues
grep "slow query\|timeout\|performance" /app/logs/app.log
```

**Log Analysis Commands:**
```bash
# Top error messages
grep ERROR /app/logs/app.log | awk '{print $5}' | sort | uniq -c | sort -nr | head -10

# Request volume by hour
grep "$(date +%Y-%m-%d)" /app/logs/app.log | awk '{print $2}' | cut -d: -f1 | sort | uniq -c

# Failed login attempts
grep "login failed" /app/logs/app.log | awk '{print $6}' | sort | uniq -c | sort -nr
```

## Performance Management

### Performance Monitoring

**Key Performance Indicators (KPIs):**

| Metric | Target | Warning | Critical |
|--------|--------|---------|----------|
| Response Time (95th) | < 500ms | > 1s | > 2s |
| Error Rate | < 0.1% | > 1% | > 5% |
| CPU Usage | < 70% | > 80% | > 90% |
| Memory Usage | < 80% | > 90% | > 95% |
| Database Connections | < 50 | > 80 | > 95 |

**Performance Testing:**
```bash
# Load testing with Apache Bench
ab -n 1000 -c 10 -H "Authorization: Bearer $TOKEN" \
   http://localhost:5000/api/v1/reports

# Stress testing with wrk
wrk -t12 -c400 -d30s --header "Authorization: Bearer $TOKEN" \
    http://localhost:5000/api/v1/reports
```

### Database Performance

**Query Performance Analysis:**
```sql
-- Slow queries
SELECT query, calls, total_time, mean_time, rows
FROM pg_stat_statements
WHERE mean_time > 100
ORDER BY total_time DESC
LIMIT 10;

-- Index usage
SELECT schemaname, tablename, attname, n_distinct, correlation
FROM pg_stats
WHERE tablename = 'reports'
ORDER BY n_distinct DESC;

-- Connection statistics
SELECT state, count(*)
FROM pg_stat_activity
GROUP BY state;
```

**Database Optimization:**
```sql
-- Update table statistics
ANALYZE;

-- Reindex if needed
REINDEX INDEX CONCURRENTLY idx_reports_status;

-- Vacuum to reclaim space
VACUUM ANALYZE reports;
```

### Cache Performance

**Redis Monitoring:**
```bash
# Redis info
redis-cli info memory
redis-cli info stats
redis-cli info keyspace

# Cache hit rate
redis-cli info stats | grep keyspace_hits
redis-cli info stats | grep keyspace_misses

# Memory usage
redis-cli info memory | grep used_memory_human
```

**Cache Optimization:**
```bash
# Clear expired keys
redis-cli --scan --pattern "expired:*" | xargs redis-cli del

# Monitor slow operations
redis-cli slowlog get 10

# Set memory policy
redis-cli config set maxmemory-policy allkeys-lru
```

## Security Operations

### Security Monitoring

**Security Events to Monitor:**
- Failed login attempts
- Privilege escalation attempts
- Unusual API access patterns
- File upload anomalies
- Database access violations

**Security Log Analysis:**
```bash
# Failed authentication attempts
grep "authentication failed" /app/logs/audit.log | \
  awk '{print $6}' | sort | uniq -c | sort -nr | head -20

# Suspicious API calls
grep "403\|401" /app/logs/app.log | \
  grep -E "admin|delete|sensitive" | tail -50

# File upload monitoring
grep "file upload" /app/logs/app.log | \
  grep -E "\.exe|\.bat|\.sh|\.php" | tail -20
```

### Vulnerability Management

**Security Scanning:**
```bash
# Container vulnerability scan
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy image sat-report-generator:latest

# Dependency vulnerability scan
pip-audit --requirement requirements.txt

# SAST scanning
bandit -r SERVER/ -f json -o security-report.json
```

**Security Updates:**
```bash
# Update base image
docker pull python:3.11-slim
docker build --no-cache -t sat-report-generator:latest .

# Update dependencies
pip-compile --upgrade requirements.in
pip install -r requirements.txt

# Security patches
apt-get update && apt-get upgrade -y
```

### Access Control Audit

**User Access Review:**
```sql
-- Active users by role
SELECT role, COUNT(*) as count, 
       COUNT(CASE WHEN last_login > NOW() - INTERVAL '30 days' THEN 1 END) as active_30d
FROM users 
WHERE is_active = true 
GROUP BY role;

-- Users with admin privileges
SELECT id, email, full_name, last_login, created_at
FROM users 
WHERE role = 'Admin' AND is_active = true
ORDER BY last_login DESC;

-- Inactive users
SELECT id, email, full_name, last_login
FROM users 
WHERE is_active = true 
  AND (last_login IS NULL OR last_login < NOW() - INTERVAL '90 days')
ORDER BY last_login ASC;
```

## Backup and Recovery

### Backup Procedures

**Daily Backup Script:**
```bash
#!/bin/bash
# daily-backup.sh

set -e

BACKUP_DIR="/backups/$(date +%Y%m%d)"
LOG_FILE="/var/log/backup.log"

echo "$(date): Starting daily backup" >> $LOG_FILE

# Create backup directory
mkdir -p $BACKUP_DIR

# Database backup
echo "$(date): Backing up database" >> $LOG_FILE
pg_dump -h $DB_HOST -U $DB_USER -d $DB_NAME \
  --format=custom --compress=9 \
  --file=$BACKUP_DIR/database.backup

# File uploads backup
echo "$(date): Backing up uploads" >> $LOG_FILE
tar -czf $BACKUP_DIR/uploads.tar.gz /app/uploads/

# Configuration backup
echo "$(date): Backing up configuration" >> $LOG_FILE
tar -czf $BACKUP_DIR/config.tar.gz /app/config/

# Upload to cloud storage
echo "$(date): Uploading to S3" >> $LOG_FILE
aws s3 sync $BACKUP_DIR s3://your-backup-bucket/daily/$(date +%Y%m%d)/

# Cleanup old backups (keep 30 days)
find /backups -type d -mtime +30 -exec rm -rf {} \;

echo "$(date): Backup completed successfully" >> $LOG_FILE
```

**Backup Verification:**
```bash
#!/bin/bash
# verify-backup.sh

BACKUP_FILE="/backups/$(date +%Y%m%d)/database.backup"

# Test database backup integrity
pg_restore --list $BACKUP_FILE > /dev/null

if [ $? -eq 0 ]; then
    echo "Backup verification successful"
else
    echo "Backup verification failed"
    exit 1
fi
```

### Recovery Procedures

**Database Recovery:**
```bash
#!/bin/bash
# restore-database.sh

BACKUP_FILE="$1"

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup_file>"
    exit 1
fi

# Stop application
docker-compose stop app

# Create recovery database
createdb -h $DB_HOST -U postgres recovery_db

# Restore to recovery database
pg_restore -h $DB_HOST -U $DB_USER -d recovery_db \
  --clean --if-exists $BACKUP_FILE

# Verify restoration
psql -h $DB_HOST -U $DB_USER -d recovery_db -c "SELECT COUNT(*) FROM reports;"

echo "Database restored to recovery_db. Review and rename if needed."
```

**Point-in-Time Recovery:**
```bash
#!/bin/bash
# point-in-time-recovery.sh

TARGET_TIME="$1"  # Format: 2023-01-01 12:00:00

# Stop application
docker-compose stop app

# Restore base backup
pg_restore -h $DB_HOST -U $DB_USER -d $DB_NAME \
  --clean --if-exists /backups/base/database.backup

# Apply WAL files up to target time
pg_ctl start -D /var/lib/postgresql/data \
  -o "-c recovery_target_time='$TARGET_TIME'"

echo "Point-in-time recovery completed to $TARGET_TIME"
```

## Maintenance Procedures

### Routine Maintenance

**Daily Tasks:**
```bash
#!/bin/bash
# daily-maintenance.sh

# Check disk space
df -h | awk '$5 > 80 {print "WARNING: " $0}'

# Check log file sizes
find /app/logs -name "*.log" -size +100M -exec ls -lh {} \;

# Database maintenance
psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "
  SELECT schemaname, tablename, n_dead_tup, n_live_tup,
         round(n_dead_tup::float / (n_live_tup + n_dead_tup) * 100, 2) as dead_ratio
  FROM pg_stat_user_tables
  WHERE n_dead_tup > 1000
  ORDER BY dead_ratio DESC;
"

# Clear old sessions
redis-cli --scan --pattern "session:*" | \
  xargs -I {} redis-cli ttl {} | \
  awk '$1 < 0 {print "Expired session found"}'
```

**Weekly Tasks:**
```bash
#!/bin/bash
# weekly-maintenance.sh

# Database vacuum and analyze
psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "VACUUM ANALYZE;"

# Update database statistics
psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "
  SELECT schemaname, tablename, last_vacuum, last_autovacuum, last_analyze
  FROM pg_stat_user_tables
  ORDER BY last_analyze ASC;
"

# Log rotation
logrotate -f /etc/logrotate.d/sat-reports

# Security scan
docker run --rm -v $(pwd):/app \
  securecodewarrior/docker-security-scan:latest /app
```

**Monthly Tasks:**
```bash
#!/bin/bash
# monthly-maintenance.sh

# Full database backup
pg_dump -h $DB_HOST -U $DB_USER -d $DB_NAME \
  --format=custom --compress=9 \
  --file=/backups/monthly/database-$(date +%Y%m).backup

# Archive old logs
tar -czf /archives/logs-$(date +%Y%m).tar.gz /app/logs/*.log.1
rm -f /app/logs/*.log.1

# Update SSL certificates
certbot renew --quiet

# Performance report
echo "Monthly Performance Report - $(date +%Y-%m)" > /reports/performance-$(date +%Y%m).txt
echo "=================================" >> /reports/performance-$(date +%Y%m).txt
echo "" >> /reports/performance-$(date +%Y%m).txt

# Add performance metrics to report
curl -s http://localhost:5000/metrics | grep -E "http_requests_total|http_request_duration" >> /reports/performance-$(date +%Y%m).txt
```

### Application Updates

**Update Procedure:**
```bash
#!/bin/bash
# update-application.sh

VERSION="$1"

if [ -z "$VERSION" ]; then
    echo "Usage: $0 <version>"
    exit 1
fi

# Pre-update backup
./backup-database.sh

# Pull new image
docker pull sat-report-generator:$VERSION

# Update docker-compose.yml with new version
sed -i "s/sat-report-generator:.*/sat-report-generator:$VERSION/" docker-compose.yml

# Run database migrations
docker-compose run --rm app python manage_db.py migrate

# Rolling update
docker-compose up -d --no-deps app

# Health check
sleep 30
curl -f http://localhost:5000/health || {
    echo "Health check failed, rolling back"
    docker-compose up -d --no-deps app:previous
    exit 1
}

echo "Update to version $VERSION completed successfully"
```

## Incident Response

### Incident Classification

**Severity Levels:**

| Level | Description | Response Time | Examples |
|-------|-------------|---------------|----------|
| P1 - Critical | Service down | 15 minutes | Complete outage, data loss |
| P2 - High | Major functionality impacted | 1 hour | Login failures, slow performance |
| P3 - Medium | Minor functionality impacted | 4 hours | Non-critical features down |
| P4 - Low | Cosmetic or minor issues | 24 hours | UI glitches, documentation |

### Incident Response Procedures

**P1 - Critical Incident Response:**
```bash
#!/bin/bash
# critical-incident-response.sh

echo "CRITICAL INCIDENT DETECTED: $(date)"

# 1. Immediate assessment
curl -f http://localhost:5000/health || echo "Application health check failed"
docker-compose ps | grep -v "Up" && echo "Container issues detected"

# 2. Check dependencies
pg_isready -h $DB_HOST -p 5432 || echo "Database connection failed"
redis-cli ping || echo "Redis connection failed"

# 3. Check resources
df -h | awk '$5 > 95 {print "CRITICAL: Disk space: " $0}'
free -m | awk 'NR==2{printf "Memory Usage: %s/%sMB (%.2f%%)\n", $3,$2,$3*100/$2 }'

# 4. Recent changes
git log --oneline -10
docker images | head -5

# 5. Error analysis
tail -100 /app/logs/app.log | grep -i error
```

**Communication Template:**
```
INCIDENT ALERT - P1 Critical

Service: SAT Report Generator
Status: INVESTIGATING
Started: [TIMESTAMP]
Impact: [DESCRIPTION]

Current Actions:
- [ACTION 1]
- [ACTION 2]

Next Update: [TIME]
Incident Commander: [NAME]
```

### Recovery Procedures

**Service Recovery Checklist:**
1. ✅ Identify root cause
2. ✅ Implement immediate fix
3. ✅ Verify service restoration
4. ✅ Monitor for stability
5. ✅ Document incident
6. ✅ Schedule post-mortem

**Rollback Procedure:**
```bash
#!/bin/bash
# rollback.sh

PREVIOUS_VERSION="$1"

echo "Rolling back to version: $PREVIOUS_VERSION"

# Stop current version
docker-compose down

# Restore previous version
docker tag sat-report-generator:$PREVIOUS_VERSION sat-report-generator:latest

# Restore database if needed
if [ "$2" = "restore-db" ]; then
    pg_restore -h $DB_HOST -U $DB_USER -d $DB_NAME \
      --clean --if-exists /backups/pre-update/database.backup
fi

# Start previous version
docker-compose up -d

# Verify rollback
sleep 30
curl -f http://localhost:5000/health && echo "Rollback successful"
```

## Capacity Planning

### Resource Monitoring

**Capacity Metrics:**
```bash
#!/bin/bash
# capacity-report.sh

echo "Capacity Report - $(date)"
echo "========================="

# CPU usage trend
echo "CPU Usage (last 24h):"
sar -u 1 1 | tail -1

# Memory usage
echo "Memory Usage:"
free -h

# Disk usage
echo "Disk Usage:"
df -h | grep -E "/$|/app|/var"

# Database size
echo "Database Size:"
psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "
  SELECT pg_size_pretty(pg_database_size('$DB_NAME')) as database_size;
"

# Connection pool usage
echo "Database Connections:"
psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "
  SELECT state, count(*) FROM pg_stat_activity GROUP BY state;
"

# Redis memory usage
echo "Redis Memory:"
redis-cli info memory | grep used_memory_human
```

### Scaling Decisions

**Horizontal Scaling Triggers:**
- CPU usage > 70% for 15 minutes
- Memory usage > 80% for 10 minutes
- Response time > 1s for 5 minutes
- Error rate > 1% for 5 minutes

**Vertical Scaling Triggers:**
- Database connections > 80% of max
- Disk I/O wait > 20%
- Memory pressure causing swapping

**Scaling Commands:**
```bash
# Kubernetes horizontal scaling
kubectl scale deployment sat-report-generator --replicas=5 -n sat-reports

# Docker Compose scaling
docker-compose up -d --scale app=3

# Database connection pool scaling
# Update DATABASE_POOL_SIZE environment variable
```

## Troubleshooting Guide

### Common Issues

**Issue: Application Won't Start**
```bash
# Diagnosis
docker-compose logs app | tail -50
docker-compose ps

# Common causes and solutions:
# 1. Database connection
psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "SELECT 1;"

# 2. Missing environment variables
docker-compose exec app env | grep -E "DATABASE_URL|SECRET_KEY|REDIS_URL"

# 3. Port conflicts
netstat -tulpn | grep :5000

# 4. File permissions
ls -la /app/uploads/
```

**Issue: Slow Performance**
```bash
# Diagnosis
curl -w "@curl-format.txt" -o /dev/null -s http://localhost:5000/api/v1/reports

# Database performance
psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "
  SELECT query, calls, total_time, mean_time
  FROM pg_stat_statements
  ORDER BY total_time DESC
  LIMIT 5;
"

# Cache performance
redis-cli info stats | grep -E "keyspace_hits|keyspace_misses"

# System resources
top -bn1 | head -20
iostat -x 1 1
```

**Issue: High Memory Usage**
```bash
# Diagnosis
ps aux --sort=-%mem | head -10
docker stats --no-stream

# Memory leaks detection
valgrind --tool=memcheck --leak-check=full python app.py

# Database memory
psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "
  SELECT setting, unit FROM pg_settings WHERE name = 'shared_buffers';
"
```

### Diagnostic Tools

**Application Diagnostics:**
```bash
# Health check with details
curl -s http://localhost:5000/health/detailed | jq .

# Metrics endpoint
curl -s http://localhost:5000/metrics | grep -E "http_requests|memory|cpu"

# Database connection test
python -c "
from sqlalchemy import create_engine
engine = create_engine('$DATABASE_URL')
conn = engine.connect()
result = conn.execute('SELECT version()')
print(result.fetchone())
conn.close()
"
```

**System Diagnostics:**
```bash
# System information
uname -a
lscpu
free -h
df -h

# Network connectivity
ping -c 3 $DB_HOST
telnet $DB_HOST 5432
nslookup $DB_HOST

# Process information
ps aux | grep -E "python|postgres|redis"
lsof -i :5000
```

## Runbooks

### Database Maintenance Runbook

**Objective:** Perform routine database maintenance
**Frequency:** Weekly
**Duration:** 30 minutes
**Prerequisites:** Database backup completed

**Steps:**
1. Check database statistics
2. Identify tables needing vacuum
3. Perform vacuum analyze
4. Update index statistics
5. Check for unused indexes
6. Verify backup integrity

**Commands:**
```sql
-- Step 1: Check statistics
SELECT schemaname, tablename, n_dead_tup, n_live_tup
FROM pg_stat_user_tables
WHERE n_dead_tup > 1000;

-- Step 2: Vacuum analyze
VACUUM ANALYZE;

-- Step 3: Check index usage
SELECT schemaname, tablename, indexname, idx_scan
FROM pg_stat_user_indexes
WHERE idx_scan = 0;
```

### SSL Certificate Renewal Runbook

**Objective:** Renew SSL certificates
**Frequency:** Monthly (automated)
**Duration:** 10 minutes

**Steps:**
1. Check certificate expiration
2. Renew certificates
3. Reload web server
4. Verify certificate validity

**Commands:**
```bash
# Check expiration
openssl x509 -in /etc/ssl/certs/sat-reports.crt -text -noout | grep "Not After"

# Renew with Let's Encrypt
certbot renew --quiet

# Reload nginx
nginx -s reload

# Verify
curl -I https://reports.yourdomain.com
```

## Alerting and Notifications

### Alert Rules

**Prometheus Alert Rules:**
```yaml
# alert-rules.yml
groups:
  - name: sat-report-generator
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value }} errors per second"

      - alert: HighResponseTime
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 2
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High response time detected"
          description: "95th percentile response time is {{ $value }}s"

      - alert: DatabaseConnectionHigh
        expr: pg_stat_activity_count > 80
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "High database connection count"
          description: "Database has {{ $value }} active connections"
```

### Notification Channels

**Slack Integration:**
```bash
#!/bin/bash
# slack-notify.sh

WEBHOOK_URL="https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK"
MESSAGE="$1"
SEVERITY="$2"

case $SEVERITY in
    "critical")
        COLOR="danger"
        EMOJI=":rotating_light:"
        ;;
    "warning")
        COLOR="warning"
        EMOJI=":warning:"
        ;;
    *)
        COLOR="good"
        EMOJI=":information_source:"
        ;;
esac

curl -X POST -H 'Content-type: application/json' \
    --data "{
        \"attachments\": [{
            \"color\": \"$COLOR\",
            \"text\": \"$EMOJI $MESSAGE\",
            \"fields\": [{
                \"title\": \"Service\",
                \"value\": \"SAT Report Generator\",
                \"short\": true
            }, {
                \"title\": \"Environment\",
                \"value\": \"Production\",
                \"short\": true
            }]
        }]
    }" \
    $WEBHOOK_URL
```

**Email Alerts:**
```python
# email-alert.py
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_alert(subject, message, severity="info"):
    msg = MIMEMultipart()
    msg['From'] = "alerts@yourdomain.com"
    msg['To'] = "ops-team@yourdomain.com"
    msg['Subject'] = f"[{severity.upper()}] {subject}"
    
    body = f"""
    Alert: {subject}
    Severity: {severity}
    Time: {datetime.now()}
    
    Details:
    {message}
    
    Dashboard: https://grafana.yourdomain.com
    Logs: https://kibana.yourdomain.com
    """
    
    msg.attach(MIMEText(body, 'plain'))
    
    server = smtplib.SMTP('smtp.yourdomain.com', 587)
    server.starttls()
    server.login("alerts@yourdomain.com", "password")
    server.send_message(msg)
    server.quit()
```

This operations guide provides comprehensive procedures for managing the SAT Report Generator in production environments with proper monitoring, maintenance, and incident response capabilities.