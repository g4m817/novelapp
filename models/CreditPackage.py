from . import db

class CreditPackage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    credit_type = db.Column(db.String(10), nullable=False)
    credits = db.Column(db.Integer, nullable=False)
    cost = db.Column(db.Float, nullable=False)
    stripe_price_id = db.Column(db.String(255), nullable=True)

    def __repr__(self):
        return f"<CreditPackage {self.credit_type} - {self.credits} credits>"