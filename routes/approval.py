from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
import os
import datetime
import base64
from docxtpl import DocxTemplate, InlineImage
from docx.shared import Mm
from utils import (
    load_submissions,
    save_submissions,
    send_approval_link,
    notify_completion,
    convert_to_pdf,
    send_client_final_document,
    get_safe_output_path
)

approval_bp = Blueprint('approval', __name__)

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
                from models import db, Report, SATReport
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
                        return redirect(url_for('main.index'))
                else:
                    current_app.logger.error(f"No report found for {submission_id}")
                    flash("Submission not found", "error")
                    return redirect(url_for('main.index'))
            except Exception as e:
                current_app.logger.error(f"Error loading from database: {e}")
                flash("Error loading submission data", "error")
                return redirect(url_for('main.index'))
        else:
            submission_data = submissions.get(submission_id)
        
        if not submission_data:
            flash("Submission not found", "error")
            return redirect(url_for('main.index'))

        approvals = submission_data.get("approvals", [])
        current_stage = next((a for a in approvals if a["stage"] == stage), None)
        
        if not current_stage:
            flash("Approval stage not found", "error")
            return redirect(url_for('main.index'))
            
        # If already approved, show status page
        if current_stage["status"] == "approved":
            flash("This stage has already been approved", "info")
            return redirect(url_for('status.view_status', submission_id=submission_id))

        if request.method == "POST":
            # Process the pad‐drawn signature (base64 PNG) from the hidden field
            sig_data = request.form.get("signature_data", "")
            if sig_data.startswith("data:image"):
                # strip off "data:image/png;base64,"
                header, b64 = sig_data.split(",", 1)
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
            
            # Map to Word template fields for Automation Manager (stage 1)
            if stage == 1:
                # Update submission data context with Word template fields
                ctx = submission_data.get("context", {})
                ctx["REVIEWED_BY_TECH_LEAD"] = current_stage["approver_name"]
                ctx["TECH_LEAD_DATE"] = datetime.datetime.now().strftime('%Y-%m-%d')
                
                # Store signature filename for Word template
                if current_stage.get("signature"):
                    ctx["SIG_REVIEW_TECH"] = current_stage["signature"]
                
                submission_data["context"] = ctx
                
                # Mark as approved and lock permanently when Automation Manager approves
                submission_data["status"] = "APPROVED"
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
                from models import db, Report, SATReport
                import json as json_module
                report = Report.query.get(submission_id)
                if report:
                    # Update the database with new approval data
                    report.approvals_json = json_module.dumps(approvals)
                    
                    # When Automation Manager (stage 1) approves, lock report permanently
                    if stage == 1:
                        report.locked = True
                        report.status = 'APPROVED'
                        report.approved_at = datetime.datetime.utcnow()
                        report.approved_by = current_stage.get("approver_email", current_stage.get("approver_name", ""))
                        current_app.logger.info(f"Automation Manager approved report {submission_id} - locking permanently")
                    
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
                ctx = submission_data['context'].copy()

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
                    # Make sure it has .png extension
                    if not prep_fn.lower().endswith('.png'):
                        prep_fn += '.png'
                        
                    # Try the full absolute path first
                    sig_path = os.path.join(current_app.config['SIGNATURES_FOLDER'], prep_fn)
                    
                    # Debug signature path extensively
                    current_app.logger.info(f"Preparer signature file: {prep_fn}")
                    current_app.logger.info(f"Full signature path: {os.path.abspath(sig_path)}")
                    current_app.logger.info(f"Signature directory exists: {os.path.exists(os.path.dirname(sig_path))}")
                    current_app.logger.info(f"Signature file exists: {os.path.exists(sig_path)}")
                    
                    if os.path.exists(sig_path):
                        try:
                            # Verify file is readable and has content
                            file_size = os.path.getsize(sig_path)
                            current_app.logger.info(f"Signature file size: {file_size} bytes")
                            
                            if file_size > 0:
                                # Create inline image with the signature
                                sig_prepared = InlineImage(tpl, sig_path, width=Mm(40))
                                current_app.logger.info("Successfully created InlineImage for preparer signature")
                            else:
                                current_app.logger.error(f"Signature file exists but is empty (0 bytes)")
                        except Exception as e:
                            current_app.logger.error(f"Error loading preparer signature: {e}", exc_info=True)
                    else:
                        # Try alternate paths as fallback
                        alternate_paths = [
                            os.path.join(current_app.root_path, 'static', 'signatures', prep_fn),
                            os.path.join(os.getcwd(), 'static', 'signatures', prep_fn)
                        ]
                        
                        for alt_path in alternate_paths:
                            current_app.logger.info(f"Trying alternate path: {os.path.abspath(alt_path)}")
                            if os.path.exists(alt_path):
                                try:
                                    sig_prepared = InlineImage(tpl, alt_path, width=Mm(40))
                                    current_app.logger.info(f"Successfully loaded signature from alternate path: {alt_path}")
                                    break
                                except Exception as e:
                                    current_app.logger.error(f"Error loading from alternate path: {e}")
                
                # Load Automation Manager signature (stage 1) with better error handling
                tech_lead_approval = next((a for a in approvals if a["stage"] == 1), None)
                if tech_lead_approval:
                    sig_fn = tech_lead_approval.get("signature")
                    if sig_fn:
                        # Make sure it has .png extension
                        if not sig_fn.lower().endswith('.png'):
                            sig_fn += '.png'
                            
                        sig_path = os.path.join(current_app.config['SIGNATURES_FOLDER'], sig_fn)
                        current_app.logger.info(f"Automation Manager signature path: {os.path.abspath(sig_path)}")
                        current_app.logger.info(f"File exists: {os.path.exists(sig_path)}")
                        
                        if os.path.exists(sig_path):
                            try:
                                file_size = os.path.getsize(sig_path)
                                current_app.logger.info(f"Automation Manager signature file size: {file_size} bytes")
                                
                                if file_size > 0:
                                    tech_lead_sig = InlineImage(tpl, sig_path, width=Mm(40))
                                    current_app.logger.info(f"Successfully loaded Automation Manager signature")
                            except Exception as e:
                                current_app.logger.error(f"Error loading Automation Manager signature: {e}")
                                tech_lead_sig = ""
                        else:
                            # Try alternate paths
                            for alt_path in [
                                os.path.join(current_app.root_path, 'static', 'signatures', sig_fn),
                                os.path.join(os.getcwd(), 'static', 'signatures', sig_fn)
                            ]:
                                if os.path.exists(alt_path):
                                    try:
                                        tech_lead_sig = InlineImage(tpl, alt_path, width=Mm(40))
                                        current_app.logger.info(f"Used alternate path for Automation Manager signature: {alt_path}")
                                        break
                                    except Exception as e:
                                        current_app.logger.error(f"Error loading from alt path: {e}")
                
                # Load PM signature (stage 2) with better error handling
                pm_approval = next((a for a in approvals if a["stage"] == 2), None)
                if pm_approval:
                    sig_fn = pm_approval.get("signature")
                    if sig_fn:
                        # Make sure it has .png extension
                        if not sig_fn.lower().endswith('.png'):
                            sig_fn += '.png'
                            
                        sig_path = os.path.join(current_app.config['SIGNATURES_FOLDER'], sig_fn)
                        current_app.logger.info(f"PM signature path: {os.path.abspath(sig_path)}")
                        current_app.logger.info(f"File exists: {os.path.exists(sig_path)}")
                        
                        if os.path.exists(sig_path):
                            try:
                                file_size = os.path.getsize(sig_path)
                                current_app.logger.info(f"PM signature file size: {file_size} bytes")
                                
                                if file_size > 0:
                                    pm_sig = InlineImage(tpl, sig_path, width=Mm(40))
                                    current_app.logger.info(f"Successfully loaded PM signature")
                            except Exception as e:
                                current_app.logger.error(f"Error loading PM signature: {e}")
                                pm_sig = ""
                        else:
                            # Try alternate paths
                            for alt_path in [
                                os.path.join(current_app.root_path, 'static', 'signatures', sig_fn),
                                os.path.join(os.getcwd(), 'static', 'signatures', sig_fn)
                            ]:
                                if os.path.exists(alt_path):
                                    try:
                                        pm_sig = InlineImage(tpl, alt_path, width=Mm(40))
                                        current_app.logger.info(f"Used alternate path for PM signature: {alt_path}")
                                        break
                                    except Exception as e:
                                        current_app.logger.error(f"Error loading from alt path: {e}")
                
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
                        from utils import send_client_final_document
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
        return redirect(url_for('main.index'))

@approval_bp.route('/reject/<submission_id>/<int:stage>', methods=['POST'])
def reject_submission(submission_id, stage):
    """Reject a submission at a specific approval stage"""
    try:
        submissions = load_submissions()
        submission_data = submissions.get(submission_id)
        
        if not submission_data:
            flash("Submission not found", "error")
            return redirect(url_for('main.index'))

        approvals = submission_data.get("approvals", [])
        current_stage = next((a for a in approvals if a["stage"] == stage), None)
        
        if not current_stage:
            flash("Approval stage not found", "error")
            return redirect(url_for('main.index'))
            
        # Only pending approvals can be rejected
        if current_stage["status"] != "pending":
            flash("This stage is not pending approval", "error")
            return redirect(url_for('status.view_status', submission_id=submission_id))

        # Mark as rejected with comment
        current_stage["status"] = "rejected"
        current_stage["comment"] = request.form.get("rejection_comment", "")
        current_stage["timestamp"] = datetime.datetime.now().isoformat()
        current_stage["approver_name"] = request.form.get("approver_name", "")
        
        # Create rejection notification for submitter
        from utils import create_status_update_notification
        try:
            user_email = submission_data.get("user_email")
            document_title = submission_data.get("context", {}).get("DOCUMENT_TITLE", "SAT Report")
            if user_email:
                create_status_update_notification(
                    user_email=user_email,
                    submission_id=submission_id,
                    status="rejected",
                    document_title=document_title,
                    approver_name=current_stage["approver_name"]
                )
        except Exception as e:
            current_app.logger.error(f"Error creating rejection notification: {e}")
        
        # Update submission
        submission_data["updated_at"] = datetime.datetime.now().isoformat()
        submissions[submission_id] = submission_data
        save_submissions(submissions)
        
        # Notify submitter about rejection
        user_email = submission_data.get("user_email")
        if user_email:
            # In a real implementation, you would add code to notify the submitter about rejection
            pass
            
        flash("Submission has been rejected with comments", "warning")
        return redirect(url_for('status.view_status', submission_id=submission_id))
        
    except Exception as e:
        current_app.logger.error(f"Error in reject_submission: {e}", exc_info=True)
        flash(f"An error occurred during the rejection process: {str(e)}", "error")
        return redirect(url_for('status.view_status', submission_id=submission_id))