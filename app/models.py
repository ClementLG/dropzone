from . import db
from datetime import datetime


class Item(db.Model):
    __tablename__ = 'item'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    # 'file' ou 'directory'
    item_type = db.Column(db.String(50), nullable=False)

    # Chemin relatif depuis la racine d'upload. Ex: 'documents/factures/file.pdf'
    path = db.Column(db.String(1024), nullable=False, unique=True)

    # Relation parent-enfant
    parent_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=True)
    children = db.relationship('Item', backref=db.backref('parent', remote_side=[id]), lazy='dynamic',
                               cascade="all, delete-orphan")

    # Champs spécifiques aux fichiers (seront NULL pour les dossiers)
    size_bytes = db.Column(db.Integer, nullable=True)
    sha256 = db.Column(db.String(64), nullable=True)
    status = db.Column(db.String(20), default='processed', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "item_type": self.item_type,
            "path": self.path,
            "parent_id": self.parent_id,
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