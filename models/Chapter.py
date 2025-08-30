from . import db

class Chapter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chapter_number = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=True)
    summary = db.Column(db.Text, nullable=True)
    chapter_image_key = db.Column(db.String(500), nullable=True)
    chapter_image_prompt = db.Column(db.String(500), nullable=True)
    story_id = db.Column(db.Integer, db.ForeignKey('story.id'), nullable=False)