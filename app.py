from flask import Flask, render_template, redirect, url_for, request, flash, abort
from sqlalchemy.dialects.mysql import JSON
from flask_sqlalchemy import SQLAlchemy
from geopy.geocoders import Nominatim

from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_migrate import Migrate
from functools import wraps
from datetime import datetime
from flask_socketio import SocketIO, emit, join_room, leave_room
from datetime import datetime
from flask_caching import Cache


import uuid
from flask import jsonify
from sqlalchemy import func

import os
import json
import redis
from functools import wraps
from sqlalchemy import or_

from flask_login import user_logged_in, user_logged_out
# caching + fuzzy
from flask_caching import Cache
from PIL import Image
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from extensions import db, migrate, login_manager, socketio, cache
from mail import mail_bp
from models import *;

#AI MODEL / Libararies/Load/Call
from transformers import BlipProcessor, BlipForConditionalGeneration
import torch
import configparser


# Dictionary of errors and their messages
error_messages = {
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Page Not Found",
    405: "Method Not Allowed",
    500: "Internal Server Error",
    502: "Bad Gateway",
    503: "Service Unavailable"
}
error_descriptions = {
    400: "The request sent by the client is invalid.",
    401: "You are not authenticated to access this page.",
    403: "You do not have permission to view this resource.",
    404: "The page you are looking for does not exist.",
    405: "This HTTP method is not allowed for this route.",
    500: "An unexpected server error occurred.",
    502: "Invalid response received from upstream server.",
    503: "The service is currently unavailable, possibly due to database or server issues."
} 


# Load BLIP model once (IMPORTANT for performance)
processor = BlipProcessor.from_pretrained(
    "Salesforce/blip-image-captioning-large",
     use_fast=False
)
model = BlipForConditionalGeneration.from_pretrained(
    "Salesforce/blip-image-captioning-large"
)
model.eval()
CATEGORY_KEYWORDS = {
    "Electronics": ["phone", "mobile", "laptop", "charger", "earphones", "headphones", "tablet", "camera"],
    "Bags": ["bag", "backpack", "handbag", "purse", "school bag"],
    "Wallets": ["wallet", "purse", "card holder"],
    "Keys": ["keys", "keychain"],
    "Books": ["book", "notebook", "textbook"],
    "Clothing": ["shirt", "pant", "shoe", "jacket", "sweater", "cap"],
    "Accessories": ["watch", "belt", "glasses", "sunglasses"],
    "Bottles": ["bottle", "water bottle", "flask"],
    "Others": []
}


try:
    from Levenshtein import distance as lev_distance # fast C implementation
    HAVE_LEV = True
except Exception:
    HAVE_LEV = False

from math import radians, cos, sin, asin, sqrt




def hash_password(password: str) -> str:
    """
    Generate a secure password hash using PBKDF2 with SHA256.
    """
    return generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)

def verify_password(stored_hash: str, password: str) -> bool:
    """
    Verify a password against the stored PBKDF2 hash.
    """
    return check_password_hash(stored_hash, password)
    
# -------------------- Flask App Setup --------------------
app = Flask(__name__)
@app.context_processor
def inject_unread_mail_count():
    if current_user.is_authenticated:
        unread_count = MailRecipient.query.filter_by(
            user_id=current_user.id,
            is_read=False
        ).count()
    else:
        unread_count = 0

    return dict(unread_count=unread_count)
    



# in-memory user -> sid set to track multiple connections per user
online_users = {}  # { user_id: set(socket_ids) }


app.config['SECRET_KEY'] = 'your_secret_key_here'
config = configparser.ConfigParser()
config.read('config.ini')

db_config = config['mysql']

host = db_config['host']
port = db_config['port']
user = db_config['user']
password = db_config['password']
database = db_config['database']

app.config['SQLALCHEMY_DATABASE_URI'] = (
    f"mysql://{user}:{password}@{host}:{port}/{database}"
)

 



app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Upload folders
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['CLAIM_DOC_FOLDER'] = os.path.join('static', 'claim_docs')
app.config['PROFILE_PIC_FOLDER'] = os.path.join('static', 'profile_pics')





# Make sure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['CLAIM_DOC_FOLDER'], exist_ok=True)
os.makedirs(app.config['PROFILE_PIC_FOLDER'], exist_ok=True)

# -------------------- Initialize Extensions --------------------
db.init_app(app)
migrate.init_app(app, db)
login_manager.init_app(app)
socketio.init_app(app)
cache.init_app(app)
# Create tables automatically
with app.app_context():
    db.create_all()
  # Check if admin already exists
    admin = User.query.filter_by(username='admin').first()

    if not admin:
        admin_user = User(
            username='admin',
            email='admin@example.com',
            password=hash_password('admin123'),
            role='admin'
        )

        db.session.add(admin_user)
        db.session.commit()

        print("Default admin created!")
    else:
        print("Admin already exists.")

cache.init_app(app, config={
    "CACHE_TYPE": "SimpleCache",
    "CACHE_DEFAULT_TIMEOUT": 300
})

login_manager.login_view = 'login'
# ---------------------Blueprint------------------
app.register_blueprint(mail_bp)

    
# -------------------- Login Manager --------------------
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# -------------------- Role Decorator --------------------
def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if current_user.role not in roles:
                flash("Access denied.", "danger")
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


    
    
# -------------------- Routes --------------------
@app.route('/')
def home():
  
 
        
    return redirect(url_for('dashboard'))

 

# -------------------- Authentication --------------------
# -------------------- Login --------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()

        # Case-insensitive search
        user = User.query.filter(func.lower(User.username) == username.lower()).first()

        if not user:
            flash('No account found with this username.', 'danger')
            return render_template('login.html')

        # Check password
        if verify_password(user.password, password):
            login_user(user)
            flash(f'Welcome back, {user.username}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid password. Please try again.', 'danger')
            return render_template('login.html')

    return render_template('login.html')
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        email = request.form['email'].strip()
        password = request.form['password'].strip()
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        city = request.form.get('city')
        country = request.form.get('country')
        street = request.form.get('street')
        zip_code = request.form.get('zip_code')

        # Check if username/email already exists (case-insensitive)
        existing_user = User.query.filter(func.lower(User.username) == username.lower()).first()
        if existing_user:
            flash('Username already exists. Choose another.', 'danger')
            return render_template('register.html')

        existing_email = User.query.filter(func.lower(User.email) == email.lower()).first()
        if existing_email:
            flash('Email already registered. Use another email.', 'danger')
            return render_template('register.html')

        # Handle profile picture
        profile_picture_file = request.files.get('profile_picture')
        if profile_picture_file and profile_picture_file.filename != '':
            filename = secure_filename(profile_picture_file.filename)
            profile_picture_file.save(os.path.join(app.config['PROFILE_PIC_FOLDER'], filename))
        else:
            filename = 'default.jpg'

        # Create new user
        new_user = User(
            username=username,
            password=hash_password(password),
            email=email,
            first_name=first_name,
            last_name=last_name,
            city=city,
            country=country,
            street=street,
            zip_code=zip_code,
            profile_picture=filename
        )

        db.session.add(new_user)
        db.session.commit()
        flash('Account created successfully! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# -------------------- User Profile --------------------
@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.first_name = request.form.get('first_name')
        current_user.last_name = request.form.get('last_name')
        current_user.email = request.form.get('email')
        current_user.city = request.form.get('city')
        current_user.country = request.form.get('country')
        current_user.street = request.form.get('street')
        current_user.zip_code = request.form.get('zip_code')

        profile_picture_file = request.files.get('profile_picture')
        if profile_picture_file:
            filename = secure_filename(profile_picture_file.filename)
            profile_picture_file.save(os.path.join(app.config['PROFILE_PIC_FOLDER'], filename))
            current_user.profile_picture = filename

        db.session.commit()
        flash('Profile updated!', 'success')
        return redirect(url_for('profile'))

    return render_template('profile.html')

# -------------------- Dashboard --------------------
# -------------------- Dashboard --------------------
@app.route('/dashboard')
@login_required
def dashboard():
    announcements = (
        Announcement.query
        .filter(
            Announcement.is_active == True,
            (Announcement.expires_at == None) |
            (Announcement.expires_at > datetime.utcnow())
        )
        .order_by(
            Announcement.is_pinned.desc(),
            Announcement.created_at.desc()
        )
        .all()
    )
    # Fetch all items (latest first)
    items = Item.query.order_by(Item.date_reported.desc()).all()
    categories = Category.query.all()

    # For each item, filter comments based on role
    for item in items:
        if current_user.role in ['admin', 'moderator']:
            # Moderators and admins see all comments
            item.filtered_comments = Comment.query.filter_by(item_id=item.id).order_by(Comment.timestamp.desc()).all()
        else:
            # Regular users see only approved comments and their own pending ones
            item.filtered_comments = Comment.query.filter(
                Comment.item_id == item.id,
                db.or_(
                    Comment.status == 'approved',
                    db.and_(
                        Comment.status == 'pending',
                        Comment.user_id == current_user.id
                    )
                )
            ).order_by(Comment.timestamp.desc()).all()

    return render_template('dashboard.html',items=items, categories=categories,announcements=announcements)
#---------------------Announcement------------------
@app.route("/announcements/create", methods=["POST"])
@login_required
def create_announcement():
    if current_user.role not in ["admin", "moderator"]:
        abort(403)

    announcement = Announcement(
        title=request.form["title"],
        message=request.form["message"],
        is_pinned=bool(request.form.get("is_pinned")),
        expires_at=request.form.get("expires_at") or None,
        created_by_id=current_user.id
    )

    db.session.add(announcement)
    db.session.commit()

    flash("Announcement published", "success")
    return redirect(url_for("dashboard"))
@app.route("/announcements/<int:id>/edit", methods=["POST"])
@login_required
def edit_announcement(id):
    if current_user.role not in ["admin", "moderator"]:
        abort(403)

    announcement = Announcement.query.get_or_404(id)

    announcement.title = request.form["title"]
    announcement.message = request.form["message"]
    announcement.is_pinned = bool(request.form.get("is_pinned"))
    announcement.expires_at = request.form.get("expires_at") or None

    db.session.commit()

    flash("Announcement updated", "success")
    return redirect(url_for("dashboard"))
@app.route("/announcements/<int:id>/delete")
@login_required
def delete_announcement(id):
    if current_user.role not in ["admin", "moderator"]:
        abort(403)

    announcement = Announcement.query.get_or_404(id)
    announcement.is_active = False

    db.session.commit()

    flash("Announcement removed", "success")
    return redirect(url_for("dashboard"))

    

# -------------------- Add Item --------------------
@app.route('/add_item', methods=['GET', 'POST'])
@login_required
def add_item():
    categories = Category.query.all()

    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        location = request.form['location']
        latitude = request.form.get('latitude', type=float)
        longitude = request.form.get('longitude', type=float)
        status = request.form.get('status', 'lost')
        category_id = request.form.get('category_id', type=int)

        photo_file = request.files.get('photo')
        filename = None

        if photo_file and photo_file.filename:
            filename = secure_filename(photo_file.filename)
            photo_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            photo_file.save(photo_path)

        item = Item(
            name=name,
            description=description,  # Human + AI text
            location=location,
            latitude=latitude,
            longitude=longitude,
            status=status,
            photo=filename,
            category_id=category_id,
            user_id=current_user.id
        )

        db.session.add(item)
        db.session.commit()

        flash('Item added successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('add_item.html', categories=categories)

@app.route('/edit_item/<int:item_id>', methods=['GET', 'POST'])
@login_required
def edit_item(item_id):
    item = Item.query.get_or_404(item_id)
    categories = Category.query.all()

    # ✅ Authorization:
    # Allow if:
    # - User is admin
    # - OR user is owner of the item
    if not current_user.role == "admin" and item.user_id != current_user.id:
        flash("You are not authorized to edit this item.", "danger")
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        item.name = request.form['name']
        item.description = request.form['description']
        item.location = request.form['location']
        item.latitude = request.form.get('latitude', type=float)
        item.longitude = request.form.get('longitude', type=float)
        item.status = request.form.get('status', 'lost')
        item.category_id = request.form.get('category_id', type=int)

        # Handle new photo (optional)
        photo_file = request.files.get('photo')
        if photo_file and photo_file.filename:
            filename = secure_filename(photo_file.filename)
            photo_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            photo_file.save(photo_path)
            item.photo = filename

        db.session.commit()

        flash('Item updated successfully!', 'success')

        # Optional: redirect admin differently
        if current_user.role == "admin":
            return redirect(url_for('dashboard'))
        else:
            return redirect(url_for('dashboard'))

    return render_template('edit_item.html', item=item, categories=categories)
@app.route('/delete_item/<int:item_id>', methods=['POST'])
@login_required
def delete_item(item_id):
    item = Item.query.get_or_404(item_id)

    # ✅ Authorization check
    if current_user.role != "admin" and item.user_id != current_user.id:
        flash("You are not authorized to delete this item.", "danger")
        return redirect(url_for('dashboard'))

    # Optional: delete image file from server
    if item.photo:
        photo_path = os.path.join(app.config['UPLOAD_FOLDER'], item.photo)
        if os.path.exists(photo_path):
            os.remove(photo_path)

    # Delete from DB
    db.session.delete(item)
    db.session.commit()

    flash("Item deleted successfully!", "success")
    return redirect(url_for('dashboard'))
@app.route('/item/<int:item_id>')
@login_required
def view_item(item_id):
    item = Item.query.get_or_404(item_id)

    # Comments visibility
    if current_user.role in ['admin', 'moderator']:
        comments = Comment.query.filter_by(item_id=item.id).order_by(Comment.timestamp.asc()).all()
    else:
        comments = Comment.query.filter(
            Comment.item_id == item.id,
            db.or_(
                Comment.status == 'approved',
                db.and_(Comment.status == 'pending', Comment.user_id == current_user.id)
            )
        ).order_by(Comment.timestamp.asc()).all()

    return render_template(
    'item_detail.html',
    item=item,
    comments=comments,
    Comment=Comment  # ✅ pass the class
)


# -------------------- Comments --------------------
@app.template_filter('hashcolor')
def hashcolor(s):
    """Generate a consistent pastel color for a string."""
    import hashlib
    h = int(hashlib.md5(s.encode()).hexdigest(), 16)
    r = (h & 0xFF0000) >> 16
    g = (h & 0x00FF00) >> 8
    b = h & 0x0000FF
    # pastel tone
    r = (r + 255) // 2
    g = (g + 255) // 2
    b = (b + 255) // 2
    return f'rgb({r},{g},{b})'



@app.route('/add_comment/<int:item_id>', methods=['POST'])
def add_comment(item_id):
    if request.is_json:
        data = request.get_json()
        content = data.get("content")
        parent_id = data.get("parent_id")
    else:
        content = request.form.get("content")
        parent_id = request.form.get("parent_id")

    if not content:
        if request.is_json:
            return jsonify({"error": "Comment cannot be empty"}), 400
        flash("Comment cannot be empty", "danger")
        return redirect(request.referrer or url_for('dashboard'))

    new_comment = Comment(
        item_id=item_id,
        content=content,
        parent_id=parent_id if parent_id else None,
        user_id=current_user.id,
        status="pending"
    )

    db.session.add(new_comment)
    db.session.commit()

    if request.is_json:
        return jsonify({
            "id": new_comment.id,
            "content": new_comment.content,
            "username": current_user.username,
            "avatar": url_for('static', filename='profile_pics/' + (current_user.profile_picture or 'default-avatar.png')),
            "timestamp": new_comment.timestamp.strftime("%Y-%m-%d %H:%M"),
            "parent_id": new_comment.parent_id
        }), 201

    flash("Comment added successfully", "success")
    return redirect(request.referrer or url_for('dashboard'))


    
@app.route('/comment/react/<int:comment_id>', methods=['POST'])
@login_required
def react_comment(comment_id):
    try:
        # Get JSON payload
        data = request.get_json()
        if not data or 'reaction' not in data:
            return jsonify({'success': False, 'error': 'No reaction provided'}), 400

        reaction_type = data['reaction']
        if reaction_type not in ['like', 'dislike']:
            return jsonify({'success': False, 'error': 'Invalid reaction type'}), 400

        # Fetch the comment
        comment = Comment.query.get_or_404(comment_id)

        # Check if user already reacted
        existing_reaction = CommentReaction.query.filter_by(
            comment_id=comment.id,
            user_id=current_user.id
        ).first()

        if existing_reaction:
            if existing_reaction.reaction == reaction_type:
                # Toggle off the same reaction
                db.session.delete(existing_reaction)
                user_reaction = None
            else:
                # Switch reaction
                existing_reaction.reaction = reaction_type
                user_reaction = reaction_type
        else:
            # Add new reaction
            new_reaction = CommentReaction(
                comment_id=comment.id,
                user_id=current_user.id,
                reaction=reaction_type
            )
            db.session.add(new_reaction)
            user_reaction = reaction_type

        db.session.commit()

        # Count likes/dislikes
        likes = CommentReaction.query.filter_by(comment_id=comment.id, reaction='like').count()
        dislikes = CommentReaction.query.filter_by(comment_id=comment.id, reaction='dislike').count()

        return jsonify({
            'success': True,
            'likes': likes,
            'dislikes': dislikes,
            'user_reaction': user_reaction
        })
    
    except Exception as e:
        # Debugging: print stack trace
        import traceback
        print(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

    
    
@app.route('/claims/all')
@login_required
@role_required('moderator', 'admin')
def all_claims():
    claims = Claim.query.order_by(Claim.timestamp.desc()).all()
    return render_template('all_claims.html', claims=claims)
    

# -------------------- Claims --------------------
@app.route('/claim_item/<int:item_id>', methods=['GET', 'POST'])
@login_required
def claim_item(item_id):
    item = Item.query.get_or_404(item_id)
    if request.method == 'POST':
        contact_info = request.form['contact_info']

        # Multiple file uploads
        uploaded_files = request.files.getlist('documents')
        saved_files = []

        for file in uploaded_files:
            if file and file.filename:
                filename = secure_filename(file.filename)
                save_path = os.path.join(app.config['CLAIM_DOC_FOLDER'], filename)
                file.save(save_path)
                saved_files.append(filename)

        # Save claim with multiple docs as JSON
        claim = Claim(
            item_id=item.id,
            user_id=current_user.id,
            contact_info=contact_info,
            document_paths=saved_files
        )

        db.session.add(claim)
        db.session.commit()
        flash('Claim submitted with multiple documents!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('claim_item.html', item=item)

# -------------------- Manage Claims (Admin/Moderator) --------------------
@app.route('/claims/pending')
@login_required
@role_required('moderator', 'admin')
def pending_claims():
    claims = Claim.query.filter_by(status='pending').all()
    return render_template('pending_claims.html', claims=claims)

@app.route('/claims/<int:claim_id>/approve')
@login_required
@role_required('moderator', 'admin')
def approve_claim(claim_id):
    claim = Claim.query.get_or_404(claim_id)
    item = claim.item
    for c in item.claims:
        if c.id != claim.id:
            c.status = 'rejected'
    claim.status = 'approved'
    item.status = 'claimed'
    db.session.commit()
    
    
    # 🔔 Push notification to the user
    push_notification(
        user_id=claim.user.id,
        message=f"Your claim for '{item.name}' has been approved!",
        url=f"/item/{item.id}"
    )


    flash(f"Claim by {claim.user.username} approved!", 'success')
    return redirect(url_for('all_claims'))


@app.route('/claims/<int:claim_id>/reject')
@login_required
@role_required('moderator', 'admin')
def reject_claim(claim_id):
    claim = Claim.query.get_or_404(claim_id)
    claim.status = 'rejected'
    db.session.commit()
    # 🔔 Notify user
    push_notification(
        user_id=claim.user_id,
        message=f"Your claim for '{claim.item.name}' was rejected.",
        url=f"/item/{claim.item.id}"
    )


    flash(f"Claim by {claim.user.username} rejected!", 'danger')
    return redirect(url_for('pending_claims'))
    
    
@app.template_filter('format_datetime')
def format_datetime(value):
    if value is None:
        return 'N/A'
    return value.strftime('%Y-%m-%d %H:%M')    
    

#Comment                        
# -------------------- Comment Moderation --------------------
@app.route('/comments/pending')
@login_required
@role_required('moderator', 'admin')
def pending_comments():
    comments = Comment.query.filter_by(status='pending').order_by(Comment.timestamp.desc()).all()
    return render_template('pending_comments.html', comments=comments)

@app.route('/comments/<int:comment_id>/approve')
@login_required
@role_required('moderator', 'admin')
def approve_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    comment.status = 'approved'
    db.session.commit()
    
    
    # 🔔 Notify comment owner
    push_notification(
        user_id=comment.user_id,
        message=f"Your comment on '{comment.item.name}' has been approved!",
        url=f"/item/{comment.item_id}"
    )
    
    flash('Comment approved successfully!', 'success')
    return redirect(url_for('pending_comments'))

@app.route('/comments/<int:comment_id>/reject')
@login_required
@role_required('moderator', 'admin')
def reject_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    comment.status = 'rejected'
    db.session.commit()
        # 🔔 Notify comment owner
    push_notification(
        user_id=comment.user_id,
        message=f"Your comment on '{comment.item.name}' was rejected.",
        url=f"/item/{comment.item_id}"
    )
    
    flash('Comment rejected.', 'danger')
    return redirect(url_for('pending_comments'))    
@app.route('/comments/<int:comment_id>/pending')
@login_required
@role_required('moderator', 'admin')
def pending_comment(comment_id):

    comment = Comment.query.get_or_404(comment_id)
    comment.status = 'pending'

    db.session.commit()

    flash('Comment moved back to pending review.', 'warning')

    return redirect(request.referrer or url_for('pending_comments'))
@app.route('/comments/<int:comment_id>/delete', methods=['POST'])
@login_required
@role_required('moderator', 'admin')
def delete_comment_moderator(comment_id):

    comment = Comment.query.get_or_404(comment_id)

    try:
        delete_comment_tree(comment)

        db.session.commit()

        flash('Comment and its replies deleted successfully.', 'success')

    except Exception:
        db.session.rollback()
        flash('Error deleting comment.', 'danger')

    return redirect(url_for('pending_comments'))





#---------Categories---------------


@app.route('/categories')
def categories():
    all_categories = Category.query.all()
    return render_template('categories.html', categories=all_categories)

@app.route('/categories/add', methods=['GET', 'POST'])
def add_category():
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']

        if not name.strip():
            flash('Category name is required.', 'danger')
            return redirect(url_for('add_category'))

        new_cat = Category(name=name, description=description)
        db.session.add(new_cat)
        db.session.commit()
        flash('Category added successfully!', 'success')
        return redirect(url_for('categories'))
    
    return render_template('add_category.html')

@app.route('/categories/delete/<int:id>')
def delete_category(id):
    category = Category.query.get_or_404(id)
    db.session.delete(category)
    db.session.commit()
    flash('Category deleted successfully.', 'success')
    return redirect(url_for('categories'))
    

 

@app.route('/manage_users')
@login_required
@role_required('admin', 'moderator')
def manage_users():
    users = User.query.order_by(User.id.desc()).all()
    return render_template('manage_users.html', users=users)

@app.route('/user/<int:user_id>')
@login_required
def view_user(user_id):
    user = User.query.get_or_404(user_id)
    return render_template('view_user.html', user=user)



@app.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    # Only admin or manager can edit users
    if current_user.role not in ['admin', 'moderator']:
        flash('Access denied: Only admins or managers can edit users.', 'danger')
        return redirect(url_for('manage_users'))

    user = User.query.get_or_404(user_id)

    if request.method == 'POST':
        user.username = request.form.get('username')
        user.email = request.form.get('email')
        user.first_name = request.form.get('first_name')
        user.last_name = request.form.get('last_name')
        user.city = request.form.get('city')
        user.country = request.form.get('country')
        user.street = request.form.get('street')
        user.zip_code = request.form.get('zip_code')
        user.role = request.form.get('role')

        # ✅ Handle password change (optional)
        new_password = request.form.get('password')
        if new_password:
            user.password = hash_password(new_password)

        # ✅ Handle profile picture update
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['PROFILE_PIC_FOLDER'], filename))
                user.profile_picture = filename

        try:
            db.session.commit()
            flash('User updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating user: {str(e)}', 'danger')

        return redirect(url_for('manage_users'))

    return render_template('edit_user.html', user=user)

@app.route('/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    # Only allow admins to delete users
    if current_user.role != 'admin':
        flash('Access denied: Only admins can delete users.', 'danger')
        return redirect(url_for('manage_users'))

    user = User.query.get_or_404(user_id)

    # Prevent self-deletion
    if user.id == current_user.id:
        flash('You cannot delete your own account.', 'warning')
        return redirect(url_for('manage_users'))

    try:
        db.session.delete(user)
        db.session.commit()
        flash(f'User "{user.username}" deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting user: {str(e)}', 'danger')

    return redirect(url_for('manage_users'))


@app.route('/set_user_role/<int:user_id>/<role>', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def set_user_role(user_id, role):

    # Allowed roles
    allowed_roles = ['user', 'moderator', 'admin']

    # Normalize role input
    role = role.strip().lower()

    # Validate role
    if role not in allowed_roles:
        flash(f'Invalid role: {role}', 'danger')
        return redirect(url_for('manage_users'))

    # Get user
    user = User.query.get_or_404(user_id)

    # Prevent changing own role
    if user.id == current_user.id:
        flash("You cannot change your own role.", 'warning')
        return redirect(url_for('manage_users'))

    # Prevent removing the last admin
    if user.role == 'admin' and role != 'admin':
        admin_count = User.query.filter_by(role='admin').count()

        if admin_count <= 1:
            flash('At least one admin account is required.', 'danger')
            return redirect(url_for('manage_users'))

    try:
        old_role = user.role
        user.role = role

        db.session.commit()

        flash(
            f"{user.username}'s role changed from {old_role} to {role}.",
            'success'
        )

    except Exception as e:
        db.session.rollback()

        app.logger.error(f"Role update error: {e}")

        flash('Error updating user role.', 'danger')

    return redirect(url_for('manage_users'))
    

 
# -------------------- Chat File Upload --------------------
ALLOWED_EXT = {'png','jpg','jpeg','gif','pdf','txt','doc','docx'}
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT


    
    
    
    
online_users = {}








#-----------------------Gen AI---------------------

def detect_category_from_caption(caption: str):
    caption = caption.lower()

    for category, keywords in CATEGORY_KEYWORDS.items():
        for word in keywords:
            if word in caption:
                return category

    return "Others"
@app.route("/generate-description", methods=["POST"])
@login_required
def generate_description():
    photo = request.files.get("photo")

    if not photo or photo.filename == "":
        return jsonify({"error": "No image uploaded"}), 400

    try:
        image = Image.open(photo).convert("RGB")

        inputs = processor(
            image,
            text="a clear photo of",
            return_tensors="pt"
        )

        with torch.no_grad():
            output = model.generate(**inputs, max_length=60)

        caption = processor.decode(output[0], skip_special_tokens=True)
        caption = caption.capitalize()

        detected_category = detect_category_from_caption(caption)

        return jsonify({
            "description": caption,
            "category": detected_category
        })

    except Exception:
        return jsonify({"error": "AI processing failed"}), 500

def get_nested_comments(item_id):
    """
    Returns comments for an item in nested structure with levels.
    Each node is a dict: {'comment': Comment, 'replies': [nodes], 'level': int}
    """
    all_comments = Comment.query.filter_by(item_id=item_id).order_by(Comment.timestamp.asc()).all()
    comment_dict = {c.id: c for c in all_comments}
    tree = []

    # Build a mapping: parent_id -> list of children
    children_map = {}
    for c in all_comments:
        children_map.setdefault(c.parent_id, []).append(c)

    def build_tree(parent_id=None, level=0):
        nodes = []
        for c in children_map.get(parent_id, []):
            node = {
                'comment': c,
                'replies': build_tree(c.id, level + 1),
                'level': level
            }
            nodes.append(node)
        return nodes

    return build_tree()


def delete_comment_tree(comment):
    """
    Recursively delete a comment and all its nested replies.
    """
    for reply in comment.replies:
        delete_comment_tree(reply)

    db.session.delete(comment)
    
@app.route('/delete_comment/<int:comment_id>', methods=['POST'])
@login_required
def delete_comment(comment_id):

    comment = Comment.query.get_or_404(comment_id)

    # Permission check
    if (
        current_user.role not in ['admin', 'moderator']
        and comment.user_id != current_user.id
        and comment.item.user_id != current_user.id
    ):
        flash("You are not allowed to delete this comment.", "danger")
        return redirect(request.referrer or url_for('dashboard'))

    try:
        delete_comment_tree(comment)

        db.session.commit()

        flash("Comment and all replies deleted.", "success")

    except Exception:
        db.session.rollback()
        flash("Error deleting comment.", "danger")

    return redirect(request.referrer or url_for('dashboard'))
    
#Search feature
# Helper to serialize Item
def serialize_item(item):
    return {
        'id': item.id,
        'name': item.name,
        'description': item.description,
        'photo': item.photo or '',
        'location': item.location or '',
        'date_reported': item.date_reported.strftime('%Y-%m-%d %H:%M'),
        'status': item.status,
        'category': item.category.name if item.category else None,
        'user': {
            'id': item.user.id,
            'username': item.user.username
        }
    }

def cache_key_for_search():
    args = request.args.to_dict(flat=True)
    key = "|".join(f"{k}:{v}" for k, v in sorted(args.items()))
    return f"search:{key}"


def require_json(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if not request.is_json and request.args.get('q') is None and request.method == 'GET':
            # allow normal GETs with query params
            pass
        return f(*a, **kw)
    return wrapper


@app.route('/api/search')
@login_required
def api_search():
    """
    JSON API used by AJAX frontend.
    Query params:
      - q (string)
      - status (lost|found|claimed or empty)
      - category_id (int)
      - date_from (YYYY-MM-DD)
      - date_to (YYYY-MM-DD)
      - page (int) default 1
      - per_page (int) default 6
      - lat (float) optional (user lat for proximity search)
      - lng (float) optional (user lng for proximity search)
      - radius_km (float) optional radius in km
      - use_my_location (bool) optional — indicates the client wants a location-based search
      - fuzzy_max (int) optional max edit distance to accept (default 3)
    """
    # Read params
    q = request.args.get('q', '', type=str).strip()
    status = request.args.get('status', type=str)
    category_id = request.args.get('category_id', type=int)
    date_from = request.args.get('date_from', type=str)
    date_to = request.args.get('date_to', type=str)
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 6, type=int)
    lat = request.args.get('lat', type=float)
    lng = request.args.get('lng', type=float)
    radius_km = request.args.get('radius_km', type=float)
    use_my_location = request.args.get('use_my_location', type=str)  # "true" or "false" or None
    fuzzy_max = request.args.get('fuzzy_max', 3, type=int)

    # If the user asked to search near them, but coords are missing -> return 400 (client should obtain coords)
    if use_my_location and use_my_location.lower() == 'true':
        if lat is None or lng is None:
            return jsonify({'error': 'missing_coordinates', 'message': 'Latitude and longitude are required for "near me" searches.'}), 400

    # Build cache key only when user did NOT request a private location-based search.
    cache_key = None
    if not (use_my_location and use_my_location.lower() == 'true'):
        # include user id so results can be personalized if needed
        args = request.args.to_dict(flat=True)
        args['uid'] = str(current_user.id if current_user.is_authenticated else 'anon')
        cache_key = "search:" + "&".join(f"{k}={args[k]}" for k in sorted(args))
        cached = cache.get(cache_key)
        if cached:
            return jsonify(cached)

    # Base SQL filters
    qry = Item.query.outerjoin(Category).join(User)

    if status and status.lower() in ('lost','found','claimed'):
        qry = qry.filter(Item.status == status.lower())
    if category_id:
        qry = qry.filter(Item.category_id == category_id)

    try:
        if date_from:
            dtf = datetime.strptime(date_from, '%Y-%m-%d')
            qry = qry.filter(Item.date_reported >= dtf)
        if date_to:
            dtt = datetime.strptime(date_to, '%Y-%m-%d')
            dtt = datetime(dtt.year, dtt.month, dtt.day, 23, 59, 59)
            qry = qry.filter(Item.date_reported <= dtt)
    except ValueError:
        pass

    # Pull candidates from DB (bounded by SQL filters)
    base_results = qry.order_by(Item.date_reported.desc()).all()

    # Apply fuzzy and proximity filtering in Python
    candidates = []
    q_lower = q.lower()
    for it in base_results:
        accept = True

        # Proximity (only if client requested it)
        if use_my_location and use_my_location.lower() == 'true' and radius_km:
            if it.latitude is None or it.longitude is None:
                accept = False
            else:
                dist = haversine_km(lat, lng, it.latitude, it.longitude)
                if dist > radius_km:
                    accept = False

        # Textual fuzzy matching if a query present
        if q and accept:
            fields = [
                (it.name or ""),
                (it.category.name if it.category else ""),
                (it.location or ""),
                ((it.description or "")[:200])
            ]
            best = None
            for text in fields:
                if not text:
                    continue
                sc = fuzzy_score(q_lower, text.lower())
                if best is None or sc < best:
                    best = sc
            # Accept if substring match OR fuzzy distance <= fuzzy_max
            if best is None:
                accept = False
            else:
                if (q_lower in (it.name or "").lower()) or (q_lower in (it.location or "").lower()) or (it.category and q_lower in it.category.name.lower()):
                    accept = True
                else:
                    accept = (best <= fuzzy_max)

        if accept:
            candidates.append(it)

    # sort & paginate
    candidates.sort(key=lambda x: x.date_reported, reverse=True)
    total = len(candidates)
    pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, pages))
    start = (page - 1) * per_page
    end = start + per_page
    page_items = candidates[start:end]

    def serialize_item(it):
        return {
            'id': it.id,
            'name': it.name,
            'description': it.description,
            'photo': it.photo or '',
            'location': it.location,
            'latitude': it.latitude,
            'longitude': it.longitude,
            'date_reported': it.date_reported.strftime('%Y-%m-%d %H:%M'),
            'status': it.status,
            'category': it.category.name if it.category else None,
            'user': {'id': it.user.id, 'username': it.user.username}
        }

    payload = {
        'items': [serialize_item(it) for it in page_items],
        'page': page,
        'per_page': per_page,
        'total': total,
        'pages': pages
    }

    # cache only when not a "near me" request (to avoid caching user-specific results)
    if cache_key:
        cache.set(cache_key, payload, timeout=60)

    return jsonify(payload)

    def serialize_item(it):
        return {
            'id': it.id,
            'name': it.name,
            'description': it.description,
            'photo': it.photo or '',
            'location': it.location,
            'latitude': it.latitude,
            'longitude': it.longitude,
            'date_reported': it.date_reported.strftime('%Y-%m-%d %H:%M'),
            'status': it.status,
            'category': it.category.name if it.category else None,
            'user': {'id': it.user.id, 'username': it.user.username}
        }

    payload = {
        'items': [serialize_item(it) for it in page_items],
        'page': page,
        'per_page': per_page,
        'total': total,
        'pages': pages
    }

    # store in cache for a short time
    cache.set(cache_key, payload, timeout=60)  # cache 60s by default
    return jsonify(payload)


@app.route('/api/suggest')
@login_required
def api_suggest():
    """
    Provide fuzzy autocomplete suggestions for the search input.
    Returns list of strings.
    """
    q = request.args.get('q', '', type=str).strip()
    max_results = request.args.get('max', 10, type=int)
    fuzzy_max = request.args.get('fuzzy_max', 2, type=int)

    if not q:
        return jsonify([])

    # first try prefix exact matches via SQL for speed (high priority)
    likeq = f"{q}%"
    rows = db.session.query(Item.name).filter(Item.name.ilike(likeq)).group_by(Item.name).limit(max_results).all()
    suggestions = [r[0] for r in rows]

    # if not enough results, fill with fuzzy matches using edit distance
    if len(suggestions) < max_results:
        all_names = [r[0] for r in db.session.query(Item.name).distinct().all()]
        candidates = []
        ql = q.lower()
        for name in all_names:
            d = fuzzy_score(ql, name.lower())
            if d <= fuzzy_max:
                candidates.append((d, name))
        candidates.sort(key=lambda x: x[0])
        for _d, name in candidates:
            if name not in suggestions:
                suggestions.append(name)
                if len(suggestions) >= max_results:
                    break

    return jsonify(suggestions[:max_results])
@app.route("/search")
def search_item():
    try:
        query = request.args.get("query", "").strip()
        category_id = request.args.get("category", type=int)
        radius = request.args.get("radius", type=float)
        lat = request.args.get("lat", type=float)
        lon = request.args.get("lon", type=float)   # ✅ FIXED
        page = request.args.get("page", 1, type=int)
        per_page = 12

        q = Item.query

        if category_id:
            q = q.filter(Item.category_id == category_id)

        if query:
            q = q.filter(
                or_(
                    Item.name.ilike(f"%{query}%"),
                    Item.description.ilike(f"%{query}%")
                )
            )

        items = q.all()

        results = []

        for it in items:

            # Proximity filter
            if lat is not None and lon is not None and radius is not None and radius > 0:
                if it.latitude is None or it.longitude is None:
                    continue

                dist = haversine_km(lat, lon, it.latitude, it.longitude)

                if dist > radius:
                    continue

                it.distance = round(dist, 2)
            else:
                it.distance = None

            results.append(it)

        total = len(results)
        pages = max(1, (total + per_page - 1) // per_page)
        page = max(1, min(page, pages))

        start = (page - 1) * per_page
        end = start + per_page
        paginated = results[start:end]

        items_json = []

        for it in paginated:
            img_url = url_for('static', filename=f"uploads/{it.photo}") if it.photo else None

            items_json.append({
                "id": it.id,
                "name": it.name,
                "description": it.description,
                "photo": img_url,
                "category": it.category.name if it.category else None,
                "status": it.status,
                "distance": getattr(it, "distance", None)
            })

        return jsonify({
            "items": items_json,
            "page": page,
            "pages": pages,
            "total": total
        })

    except Exception as e:
        print("Search error:", e)
        return jsonify({"error": str(e)}), 500





geolocator = Nominatim(user_agent="geo_locator_app")

@app.route('/get_address', methods=['POST'])
def get_address():
    data = request.get_json()

    latitude = data.get('latitude')
    longitude = data.get('longitude')

    if latitude is None or longitude is None:
        return jsonify({'error': 'Missing coordinates'}), 400

    try:
        location = geolocator.reverse((latitude, longitude), exactly_one=True)

        if location:
            return jsonify({
                'address': location.address
            })
        else:
            return jsonify({
                'address': 'Address not found'
            })

    except Exception as e:
        return jsonify({'error': str(e)}), 500



# ---------------- Helper: fuzzy match using Levenshtein (or fallback) ----------------
def fuzzy_score(a: str, b: str) -> int:
    """
    Lower is better (distance). Uses Levenshtein.distance if available,
    otherwise falls back to a simple implementation using dynamic programming.
    """
    if not a or not b:
        return max(len(a or ""), len(b or ""))
    a = a.lower()
    b = b.lower()
    if HAVE_LEV:
        return Levenshtein.distance(a, b)
    # fallback: simple DP edit distance (Levenshtein)
    m, n = len(a), len(b)
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, n + 1):
            temp = dp[j]
            if a[i - 1] == b[j - 1]:
                dp[j] = prev
            else:
                dp[j] = 1 + min(prev, dp[j], dp[j - 1])
            prev = temp
    return dp[n]

# ---------------- Helper: haversine distance (km) ----------------
def haversine_km(lat1, lon1, lat2, lon2):
    # convert degrees to radians
    lat1, lon1, lat2, lon2 = map(radians, (lat1, lon1, lat2, lon2))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    R = 6371.0
    return R * c


@app.route("/search/page")
def search_page():
    # Preload categories (optional)
    categories = Category.query.order_by(Category.name).all()
    return render_template("search.html", categories=categories)
@app.route("/autocomplete")
def autocomplete():
    q = request.args.get("q", "").strip().lower()
    if not q:
        return jsonify([])

    # Get only item names for speed
    names = [i.name for i in Item.query.with_entities(Item.name).all()]

    # Prefix matches
    prefix_matches = [n for n in names if n.lower().startswith(q)]

    # Fuzzy matches (distance ≤ 2)
    fuzzy_matches = [
        n for n in names
        if Levenshtein.distance(q, n.lower()) <= 2
    ]

    # Combine & dedupe
    results = list(dict.fromkeys(prefix_matches + fuzzy_matches))

    return jsonify(results[:10])   # return only top 10 suggestions
    


    
# -------------------- Notification Helper Function --------------------
def push_notification(user_id, message, url=None):
    # Save in DB
    notif = Notification(user_id=user_id, message=message, url=url)
    db.session.add(notif)
    db.session.commit()

    # Emit via SocketIO if user is online
    if user_id in online_users:
        for sid in online_users[user_id]:
            socketio.emit('new_notification', {
                'id': notif.id,
                'message': notif.message,
                'url': notif.url or '#',
                'read': notif.read,
                'timestamp': notif.timestamp.strftime('%H:%M')
            }, room=sid)

 
    

@app.route('/notifications')
@login_required
def notifications():
    notifications = (
        Notification.query
        .filter_by(user_id=current_user.id)
        .order_by(Notification.timestamp.desc())
        .all()
    )

    return jsonify([
        {
            'id': n.id,
            'message': n.message,
            'url': n.url,
            'read': n.read,
            'timestamp': n.timestamp.strftime('%Y-%m-%d %H:%M')
        }
        for n in notifications
    ])

@app.route('/notifications/all')
@login_required
def all_notifications():
    # Get all notifications for the current user
    notifications = (
        Notification.query
        .filter_by(user_id=current_user.id)
        .order_by(Notification.timestamp.desc())
        .all()
    )

    # Check if more notifications are available, based on the list length
    has_more = len(notifications) > 5  # You can adjust this as needed, e.g., show 5 notifications initially

    return render_template(
        'notifications.html',
        notifications=notifications[:5],  # Show only the first 5 for now
        has_more=has_more
    )

@app.route('/notifications/load_more', methods=['GET'])
@login_required
def load_more_notifications():
    # Define how many notifications to load at a time
    limit = 5

    # Get the last notification's timestamp to load older notifications (or the first one if it's the first load)
    last_timestamp = request.args.get('last_timestamp', None, type=str)

    # Query the notifications based on the timestamp
    query = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.timestamp.desc())

    if last_timestamp:
        # If there is a last timestamp, only get notifications older than the last one
        query = query.filter(Notification.timestamp < last_timestamp)

    notifications = query.limit(limit).all()

    # If notifications exist, convert them to a list of dicts
    notifications_data = [n.to_dict() for n in notifications]

    # If there are more notifications, we'll pass that info back
    has_more = len(notifications_data) == limit

    return jsonify({
        'notifications': notifications_data,
        'has_more': has_more
    })


@app.route('/notifications/read/<int:notif_id>', methods=['POST'])
@login_required
def mark_notification_read(notif_id):
    notif = Notification.query.get_or_404(notif_id)
    if notif.user_id != current_user.id:
        abort(403)
    notif.read = True
    db.session.commit()
    return jsonify({'success': True})

@app.route('/notifications/mark_all_read', methods=['POST'])
@login_required
def mark_all_notifications_read():
    Notification.query.filter_by(user_id=current_user.id, read=False).update({'read': True})
    db.session.commit()
    return jsonify({'success': True})

@app.route('/notifications/unread_count')
@login_required
def unread_notification_count():
    count = Notification.query.filter_by(
        user_id=current_user.id,
        read=False
    ).count()
    return jsonify({'count': count})
    
@user_logged_in.connect_via(app)
def when_user_logged_in(sender, user):
    if not user or not user.id:
        return

    user.is_online = True
    db.session.commit()

    all_users = User.query.filter(User.id != user.id).all()
    for u in all_users:
        Notification.safe_create(
            user_id=u.id,
            message=f"{user.first_name+' '+user.last_name} just came online 💬",
            url=f"/user/{user.id}"
        )

    socketio.emit('user_status_update', {
        'user_id': user.id,
        'username': user.username,
        'status': 'online'
    }, to='*')

@user_logged_out.connect_via(app)
def when_user_logged_out(sender, user):
    if not user or not user.id:
        return

    user.is_online = False
    db.session.commit()

    all_users = User.query.filter(User.id != user.id).all()
    for u in all_users:
        Notification.safe_create(
            user_id=u.id,
            message=f"{user.first_name+' '+user.last_name} went offline 😴",
            url=f"/user/{user.id}"
        )

    socketio.emit('user_status_update', {
        'user_id': user.id,
        'username': user.username,
        'status': 'offline'
    }, to='*')

@app.route('/notifications/delete/<int:notif_id>', methods=['POST'])
@login_required
def delete_notification(notif_id):
    notif = Notification.query.get_or_404(notif_id)
    if notif.user_id != current_user.id:
        abort(403)
    db.session.delete(notif)
    db.session.commit()
    return jsonify({'success': True, 'notif_id': notif_id})
    
# Generic error handler

@app.errorhandler(Exception)
def handle_generic_errors(e):

    # Default values for unexpected errors
    code = 500
    message = error_messages.get(code, "Something went wrong")
    description = error_descriptions.get(code, "An unexpected error occurred.")

    return render_template(
        "error.html",
        code=code,
        message=message,
        description=description
    ), code
    
# -------------------- Run App --------------------
if __name__ == "__main__":

    import eventlet
    import eventlet.wsgi
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
    # Flask-Caching config: start with SimpleCache (in-memory). For production use RedisCache.
    app.config.setdefault("CACHE_TYPE", "SimpleCache")
    app.config.setdefault("CACHE_DEFAULT_TIMEOUT", 60)  # seconds
   


    
