from . import db

class SiteConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    registration_disabled = db.Column(db.Boolean, default=False)
    maintenance_mode = db.Column(db.Boolean, default=False)