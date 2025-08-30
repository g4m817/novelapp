from datetime import datetime
from . import db

class StoryArc(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    story_id = db.Column(db.Integer, db.ForeignKey('story.id'), nullable=False)
    arc_text = db.Column(db.Text, nullable=False)
    arc_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<StoryArc {self.id} for Story {self.story_id}>"