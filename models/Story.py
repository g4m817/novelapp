from datetime import datetime
from . import db

story_flags = db.Table('story_flags',
    db.Column('story_id', db.Integer, db.ForeignKey('story.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True)
)

story_tags = db.Table('story_tags',
    db.Column('story_id', db.Integer, db.ForeignKey('story.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), primary_key=True)
)

class Story(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    chapters_count = db.Column(db.Integer, nullable=False)
    details = db.Column(db.Text, nullable=True)
    tags = db.relationship('Tag', secondary=story_tags, backref=db.backref('stories', lazy='dynamic'))
    shared = db.Column(db.Boolean, default=False)
    spotlight = db.Column(db.Boolean, default=False)
    flagged = db.Column(db.Boolean, default=False)
    final_markdown = db.Column(db.Text, nullable=True)
    writing_style = db.Column(db.Text, nullable=True)
    inspirations = db.Column(db.Text, nullable=True)
    is_mature = db.Column(db.Boolean, default=False)
    comments = db.relationship('Comment', backref='story', lazy=True, cascade="all, delete-orphan")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    chapters = db.relationship('Chapter', backref='story', lazy=True, cascade="all, delete-orphan")
    favorites_count = db.Column(db.Integer, default=0)
    cover_image_prompt = db.Column(db.String(500), nullable=True)
    cover_image_key = db.Column(db.String(500), nullable=True)
    flaggers = db.relationship('User', secondary=story_flags, backref=db.backref('flagged_stories', lazy='dynamic'), lazy='dynamic')
    arcs = db.relationship('StoryArc', backref='story', lazy=True, cascade="all, delete-orphan")
    
    def to_dict(self):
        tag_list = [{"id": tag.id, "name": tag.name} for tag in self.tags]
        arcs_list = [arc.arc_text for arc in self.arcs] if self.arcs else []
        return {
            "id": self.id,
            "title": self.title,
            "chapters_count": self.chapters_count,
            "author": "",
            "details": self.details,
            "shared": self.shared,
            "spotlight": self.spotlight,
            "flagged": self.flagged,
            "cover_image_key": self.cover_image_key,
            "favorites_count": self.favorites_count or 0,
            "tags": tag_list,
            "created_at": self.created_at.isoformat(),
            "user_id": self.user_id,
            "arcs": arcs_list,
            "presigned_cover_url":""
        }