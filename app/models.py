from app import db
from datetime import datetime

# Association tables
student_career = db.Table('student_career',
    db.Column('student_id', db.Integer, db.ForeignKey('student.id'), primary_key=True),
    db.Column('career_id', db.Integer, db.ForeignKey('career.id'), primary_key=True)
)

student_course = db.Table('student_course',
    db.Column('student_id', db.Integer, db.ForeignKey('student.id'), primary_key=True),
    db.Column('course_id', db.Integer, db.ForeignKey('course.id'), primary_key=True)
)

# Association table for student statuses with proper foreign keys
student_status = db.Table('student_status',
    db.Column('student_id', db.Integer, db.ForeignKey('student.id'), primary_key=True),
    db.Column('status_id', db.Integer, db.ForeignKey('status.id'), primary_key=True)
)

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    legajo = db.Column(db.String(20), unique=True, nullable=False)
    nombre = db.Column(db.String(100))
    apellido = db.Column(db.String(100))
    tipo_documento = db.Column(db.String(20))
    documento = db.Column(db.String(20))
    nacionalidad = db.Column(db.String(50))
    fecha_nacimiento = db.Column(db.DateTime)
    domicilio = db.Column(db.String(200))
    domicilio_origen = db.Column(db.String(200))
    telefono = db.Column(db.String(20))
    correo = db.Column(db.String(100))
    cuil = db.Column(db.String(20))
    sexo = db.Column(db.String(10))
    
    # Relationships
    careers = db.relationship('Career', secondary=student_career, backref=db.backref('students', lazy='dynamic'))
    courses = db.relationship('Course', secondary=student_course, backref=db.backref('students', lazy='dynamic'))
    statuses = db.relationship('Status', secondary=student_status, backref=db.backref('students', lazy='dynamic'))
    
    # Tracking information
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    source_file = db.Column(db.String(100))
    
    def __repr__(self):
        return f'<Student {self.legajo}: {self.apellido}, {self.nombre}>'

class Status(db.Model):
    """Model to store valid student statuses"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20), unique=True, nullable=False)
    description = db.Column(db.String(200))
    source_row_count = db.Column(db.Integer, default=0)  # Track total entries from source files

    def __init__(self, name, description=None):
        self.name = name
        self.description = description
        self.source_row_count = 0

    @staticmethod
    def initialize_default_statuses():
        """Initialize default status values"""
        default_statuses = [
            ('active', 'Active student'),
            ('inactive', 'Inactive student'),
            ('re-enrolled', 'Re-enrolled student'),
            ('incoming', 'Incoming student')
        ]
        
        for name, description in default_statuses:
            if not Status.query.filter_by(name=name).first():
                status = Status(name=name, description=description)
                db.session.add(status)
        
        try:
            db.session.commit()
        except:
            db.session.rollback()

    def __repr__(self):
        return f'<Status {self.name}>'

class Career(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    plan = db.Column(db.String(20))
    version = db.Column(db.String(20))
    
    def __repr__(self):
        return f'<Career {self.name} - Plan: {self.plan}>'

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    career_id = db.Column(db.Integer, db.ForeignKey('career.id'))
    career = db.relationship('Career', backref=db.backref('courses', lazy=True))
    
    def __repr__(self):
        return f'<Course {self.name}>'