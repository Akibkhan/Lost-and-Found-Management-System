from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user,user_logged_in, user_logged_out
from extensions import *;
from datetime import datetime
from sqlalchemy.dialects.mysql import JSON

# -------------------- Models --------------------


# ===================== USER =====================
class User(UserMixin, db.Model):
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    role = db.Column(db.String(20), default='user')
    profile_picture = db.Column(db.String(200), default='default.jpg')

    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    city = db.Column(db.String(100))
    country = db.Column(db.String(100))
    street = db.Column(db.String(200))
    zip_code = db.Column(db.String(20))

    is_online = db.Column(db.Boolean, default=False)

    # Relationships
    items = db.relationship('Item', back_populates='user', lazy=True)
    comments = db.relationship('Comment', back_populates='user', lazy=True)
    claims = db.relationship('Claim', back_populates='user', lazy=True)
    reactions = db.relationship('CommentReaction', back_populates='user', lazy=True)

    announcements = db.relationship('Announcement', back_populates='created_by', lazy=True)

    sent_messages = db.relationship(
        'Message',
        foreign_keys='Message.sender_id',
        back_populates='sender'
    )
    received_messages = db.relationship(
        'Message',
        foreign_keys='Message.receiver_id',
        back_populates='receiver'
    )

    notifications = db.relationship(
    'Notification',
    back_populates='user',
    cascade='all, delete-orphan',
    lazy=True
)

    @property
    def get_reactions_json(self):
        return {str(r.comment_id): r.reaction for r in self.reactions}


# ===================== MAIL =============================
# association table for many-to-many relationship
class MailRecipient(db.Model):
    __tablename__ = "mail_recipients"

    mail_id = db.Column(db.Integer, db.ForeignKey("mail.id"), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), primary_key=True)

    is_read = db.Column(db.Boolean, default=False)

    mail = db.relationship("Mail", back_populates="recipients")
    user = db.relationship("User")

class Mail(db.Model):
    __tablename__ = 'mail'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    subject = db.Column(db.String(30), nullable=False)
    message = db.Column(db.String(1000), nullable=False)
    priority = db.Column(db.String(10), nullable=False, default='normal')  # low, normal, high
    status = db.Column(db.String(20), nullable=False, default='inbox')      # inbox, archive, trash
    created = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    sender = db.relationship('User', foreign_keys=[sender_id], backref='mails_sent')

    
# multiple recipients
    recipients = db.relationship(
        "MailRecipient",
        back_populates="mail",
        cascade="all, delete-orphan"
    )
    

    def __repr__(self):
        return f"<Mail {self.subject} from {self.sender.username}>"
# ===================== ANNOUNCEMENT =====================
class Announcement(db.Model):
    __tablename__ = "announcement"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)

    is_active = db.Column(db.Boolean, default=True)
    is_pinned = db.Column(db.Boolean, default=False)
    expires_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_by = db.relationship('User', back_populates='announcements')

    def is_expired(self):
        return self.expires_at and self.expires_at < datetime.utcnow()


# ===================== ITEM =====================
class Item(db.Model):
    __tablename__ = 'item'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    photo = db.Column(db.String(200))
    location = db.Column(db.String(255))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    date_reported = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='lost')

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))

    user = db.relationship('User', back_populates='items')
    category = db.relationship('Category', back_populates='items')

    comments = db.relationship(
        'Comment',
        back_populates='item',
        cascade='all, delete-orphan',
        lazy=True
    )

    claims = db.relationship(
        'Claim',
        back_populates='item',
        cascade='all, delete-orphan',
        lazy=True
    )


# ===================== CLAIM =====================
class Claim(db.Model):
    __tablename__ = 'claim'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)

    contact_info = db.Column(db.String(255), nullable=False)
    document_paths = db.Column(JSON)  # stores list of filenames

    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='pending')

    user = db.relationship('User', back_populates='claims')
    item = db.relationship('Item', back_populates='claims')


# ===================== COMMENT =====================
class Comment(db.Model):
    __tablename__ = 'comment'

    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default="pending")

    likes = db.Column(db.Integer, default=0)
    dislikes = db.Column(db.Integer, default=0)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)

    parent_id = db.Column(db.Integer, db.ForeignKey('comment.id'))

    user = db.relationship('User', back_populates='comments')
    item = db.relationship('Item', back_populates='comments')

    replies = db.relationship(
    'Comment',
    backref=db.backref('parent', remote_side=[id]),
    lazy=True
        )


    reactions = db.relationship(
        'CommentReaction',
        back_populates='comment',
        cascade='all, delete-orphan'
    )


# ===================== COMMENT REACTION =====================
class CommentReaction(db.Model):
    __tablename__ = 'comment_reaction'

    id = db.Column(db.Integer, primary_key=True)
    comment_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reaction = db.Column(db.String(10), nullable=False)

    comment = db.relationship('Comment', back_populates='reactions')
    user = db.relationship('User', back_populates='reactions')

    __table_args__ = (
        db.UniqueConstraint('comment_id', 'user_id', name='unique_user_reaction'),
    )


# ===================== CATEGORY =====================
class Category(db.Model):
    __tablename__ = 'category'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)

    items = db.relationship('Item', back_populates='category')

    def __repr__(self):
        return f"<Category {self.name}>"


# ===================== MESSAGE =====================
class Message(db.Model):
    __tablename__ = 'messages'

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    message = db.Column(db.Text)
    attachment = db.Column(db.String(255))
    attachment_type = db.Column(db.String(100))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    read = db.Column(db.Boolean, default=False)

    sender = db.relationship('User', foreign_keys=[sender_id], back_populates='sent_messages')
    receiver = db.relationship('User', foreign_keys=[receiver_id], back_populates='received_messages')


# ===================== NOTIFICATION =====================
class Notification(db.Model):
    __tablename__ = 'notification'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
    db.Integer,
    db.ForeignKey('user.id', ondelete='CASCADE'),
    nullable=False)
    message = db.Column(db.String(255))
    url = db.Column(db.String(255))
    read = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', back_populates='notifications')

    @classmethod
    def safe_create(cls, user_id, message, url=None):
        if not user_id:
            return

        notif = cls(
            user_id=user_id,
            message=message,
            url=url,
            read=False
        )

        try:
            db.session.add(notif)
            db.session.commit()

            socketio.emit(
                'new_notification',
                {
                    'id': notif.id,
                    'message': notif.message,
                    'url': notif.url,
                    'timestamp': notif.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                },
                room=f"user_{user_id}"
            )
        except Exception:
            db.session.rollback()
    def __repr__(self):
        return f"<Notification {self.message}>"

    def to_dict(self):
        return {
            'id': self.id,
            'message': self.message,
            'url': self.url,
            'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M'),
            'read': self.read
        }
