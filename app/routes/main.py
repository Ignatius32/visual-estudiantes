from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from werkzeug.utils import secure_filename
from flask_login import login_user, logout_user, login_required, current_user
import pandas as pd
import os
from datetime import datetime

from app.models import Student, Career, Course, Status, User, student_career, student_course, student_status
from app import db

main = Blueprint('main', __name__)

ALLOWED_EXTENSIONS = {'xlsx', 'xls'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@main.route('/')
def index():
    # Get unique student counts for each status (distinct by student.id)
    active_unique = db.session.query(Student).join(student_status).join(Status).filter(
        Status.name == 'active'
    ).distinct().count()
    
    inactive_unique = db.session.query(Student).join(student_status).join(Status).filter(
        Status.name == 'inactive'
    ).distinct().count()
    
    reregistered_unique = db.session.query(Student).join(student_status).join(Status).filter(
        Status.name == 're-enrolled'
    ).distinct().count()
    
    incoming_unique = db.session.query(Student).join(student_status).join(Status).filter(
        Status.name == 'incoming'
    ).distinct().count()
    
    # Get total unique students across all statuses
    total_unique = db.session.query(Student).count()
    
    # Get counts of students with multiple statuses
    active_and_reenrolled = db.session.query(Student).distinct()\
        .join(student_status).join(Status)\
        .filter(Status.name.in_(['active', 're-enrolled']))\
        .group_by(Student.id)\
        .having(db.func.count(db.distinct(Status.name)) == 2)\
        .count()
    
    active_and_incoming = db.session.query(Student).distinct()\
        .join(student_status).join(Status)\
        .filter(Status.name.in_(['active', 'incoming']))\
        .group_by(Student.id)\
        .having(db.func.count(db.distinct(Status.name)) == 2)\
        .count()
    
    return render_template('index.html', 
                        active_unique=active_unique,
                        inactive_unique=inactive_unique,
                        reregistered_unique=reregistered_unique,
                        incoming_unique=incoming_unique,
                        total_unique=total_unique,
                        active_and_reenrolled=active_and_reenrolled,
                        active_and_incoming=active_and_incoming)

@main.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get('next')
            if not next_page or not next_page.startswith('/'):
                next_page = url_for('main.index')
            flash('Inicio de sesión exitoso.', 'success')
            return redirect(next_page)
        flash('Usuario o contraseña incorrectos.', 'error')
    
    return render_template('login.html')

@main.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Has cerrado sesión.', 'info')
    return redirect(url_for('main.index'))

@main.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        
        file = request.files['file']
        file_type = request.form.get('file_type', 'unknown')
        
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            try:
                process_file(filepath, file_type)
                flash(f'Successfully processed {filename}')
            except Exception as e:
                flash(f'Error processing file: {str(e)}')
            
            return redirect(url_for('main.index'))
    
    return render_template('upload.html')

def get_or_create_status(name):
    """Get existing status or create a new one"""
    status = Status.query.filter_by(name=name).first()
    if not status:
        status = Status(name=name)
        db.session.add(status)
        db.session.commit()
    return status

def process_file(filepath, file_type):
    # Read the Excel file
    df = pd.read_excel(filepath, header=0)  # Explicitly set header row
    
    # Map file types to status
    status_mapping = {
        'active': 'active',
        'inactive': 'inactive',
        'reregistered': 're-enrolled',
        'incoming': 'incoming'
    }
    status_name = status_mapping.get(file_type, 'unknown')
    
    # Get or create the status
    status = get_or_create_status(status_name)
    
    # Reset the count before adding new rows
    status.source_row_count = 0
    db.session.commit()
    
    # Update the raw count from the Excel file (excluding header)
    total_rows = len(df)
    status.source_row_count = total_rows
    db.session.commit()

    # Process each row in the dataframe
    for _, row in df.iterrows():
        try:
            # Validate required student data
            if pd.isna(row.get('Legajo')) or pd.isna(row.get('Nombre')):
                raise ValueError(f"Missing required student data (Legajo or Nombre) for row")

            # Check if student already exists by legajo
            student = Student.query.filter_by(legajo=str(row['Legajo'])).first()
            
            # Handle date parsing with validation - make fecha_nacimiento optional
            fecha_nacimiento = None
            if 'Fecha Nacimiento' in row and pd.notna(row['Fecha Nacimiento']):
                try:
                    date_val = pd.to_datetime(row['Fecha Nacimiento'], errors='coerce')
                    # Validate the date is within reasonable bounds (e.g., between 1900 and current year)
                    if date_val and 1900 <= date_val.year <= datetime.now().year:
                        fecha_nacimiento = date_val.to_pydatetime()
                except (ValueError, TypeError, pd.errors.OutOfBoundsDatetime):
                    # If date parsing fails, we'll keep None without raising an error
                    pass
            
            # Prepare student data with data validation
            student_data = {
                'legajo': str(row['Legajo']),
                'nombre': str(row['Nombre']),
                'apellido': str(row.get('Apellido', '')),
                'tipo_documento': str(row['Tipo Documento']) if 'Tipo Documento' in row else str(row.get('Tipo documento', '')),
                'documento': str(row['Documento']),
                'nacionalidad': str(row['Nacionalidad']),
                'fecha_nacimiento': fecha_nacimiento,  # This will be None if not present or invalid
                'domicilio': str(row['Domicilio']),
                'domicilio_origen': str(row['Domicilio origen']) if 'Domicilio origen' in row else str(row.get('Domicilio Origen', '')),
                'telefono': str(row['Telefono']),
                'correo': str(row['Correo']),
                'cuil': str(row['Cuil']),
                'sexo': str(row['Sexo']),
                'source_file': os.path.basename(filepath)
            }
            
            # Replace 'nan' strings with empty strings
            for key, value in student_data.items():
                if value == 'nan':
                    student_data[key] = ''
            
            if student:
                # Update existing student
                for key, value in student_data.items():
                    setattr(student, key, value)
            else:
                # Create new student
                student = Student(**student_data)
                db.session.add(student)
                
            # Commit to ensure student has an ID
            db.session.commit()
            
            # Validate career data before processing
            if pd.isna(row.get('Carrera')) or str(row.get('Carrera')).lower() == 'nan':
                raise ValueError(f"Missing or invalid career name for student {row['Legajo']}")
            
            # Process career information with validation
            career_data = {
                'name': str(row['Carrera']).strip(),
                'plan': str(row.get('Plan', '')).strip(),
                'version': str(row.get('Version', '')).strip()
            }
            
            # Replace 'nan' strings with empty strings
            for key, value in career_data.items():
                if value.lower() == 'nan':
                    career_data[key] = ''
            
            career = Career.query.filter_by(
                name=career_data['name'],
                plan=career_data['plan'],
                version=career_data['version']
            ).first()
            
            if not career:
                career = Career(**career_data)
                db.session.add(career)
                db.session.commit()
            
            # Add career to student if not already present
            if career not in student.careers:
                student.careers.append(career)
                db.session.commit()
            
            # Process course (materia) if present with validation
            materia_col = next((col for col in row.index if col.strip() == 'Materia'), None)
            if materia_col and pd.notna(row[materia_col]) and str(row[materia_col]).lower() != 'nan':
                course_name = str(row[materia_col]).strip()
                
                # Look for existing course with same name and career
                course = Course.query.filter_by(
                    name=course_name,
                    career_id=career.id
                ).first()
                
                if not course:
                    # Create new course for this career
                    course = Course(
                        name=course_name,
                        career_id=career.id
                    )
                    db.session.add(course)
                    db.session.commit()
                
                # Add course to student if not already present
                if course not in student.courses:
                    student.courses.append(course)
                    db.session.commit()
            
            # Add status to student only if it doesn't exist
            if status not in student.statuses:
                student.statuses.append(status)
                db.session.commit()
            
        except Exception as e:
            db.session.rollback()
            legajo = row.get('Legajo', 'Unknown')
            if isinstance(e, ValueError):
                raise Exception(f"Error processing student {legajo}: {str(e)}")
            else:
                raise Exception(f"Error processing student {legajo}: {str(e)}\nData: {row.to_dict()}")

@main.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@main.route('/students')
@login_required
def student_list():
    students = Student.query.all()
    return render_template('students.html', students=students)

@main.route('/clear-data', methods=['POST'])
@login_required
def clear_data():
    try:
        # Delete all records from association tables first
        db.session.execute(student_course.delete())
        db.session.execute(student_career.delete())
        db.session.execute(student_status.delete())
        
        # Delete records from main tables
        Course.query.delete()
        Career.query.delete()
        Student.query.delete()
        Status.query.delete()
        
        db.session.commit()
        flash('All data has been successfully cleared from the database.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error clearing data: {str(e)}', 'error')
    
    return redirect(url_for('main.index'))