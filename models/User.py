from flask_bcrypt import Bcrypt
from datetime import datetime
from . import db
bcrypt = Bcrypt()

favorites = db.Table('favorites',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('story_id', db.Integer, db.ForeignKey('story.id'))
)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    is_verified = db.Column(db.Boolean, default=False)
    role_id = db.Column(db.Integer, db.ForeignKey('role.id'), nullable=False)
    role = db.relationship("Role", backref="users")
    show_mature = db.Column(db.Boolean, default=False)
    text_credits = db.Column(db.Integer, default=0)
    image_credits = db.Column(db.Integer, default=0)
    audio_credits = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    stories = db.relationship('Story', backref='user', lazy=True)
    favorite_stories = db.relationship('Story', secondary=favorites,
                                       backref=db.backref('favorited_by', lazy='dynamic'),
                                       lazy='dynamic')
    
    failed_attempts = db.Column(db.Integer, default=0)
    last_failed_attempt = db.Column(db.DateTime, nullable=True)
    locked_until = db.Column(db.DateTime, nullable=True)
    
    is_locked = db.Column(db.Boolean, default=False)
    last_login_ip = db.Column(db.String(45), nullable=True)
    
    under_review = db.Column(db.Boolean, default=False)
    stripe_customer_id = db.Column(db.String(255), nullable=True)
    stripe_subscription_id = db.Column(db.String(255), nullable=True)

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")
        
    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)