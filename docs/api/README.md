# SAT Report Generator API Documentation

## Overview

The SAT Report Generator API is a comprehensive RESTful API that provides enterprise-grade functionality for managing Site Acceptance Testing (SAT) reports. This API enables organizations to streamline their testing documentation processes with robust security, scalability, and compliance features.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Authentication](#authentication)
3. [API Reference](#api-reference)
4. [Error Handling](#error-handling)
5. [Rate Limiting](#rate-limiting)
6. [Pagination](#pagination)
7. [Filtering and Search](#filtering-and-search)
8. [Webhooks](#webhooks)
9. [SDKs and Libraries](#sdks-and-libraries)
10. [Examples](#examples)
11. [Changelog](#changelog)

## Getting Started

### Base URL

The API is available at the following base URLs:

- **Production**: `https://api.satreportgenerator.com/api/v1`
- **Staging**: `https://staging-api.satreportgenerator.com/api/v1`
- **Development**: `http://localhost:5000/api/v1`

### API Version

Current API version: **v1.0.0**

The API uses URL-based versioning. All endpoints are prefixed with `/api/v1/`.

### Content Type

All API requests and responses use JSON format:
- Request Content-Type: `application/json`
- Response Content-Type: `application/json`

### Quick Start

1. **Register an account** or obtain API credentials
2. **Authenticate** using JWT tokens or API keys
3. **Make your first API call** to list reports
4. **Explore the interactive documentation** at `/api/v1/docs/`

```bash
# Example: Get list of reports
curl -X GET "https://api.satreportgenerator.com/api/v1/reports" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json"
```

## Authentication

The API supports multiple authentication methods to accommodate different use cases:

### JWT Bearer Tokens (Recommended)

JWT tokens are the preferred authentication method for web applications and mobile clients.

**Obtaining a token:**
```bash
curl -X POST "https://api.satreportgenerator.com/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "your_password"
  }'
```

**Using the token:**
```bash
curl -X GET "https://api.satreportgenerator.com/api/v1/reports" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

**Token Properties:**
- **Expiration**: 1 hour
- **Refresh**: Use `/auth/token/refresh` endpoint
- **Format**: `Bearer <jwt_token>`

### API Keys

API keys are ideal for server-to-server integrations and automated systems.

**Using API keys:**
```bash
curl -X GET "https://api.satreportgenerator.com/api/v1/reports" \
  -H "X-API-Key: sk_live_1234567890abcdef"
```

**API Key Properties:**
- **Format**: `sk_live_` or `sk_test_` prefix
- **Scopes**: Configurable permissions per key
- **Rate Limits**: Customizable per key
- **Management**: Contact your system administrator

### Multi-Factor Authentication (MFA)

For enhanced security, MFA can be enabled on user accounts:

```bash
# Login with MFA
curl -X POST "https://api.satreportgenerator.com/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "your_password",
    "mfa_token": "123456"
  }'
```

## API Reference

### Core Resources

#### Reports
- `GET /reports` - List reports
- `POST /reports` - Create report
- `GET /reports/{id}` - Get report
- `PUT /reports/{id}` - Update report
- `DELETE /reports/{id}` - Delete report
- `POST /reports/{id}/submit` - Submit for approval
- `POST /reports/{id}/approve` - Approve/reject report
- `POST /reports/{id}/generate` - Generate document
- `GET /reports/{id}/download` - Download document

#### Users
- `GET /users` - List users (admin only)
- `GET /users/{id}` - Get user
- `PUT /users/{id}` - Update user
- `DELETE /users/{id}` - Delete user (admin only)
- `GET /users/me` - Get current user profile
- `POST /users/{id}/approve` - Approve user (admin only)

#### Authentication
- `POST /auth/login` - User login
- `POST /auth/logout` - User logout
- `POST /auth/register` - User registration
- `POST /auth/token/refresh` - Refresh JWT token
- `POST /auth/mfa/setup` - Setup MFA
- `POST /auth/mfa/verify` - Verify MFA
- `POST /auth/password/change` - Change password

#### Files
- `POST /files/upload` - Upload file
- `GET /files/{id}` - Get file
- `DELETE /files/{id}` - Delete file
- `GET /files/{id}/download` - Download file

### Interactive Documentation

Explore the complete API reference with interactive examples:

- **Swagger UI**: `/api/v1/docs/swagger`
- **ReDoc**: `/api/v1/docs/redoc`
- **OpenAPI Spec**: `/api/v1/docs/openapi.json`
- **Postman Collection**: `/api/v1/docs/postman`

## Error Handling

The API uses standard HTTP status codes and returns detailed error information in a consistent format following RFC 7807 Problem Details.

### Error Response Format

```json
{
  "error": {
    "message": "Human readable error message",
    "status_code": 400,
    "code": "ERROR_CODE",
    "details": {
      "field": ["Specific validation error"]
    },
    "timestamp": "2023-01-01T00:00:00Z",
    "path": "/api/v1/reports",
    "correlation_id": "req_123456789"
  }
}
```

### Common HTTP Status Codes

| Code | Description | When it occurs |
|------|-------------|----------------|
| 200 | OK | Successful GET, PUT requests |
| 201 | Created | Successful POST requests |
| 204 | No Content | Successful DELETE requests |
| 400 | Bad Request | Invalid request data |
| 401 | Unauthorized | Authentication required |
| 403 | Forbidden | Access denied |
| 404 | Not Found | Resource not found |
| 409 | Conflict | Resource already exists |
| 422 | Unprocessable Entity | Validation errors |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server error |

### Error Codes

| Code | Description |
|------|-------------|
| `VALIDATION_ERROR` | Request validation failed |
| `AUTHENTICATION_REQUIRED` | Authentication token required |
| `ACCESS_DENIED` | Insufficient permissions |
| `NOT_FOUND` | Resource not found |
| `CONFLICT` | Resource already exists |
| `RATE_LIMIT_EXCEEDED` | Too many requests |
| `INTERNAL_ERROR` | Internal server error |

## Rate Limiting

The API implements rate limiting to ensure fair usage and system stability.

### Rate Limits

| Authentication Type | Requests per Hour | Burst Limit |
|-------------------|------------------|-------------|
| Authenticated Users | 1,000 | 100 |
| API Keys | Configurable | Configurable |
| Anonymous | 100 | 10 |

### Rate Limit Headers

Rate limit information is included in response headers:

```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1640995200
X-RateLimit-Window: 3600
```

### Handling Rate Limits

When rate limited, the API returns a 429 status code:

```json
{
  "error": {
    "message": "Rate limit exceeded",
    "status_code": 429,
    "code": "RATE_LIMIT_EXCEEDED",
    "details": {
      "retry_after": 3600
    }
  }
}
```

## Pagination

List endpoints support cursor-based pagination for optimal performance.

### Pagination Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | integer | 1 | Page number |
| `per_page` | integer | 20 | Items per page (max 100) |
| `sort_by` | string | created_at | Sort field |
| `sort_order` | string | desc | Sort direction (asc/desc) |

### Pagination Response

```json
{
  "data": [...],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 100,
    "pages": 5,
    "has_next": true,
    "has_prev": false,
    "next_page": 2,
    "prev_page": null
  }
}
```

### Example

```bash
curl -X GET "https://api.satreportgenerator.com/api/v1/reports?page=2&per_page=50&sort_by=updated_at&sort_order=asc" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Filtering and Search

Most list endpoints support filtering and full-text search capabilities.

### Common Filters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `search` | Full-text search | `?search=automation` |
| `status` | Filter by status | `?status=approved` |
| `created_by` | Filter by creator | `?created_by=user123` |
| `client` | Filter by client | `?client=acme` |
| `date_from` | Filter from date | `?date_from=2023-01-01` |
| `date_to` | Filter to date | `?date_to=2023-12-31` |

### Search Examples

```bash
# Search reports by title
curl -X GET "https://api.satreportgenerator.com/api/v1/reports?search=automation+testing" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Filter by status and client
curl -X GET "https://api.satreportgenerator.com/api/v1/reports?status=approved&client=acme" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Date range filter
curl -X GET "https://api.satreportgenerator.com/api/v1/reports?date_from=2023-01-01&date_to=2023-12-31" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Webhooks

Webhooks allow your application to receive real-time notifications about events in the SAT Report Generator system.

### Supported Events

| Event | Description |
|-------|-------------|
| `report.created` | New report created |
| `report.updated` | Report updated |
| `report.submitted` | Report submitted for approval |
| `report.approved` | Report approved |
| `report.rejected` | Report rejected |
| `report.generated` | Report document generated |
| `user.registered` | New user registered |
| `user.approved` | User account approved |

### Webhook Payload

```json
{
  "event": "report.approved",
  "timestamp": "2023-01-01T00:00:00Z",
  "data": {
    "report": {
      "id": "report_123",
      "document_title": "SAT Report for Project Alpha",
      "status": "approved"
    },
    "approved_by": {
      "id": "user_456",
      "full_name": "John Doe"
    }
  }
}
```

### Webhook Security

Webhooks are secured using HMAC-SHA256 signatures:

```python
import hmac
import hashlib

def verify_webhook(payload, signature, secret):
    expected = hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)
```

## SDKs and Libraries

Official SDKs are available for popular programming languages:

### Python SDK

```bash
pip install sat-report-generator-sdk
```

```python
from sat_report_generator import Client

client = Client(api_key="your_api_key")
reports = client.reports.list()
```

### JavaScript/Node.js SDK

```bash
npm install sat-report-generator-sdk
```

```javascript
const { SATReportClient } = require('sat-report-generator-sdk');

const client = new SATReportClient({ apiKey: 'your_api_key' });
const reports = await client.reports.list();
```

### cURL Examples

Complete cURL examples are available in our [examples repository](https://github.com/sat-report-generator/api-examples).

## Examples

### Creating a Report

```bash
curl -X POST "https://api.satreportgenerator.com/api/v1/reports" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "document_title": "SAT Report for Project Alpha",
    "document_reference": "DOC-2023-001",
    "project_reference": "PROJ-ALPHA-2023",
    "client_name": "Acme Corporation",
    "revision": "R1",
    "prepared_by": "John Doe",
    "date": "2023-01-01",
    "purpose": "Site Acceptance Testing for new automation system",
    "scope": "Testing of PLC, SCADA, and HMI systems"
  }'
```

### Approval Workflow

```bash
# Submit report for approval
curl -X POST "https://api.satreportgenerator.com/api/v1/reports/report_123/submit" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Approve report
curl -X POST "https://api.satreportgenerator.com/api/v1/reports/report_123/approve" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "approve",
    "comments": "Report looks good, approved for generation"
  }'
```

### File Upload

```bash
curl -X POST "https://api.satreportgenerator.com/api/v1/files/upload" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@/path/to/document.pdf" \
  -F "report_id=report_123" \
  -F "file_type=attachment"
```

## Changelog

### v1.0.0 (Current)
- Initial API release
- Core report management functionality
- User authentication and authorization
- File upload and management
- Approval workflows
- Multi-factor authentication support
- Comprehensive error handling
- Rate limiting and security features

### Upcoming Features
- Real-time notifications via WebSockets
- Advanced reporting and analytics
- Bulk operations support
- Enhanced search capabilities
- Additional file format support

## Support

For API support and questions:

- **Email**: api-support@satreportgenerator.com
- **Documentation**: https://docs.satreportgenerator.com
- **Status Page**: https://status.satreportgenerator.com
- **GitHub Issues**: https://github.com/sat-report-generator/api/issues

## Legal

- **Terms of Service**: https://satreportgenerator.com/terms
- **Privacy Policy**: https://satreportgenerator.com/privacy
- **License**: Proprietary