from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from extensions import db
from models import Mail, MailRecipient, User

# Create Blueprint
mail_bp = Blueprint("mail", __name__, template_folder="templates/mail")


# -------------------- Routes --------------------


@mail_bp.route('/mail/compose', methods=['GET', 'POST'])
@login_required
def create_mail():

    recipient_id = request.args.get('recipient_id')  # get from URL
    users = User.query.filter(User.id != current_user.id).all()

    if request.method == 'POST':
        subject = request.form['subject']
        message = request.form['message']
        priority = request.form['priority']
        recipient_ids = request.form.getlist('recipients')

        mail = Mail(
            subject=subject,
            message=message,
            priority=priority,
            sender_id=current_user.id
        )

        mail.recipients = User.query.filter(User.id.in_(recipient_ids)).all()

        db.session.add(mail)
        db.session.commit()

        flash('Mail sent successfully!', 'success')
        return redirect(url_for('mail.view_mail', mail_id=mail.id))

    return render_template(
        'mail/compose.html',
        users=users,
        recipient_id=recipient_id
    )
    
@mail_bp.route('/mail/view/<int:mail_id>')
@login_required
def view_mail(mail_id):
    mail = Mail.query.get_or_404(mail_id)

    recipient_entry = MailRecipient.query.filter_by(
        mail_id=mail.id,
        user_id=current_user.id
    ).first()

    if recipient_entry and not recipient_entry.is_read:
        recipient_entry.is_read = True
        db.session.commit()
    elif mail.sender_id != current_user.id:
        flash("You are not authorized to view this mail.", "danger")
        return redirect(url_for('mail.list_mails', folder='inbox'))

    return render_template('mail/view.html', mail=mail)


@mail_bp.route('/mail/edit/<int:mail_id>', methods=['GET', 'POST'])
@login_required
def edit_mail(mail_id):
    mail = Mail.query.get_or_404(mail_id)

    if mail.sender_id != current_user.id:
        flash('You cannot edit this mail.', 'danger')
        return redirect(url_for('mail.view_mail', mail_id=mail.id))

    users = User.query.filter(User.id != current_user.id).all()

    if request.method == 'POST':
        mail.subject = request.form['subject']
        mail.message = request.form['message']
        mail.priority = request.form['priority']
        mail.status = request.form['status']

        recipient_ids = request.form.getlist('recipients')
        mail.recipients = User.query.filter(User.id.in_(recipient_ids)).all()

        db.session.commit()
        flash('Mail updated successfully!', 'success')
        return redirect(url_for('mail.view_mail', mail_id=mail.id))

    return render_template('mail/edit.html', mail=mail, users=users)


@mail_bp.route('/mail/<int:mail_id>/delete', methods=['POST'])
@login_required
def delete_mail(mail_id):
    mail = Mail.query.get_or_404(mail_id)

    if current_user.role == 'admin' or mail.sender_id == current_user.id:
        db.session.delete(mail)
        db.session.commit()
        flash('Mail deleted successfully!', 'success')
        return redirect(url_for('mail.list_mails', folder='inbox'))

    if current_user in mail.recipients:
        mail.status = 'trash'
        db.session.commit()
        flash('Mail moved to trash.', 'success')
        return redirect(url_for('mail.list_mails', folder='inbox'))

    flash('You cannot delete this mail.', 'danger')
    return redirect(url_for('mail.view_mail', mail_id=mail.id))


@mail_bp.route('/mail/<folder>')
@login_required
def list_mails(folder):
    folder = folder.lower()
    if folder not in ['inbox', 'sent', 'archive', 'trash']:
        flash('Invalid folder', 'danger')
        return redirect(url_for('mail.list_mails', folder='inbox'))

    if folder == 'sent':
        mails = Mail.query.filter_by(sender_id=current_user.id)\
            .order_by(Mail.created.desc()).all()
        folder_title = "Sent Mails"

    elif folder == 'inbox':
        # ✅ ONLY where current user is an intended recipient
        mails = Mail.query.filter(
            Mail.recipients.any(user_id=current_user.id)
        ).order_by(Mail.created.desc()).all()
        folder_title = "Inbox"

    else:
        # archive / trash → still must be recipient + status
        mails = Mail.query.filter(
            Mail.recipients.any(user_id=current_user.id),
            Mail.status == folder
        ).order_by(Mail.created.desc()).all()
        folder_title = folder.capitalize()

    return render_template('mail/list.html', mails=mails, folder_title=folder_title)


@mail_bp.route("/api/mails")
@login_required
def api_mails():
    mails = Mail.query.join(MailRecipient)\
        .filter(MailRecipient.user_id == current_user.id)\
        .order_by(Mail.created.desc())\
        .limit(5)\
        .all()

    data = []
    for m in mails:
        recipient_entry = MailRecipient.query.filter_by(
            mail_id=m.id,
            user_id=current_user.id
        ).first()

        data.append({
            "id": m.id,
            "subject": m.subject,
            "message": m.message,
            "priority": m.priority,
            "is_read": recipient_entry.is_read if recipient_entry else True,
            "sender": (
                f"{m.sender.first_name or ''} {m.sender.last_name or ''}".strip()
                if m.sender.first_name or m.sender.last_name
                else m.sender.username
            ),
            "created": m.created.isoformat(),
            "avatar": url_for("static", filename=f"profile_pics/{m.sender.profile_picture}")
        })

    return jsonify(data)