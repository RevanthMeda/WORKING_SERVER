"""
Marshmallow schemas for API request/response serialization.
"""
from marshmallow import Schema, fields, validates, ValidationError, post_load
from datetime import datetime
import re


class BaseSchema(Schema):
    """Base schema with common functionality."""
    
    class Meta:
        ordered = True
        strict = True
    
    @post_load
    def strip_strings(self, data, **kwargs):
        """Strip whitespace from string fields."""
        for key, value in data.items():
            if isinstance(value, str):
                data[key] = value.strip()
        return data


class PaginationSchema(BaseSchema):
    """Schema for pagination parameters."""
    
    page = fields.Integer(load_default=1, validate=lambda x: x >= 1)
    per_page = fields.Integer(load_default=20, validate=lambda x: 1 <= x <= 100)
    search = fields.String(load_default='')
    sort_by = fields.String(load_default='created_at')
    sort_order = fields.String(load_default='desc', validate=lambda x: x in ['asc', 'desc'])


class UserSchema(BaseSchema):
    """User serialization schema."""
    
    id = fields.String(dump_only=True)
    email = fields.Email(required=True)
    full_name = fields.String(required=True, validate=lambda x: 2 <= len(x.strip()) <= 100)
    role = fields.String(required=True, validate=lambda x: x in ['Engineer', 'Admin', 'PM', 'Automation Manager'])
    is_active = fields.Boolean(dump_only=True)
    is_approved = fields.Boolean(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    last_login = fields.DateTime(dump_only=True)
    
    @validates('full_name')
    def validate_full_name(self, value):
        if not re.match(r'^[a-zA-Z\s\-\.]+$', value.strip()):
            raise ValidationError('Full name contains invalid characters')


class UserRegistrationSchema(BaseSchema):
    """User registration schema."""
    
    email = fields.Email(required=True)
    full_name = fields.String(required=True, validate=lambda x: 2 <= len(x.strip()) <= 100)
    password = fields.String(required=True, validate=lambda x: len(x) >= 12, load_only=True)
    requested_role = fields.String(required=True, validate=lambda x: x in ['Engineer', 'Admin', 'PM', 'Automation Manager'])
    
    @validates('password')
    def validate_password(self, value):
        from security.authentication import PasswordPolicy
        is_valid, errors = PasswordPolicy.validate_password(value)
        if not is_valid:
            raise ValidationError(errors)


class UserUpdateSchema(BaseSchema):
    """User update schema."""
    
    full_name = fields.String(validate=lambda x: 2 <= len(x.strip()) <= 100)
    role = fields.String(validate=lambda x: x in ['Engineer', 'Admin', 'PM', 'Automation Manager'])
    is_active = fields.Boolean()
    is_approved = fields.Boolean()


class LoginSchema(BaseSchema):
    """Login request schema."""
    
    email = fields.Email(required=True)
    password = fields.String(required=True, load_only=True)
    remember_me = fields.Boolean(load_default=False)
    mfa_token = fields.String()


class TokenResponseSchema(BaseSchema):
    """Token response schema."""
    
    access_token = fields.String()
    token_type = fields.String()
    expires_in = fields.Integer()
    user = fields.Nested(UserSchema)


class ReportSchema(BaseSchema):
    """Report serialization schema."""
    
    id = fields.String(dump_only=True)
    document_title = fields.String(required=True, validate=lambda x: 5 <= len(x.strip()) <= 200)
    document_reference = fields.String(required=True, validate=lambda x: 3 <= len(x.strip()) <= 50)
    project_reference = fields.String(required=True, validate=lambda x: 3 <= len(x.strip()) <= 50)
    client_name = fields.String(required=True, validate=lambda x: 2 <= len(x.strip()) <= 100)
    revision = fields.String(required=True, validate=lambda x: len(x.strip()) <= 10)
    prepared_by = fields.String(required=True, validate=lambda x: 2 <= len(x.strip()) <= 100)
    date = fields.Date(required=True)
    purpose = fields.String(required=True, validate=lambda x: 10 <= len(x.strip()) <= 1000)
    scope = fields.String(required=True, validate=lambda x: 10 <= len(x.strip()) <= 2000)
    status = fields.String(dump_only=True)
    created_by = fields.String(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)
    
    @validates('document_reference')
    def validate_document_reference(self, value):
        if not re.match(r'^[A-Z0-9\-_]+$', value.upper()):
            raise ValidationError('Document reference must contain only letters, numbers, hyphens, and underscores')
    
    @validates('project_reference')
    def validate_project_reference(self, value):
        if not re.match(r'^[A-Z0-9\-_]+$', value.upper()):
            raise ValidationError('Project reference must contain only letters, numbers, hyphens, and underscores')


class ReportCreateSchema(BaseSchema):
    """Report creation schema."""
    
    document_title = fields.String(required=True, validate=lambda x: 5 <= len(x.strip()) <= 200)
    document_reference = fields.String(required=True, validate=lambda x: 3 <= len(x.strip()) <= 50)
    project_reference = fields.String(required=True, validate=lambda x: 3 <= len(x.strip()) <= 50)
    client_name = fields.String(required=True, validate=lambda x: 2 <= len(x.strip()) <= 100)
    revision = fields.String(required=True, validate=lambda x: len(x.strip()) <= 10)
    prepared_by = fields.String(required=True, validate=lambda x: 2 <= len(x.strip()) <= 100)
    date = fields.Date(required=True)
    purpose = fields.String(required=True, validate=lambda x: 10 <= len(x.strip()) <= 1000)
    scope = fields.String(required=True, validate=lambda x: 10 <= len(x.strip()) <= 2000)


class ReportUpdateSchema(BaseSchema):
    """Report update schema."""
    
    document_title = fields.String(validate=lambda x: 5 <= len(x.strip()) <= 200)
    document_reference = fields.String(validate=lambda x: 3 <= len(x.strip()) <= 50)
    project_reference = fields.String(validate=lambda x: 3 <= len(x.strip()) <= 50)
    client_name = fields.String(validate=lambda x: 2 <= len(x.strip()) <= 100)
    revision = fields.String(validate=lambda x: len(x.strip()) <= 10)
    prepared_by = fields.String(validate=lambda x: 2 <= len(x.strip()) <= 100)
    date = fields.Date()
    purpose = fields.String(validate=lambda x: 10 <= len(x.strip()) <= 1000)
    scope = fields.String(validate=lambda x: 10 <= len(x.strip()) <= 2000)


class ReportListSchema(BaseSchema):
    """Report list response schema."""
    
    reports = fields.List(fields.Nested(ReportSchema))
    total = fields.Integer()
    page = fields.Integer()
    per_page = fields.Integer()
    pages = fields.Integer()


class ApprovalSchema(BaseSchema):
    """Approval request schema."""
    
    action = fields.String(required=True, validate=lambda x: x in ['approve', 'reject'])
    comments = fields.String()


class FileUploadSchema(BaseSchema):
    """File upload schema."""
    
    filename = fields.String(required=True)
    file_size = fields.Integer(required=True)
    content_type = fields.String(required=True)
    
    @validates('filename')
    def validate_filename(self, value):
        from security.validation import InputValidator
        is_valid, error = InputValidator.validate_filename(value)
        if not is_valid:
            raise ValidationError(error)
    
    @validates('file_size')
    def validate_file_size(self, value):
        from security.validation import InputValidator
        is_valid, error = InputValidator.validate_file_size(value)
        if not is_valid:
            raise ValidationError(error)
    
    @validates('content_type')
    def validate_content_type(self, value):
        allowed_types = [
            'image/png', 'image/jpeg', 'image/gif', 'image/webp',
            'application/pdf', 
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/msword'
        ]
        if value not in allowed_types:
            raise ValidationError(f'Content type not allowed. Allowed types: {", ".join(allowed_types)}')


class PasswordChangeSchema(BaseSchema):
    """Password change schema."""
    
    current_password = fields.String(required=True, load_only=True)
    new_password = fields.String(required=True, load_only=True)
    
    @validates('new_password')
    def validate_new_password(self, value):
        from security.authentication import PasswordPolicy
        is_valid, errors = PasswordPolicy.validate_password(value)
        if not is_valid:
            raise ValidationError(errors)


class MFASetupSchema(BaseSchema):
    """MFA setup response schema."""
    
    secret = fields.String()
    qr_code_url = fields.String()
    backup_codes = fields.List(fields.String())


class MFAVerifySchema(BaseSchema):
    """MFA verification schema."""
    
    token = fields.String(required=True, validate=lambda x: len(x) == 6 and x.isdigit())


class StatsSchema(BaseSchema):
    """Statistics response schema."""
    
    total_reports = fields.Integer()
    draft_reports = fields.Integer()
    pending_approval = fields.Integer()
    approved_reports = fields.Integer()
    generated_reports = fields.Integer()
    rejected_reports = fields.Integer()


class UserStatsSchema(BaseSchema):
    """User statistics response schema."""
    
    total_users = fields.Integer()
    active_users = fields.Integer()
    inactive_users = fields.Integer()
    pending_approval = fields.Integer()
    role_distribution = fields.Dict()


class AuditLogSchema(BaseSchema):
    """Audit log schema."""
    
    id = fields.String()
    event_type = fields.String()
    severity = fields.String()
    user_id = fields.String()
    session_id = fields.String()
    ip_address = fields.String()
    user_agent = fields.String()
    resource_type = fields.String()
    resource_id = fields.String()
    action = fields.String()
    details = fields.Dict()
    timestamp = fields.DateTime()
    checksum = fields.String()


class HealthCheckSchema(BaseSchema):
    """Health check response schema."""
    
    status = fields.String()
    timestamp = fields.DateTime()
    version = fields.String()
    database = fields.String()
    services = fields.Dict()


# Schema instances for reuse
user_schema = UserSchema()
users_schema = UserSchema(many=True)
user_registration_schema = UserRegistrationSchema()
user_update_schema = UserUpdateSchema()
login_schema = LoginSchema()
token_response_schema = TokenResponseSchema()

report_schema = ReportSchema()
reports_schema = ReportSchema(many=True)
report_create_schema = ReportCreateSchema()
report_update_schema = ReportUpdateSchema()
report_list_schema = ReportListSchema()

approval_schema = ApprovalSchema()
file_upload_schema = FileUploadSchema()
password_change_schema = PasswordChangeSchema()
mfa_setup_schema = MFASetupSchema()
mfa_verify_schema = MFAVerifySchema()

stats_schema = StatsSchema()
user_stats_schema = UserStatsSchema()
audit_log_schema = AuditLogSchema()
audit_logs_schema = AuditLogSchema(many=True)
health_check_schema = HealthCheckSchema()

pagination_schema = PaginationSchema()
