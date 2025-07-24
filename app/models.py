from . import db
from datetime import datetime

class File(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    size_bytes = db.Column(db.Integer, nullable=False)
    sha256 = db.Column(db.String(64), nullable=True) # Nullable car calculé après
    status = db.Column(db.String(20), default='pending', nullable=False) # pending, processed, error
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "filename": self.filename,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "status": self.status,
            "created_at": self.created_at.isoformat() + 'Z',
            "expires_at": self.expires_at.isoformat() + 'Z' if self.expires_at else None
        }

class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    action = db.Column(db.String(50), nullable=False)
    details = db.Column(db.String(500))

    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() + 'Z',
            "action": self.action,
            "details": self.details
        }