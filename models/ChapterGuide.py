from datetime import datetime
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy import JSON
from . import db

class ChapterGuide(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    story_id = db.Column(db.Integer, db.ForeignKey('story.id'), nullable=False)
    chapter_title = db.Column(db.String(200), nullable=False)
    part_index = db.Column(db.Integer, nullable=False)
    part_text = db.Column(db.Text, nullable=False)
    characters = db.Column(MutableList.as_mutable(JSON), nullable=True, default=[])
    locations = db.Column(MutableList.as_mutable(JSON), nullable=True, default=[])   
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return (
            f"<ChapterGuide Story:{self.story_id} "
            f"Chapter:{self.chapter_title} Part:{self.part_index}>"
        )