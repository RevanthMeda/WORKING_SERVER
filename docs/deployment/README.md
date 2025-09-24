# SAT Report Generator - Deployment Guide

## Overview

This guide provides comprehensive instructions for deploying the SAT Report Generator application in various environments, from development to production. The application is designed to run in containerized environments using Docker and Kubernetes, with support for traditional deployment methods.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Docker Deployment](#docker-deployment)
4. [Kubernetes Deployment](#kubernetes-deployment)
5. [Production Deployment](#production-deployment)
6. [Configuration Management](#configuration-management)
7. [Database Setup](#database-setup)
8. [SSL/TLS Configuration](#ssltls-configuration)
9. [Monitoring and Logging](#monitoring-and-logging)
10. [Backup and Recovery](#backup-and-recovery)
11. [Troubleshooting](#troubleshooting)

## Prerequisites

### System Requirements

**Minimum Requirements:**
- CPU: 2 cores
- RAM: 4GB
- Storage: 20GB
- OS: Linux (Ubuntu 20.04+ recommended), Windows Server 2019+, macOS 10.15+

**Recommended for Production:**
- CPU: 4+ cores
- RAM: 8GB+
- Storage: 100GB+ SSD
- Load balancer (nginx, HAProxy, or cloud LB)
- Database server (PostgreSQL 12+ or MySQL 8+)
- Redis server for caching

### Software Dependencies

**Required:**
- Docker 20.10+
- Docker Compose 2.0+
- Python 3.11+ (for local development)
- Node.js 16+ (for frontend assets)

**Optional:**
- Kubernetes 1.21+
- Helm 3.0+
- Terraform 1.0+ (for infrastructure as code)

### Network Requirements

**Ports:**
- 5000: Application server (HTTP)
- 443: HTTPS (production)
- 80: HTTP redirect to HTTPS
- 5432: PostgreSQL (if using external DB)
- 6379: Redis (if using external cache)

**Firewall Rules:**
- Allow inbound traffic on ports 80, 443
- Allow outbound traffic for email (SMTP)
- Allow database connections from application servers
- Allow monitoring traffic (Prometheus, etc.)

## Environment Setup

### Development Environment

1. **Clone the repository:**
```bash
git clone https://github.com/your-org/sat-report-generator.git
cd sat-report-generator
```

2. **Set up environment variables:**
```bash
cp SERVER/.env.example SERVER/.env
# Edit .env with your configuration
```

3. **Start with Docker Compose:**
```bash
docker-compose -f docker-compose.dev.yml up -d
```

4. **Initialize the database:**
```bash
docker-compose exec app python manage_db.py init
docker-compose exec app python manage_db.py migrate
```

### Staging Environment

1. **Prepare environment configuration:**
```bash
# Create staging configuration
cp config/staging.yaml.example config/staging.yaml
# Edit staging.yaml with staging-specific settings
```

2. **Deploy using Docker Compose:**
```bash
docker-compose -f docker-compose.staging.yml up -d
```

3. **Run database migrations:**
```bash
docker-compose exec app python manage_db.py migrate
```

4. **Verify deployment:**
```bash
curl -f http://localhost:5000/health || echo "Health check failed"
```

## Docker Deployment

### Single Container Deployment

**Build the image:**
```bash
docker build -t sat-report-generator:latest .
```

**Run the container:**
```bash
docker run -d \
  --name sat-report-generator \
  -p 5000:5000 \
  -e DATABASE_URL="postgresql://user:pass@db:5432/satreports" \
  -e REDIS_URL="redis://redis:6379/0" \
  -e SECRET_KEY="your-secret-key" \
  -v /path/to/uploads:/app/uploads \
  sat-report-generator:latest
```

### Docker Compose Deployment

**Production docker-compose.yml:**
```yaml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "5000:5000"
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/satreports
      - REDIS_URL=redis://redis:6379/0
      - SECRET_KEY=${SECRET_KEY}
      - FLASK_ENV=production
    volumes:
      - uploads:/app/uploads
      - logs:/app/logs
    depends_on:
      - db
      - redis
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  db:
    image: postgres:14
    environment:
      - POSTGRES_DB=satreports
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./docker/nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./docker/nginx/default.conf:/etc/nginx/conf.d/default.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - app
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
  uploads:
  logs:
```

**Deploy:**
```bash
# Set environment variables
export SECRET_KEY="your-very-secure-secret-key"
export DB_PASSWORD="secure-database-password"

# Deploy
docker-compose up -d

# Check status
docker-compose ps
docker-compose logs -f app
```

## Kubernetes Deployment

### Prerequisites

1. **Kubernetes cluster** (1.21+)
2. **kubectl** configured
3. **Helm** installed (optional but recommended)

### Using Helm Charts

**Install with Helm:**
```bash
# Add the repository
helm repo add sat-report-generator https://charts.satreportgenerator.com
helm repo update

# Install
helm install sat-report-generator sat-report-generator/sat-report-generator \
  --namespace sat-reports \
  --create-namespace \
  --values values.production.yaml
```

**Custom values.yaml:**
```yaml
# values.production.yaml
replicaCount: 3

image:
  repository: sat-report-generator
  tag: "1.0.0"
  pullPolicy: IfNotPresent

service:
  type: ClusterIP
  port: 80

ingress:
  enabled: true
  className: "nginx"
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
  hosts:
    - host: reports.yourdomain.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: sat-reports-tls
      hosts:
        - reports.yourdomain.com

postgresql:
  enabled: true
  auth:
    postgresPassword: "secure-password"
    database: "satreports"
  primary:
    persistence:
      enabled: true
      size: 20Gi

redis:
  enabled: true
  auth:
    enabled: false
  master:
    persistence:
      enabled: true
      size: 8Gi

autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70
  targetMemoryUtilizationPercentage: 80

resources:
  limits:
    cpu: 1000m
    memory: 1Gi
  requests:
    cpu: 500m
    memory: 512Mi

nodeSelector: {}
tolerations: []
affinity: {}
```

### Manual Kubernetes Deployment

**Deploy using kubectl:**
```bash
# Create namespace
kubectl create namespace sat-reports

# Apply configurations
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/pvc.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml
kubectl apply -f k8s/hpa.yaml

# Check deployment
kubectl get pods -n sat-reports
kubectl get services -n sat-reports
kubectl get ingress -n sat-reports
```

**Monitor deployment:**
```bash
# Watch pods
kubectl get pods -n sat-reports -w

# Check logs
kubectl logs -f deployment/sat-report-generator -n sat-reports

# Port forward for testing
kubectl port-forward service/sat-report-generator 8080:80 -n sat-reports
```

## Production Deployment

### High Availability Setup

**Architecture Components:**
- Load Balancer (nginx/HAProxy/Cloud LB)
- Multiple application instances (3+ replicas)
- Database cluster (PostgreSQL with replication)
- Redis cluster for caching
- Shared storage for file uploads
- Monitoring and logging stack

**Load Balancer Configuration (nginx):**
```nginx
upstream sat_report_generator {
    least_conn;
    server app1:5000 max_fails=3 fail_timeout=30s;
    server app2:5000 max_fails=3 fail_timeout=30s;
    server app3:5000 max_fails=3 fail_timeout=30s;
}

server {
    listen 80;
    server_name reports.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name reports.yourdomain.com;

    ssl_certificate /etc/ssl/certs/sat-reports.crt;
    ssl_certificate_key /etc/ssl/private/sat-reports.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;
    ssl_prefer_server_ciphers off;

    location / {
        proxy_pass http://sat_report_generator;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Health check
        proxy_connect_timeout 5s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    location /health {
        access_log off;
        proxy_pass http://sat_report_generator;
    }
}
```

### Database Configuration

**PostgreSQL High Availability:**
```yaml
# postgresql-ha.yaml
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: postgres-cluster
  namespace: sat-reports
spec:
  instances: 3
  
  postgresql:
    parameters:
      max_connections: "200"
      shared_buffers: "256MB"
      effective_cache_size: "1GB"
      work_mem: "4MB"
      maintenance_work_mem: "64MB"
      
  bootstrap:
    initdb:
      database: satreports
      owner: satreports
      secret:
        name: postgres-credentials
        
  storage:
    size: 100Gi
    storageClass: fast-ssd
    
  monitoring:
    enabled: true
    
  backup:
    retentionPolicy: "30d"
    barmanObjectStore:
      destinationPath: "s3://backups/postgres"
      s3Credentials:
        accessKeyId:
          name: backup-credentials
          key: ACCESS_KEY_ID
        secretAccessKey:
          name: backup-credentials
          key: SECRET_ACCESS_KEY
```

### Security Hardening

**Application Security:**
```bash
# Run security scan
docker run --rm -v $(pwd):/app \
  securecodewarrior/docker-security-scan:latest \
  /app

# Update base image regularly
docker pull python:3.11-slim
docker build --no-cache -t sat-report-generator:latest .
```

**Network Security:**
```yaml
# network-policy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: sat-reports-network-policy
  namespace: sat-reports
spec:
  podSelector:
    matchLabels:
      app: sat-report-generator
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: ingress-nginx
    ports:
    - protocol: TCP
      port: 5000
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: postgresql
    ports:
    - protocol: TCP
      port: 5432
  - to:
    - podSelector:
        matchLabels:
          app: redis
    ports:
    - protocol: TCP
      port: 6379
```

## Configuration Management

### Environment Variables

**Required Environment Variables:**
```bash
# Application
SECRET_KEY=your-very-secure-secret-key-here
FLASK_ENV=production
DEBUG=false

# Database
DATABASE_URL=postgresql://user:pass@host:5432/dbname
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=30

# Redis
REDIS_URL=redis://host:6379/0
CACHE_DEFAULT_TIMEOUT=300

# Email
MAIL_SERVER=smtp.yourdomain.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=noreply@yourdomain.com
MAIL_PASSWORD=email-password

# File Storage
UPLOAD_FOLDER=/app/uploads
MAX_CONTENT_LENGTH=16777216  # 16MB

# Security
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_HTTPONLY=true
SESSION_COOKIE_SAMESITE=Lax
WTF_CSRF_TIME_LIMIT=3600

# Monitoring
PROMETHEUS_METRICS_ENABLED=true
LOG_LEVEL=INFO
```

### Configuration Files

**Production config (config/production.yaml):**
```yaml
# Application settings
app:
  name: "SAT Report Generator"
  version: "1.0.0"
  debug: false
  testing: false
  
# Database configuration
database:
  url: "${DATABASE_URL}"
  pool_size: 20
  max_overflow: 30
  pool_timeout: 30
  pool_recycle: 3600
  echo: false

# Cache configuration
cache:
  type: "redis"
  redis_url: "${REDIS_URL}"
  default_timeout: 300
  key_prefix: "sat_reports:"

# Security settings
security:
  secret_key: "${SECRET_KEY}"
  password_hash_method: "pbkdf2:sha256"
  password_salt_length: 16
  session_timeout: 3600
  max_login_attempts: 5
  lockout_duration: 900

# File upload settings
uploads:
  folder: "/app/uploads"
  max_file_size: 16777216  # 16MB
  allowed_extensions: ["pdf", "doc", "docx", "xls", "xlsx", "png", "jpg", "jpeg"]

# Email settings
mail:
  server: "${MAIL_SERVER}"
  port: 587
  use_tls: true
  username: "${MAIL_USERNAME}"
  password: "${MAIL_PASSWORD}"
  default_sender: "noreply@yourdomain.com"

# Monitoring settings
monitoring:
  prometheus_enabled: true
  metrics_port: 9090
  health_check_endpoint: "/health"
  
# Logging settings
logging:
  level: "INFO"
  format: "json"
  file: "/app/logs/app.log"
  max_bytes: 10485760  # 10MB
  backup_count: 5
```

## Database Setup

### PostgreSQL Setup

**Initialize database:**
```sql
-- Create database and user
CREATE DATABASE satreports;
CREATE USER satreports WITH PASSWORD 'secure-password';
GRANT ALL PRIVILEGES ON DATABASE satreports TO satreports;

-- Connect to database
\c satreports;

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";

-- Grant schema permissions
GRANT ALL ON SCHEMA public TO satreports;
```

**Run migrations:**
```bash
# Using Docker
docker-compose exec app python manage_db.py migrate

# Using kubectl
kubectl exec -it deployment/sat-report-generator -n sat-reports -- \
  python manage_db.py migrate

# Direct execution
cd SERVER
python manage_db.py migrate
```

**Database optimization:**
```sql
-- Create indexes for better performance
CREATE INDEX CONCURRENTLY idx_reports_status ON reports(status);
CREATE INDEX CONCURRENTLY idx_reports_created_by ON reports(created_by);
CREATE INDEX CONCURRENTLY idx_reports_created_at ON reports(created_at);
CREATE INDEX CONCURRENTLY idx_reports_search ON reports USING gin(to_tsvector('english', document_title || ' ' || client_name));

-- Update statistics
ANALYZE;
```

### Database Backup

**Automated backup script:**
```bash
#!/bin/bash
# backup-database.sh

BACKUP_DIR="/backups/postgres"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="satreports"
DB_USER="satreports"
DB_HOST="localhost"

# Create backup directory
mkdir -p $BACKUP_DIR

# Create backup
pg_dump -h $DB_HOST -U $DB_USER -d $DB_NAME \
  --verbose --clean --no-owner --no-privileges \
  --format=custom \
  --file=$BACKUP_DIR/satreports_$DATE.backup

# Compress backup
gzip $BACKUP_DIR/satreports_$DATE.backup

# Remove backups older than 30 days
find $BACKUP_DIR -name "*.backup.gz" -mtime +30 -delete

echo "Backup completed: satreports_$DATE.backup.gz"
```

**Cron job for automated backups:**
```bash
# Add to crontab
0 2 * * * /path/to/backup-database.sh >> /var/log/backup.log 2>&1
```

## SSL/TLS Configuration

### Let's Encrypt with Certbot

**Install Certbot:**
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install certbot python3-certbot-nginx

# CentOS/RHEL
sudo yum install certbot python3-certbot-nginx
```

**Obtain certificate:**
```bash
sudo certbot --nginx -d reports.yourdomain.com
```

**Auto-renewal:**
```bash
# Test renewal
sudo certbot renew --dry-run

# Add to crontab
0 12 * * * /usr/bin/certbot renew --quiet
```

### Manual SSL Certificate

**Generate CSR:**
```bash
openssl req -new -newkey rsa:2048 -nodes \
  -keyout sat-reports.key \
  -out sat-reports.csr \
  -subj "/C=US/ST=State/L=City/O=Organization/CN=reports.yourdomain.com"
```

**Install certificate:**
```bash
# Copy certificate files
sudo cp sat-reports.crt /etc/ssl/certs/
sudo cp sat-reports.key /etc/ssl/private/
sudo chmod 600 /etc/ssl/private/sat-reports.key
```

## Monitoring and Logging

### Prometheus Monitoring

**Prometheus configuration:**
```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "alert-rules.yml"

scrape_configs:
  - job_name: 'sat-report-generator'
    static_configs:
      - targets: ['app:5000']
    metrics_path: '/metrics'
    scrape_interval: 30s

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093
```

**Grafana Dashboard:**
```json
{
  "dashboard": {
    "title": "SAT Report Generator",
    "panels": [
      {
        "title": "Request Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(http_requests_total[5m])",
            "legendFormat": "{{method}} {{endpoint}}"
          }
        ]
      },
      {
        "title": "Response Time",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))",
            "legendFormat": "95th percentile"
          }
        ]
      }
    ]
  }
}
```

### Centralized Logging

**ELK Stack configuration:**
```yaml
# docker-compose.logging.yml
version: '3.8'

services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.5.0
    environment:
      - discovery.type=single-node
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
    volumes:
      - elasticsearch_data:/usr/share/elasticsearch/data

  logstash:
    image: docker.elastic.co/logstash/logstash:8.5.0
    volumes:
      - ./logstash/pipeline:/usr/share/logstash/pipeline
    depends_on:
      - elasticsearch

  kibana:
    image: docker.elastic.co/kibana/kibana:8.5.0
    ports:
      - "5601:5601"
    environment:
      - ELASTICSEARCH_HOSTS=http://elasticsearch:9200
    depends_on:
      - elasticsearch

volumes:
  elasticsearch_data:
```

## Backup and Recovery

### Application Backup Strategy

**Components to backup:**
1. Database (PostgreSQL)
2. File uploads
3. Configuration files
4. SSL certificates
5. Application logs

**Backup script:**
```bash
#!/bin/bash
# full-backup.sh

BACKUP_ROOT="/backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="$BACKUP_ROOT/sat-reports-$DATE"

mkdir -p $BACKUP_DIR

# Database backup
pg_dump -h localhost -U satreports satreports \
  --format=custom --file=$BACKUP_DIR/database.backup

# File uploads backup
tar -czf $BACKUP_DIR/uploads.tar.gz /app/uploads/

# Configuration backup
tar -czf $BACKUP_DIR/config.tar.gz /app/config/

# Create manifest
cat > $BACKUP_DIR/manifest.txt << EOF
Backup Date: $(date)
Database: database.backup
Uploads: uploads.tar.gz
Config: config.tar.gz
EOF

# Upload to S3 (optional)
aws s3 sync $BACKUP_DIR s3://your-backup-bucket/sat-reports/$DATE/

echo "Backup completed: $BACKUP_DIR"
```

### Disaster Recovery

**Recovery procedure:**
```bash
#!/bin/bash
# restore.sh

BACKUP_DIR="/backups/sat-reports-20231201_020000"

# Stop application
docker-compose down

# Restore database
pg_restore -h localhost -U satreports -d satreports \
  --clean --if-exists $BACKUP_DIR/database.backup

# Restore uploads
tar -xzf $BACKUP_DIR/uploads.tar.gz -C /

# Restore configuration
tar -xzf $BACKUP_DIR/config.tar.gz -C /

# Start application
docker-compose up -d

echo "Recovery completed"
```

## Troubleshooting

### Common Issues

**Application won't start:**
```bash
# Check logs
docker-compose logs app

# Common causes:
# 1. Database connection issues
# 2. Missing environment variables
# 3. Port conflicts
# 4. Permission issues

# Debug steps:
docker-compose exec app python -c "from app import create_app; app = create_app(); print('App created successfully')"
```

**Database connection errors:**
```bash
# Test database connection
docker-compose exec app python -c "
from models import db
from app import create_app
app = create_app()
with app.app_context():
    try:
        db.engine.execute('SELECT 1')
        print('Database connection successful')
    except Exception as e:
        print(f'Database connection failed: {e}')
"
```

**Performance issues:**
```bash
# Check resource usage
docker stats

# Check database performance
docker-compose exec db psql -U postgres -d satreports -c "
SELECT query, calls, total_time, mean_time 
FROM pg_stat_statements 
ORDER BY total_time DESC 
LIMIT 10;
"

# Check application metrics
curl http://localhost:5000/metrics
```

### Health Checks

**Application health check:**
```bash
#!/bin/bash
# health-check.sh

URL="http://localhost:5000/health"
TIMEOUT=10

response=$(curl -s -o /dev/null -w "%{http_code}" --max-time $TIMEOUT $URL)

if [ $response -eq 200 ]; then
    echo "Health check passed"
    exit 0
else
    echo "Health check failed with status: $response"
    exit 1
fi
```

**Database health check:**
```bash
#!/bin/bash
# db-health-check.sh

DB_HOST="localhost"
DB_PORT="5432"
DB_NAME="satreports"
DB_USER="satreports"

pg_isready -h $DB_HOST -p $DB_PORT -d $DB_NAME -U $DB_USER

if [ $? -eq 0 ]; then
    echo "Database is ready"
    exit 0
else
    echo "Database is not ready"
    exit 1
fi
```

### Log Analysis

**Common log patterns:**
```bash
# Error analysis
grep -i error /app/logs/app.log | tail -20

# Performance analysis
grep "slow query" /app/logs/app.log

# Security analysis
grep -i "authentication\|authorization\|login" /app/logs/app.log
```

**Log rotation:**
```bash
# logrotate configuration
cat > /etc/logrotate.d/sat-reports << EOF
/app/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 app app
    postrotate
        docker-compose exec app kill -USR1 1
    endscript
}
EOF
```

This deployment guide provides comprehensive instructions for deploying the SAT Report Generator in various environments with proper security, monitoring, and backup procedures.