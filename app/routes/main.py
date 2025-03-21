from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from werkzeug.utils import secure_filename
from flask_login import login_user, logout_user, login_required, current_user
import pandas as pd
import os
from datetime import datetime
from sqlalchemy import text

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
    
    # Track processed students to prevent duplicate status assignments
    processed_students = set()

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
            
            # Track this student to prevent duplicate status assignments within same file
            student_key = f"{student.id}_{status.id}"
            if student_key in processed_students:
                # Skip this student-status combination as it's already been processed
                continue
            processed_students.add(student_key)
            
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
                
                # Look for existing course with same name and SAME CAREER
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

@main.route('/fix-duplicates', methods=['POST'])
@login_required
def fix_duplicates():
    """
    Identifies and removes duplicate student associations in the database.
    This fixes incorrect student counts in the dashboard.
    """
    try:
        # 1. Find duplicate student-status entries
        status_duplicates = db.session.execute(text("""
            WITH duplicates AS (
                SELECT student_id, status_id, COUNT(*) as count
                FROM student_status
                GROUP BY student_id, status_id
                HAVING COUNT(*) > 1
            )
            SELECT ss.student_id, ss.status_id, s.legajo, st.name as status_name
            FROM student_status ss
            JOIN duplicates d ON ss.student_id = d.student_id AND ss.status_id = d.status_id
            JOIN student s ON ss.student_id = s.id
            JOIN status st ON ss.status_id = st.id
            ORDER BY ss.student_id, ss.status_id
        """))
        
        # Process and remove duplicate entries from student_status
        status_processed = {}
        for row in status_duplicates:
            key = f"{row.student_id}_{row.status_id}"
            if key not in status_processed:
                status_processed[key] = True
                continue
            
            # Delete the duplicate association
            db.session.execute(text(
                "DELETE FROM student_status WHERE student_id = :student_id AND status_id = :status_id LIMIT 1"
            ), {"student_id": row.student_id, "status_id": row.status_id})
            
        # 2. Find duplicate student-course entries
        course_duplicates = db.session.execute(text("""
            WITH duplicates AS (
                SELECT student_id, course_id, COUNT(*) as count
                FROM student_course
                GROUP BY student_id, course_id
                HAVING COUNT(*) > 1
            )
            SELECT sc.student_id, sc.course_id, s.legajo, c.name as course_name
            FROM student_course sc
            JOIN duplicates d ON sc.student_id = d.student_id AND sc.course_id = d.course_id
            JOIN student s ON sc.student_id = s.id
            JOIN course c ON sc.course_id = c.id
            ORDER BY sc.student_id, sc.course_id
        """))
        
        # Process and remove duplicate entries from student_course
        course_processed = {}
        for row in course_duplicates:
            key = f"{row.student_id}_{row.course_id}"
            if key not in course_processed:
                course_processed[key] = True
                continue
            
            # Delete the duplicate association
            db.session.execute(text(
                "DELETE FROM student_course WHERE student_id = :student_id AND course_id = :course_id LIMIT 1"
            ), {"student_id": row.student_id, "course_id": row.course_id})
            
        # 3. Find duplicate student-career entries
        career_duplicates = db.session.execute(text("""
            WITH duplicates AS (
                SELECT student_id, career_id, COUNT(*) as count
                FROM student_career
                GROUP BY student_id, career_id
                HAVING COUNT(*) > 1
            )
            SELECT sc.student_id, sc.career_id, s.legajo, c.name as career_name
            FROM student_career sc
            JOIN duplicates d ON sc.student_id = d.student_id AND sc.career_id = d.career_id
            JOIN student s ON sc.student_id = s.id
            JOIN career c ON sc.career_id = c.id
            ORDER BY sc.student_id, sc.career_id
        """))
        
        # Process and remove duplicate entries from student_career
        career_processed = {}
        for row in career_duplicates:
            key = f"{row.student_id}_{row.career_id}"
            if key not in career_processed:
                career_processed[key] = True
                continue
            
            # Delete the duplicate association
            db.session.execute(text(
                "DELETE FROM student_career WHERE student_id = :student_id AND career_id = :career_id LIMIT 1"
            ), {"student_id": row.student_id, "career_id": row.career_id})
        
        # 4. Fix incorrect course associations (courses assigned to wrong careers)
        # This will list any courses that might have been incorrectly associated
        incorrect_associations = db.session.execute(text("""
            SELECT s.id as student_id, s.legajo, c.id as course_id, c.name as course_name, 
                   ca.id as career_id, ca.name as career_name
            FROM student s
            JOIN student_course sc ON s.id = sc.student_id
            JOIN course c ON sc.course_id = c.id
            JOIN career ca ON c.career_id = ca.id
            LEFT JOIN student_career sca ON s.id = sca.student_id AND ca.id = sca.career_id
            WHERE sca.student_id IS NULL
        """))
        
        # For each incorrect association, we either:
        # 1. Remove the course association if student doesn't belong to that career
        # 2. Add the career to the student's list of careers
        for row in incorrect_associations:
            # Check if student is in a different career with same course name
            alternate_course = db.session.execute(text("""
                SELECT c.id
                FROM course c
                JOIN career ca ON c.career_id = ca.id
                JOIN student_career sc ON ca.id = sc.career_id
                WHERE sc.student_id = :student_id AND c.name = :course_name
                LIMIT 1
            """), {"student_id": row.student_id, "course_name": row.course_name}).fetchone()
            
            if alternate_course:
                # Student has a course with same name in a different career
                # Remove incorrect course association
                db.session.execute(text(
                    "DELETE FROM student_course WHERE student_id = :student_id AND course_id = :course_id"
                ), {"student_id": row.student_id, "course_id": row.course_id})
            else:
                # Add the career to the student's list if appropriate
                # This assumes course exists in a career that student should be in
                db.session.execute(text(
                    "INSERT INTO student_career (student_id, career_id) VALUES (:student_id, :career_id)"
                ), {"student_id": row.student_id, "career_id": row.career_id})
        
        # 5. Fix any courses with no career association
        courses_without_career = db.session.execute(text("""
            SELECT id, name FROM course WHERE career_id IS NULL
        """))
        
        for row in courses_without_career:
            # Delete these courses as they're invalid in our model
            db.session.execute(text(
                "DELETE FROM student_course WHERE course_id = :course_id"
            ), {"course_id": row.id})
            
            db.session.execute(text(
                "DELETE FROM course WHERE id = :course_id"
            ), {"course_id": row.id})
        
        db.session.commit()
        flash('Database has been fixed. Duplicates removed and incorrect associations corrected.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error fixing duplicates: {str(e)}', 'error')
    
    return redirect(url_for('main.index'))