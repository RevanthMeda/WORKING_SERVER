from typing import Any
import json

def _normalize_url_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
        except Exception:
            pass
        return [value] if value else []
    if not value:
        return []
    try:
        return [str(item) for item in list(value)]
    except TypeError:
        return [str(value)]

def _resolve_urls(key: str, model_value: Any, existing_data: dict) -> list[str]:
    existing_value = existing_data.get(key) if isinstance(existing_data, dict) else None
    urls = _normalize_url_list(existing_value)
    return urls if urls else _normalize_url_list(model_value)

@main_bp.route('/generate', methods=['POST'])
@login_required
def generate():
    """Generate a SAT report from form data"""
    try:
        # Log request details for debugging
        current_app.logger.info(f"Generate request from: {request.remote_addr}")
        current_app.logger.info(f"Request form data keys: {list(request.form.keys())}")


        # Retrieve submission id and current report
        submission_id = request.form.get("submission_id", "").strip()

        # Create a new submission ID if needed
        if not submission_id:
            submission_id = str(uuid.uuid4())

        # Get or create report record
        report = Report.query.get(submission_id)
        is_new_report = False
        if not report:
            is_new_report = True
            report = Report(
                id=submission_id,
                type='SAT',
                status='DRAFT',
                user_email=current_user.email if hasattr(current_user, 'email') else '',
                approvals_json='[]',
                version='R0'  # Always start with R0 for new reports
            )
            db.session.add(report)
        else:
            # This is an edit/resubmit - increment version
            if not is_new_report:
                current_version = report.version or 'R0'
                if current_version.startswith('R'):
                    try:
                        version_num = int(current_version[1:])
                        report.version = f'R{version_num + 1}'
                    except ValueError:
                        report.version = 'R1'
                else:
                    report.version = 'R1'
                current_app.logger.info(f"Version incremented to: {report.version}")

            # Reset approval workflow for resubmission
            report.status = 'DRAFT'
            report.locked = False
            report.approval_notification_sent = False

        # Get or create SAT report record
        sat_report = SATReport.query.filter_by(report_id=submission_id).first()
        if not sat_report:
            sat_report = SATReport(
                report_id=submission_id,
                data_json='{}',
                scada_image_urls='[]',
                trends_image_urls='[]',
                alarm_image_urls='[]'
            )
            db.session.add(sat_report)

        # Load existing data for processing
        existing_data = json.loads(sat_report.data_json) if sat_report.data_json != '{}' else {}
        sub = existing_data  # For compatibility with existing code
        existing_context = existing_data.get('context', {}) if isinstance(existing_data, dict) else {}

        prepared_signature_filename = (
            existing_context.get('prepared_signature')
            or existing_data.get('prepared_signature')
            if isinstance(existing_data, dict) else ""
        ) or ""
        prepared_timestamp = (
            existing_context.get('prepared_timestamp')
            or existing_data.get('prepared_timestamp')
            if isinstance(existing_data, dict) else None
        )
        existing_sig_review_tech_file = existing_context.get('SIG_REVIEW_TECH', '') or ''
        existing_sig_review_pm_file = existing_context.get('SIG_REVIEW_PM', '') or ''
        existing_sig_client_file = existing_context.get('SIG_APPROVAL_CLIENT', '') or ''

        # Grab the approver emails from the form
        approver_emails = [
            request.form.get("approver_1_email", "").strip(),
            request.form.get("approver_2_email", "").strip(),
            request.form.get("approver_3_email", "").strip(),
        ]

        # Initialize (or update) the approvals list and lock flag
        approvals, locked = setup_approval_workflow_db(report, approver_emails)
        report.locked = locked
        report.approvals_json = json.dumps(approvals)

        # Create the upload directory for this submission
        upload_root_cfg = current_app.config.get('UPLOAD_ROOT')
        if not isinstance(upload_root_cfg, str) or not upload_root_cfg:
            static_root = current_app.static_folder or os.path.join(current_app.root_path, 'static')
            upload_root_cfg = os.path.join(static_root, 'uploads')
        upload_dir = os.path.join(upload_root_cfg, submission_id)
        os.makedirs(upload_dir, exist_ok=True)

        # Initialize DocxTemplate
        from docxtpl import DocxTemplate, InlineImage
        from docx.shared import Mm
        from werkzeug.utils import secure_filename
        import base64
        import time
        import shutil

        doc = DocxTemplate(current_app.config['TEMPLATE_FILE'])

        # Initialize image URLs lists from database
        scada_urls = _normalize_url_list(sat_report.scada_image_urls)
        trends_urls = _normalize_url_list(sat_report.trends_image_urls)
        alarm_urls = _normalize_url_list(sat_report.alarm_image_urls)

        def load_signature_inline(filename, width_mm=40):
            """Rehydrate stored signature filenames into InlineImage objects for rendering."""
            if not filename:
                return ""
            base_names = [filename]
            if not os.path.splitext(filename)[1]:
                base_names.append(f"{filename}.png")
            sig_folder_cfg = current_app.config.get('SIGNATURES_FOLDER')
            candidates = []
            for name in base_names:
                if isinstance(sig_folder_cfg, str) and sig_folder_cfg:
                    candidates.append(os.path.join(sig_folder_cfg, name))
                candidates.append(os.path.join(current_app.root_path, 'static', 'signatures', name))
                candidates.append(os.path.join(os.getcwd(), 'static', 'signatures', name))
            for candidate in candidates:
                try:
                    if os.path.exists(candidate) and os.path.getsize(candidate) > 0:
                        return InlineImage(doc, candidate, width=Mm(width_mm))
                except Exception as e:
                    current_app.logger.error(f"Error loading signature from {candidate}: {e}", exc_info=True)
            return ""

        # Process signature data
        sig_data_url = request.form.get("sig_prepared_data", "")
        sig_prepared_image: Any = ""

        if sig_data_url:
            try:
                if "," not in sig_data_url:
                    raise ValueError("Invalid signature data format")
                _, encoded = sig_data_url.split(",", 1)
                data = base64.b64decode(encoded)

                sig_folder_cfg = current_app.config.get('SIGNATURES_FOLDER')
                if not isinstance(sig_folder_cfg, str) or not sig_folder_cfg:
                    raise KeyError("SIGNATURES_FOLDER not configured")
                os.makedirs(sig_folder_cfg, exist_ok=True)

                fn = f"{submission_id}_prepared_{int(time.time())}.png"
                out_path = os.path.join(sig_folder_cfg, fn)

                with open(out_path, "wb") as signature_file:
                    signature_file.write(data)

                if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                    sub.setdefault("context", {})["prepared_signature"] = fn
                    sub["prepared_signature"] = fn

                    current_timestamp = dt.datetime.now().isoformat()
                    sub.setdefault("context", {})["prepared_timestamp"] = current_timestamp
                    prepared_signature_filename = fn
                    prepared_timestamp = current_timestamp

                    current_app.logger.info("Stored preparer signature at %s", os.path.abspath(out_path))

                    try:
                        sig_prepared_image = InlineImage(doc, out_path, width=Mm(40))
                    except Exception as inline_error:
                        current_app.logger.error("Error creating preparer signature image: %s", inline_error)
                else:
                    raise FileNotFoundError(f"Signature file not created or empty: {out_path}")
            except Exception as error:
                current_app.logger.error("Error processing signature data: %s", error, exc_info=True)
        else:
            sig_prepared_image = load_signature_inline(prepared_signature_filename)

        # Initialize approval signatures
        SIG_APPROVER_1 = load_signature_inline(existing_sig_review_tech_file)
        SIG_APPROVER_2 = load_signature_inline(existing_sig_review_pm_file)
        SIG_APPROVER_3 = load_signature_inline(existing_sig_client_file)

        # Improved image file handling
        def save_new(field, url_list, inline_list):
            """Save new uploaded files with better error handling and path resolution"""
            for f in request.files.getlist(field):
                if not f or not f.filename:
                    continue

                try:
                    # Create a secure filename and ensure uniqueness
                    fn = secure_filename(f.filename)
                    uniq_fn = f"{uuid.uuid4().hex}_{fn}"

                    # Ensure the upload directory exists
                    os.makedirs(upload_dir, exist_ok=True)

                    # Create absolute path for file storage
                    disk_fp = os.path.join(upload_dir, uniq_fn)

                    # Save the file
                    f.save(disk_fp)
                    current_app.logger.info(f"Saved uploaded file to: {disk_fp}")

                    # Create proper URL and add image object
                    try:
                        # Add public URL for edit-mode preview
                        # Use posix-style paths for URLs (forward slashes)
                        rel_path = os.path.join("uploads", submission_id, uniq_fn).replace("\\", "/")
                        url = url_for("static", filename=rel_path)
                        url_list.append(url)
                        current_app.logger.info(f"Added image URL: {url}")

                        # 2) Create InlineImage and handle potential corruption
                        try:
                            current_app.logger.info(f"Attempting to create InlineImage with path: {disk_fp}")
                            inline_image = InlineImage(doc, disk_fp, width=Mm(150))
                            inline_list.append(inline_image)
                            current_app.logger.info(f"Successfully created InlineImage for: {uniq_fn}")
                        except Exception as e:
                            current_app.logger.error(f"Error creating InlineImage for {fn}: {e}", exc_info=True)
                    except Exception as e:
                        current_app.logger.error(f"Error processing image {fn}: {e}", exc_info=True)

                except Exception as e:
                    current_app.logger.error(f"Failed to save file {f.filename}: {e}", exc_info=True)

        # Remove images flagged for deletion
        handle_image_removals(request.form, "removed_scada_screenshots", scada_urls)
        handle_image_removals(request.form, "removed_trends_screenshots", trends_urls)
        handle_image_removals(request.form, "removed_alarm_screenshots", alarm_urls)

        scada_image_objects = []
        trends_image_objects = []
        alarm_image_objects = []

        # Process new image uploads (appends to both URL lists and image object lists)
        save_new("scada_screenshots[]", scada_urls, scada_image_objects)
        save_new("trends_screenshots[]", trends_urls, trends_image_objects)
        save_new("alarm_screenshots[]", alarm_urls, alarm_image_objects)

        # Prepare signature placeholders
        # Prepare signature placeholders (legacy fields retained for compatibility)
        sig_prepared_by = ""
        SIG_REVIEW_TECH = ""
        SIG_APPROVAL_CLIENT = ""

        # Extract table data using the unified schema helpers
        ui_tables = extract_ui_tables(request.form)
        doc_tables = build_doc_tables(ui_tables)
        legacy_tables = migrate_context_tables(existing_data.get('context', {}))
        combined_tables = dict(legacy_tables)
        combined_tables.update(ui_tables)

        # Build final context for the DOCX
        # Build final context for document rendering
        context: dict[str, Any] = {
            "DOCUMENT_TITLE": request.form.get('document_title', ''),
            "PROJECT_REFERENCE": request.form.get('project_reference', ''),
            "DOCUMENT_REFERENCE": request.form.get('document_reference', ''),
            "DATE": request.form.get('date', ''),
            "CLIENT_NAME": request.form.get('client_name', ''),
            "REVISION": request.form.get('revision', ''),
            "REVISION_DETAILS": request.form.get('revision_details', ''),
            "REVISION_DATE": request.form.get('revision_date', ''),
            "PREPARED_BY": request.form.get('prepared_by', ''),
            "SIG_PREPARED": sig_prepared_image,
            "SIG_PREPARED_BY": sig_prepared_by,
            "REVIEWED_BY_TECH_LEAD": request.form.get('reviewed_by_tech_lead', ''),
            "SIG_REVIEW_TECH": SIG_REVIEW_TECH,
            "REVIEWED_BY_PM": request.form.get('reviewed_by_pm', ''),
            "APPROVED_BY_CLIENT": request.form.get('approved_by_client', ''),
            "SIG_APPROVAL_CLIENT": SIG_APPROVAL_CLIENT,
            "PURPOSE": request.form.get("purpose", ""),
            "SCOPE": request.form.get("scope", ""),
            "SCADA_IMAGES": scada_image_objects,
            "TRENDS_IMAGES": trends_image_objects,
            "ALARM_IMAGES": alarm_image_objects,
            "SIG_APPROVER_1": SIG_APPROVER_1,
            "SIG_APPROVER_2": SIG_APPROVER_2,
            "SIG_APPROVER_3": SIG_APPROVER_3,
            "prepared_signature": prepared_signature_filename,
            "prepared_timestamp": prepared_timestamp or "",
        }
        context['SCADA_SCREENSHOTS'] = scada_urls
        context['TRENDS_SCREENSHOTS'] = trends_urls
        context['ALARM_SCREENSHOTS'] = alarm_urls

        for key, value in doc_tables.items():
            if key not in context:
                context[key] = value
        # For storage, remove the InlineImage objects recursively
        context_to_store: dict[str, Any] = dict(context)
        for key, value in combined_tables.items():
            context_to_store[key] = value
        context_to_store['SIG_PREPARED'] = prepared_signature_filename or context_to_store.get('SIG_PREPARED', '')
        context_to_store['prepared_signature'] = prepared_signature_filename or context_to_store.get('prepared_signature', '')
        if prepared_timestamp:
            context_to_store['prepared_timestamp'] = prepared_timestamp
        if existing_sig_review_tech_file:
            context_to_store['SIG_REVIEW_TECH'] = existing_sig_review_tech_file
        if existing_sig_review_pm_file:
            context_to_store['SIG_REVIEW_PM'] = existing_sig_review_pm_file
        if existing_sig_client_file:
            context_to_store['SIG_APPROVAL_CLIENT'] = existing_sig_client_file
        def remove_inline_images(obj):
            """Recursively remove InlineImage objects from nested data structures"""
            if isinstance(obj, InlineImage):
                return None
            elif isinstance(obj, dict):
                return {k: remove_inline_images(v) for k, v in obj.items() if not isinstance(v, InlineImage)}
            elif isinstance(obj, list):
                return [remove_inline_images(item) for item in obj if not isinstance(item, InlineImage)]
            else:
                return obj

        # Apply the cleaning function to all context data
        for key in list(context_to_store.keys()):
            context_to_store[key] = remove_inline_images(context_to_store[key])

        # Store approver emails in context for later retrieval in edit form
        context_to_store["approver_1_email"] = approver_emails[0]
        context_to_store["approver_2_email"] = approver_emails[1]
        context_to_store["approver_3_email"] = approver_emails[2]

        # Update report metadata
        report.document_title = context_to_store.get('DOCUMENT_TITLE', '')
        report.document_reference = context_to_store.get('DOCUMENT_REFERENCE', '')
        report.project_reference = context_to_store.get('PROJECT_REFERENCE', '')
        report.client_name = context_to_store.get('CLIENT_NAME', '')
        report.revision = context_to_store.get('REVISION', '')
        report.prepared_by = context_to_store.get('PREPARED_BY', '')
        report.updated_at = dt.datetime.utcnow()
        
        # CRITICAL: Update status to PENDING when submitted for approval
        # Only change from DRAFT to PENDING if there are approvers
        if approvals and len(approvals) > 0:
            report.status = 'PENDING'
            current_app.logger.info(f"Report {submission_id} status changed to PENDING (submitted for approval)")
        else:
            # No approvers = stays as DRAFT
            if not report.status or report.status == '':
                report.status = 'DRAFT'
            current_app.logger.info(f"Report {submission_id} status remains {report.status} (no approvals)")

        # Prepare submission data for storage
        submission_data = {
            "context": context_to_store,
            "user_email": current_user.email if hasattr(current_user, 'email') else request.form.get("user_email", ""),
            "approvals": approvals,
            "locked": locked,
            "scada_image_urls": scada_urls,
            "trends_image_urls": trends_urls,
            "alarm_image_urls": alarm_urls,
            "created_at": existing_data.get("created_at", dt.datetime.now().isoformat()),
            "updated_at": dt.datetime.now().isoformat(),
            "prepared_signature": prepared_signature_filename,
            "prepared_timestamp": prepared_timestamp,
        }

        for table_key in TABLE_UI_KEYS:
            submission_data[table_key] = context_to_store.get(table_key, [])

        try:
            submissions = load_submissions()
            if isinstance(submissions, list):
                submissions = {}
            submissions[submission_id] = submission_data
            save_submissions(submissions)
        except Exception as save_error:
            current_app.logger.info(f"Could not persist final snapshot to file: {save_error}")
        # Update SAT report data
        sat_report.data_json = json.dumps(submission_data)
        sat_report.date = context_to_store.get('DATE', '')
        sat_report.purpose = context_to_store.get('PURPOSE', '')
        sat_report.scope = context_to_store.get('SCOPE', '')
        sat_report.scada_image_urls = json.dumps(scada_urls)
        sat_report.trends_image_urls = json.dumps(trends_urls)
        sat_report.alarm_image_urls = json.dumps(alarm_urls)

        # Save to database
        db.session.commit()

        # Refresh dashboard statistics for assigned approvers
        try:
            role_map = {0: 'Automation Manager', 1: 'PM'}
            for idx, email in enumerate(approver_emails[:2]):
                if email:
                    compute_and_cache_dashboard_stats(role_map[idx], email)
        except Exception as stats_error:
            current_app.logger.warning(f"Could not refresh dashboard stats: {stats_error}")

        # Render the DOCX template with error handling
        try:
            current_app.logger.info("Starting document rendering...")
            current_app.logger.debug(f"Context keys: {list(context.keys())}")
            
            # Check for problematic values in context
            for key, value in context.items():
                if value is None:
                    current_app.logger.warning(f"Context key '{key}' has None value")
                elif isinstance(value, (list, dict)) and not value:
                    current_app.logger.debug(f"Context key '{key}' is empty {type(value).__name__}")
            
            doc.render(context)
            current_app.logger.info("Document rendering completed successfully")
        except Exception as render_error:
            current_app.logger.error(f"Error rendering document template: {render_error}", exc_info=True)
            flash(f"Error generating document: {str(render_error)}", "error")
            return redirect(url_for('index'))

        # Build a timestamped filename and save to the OS temp directory
        import tempfile
        timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"SAT_Report_{timestamp}.docx"
        temp_path = os.path.join(tempfile.gettempdir(), filename)

        try:
            doc.save(temp_path)
            current_app.logger.info(f"Document saved to temp path: {temp_path}")
            
            # Verify the file exists and has content
            if not os.path.exists(temp_path):
                raise Exception(f"Document file was not created at {temp_path}")
            
            file_size = os.path.getsize(temp_path)
            if file_size < 1000:  # A valid docx should be at least a few KB
                raise Exception(f"Document file is too small ({file_size} bytes), likely corrupt")
            
            current_app.logger.info(f"Document file verified: {file_size} bytes")
        except Exception as save_error:
            current_app.logger.error(f"Error saving document: {save_error}", exc_info=True)
            flash(f"Error saving document: {str(save_error)}", "error")
            return redirect(url_for('index'))

        # Save to a permanent, submission-specific location
        try:
            output_dir = current_app.config.get('OUTPUT_DIR')
            if not isinstance(output_dir, str) or not output_dir:
                raise KeyError("OUTPUT_DIR missing or invalid")
            os.makedirs(output_dir, exist_ok=True)
            permanent_path = os.path.join(output_dir, f'SAT_Report_{submission_id}_Final.docx')
            shutil.copyfile(temp_path, permanent_path)
            current_app.logger.info(f"Copied report to permanent location: {permanent_path}")
        except KeyError:
            current_app.logger.warning("OUTPUT_DIR not configured. Skipping permanent save.")
        except Exception as e:
            current_app.logger.warning(f"Could not copy to permanent outputs folder: {e}")

        first_stage = approvals[0] if approvals else None

        # AI Email Content Generation
        approver_email_subject = None
        approver_email_body = None
        submitter_email_subject = None
        submitter_email_body = None
        try:
            import requests

            def _call_email_generator(payload):
                response = requests.post(
                    url_for('ai.generate_email', _external=True),
                    json=payload,
                    headers={'Content-Type': 'application/json'},
                    verify=False
                )
                if response.status_code == 200:
                    return response.json()
                current_app.logger.error(
                    "AI email generation failed with status %s: %s",
                    response.status_code,
                    response.text,
                )
                return None

            # Generate approver-focused content
            approver_payload = {'submission_id': submission_id, 'audience': 'approver'}
            if first_stage:
                approver_payload['stage'] = first_stage.get('stage')
                approver_payload['approver_title'] = first_stage.get('title')
            approver_content = _call_email_generator(approver_payload)
            if approver_content:
                approver_email_subject = approver_content.get('subject')
                approver_email_body = approver_content.get('body')
                current_app.logger.info(f"Generated approver email content for {submission_id}")

            # Generate submitter-focused content
            submitter_content = _call_email_generator({'submission_id': submission_id, 'audience': 'submitter'})
            if submitter_content:
                submitter_email_subject = submitter_content.get('subject')
                submitter_email_body = submitter_content.get('body')
                current_app.logger.info(f"Generated submitter email content for {submission_id}")
        except Exception as e:
            current_app.logger.error(f"Error calling AI email generation service: {e}")

        # Notify first approver exactly once
        if not report.approval_notification_sent:
            if first_stage:
                first_email = first_stage["approver_email"]
                # Corrected call to send_approval_link
                sent = send_approval_link(
                    first_email,
                    submission_id,
                    first_stage["stage"],
                    subject=approver_email_subject,
                    html_content=approver_email_body
                )
                current_app.logger.info(f"Approval email to {first_email}: {sent}")

                # Create approval notification
                try:
                    document_title = context.get("DOCUMENT_TITLE", "SAT Report")
                    create_approval_notification(
                        approver_email=first_email,
                        submission_id=submission_id,
                        stage=first_stage["stage"],
                        document_title=document_title
                    )

                    # Also notify admins about new submission
                    from models import User
                    admin_emails = [u.email for u in User.query.filter_by(role='Admin').all()]
                    if admin_emails:
                        create_new_submission_notification(
                            admin_emails=admin_emails,
                            submission_id=submission_id,
                            document_title=document_title,
                            submitter_email=current_user.email
                        )
                except Exception as e:
                    current_app.logger.error(f"Error creating submission notifications: {e}")

                report.approval_notification_sent = True
                db.session.commit()

        # Send edit link email to user (with graceful failure)
        email_sent = False
        if current_app.config.get('ENABLE_EMAIL_NOTIFICATIONS', True):
            try:
                # Use generated email content if available, but adapt it for the user
                user_email_subject = f"SAT Report Submitted: {report.document_title}"
                user_email_body = submitter_email_body  # Can be adapted if needed

                email_result = send_edit_link(
                    report.user_email, 
                    submission_id,
                    subject=submitter_email_subject or user_email_subject,
                    html_content=user_email_body
                )
                if email_result:
                    email_sent = True
                    current_app.logger.info(f"Email sent successfully to {report.user_email}")
                else:
                    current_app.logger.warning(f"Failed to send email to {report.user_email}")
            except Exception as e:
                current_app.logger.error(f"Email sending error: {e}")

        # Always show success message regardless of email status
        success_message = "Report generated successfully!"
        if email_sent:
            success_message += " An edit link has been sent to your email."
        else:
            success_message += " You can access your report using the status page."

        flash(success_message, "success")

        response_payload = {
            "success": True,
            "message": success_message,
            "submission_id": submission_id,
            "redirect_url": url_for('status.view_status', submission_id=submission_id),
            "download_url": url_for('status.download_report', submission_id=submission_id)
        }

        wants_json = (
            request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            or 'application/json' in request.headers.get('Accept', '')
        )

        if wants_json:
            return jsonify(response_payload)

        return redirect(response_payload["redirect_url"])

    except Exception as e:
        current_app.logger.error(f"Error in generate: {e}", exc_info=True)
        flash(f"An error occurred while generating the report: {str(e)}", "error")
        return redirect(url_for('index'))

@main_bp.route('/save_progress', methods=['POST'])
@login_required
def save_progress():
    """Save form progress without generating report"""
    try:
        from models import db, Report, SATReport

        # Get submission ID or create new one
        submission_id = request.form.get("submission_id", "").strip()
        if not submission_id:
            submission_id = str(uuid.uuid4())

        # Get or create report record
        report = Report.query.get(submission_id)
        if not report:
            report = Report(
                id=submission_id,
                type='SAT',
                status='DRAFT',  # Always start as DRAFT
                user_email=current_user.email if hasattr(current_user, 'email') else '',
                approvals_json='[]'
            )
            db.session.add(report)
        
        # Ensure user_email is set
        if not report.user_email and hasattr(current_user, 'email'):
            report.user_email = current_user.email

        # IMPORTANT: Ensure status remains DRAFT for save progress (not submission)
        # Only preserve existing non-draft status if it's already PENDING/APPROVED
        if not report.status or report.status == '':
            report.status = 'DRAFT'
        current_app.logger.info(f"Save progress: Report {submission_id} status is {report.status}")

        # Get or create SAT report record
        sat_report = SATReport.query.filter_by(report_id=submission_id).first()
        if not sat_report:
            sat_report = SATReport(
                report_id=submission_id,
                data_json='{}',
                scada_image_urls='[]',
                trends_image_urls='[]',
                alarm_image_urls='[]'
            )
            db.session.add(sat_report)

        # Load existing data
        existing_data = json.loads(sat_report.data_json) if sat_report.data_json != '{}' else {}
        form_data = request.form.to_dict()
        # Build context from current form data
        context = {
            "DOCUMENT_TITLE": form_data.get('document_title', ''),
            "PROJECT_REFERENCE": form_data.get('project_reference', ''),
            "DOCUMENT_REFERENCE": form_data.get('document_reference', ''),
            "DATE": form_data.get('date', ''),
            "CLIENT_NAME": form_data.get('client_name', ''),
            "REVISION": form_data.get('revision', ''),
            "REVISION_DETAILS": form_data.get('revision_details', ''),
            "REVISION_DATE": form_data.get('revision_date', ''),
            "PREPARED_BY": form_data.get('prepared_by', ''),
            "REVIEWED_BY_TECH_LEAD": form_data.get('reviewed_by_tech_lead', ''),
            "REVIEWED_BY_PM": form_data.get('reviewed_by_pm', ''),
            "APPROVED_BY_CLIENT": form_data.get('approved_by_client', ''),
            "PURPOSE": form_data.get("purpose", ""),
            "SCOPE": form_data.get("scope", ""),
            "approver_1_email": form_data.get("approver_1_email", ""),
            "approver_2_email": form_data.get("approver_2_email", ""),
            "approver_3_email": form_data.get("approver_3_email", ""),
        }

        existing_context = migrate_context_tables(existing_data.get('context', {}))
        for key, value in existing_context.items():
            if key not in context:
                context[key] = value

        upload_root_cfg = current_app.config.get('UPLOAD_ROOT')
        if not isinstance(upload_root_cfg, str) or not upload_root_cfg:
            static_root = current_app.static_folder or os.path.join(current_app.root_path, 'static')
            upload_root_cfg = os.path.join(static_root, 'uploads')
        upload_dir = os.path.join(upload_root_cfg, submission_id)
        os.makedirs(upload_dir, exist_ok=True)

        scada_urls = _resolve_urls('scada_image_urls', sat_report.scada_image_urls, existing_data)
        trends_urls = _resolve_urls('trends_image_urls', sat_report.trends_image_urls, existing_data)
        alarm_urls = _resolve_urls('alarm_image_urls', sat_report.alarm_image_urls, existing_data)

        # Handle removal of images marked for deletion in the form
        # The `handle_image_removals` function processes the comma-separated
        # string of URLs from the `removed_scada_screenshots` field.
        handle_image_removals(request.form, 'removed_scada_screenshots', scada_urls)
        handle_image_removals(request.form, 'removed_trends_screenshots', trends_urls)
        handle_image_removals(request.form, 'removed_alarm_screenshots', alarm_urls)

        from werkzeug.utils import secure_filename
        from PIL import Image

        def save_uploaded_images(field_name, url_list):
            for storage in request.files.getlist(field_name):
                if not storage or not storage.filename:
                    continue
                if not allowed_file(storage.filename):
                    current_app.logger.debug(f"Skipped file with invalid extension: {storage.filename}")
                    continue
                try:
                    filename = secure_filename(storage.filename)
                    unique_name = f"{uuid.uuid4().hex}_{filename}"
                    disk_path = os.path.join(upload_dir, unique_name)
                    storage.save(disk_path)

                    try:
                        with Image.open(disk_path) as img:
                            img.verify()
                    except Exception as img_error:
                        current_app.logger.warning(f"Invalid image uploaded ({storage.filename}): {img_error}")
                        try:
                            os.remove(disk_path)
                        except Exception:
                            pass
                        continue

                    rel_path = os.path.join('uploads', submission_id, unique_name).replace('\\', '/')
                    url = url_for('static', filename=rel_path)
                    url_list.append(url)
                except Exception as upload_error:
                    current_app.logger.error(f"Error saving uploaded image {storage.filename}: {upload_error}", exc_info=True)

        save_uploaded_images('scada_screenshots[]', scada_urls)
        save_uploaded_images('trends_screenshots[]', trends_urls)
        save_uploaded_images('alarm_screenshots[]', alarm_urls)

        context['SCADA_SCREENSHOTS'] = scada_urls
        context['TRENDS_SCREENSHOTS'] = trends_urls
        context['ALARM_SCREENSHOTS'] = alarm_urls

        ui_tables = extract_ui_tables(request.form)
        for key, value in ui_tables.items():
            context[key] = value

        doc_tables = build_doc_tables(ui_tables)
        for key, value in doc_tables.items():
            if key not in context:
                context[key] = value

        # Update report metadata
        report.document_title = context.get('DOCUMENT_TITLE', '')
        report.updated_at = dt.datetime.utcnow()

        # Prepare submission data for storage
        submission_data = {
            "context": context,
            "user_email": current_user.email if hasattr(current_user, 'email') else form_data.get("user_email", ""),
            "approvals": existing_data.get("approvals", []),
            "locked": existing_data.get("locked", False),
            "scada_image_urls": scada_urls,
            "trends_image_urls": trends_urls,
            "alarm_image_urls": alarm_urls,
            "created_at": existing_data.get("created_at", dt.datetime.now().isoformat()),
            "updated_at": dt.datetime.now().isoformat(),
            "auto_saved": True  # Mark as auto-saved
        }

        for table_key in TABLE_UI_KEYS:
            submission_data[table_key] = context.get(table_key, [])

        try:
            submissions = load_submissions()
            if isinstance(submissions, list):
                submissions = {}
            submissions[submission_id] = submission_data
            save_submissions(submissions)
        except Exception as save_error:
            current_app.logger.debug(f"Auto-save snapshot file update skipped: {save_error}")

        # Update SAT report data
        sat_report.data_json = json.dumps(submission_data)
        sat_report.scada_image_urls = json.dumps(scada_urls)
        sat_report.trends_image_urls = json.dumps(trends_urls)
        sat_report.alarm_image_urls = json.dumps(alarm_urls)
        sat_report.date = context.get('DATE', '')
        sat_report.purpose = context.get('PURPOSE', '')
        sat_report.scope = context.get('SCOPE', '')

        # Save to database
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Progress saved successfully',
            'submission_id': submission_id,
            'timestamp': dt.datetime.now().isoformat()
        })

    except Exception as e:
        current_app.logger.error(f"Error in auto-save: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Auto-save failed: {str(e)}'
        }), 500

@main_bp.route('/auto_save_progress', methods=['POST'])
@login_required
def auto_save_progress():
    """Auto-save wrapper that reuses save_progress logic."""
    return save_progress()
