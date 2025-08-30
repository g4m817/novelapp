from . import db

class CreditConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.Text, nullable=False)
    action = db.Column(db.String(50), unique=True)
    modifier = db.Column(db.Float, nullable=False)