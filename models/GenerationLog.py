from datetime import datetime
from . import db

class GenerationLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    task_id = db.Column(db.String(100), nullable=False)
    generation_type = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    predicted_cost = db.Column(db.Integer, nullable=True)
    real_cost = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(20), nullable=False)
    error_message = db.Column(db.Text, nullable=True)
    model = db.Column(db.Text, nullable=True)
    input_tokens = db.Column(db.Integer, default=0)
    output_tokens = db.Column(db.Integer, default=0)

    def __repr__(self):
        return f"<GenerationLog {self.generation_type} - {self.status}>"