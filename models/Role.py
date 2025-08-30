from . import db

class Role(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    default_text_credits = db.Column(db.Integer, default=0)
    default_image_credits = db.Column(db.Integer, default=0)
    default_audio_credits = db.Column(db.Integer, default=0)
    cost = db.Column(db.Float, default=0, nullable=True)
    protected = db.Column(db.Boolean, default=False)
    stripe_price_id = db.Column(db.String(255), nullable=True)

    def __repr__(self):
        return f"<Role {self.name}>"