from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import current_user
import os
import datetime
import base64
import json
import html
from docxtpl import DocxTemplate, InlineImage
from docx.shared import Mm
from models import db, Report, SATReport
from utils import (
    load_submissions,
    save_submissions,
    send_approval_link,
    notify_completion,
    convert_to_pdf,
    send_client_final_document,
    send_email,
    update_toc_page_numbers,
)
from services.dashboard_stats import compute_and_cache_dashboard_stats

approval_bp = Blueprint('approval', __name__)


def _load_inline_signature_image(tpl: DocxTemplate, filename: str, width_mm: int = 40):
    """Return an InlineImage for a signature file using robust path resolution."""
    if not filename:
        return ""

    candidates = []
    base_names = [filename]
    if not os.path.splitext(filename)[1]:
        base_names.append(f"{filename}.png")

    base_dirs = [
        current_app.config.get('SIGNATURES_FOLDER'),
        os.path.join(current_app.root_path, 'static', 'signatures'),
        os.path.join(os.getcwd(), 'static', 'signatures'),
    ]

    # If the filename is already an absolute path or contains a separator, try it directly first
    for name in base_names:
        if os.path.isabs(name) or os.path.sep in name or '/' in name:
            candidates.append(name)

    for base in filter(None, base_dirs):
        for name in base_names:
            candidates.append(os.path.join(base, name))

    for candidate in candidates:
        try:
            if os.path.exists(candidate) and os.path.getsize(candidate) > 0:
                current_app.logger.info(f"Loaded signature from {candidate}")
                return InlineImage(tpl, candidate, width=Mm(width_mm))
        except Exception as exc:
            current_app.logger.error(f"Failed to load signature from {candidate}: {exc}", exc_info=True)
    current_app.logger.warning(f"No signature file found for {filename}; tried {len(candidates)} candidates: {candidates}")
    return ""


def _extract_flagged_items(raw_payload):
    """Parse flagged issues payload from the approval forms."""
    if not raw_payload:
        return []
    try:
        data = json.loads(raw_payload)
    except (ValueError, TypeError) as exc:
        current_app.logger.warning(f"Could not parse flagged issues payload: {exc}")
        return []

    cleaned = []
    for entry in data if isinstance(data, list) else []:
        if not isinstance(entry, dict):
            continue
        location = (entry.get("location") or "").strip()
        note = (entry.get("note") or "").strip()
        action = (entry.get("action") or "").strip()
        severity = (entry.get("severity") or "").strip()
        if not any([location, note, action]):
            continue
        cleaned.append({
            "location": location,
            "note": note,
            "action": action,
            "severity": severity or "Medium",
        })
    return cleaned


def _summarize_flags(flags):
    """Create a concise textual summary for flagged issues."""
    if not flags:
        return ""
    summaries = []
    for item in flags:
        bits = []
        if item.get("location"):
            bits.append(item["location"])
        if item.get("note"):
            bits.append(item["note"])
        summary = " - ".join(bits) if bits else ""
        if item.get("severity"):
            summary = f"{summary} (Severity: {item['severity']})" if summary else f"Severity: {item['severity']}"
        if item.get("action"):
            summary = f"{summary} | Action: {item['action']}" if summary else f"Action: {item['action']}"
        if summary:
            summaries.append(summary)
    return "; ".join(summaries)


def _apply_flags_to_context(context, stage, flags, summary):
    """Persist flagged issues into the submission context for downstream use."""
    if not isinstance(context, dict):
        context = {}
    stage_key = f"stage_{stage}"
    approval_flags = context.get("APPROVAL_FLAGS")
    if not isinstance(approval_flags, dict):
        approval_flags = {}

    if flags:
        approval_flags[stage_key] = flags
        context["APPROVAL_FLAGS"] = approval_flags
        context[f"STAGE_{stage}_FLAG_SUMMARY"] = summary or _summarize_flags(flags)
    else:
        if stage_key in approval_flags:
            approval_flags.pop(stage_key, None)
        if approval_flags:
            context["APPROVAL_FLAGS"] = approval_flags
        elif "APPROVAL_FLAGS" in context:
            context.pop("APPROVAL_FLAGS")
        context.pop(f"STAGE_{stage}_FLAG_SUMMARY", None)

    return context

@approval_bp.route('/<submission_id>/<int:stage>', methods=['GET', 'POST'])
def approve_submission(submission_id, stage):
    """Handle approval workflow for a submission"""
    try:
        submissions = load_submissions()
        
        # Fix: Ensure submissions is a dictionary, not a list
        if isinstance(submissions, list):
            current_app.logger.error(f"Submissions loaded as list instead of dict: {type(submissions)}")
            # Try to load from database instead
            try:
                report = Report.query.get(submission_id)
                if report:
                    sat_report = SATReport.query.filter_by(report_id=submission_id).first()
                    if sat_report and sat_report.data_json:
                        import json as json_module
                        submission_data = json_module.loads(sat_report.data_json)
                        current_app.logger.info(f"Loaded submission data from database for {submission_id}")
                    else:
                        current_app.logger.error(f"No SAT report data found for {submission_id}")
                        flash("Submission data not found", "error")
                        return redirect(url_for('index'))
                else:
                    current_app.logger.error(f"No report found for {submission_id}")
                    flash("Submission not found", "error")
                    return redirect(url_for('index'))
            except Exception as e:
                current_app.logger.error(f"Error loading from database: {e}")
                flash("Error loading submission data", "error")
                return redirect(url_for('index'))
        else:
            submission_data = submissions.get(submission_id)
        
        if not submission_data:
            flash("Submission not found", "error")
            return redirect(url_for('index'))

        approvals = submission_data.get("approvals", [])
        current_stage = next((a for a in approvals if a["stage"] == stage), None)
        
        if not current_stage:
            flash("Approval stage not found", "error")
            return redirect(url_for('index'))

        if stage == 2:
            stage1 = next((a for a in approvals if str(a.get("stage")) == "1"), None)
            stage1_status = (stage1.get("status") or "").lower() if stage1 else ""
            if stage1_status != "approved":
                flash("Automation Manager approval is required before PM review.", "warning")
                return redirect(url_for('status.view_status', submission_id=submission_id))
            
        # If already approved, show status page
        if current_stage["status"] == "approved":
            flash("This stage has already been approved", "info")
            return redirect(url_for('status.view_status', submission_id=submission_id))

        if request.method == "POST":
            # Process the pad‐drawn signature (base64 PNG) from the hidden field
            sig_data = request.form.get("signature_data", "")
            if sig_data.startswith("data:image"):
                # strip off "data:image/png;base64,"
                _header, b64 = sig_data.split(",", 1)
                data = base64.b64decode(b64)
                fn = f"{submission_id}_{stage}.png"
                
                # Ensure signatures folder exists
                sig_folder = current_app.config.get('SIGNATURES_FOLDER', 'static/signatures')
                if not os.path.exists(sig_folder):
                    os.makedirs(sig_folder, exist_ok=True)
                
                path = os.path.join(sig_folder, fn)
                
                # Try to remove existing file if it exists (might be locked)
                try:
                    if os.path.exists(path):
                        os.remove(path)
                except Exception as e:
                    current_app.logger.warning(f"Could not remove existing signature file: {e}")
                
                # Write the new signature file
                try:
                    with open(path, "wb") as img:
                        img.write(data)
                    # record just the filename so later we can load & embed it
                    current_stage["signature"] = fn
                except PermissionError as e:
                    current_app.logger.error(f"Permission error saving signature: {e}")
                    # Try alternative location in temp folder
                    import tempfile
                    temp_path = os.path.join(tempfile.gettempdir(), fn)
                    with open(temp_path, "wb") as img:
                        img.write(data)
                    current_stage["signature"] = temp_path
                except Exception as e:
                    current_app.logger.error(f"Error saving signature: {e}")
                    flash("Could not save signature, but approval will continue", "warning")

            # Capture approval comment and mark as approved
            current_stage["comment"] = request.form.get("approval_comment", "")
            current_stage["status"] = "approved"
            current_stage["timestamp"] = datetime.datetime.now().isoformat()
            current_stage["approver_name"] = request.form.get("approver_name", "")

            # Persist flagged issues
            flags_payload = request.form.get("flagged_issues", "")
            flagged_items = _extract_flagged_items(flags_payload)
            if flagged_items:
                current_stage["flags"] = flagged_items
                current_stage["flag_summary"] = _summarize_flags(flagged_items)
            else:
                current_stage.pop("flags", None)
                current_stage.pop("flag_summary", None)

            ctx = submission_data.get("context")
            if not isinstance(ctx, dict):
                ctx = {}
            ctx = _apply_flags_to_context(ctx, stage, flagged_items, current_stage.get("flag_summary"))
            
            # Map to Word template fields for Automation Manager (stage 1)
            if stage == 1:
                ctx["REVIEWED_BY_TECH_LEAD"] = current_stage["approver_name"]
                ctx["TECH_LEAD_DATE"] = datetime.datetime.now().strftime('%Y-%m-%d')
                
                # Store signature filename for Word template
                if current_stage.get("signature"):
                    ctx["SIG_REVIEW_TECH"] = current_stage["signature"]
            elif stage == 2:
                ctx["REVIEWED_BY_PM"] = current_stage["approver_name"]
                ctx["PM_DATE"] = datetime.datetime.now().strftime('%Y-%m-%d')
                if current_stage.get("signature"):
                    ctx["SIG_REVIEW_PM"] = current_stage["signature"]

            submission_data["context"] = ctx

            if stage == 1:
                # Stage 1 approval locks editing but keeps workflow in pending state for PM
                submission_data["status"] = "PENDING"
                submission_data["locked"] = True
            
            # Create notification for submitter
            from utils import create_status_update_notification
            try:
                user_email = submission_data.get("user_email")
                document_title = submission_data.get("context", {}).get("DOCUMENT_TITLE", "SAT Report")
                if user_email:
                    create_status_update_notification(
                        user_email=user_email,
                        submission_id=submission_id,
                        status="approved",
                        document_title=document_title,
                        approver_name=current_stage["approver_name"]
                    )
            except Exception as e:
                current_app.logger.error(f"Error creating approval notification: {e}")

            # Once a stage is approved, lock editing 
            submission_data["locked"] = True

            # Update last modified timestamp
            submission_data["updated_at"] = datetime.datetime.now().isoformat()
            
            # Save changes
            submissions[submission_id] = submission_data
            save_submissions(submissions)
            
            # Also update the database Report record
            try:
                import json as json_module
                report = Report.query.get(submission_id)
                if report:
                    # Update the database with new approval data
                    report.approvals_json = json_module.dumps(approvals)
                    
                    # Apply stage-specific metadata updates
                    if stage == 1:
                        report.locked = True
                        report.status = 'PENDING'
                        report.approved_at = None
                        report.approved_by = None
                        current_app.logger.info(
                            f"Automation Manager approved report {submission_id} - awaiting PM review"
                        )
                    elif stage == 2:
                        report.locked = True
                        report.status = 'APPROVED'
                        report.approved_at = datetime.datetime.utcnow()
                        report.approved_by = current_stage.get(
                            "approver_email",
                            current_stage.get("approver_name", "")
                        )
                        current_app.logger.info(
                            f"PM approved report {submission_id} - workflow complete"
                        )
                    
                    # Commit Report changes immediately to ensure database is updated
                    db.session.commit()
                    current_app.logger.info(f"Successfully updated Report database record for {submission_id}, locked={report.locked}, status={report.status}")
                    
                    # Update SAT report data with Word template fields
                    sat_report = SATReport.query.filter_by(report_id=submission_id).first()
                    if sat_report:
                        import json as json_module
                        try:
                            stored_data = json_module.loads(sat_report.data_json)
                            stored_data["context"] = submission_data.get("context", {})
                            sat_report.data_json = json_module.dumps(stored_data)
                            db.session.commit()
                            current_app.logger.info(f"Updated SAT report data with approval context for submission {submission_id}")
                        except Exception as e:
                            current_app.logger.error(f"Error updating SAT report data: {e}")
                            db.session.rollback()

                    # Refresh dashboard statistics for impacted approvers
                    try:
                        if stage == 1:
                            if current_stage.get("approver_email"):
                                compute_and_cache_dashboard_stats('Automation Manager', current_stage["approver_email"])
                            pm_stage = next((a for a in approvals if a.get("stage") == 2), None)
                            if pm_stage and pm_stage.get("approver_email"):
                                compute_and_cache_dashboard_stats('PM', pm_stage["approver_email"])
                        elif stage == 2:
                            if current_stage.get("approver_email"):
                                compute_and_cache_dashboard_stats('PM', current_stage["approver_email"])
                            am_stage = next((a for a in approvals if a.get("stage") == 1), None)
                            if am_stage and am_stage.get("approver_email"):
                                compute_and_cache_dashboard_stats('Automation Manager', am_stage["approver_email"])
                    except Exception as stats_error:
                        current_app.logger.warning(f"Unable to refresh dashboard stats: {stats_error}")
                else:
                    current_app.logger.error(f"Report {submission_id} not found in database for approval update")
                    
            except Exception as e:
                current_app.logger.error(f"Error updating database: {e}")
                db.session.rollback()

            # Determine if this is the PM approval (stage 2)
            # After PM approves, we finalize the document and send to client
            is_final_approval = stage == 2
            
            
            if is_final_approval:
                tpl = DocxTemplate(current_app.config['TEMPLATE_FILE'])
                base_context = submission_data.get('context', {})
                ctx = base_context.copy() if isinstance(base_context, dict) else {}
                submission_data["status"] = "APPROVED"
                submission_data["locked"] = True

                approval_flag_sections = []
                for approval_item in approvals:
                    stage_flags = approval_item.get("flags") or []
                    if not stage_flags:
                        continue
                    summary_text = approval_item.get("flag_summary") or _summarize_flags(stage_flags)
                    approval_flag_sections.append({
                        "stage": approval_item.get("stage"),
                        "title": approval_item.get("title") or f"Stage {approval_item.get('stage')}",
                        "summary": summary_text,
                        "items": stage_flags,
                    })
                if approval_flag_sections:
                    ctx["APPROVAL_FLAGS_DETAIL"] = approval_flag_sections
                    ctx["APPROVAL_FLAGS_SUMMARY"] = "\n".join(
                        filter(
                            None,
                            [
                                f"Stage {section.get('stage')}: {section.get('summary')}"
                                if section.get("stage") else section.get("summary", "")
                                for section in approval_flag_sections
                            ],
                        )
                    )

                # Check and log all parameters for debugging
                current_app.logger.info(f"Preparing final document with context keys: {list(ctx.keys())}")
                
                # Initialize signature variables with proper fallbacks
                sig_prepared = ""
                tech_lead_sig = ""
                pm_sig = ""
                
                # Improved prepared signature handling
                prep_fn = None
                # First check in submission data root (most reliable place)
                if "prepared_signature" in submission_data:
                    prep_fn = submission_data.get("prepared_signature")
                    current_app.logger.info(f"Found prepared signature in submission data: {prep_fn}")
                # Then check in context
                elif "prepared_signature" in ctx:
                    prep_fn = ctx.get("prepared_signature")
                    current_app.logger.info(f"Found prepared signature in context: {prep_fn}")

                if prep_fn:
                    sig_prepared = _load_inline_signature_image(tpl, prep_fn)
                
                # Load Automation Manager signature (stage 1) with better error handling
                tech_lead_approval = next((a for a in approvals if a["stage"] == 1), None)
                if tech_lead_approval:
                    sig_fn = tech_lead_approval.get("signature")
                    if sig_fn and isinstance(submission_data.get("context"), dict):
                        submission_data["context"]["SIG_REVIEW_TECH"] = sig_fn
                    if sig_fn:
                        tech_lead_sig = _load_inline_signature_image(tpl, sig_fn)
                
                # Load PM signature (stage 2) with better error handling
                pm_approval = next((a for a in approvals if a["stage"] == 2), None)
                if pm_approval:
                    sig_fn = pm_approval.get("signature")
                    if sig_fn and isinstance(submission_data.get("context"), dict):
                        submission_data["context"]["SIG_REVIEW_PM"] = sig_fn
                    if sig_fn:
                        pm_sig = _load_inline_signature_image(tpl, sig_fn)
                
                # Format timestamps consistently
                tech_lead_date = ""
                pm_date = ""
                preparer_date = ""
                
                # Helper function for consistent date formatting
                def format_iso_timestamp(timestamp):
                    if not timestamp:
                        return ""
                    try:
                        date_obj = datetime.datetime.fromisoformat(timestamp)
                        return date_obj.strftime("%d-%m-%Y %H:%M")
                    except Exception as e:
                        current_app.logger.error(f"Error formatting timestamp: {e}")
                        return ""
                
                # Format Automation Manager approval date
                if tech_lead_approval and tech_lead_approval.get("timestamp"):
                    tech_lead_date = format_iso_timestamp(tech_lead_approval.get("timestamp"))
                
                # Format PM approval date
                if pm_approval and pm_approval.get("timestamp"):
                    pm_date = format_iso_timestamp(pm_approval.get("timestamp"))
                
                # Format preparer timestamp
                if "prepared_timestamp" in ctx:
                    preparer_date = format_iso_timestamp(ctx.get("prepared_timestamp"))
                
                # Comprehensive signature mapping with fallbacks
                signature_mapping = {
                    # Primary signature mappings
                    "SIG_PREPARED": sig_prepared or "",
                    "SIG_REVIEW_TECH": tech_lead_sig or "",
                    "SIG_REVIEW_PM": pm_sig or "",
                    "SIG_APPROVAL_CLIENT": "",
                    
                    # Alternative signature mappings
                    "SIG_PREPARED_BY": sig_prepared or "",
                    "SIG_APPROVER_1": tech_lead_sig or "",
                    "SIG_APPROVER_2": pm_sig or "",
                    "SIG_APPROVER_3": "",
                    
                    # Date variables
                    "TECH_LEAD_DATE": tech_lead_date,
                    "PM_DATE": pm_date,
                    "PREPARER_DATE": preparer_date
                }
                
                # Log the signature mapping
                current_app.logger.info(f"Applying {len(signature_mapping)} signature variables to template")
                for key, value in signature_mapping.items():
                    is_image = "InlineImage" in str(type(value))
                    current_app.logger.info(f"  {key}: {'[InlineImage]' if is_image else value}")
                
                # Update context with signatures - ensure they're properly added
                ctx.update(signature_mapping)
                
                # Render with improved error handling
                try:
                    tpl.render(ctx)
                    out = os.path.abspath(current_app.config['OUTPUT_FILE'])
                    
                    # Save to temporary file first, then move atomically
                    temp_out = out + '.tmp'
                    tpl.save(temp_out)
                    
                    # Verify file integrity before finalizing
                    if os.path.exists(temp_out) and os.path.getsize(temp_out) > 0:
                        import shutil
                        shutil.move(temp_out, out)
                        current_app.logger.info(f"Template successfully rendered and saved to: {out} ({os.path.getsize(out)} bytes)")
                    else:
                        raise Exception("Document generation failed - empty or missing file")

                except Exception as e:
                    current_app.logger.error(f"Error rendering template: {e}", exc_info=True)
                    flash(f"Error generating final document: {str(e)}", "error")
                    return redirect(url_for('status.view_status', submission_id=submission_id))

                # Optionally refresh TOC page numbers (Windows/Word only)
                if current_app.config.get('AUTO_UPDATE_TOC', False):
                    try:
                        update_toc_page_numbers(out)
                    except Exception as toc_error:
                        current_app.logger.warning(f"TOC page-number update skipped: {toc_error}")

                # Generate PDF if enabled
                if current_app.config.get('ENABLE_PDF_EXPORT', False):
                    pdf = convert_to_pdf(out)
                    if pdf:
                        submission_data["pdf_path"] = pdf
                        save_submissions(submissions)

                # Improved client email finding and notification
                # Always get client email from approvals list with better error handling
                client_email = None
                client_approval = next((a for a in approvals if a["stage"] == 3), None)
                if client_approval:
                    client_email = client_approval.get("approver_email")
                    current_app.logger.info(f"Found client email for notification: {client_email}")
                else:
                    current_app.logger.warning("No stage 3 (client) approval found in workflow")
                    
                    # Try fallback methods to find client email
                    if "approver_3_email" in submission_data.get("context", {}):
                        client_email = submission_data["context"]["approver_3_email"]
                        current_app.logger.info(f"Using fallback client email from context: {client_email}")
                    elif "CLIENT_EMAIL" in submission_data.get("context", {}):
                        client_email = submission_data["context"]["CLIENT_EMAIL"]
                        current_app.logger.info(f"Using fallback CLIENT_EMAIL from context: {client_email}")

                # Notify the submitter 
                notify_completion(submission_data.get("user_email"), submission_id)
                
                # Create completion notification
                from utils import create_completion_notification
                try:
                    user_email = submission_data.get("user_email")
                    document_title = submission_data.get("context", {}).get("DOCUMENT_TITLE", "SAT Report")
                    if user_email:
                        create_completion_notification(
                            user_email=user_email,
                            submission_id=submission_id,
                            document_title=document_title
                        )
                except Exception as e:
                    current_app.logger.error(f"Error creating completion notification: {e}")
                
                # Send the final document to the client
                if client_email:
                    try:
                        current_app.logger.info(f"Sending final document to client: {client_email}")
                        result = send_client_final_document(
                            client_email, 
                            submission_id, 
                            submission_data.get("context", {}).get("DOCUMENT_TITLE", "SAT Report")
                        )
                        current_app.logger.info(f"Client notification result: {result}")
                        flash(f"All approvals complete! The submitter and client ({client_email}) have been notified.", "success")
                    except Exception as e:
                        current_app.logger.error(f"Error sending client notification: {e}", exc_info=True)
                        flash(f"All approvals complete! The submitter has been notified, but there was an error sending client notification to {client_email}.", "warning")
                else:
                    current_app.logger.error("No client email found for final notification")
                    flash("All approvals complete! The submitter has been notified, but no client email was found.", "warning")
                
                return redirect(url_for('status.view_status', submission_id=submission_id))

            else:
                # Not final approval: notify the next approver
                next_stage = next(
                    (a for a in approvals if a["stage"] > stage and a["status"] == "pending"),
                    None
                )
                if next_stage:
                    current_app.logger.info("Notifying next approver: %s", next_stage["approver_email"])
                    send_approval_link(
                        next_stage["approver_email"],
                        submission_id,
                        next_stage["stage"]
                    )
                    
                    # Create notification for next approver
                    from utils import create_approval_notification
                    try:
                        document_title = submission_data.get("context", {}).get("DOCUMENT_TITLE", "SAT Report")
                        create_approval_notification(
                            approver_email=next_stage["approver_email"],
                            submission_id=submission_id,
                            stage=next_stage["stage"],
                            document_title=document_title
                        )
                    except Exception as e:
                        current_app.logger.error(f"Error creating approval notification: {e}")
                    flash(f"Stage {stage} approved. Next approver has been notified.", "success")
                else:
                    flash(f"Stage {stage} approved.", "success")
                return redirect(url_for('status.view_status', submission_id=submission_id))

        
        # For GET: Render approval page so approver can review and sign (with DOCX download option)
        context = {
            "submission_id": submission_id,
            "stage": stage,
            "approval": current_stage,
            "approvals": approvals,
            "document_title": submission_data.get("context", {}).get("DOCUMENT_TITLE", "SAT Report"),
            "project_reference": submission_data.get("context", {}).get("PROJECT_REFERENCE", ""),
            "client_name": submission_data.get("context", {}).get("CLIENT_NAME", ""),
            "prepared_by": submission_data.get("context", {}).get("PREPARED_BY", "")
        }
        
        return render_template("approve.html", **context)
        
    except Exception as e:
        current_app.logger.error(f"Error in approve_submission: {e}", exc_info=True)
        flash(f"An error occurred during the approval process: {str(e)}", "error")
        return redirect(url_for('index'))

@approval_bp.route('/reject/<submission_id>/<int:stage>', methods=['POST'])
def reject_submission(submission_id, stage):
    """Reject a submission at a specific approval stage"""
    try:
        submissions = load_submissions()
        submission_data = submissions.get(submission_id)
        
        if not submission_data:
            flash("Submission not found", "error")
            return redirect(url_for('index'))

        approvals = submission_data.get("approvals", [])
        current_stage = next((a for a in approvals if a["stage"] == stage), None)
        
        if not current_stage:
            flash("Approval stage not found", "error")
            return redirect(url_for('index'))
            
        # Only pending approvals can be rejected
        if current_stage["status"] != "pending":
            flash("This stage is not pending approval", "error")
            return redirect(url_for('status.view_status', submission_id=submission_id))

        rejection_comment = request.form.get("rejection_comment", "") or ""
        approver_name = request.form.get("approver_name", "")

        # Mark as rejected with comment
        current_stage["status"] = "rejected"
        current_stage["comment"] = rejection_comment
        current_stage["timestamp"] = datetime.datetime.now().isoformat()
        current_stage["approver_name"] = approver_name
        # Ensure approver email is stored for downstream stats/notifications
        current_stage.setdefault("approver_email", getattr(current_user, "email", None))

        flags_payload = request.form.get("flagged_issues", "")
        flagged_items = _extract_flagged_items(flags_payload)
        if flagged_items:
            current_stage["flags"] = flagged_items
            current_stage["flag_summary"] = _summarize_flags(flagged_items)
        else:
            current_stage.pop("flags", None)
            current_stage.pop("flag_summary", None)
        
        # Update submission state for UI and history
        submission_data["status"] = "REJECTED"
        submission_data["locked"] = False
        submission_data["approvals"] = approvals
        submission_data["updated_at"] = datetime.datetime.now().isoformat()
        submissions[submission_id] = submission_data
        save_submissions(submissions)

        # Persist rejection to the Report record for dashboard counts and gating
        try:
            report = Report.query.get(submission_id)
            if report:
                report.approvals_json = json.dumps(approvals)
                report.status = "REJECTED"
                report.locked = False
                report.approved_at = None
                report.approved_by = None
                db.session.commit()
            else:
                current_app.logger.warning(f"Report {submission_id} not found when applying rejection update")
        except Exception as db_error:
            current_app.logger.error(f"Error updating report status on rejection: {db_error}", exc_info=True)
            db.session.rollback()

        # Refresh dashboard stats caches so rejected counts update immediately
        try:
            for approval in approvals:
                approver_email = approval.get("approver_email")
                stage_num = str(approval.get("stage"))
                role = "Automation Manager" if stage_num == "1" else "PM" if stage_num == "2" else None
                if role and approver_email:
                    compute_and_cache_dashboard_stats(role, approver_email)
        except Exception as stats_error:
            current_app.logger.warning(f"Could not refresh dashboard stats after rejection: {stats_error}")

        # Create rejection notification for submitter
        from utils import create_status_update_notification
        document_title = submission_data.get("context", {}).get("DOCUMENT_TITLE", "SAT Report")
        user_email = submission_data.get("user_email")
        try:
            if user_email:
                create_status_update_notification(
                    user_email=user_email,
                    submission_id=submission_id,
                    status="rejected",
                    document_title=document_title,
                    approver_name=approver_name
                )
        except Exception as e:
            current_app.logger.error(f"Error creating rejection notification: {e}")

        # Email the engineer with rejection details and next steps
        try:
            if user_email:
                status_url = url_for('status.view_status', submission_id=submission_id, _external=True)
                edit_url = url_for('main.edit_submission', submission_id=submission_id, _external=True)
                safe_comment = html.escape(rejection_comment).replace("\n", "<br>") or "No reason provided."
                subject = f"Report rejected at stage {stage} - action required"
                html_body = f"""
                <html>
                <body>
                    <h2>{document_title}</h2>
                    <p>Your report was rejected at stage {stage} by {html.escape(approver_name or 'the approver')}.</p>
                    <p><strong>Reason:</strong><br>{safe_comment}</p>
                    <p>
                        <a href="{status_url}">View status</a> | 
                        <a href="{edit_url}">Update the report</a>
                    </p>
                </body>
                </html>
                """
                send_email(user_email, subject, html_body)
        except Exception as email_error:
            current_app.logger.error(f"Error sending rejection email: {email_error}")
            
        flash("Submission has been rejected with comments", "warning")
        return redirect(url_for('status.view_status', submission_id=submission_id))
        
    except Exception as e:
        current_app.logger.error(f"Error in reject_submission: {e}", exc_info=True)
        flash(f"An error occurred during the rejection process: {str(e)}", "error")
        return redirect(url_for('status.view_status', submission_id=submission_id))
