from . import db

class TokenCostConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cost_per_credit = db.Column(db.Float, nullable=False)
    cost_per_1m_input = db.Column(db.Float, nullable=False)
    cost_per_1m_output = db.Column(db.Float, nullable=False)
    o1_cost_per_credit = db.Column(db.Float, nullable=False)
    o1_cost_per_1m_input = db.Column(db.Float, nullable=False)
    o1_cost_per_1m_output = db.Column(db.Float, nullable=False)
    dall_e_price_per_image = db.Column(db.Float, nullable=False)