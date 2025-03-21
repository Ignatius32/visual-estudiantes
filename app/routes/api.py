from flask import Blueprint, jsonify, request
from app.models import Student, Status, Career, Course, student_career, student_course, student_status
from sqlalchemy import func, and_, or_, text, distinct
from app import db
import logging
import sys

# Configure logging
logging.basicConfig(stream=sys.stdout, level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('api')

api_bp = Blueprint('api', __name__)

@api_bp.route('/api/student-stats')
def student_stats():
    """
    API endpoint to provide student statistics for the dashboard
    """
    selected_career = request.args.get('career')
    logger.info(f"API called with career filter: {selected_career}")
    
    # Get all careers for the filter dropdown
    careers = db.session.query(Career.name).distinct().all()
    all_careers = [career[0] for career in careers]
    
    # Status distribution with career filter and distinct student ids
    def get_student_count(status_name):
        query = db.session.query(Student.id).distinct()\
            .join(student_status)\
            .join(Status)\
            .filter(Status.name == status_name)
        
        if selected_career:
            query = query.join(student_career)\
                .join(Career)\
                .filter(Career.name == selected_career)
        
        return query.count()
    
    status_counts = {
        'enrollment': {
            'active': get_student_count('active'),
            'inactive': get_student_count('inactive')
        },
        'registration': {
            're-enrolled': get_student_count('re-enrolled'),
            'incoming': get_student_count('incoming')
        }
    }
    
    # Log some basic database stats with career filter
    base_query = db.session.query(Student.id).distinct()
    course_query = db.session.query(Course.id).distinct()
    
    if selected_career:
        base_query = base_query.join(student_career)\
            .join(Career)\
            .filter(Career.name == selected_career)
        course_query = course_query.join(Career)\
            .filter(Career.name == selected_career)
    
    total_students = base_query.count()
    total_courses = course_query.count()
    course_names = [c[0] for c in course_query.with_entities(Course.name).limit(5).all()]
    
    logger.info(f"Database stats: {total_students} students, {total_courses} courses")
    logger.info(f"Sample courses: {course_names}")
    
    # Course distribution for re-enrolled and incoming students
    course_distribution = {
        're-enrolled': {},
        'incoming': {}
    }
    
    # Modified method to get course distribution with DISTINCT student count
    for status_name in ['re-enrolled', 'incoming']:
        try:
            # Build query with career info always included and ensuring distinct student counting
            sql = """
            SELECT c.id, c.name, ca.name as career_name, COUNT(DISTINCT s.id) as student_count
            FROM course c
            JOIN career ca ON c.career_id = ca.id
            JOIN student_course sc ON c.id = sc.course_id
            JOIN student s ON sc.student_id = s.id
            JOIN student_status ss ON s.id = ss.student_id
            JOIN status st ON ss.status_id = st.id
            WHERE st.name = :status_name
            """
            
            params = {'status_name': status_name}
            
            if selected_career:
                sql += " AND ca.name = :career_name"
                params['career_name'] = selected_career
            
            sql += """
            GROUP BY c.id, c.name, ca.name
            HAVING COUNT(DISTINCT s.id) > 0
            ORDER BY ca.name, c.name
            """
            
            results = db.session.execute(text(sql), params).fetchall()
            
            logger.info(f"SQL query for {status_name} returned {len(results)} courses")
            
            # Process results - include career name in the course key
            for row in results:
                course_id, course_name, career_name, student_count = row
                # Create a unique key that includes both course name and career
                course_key = f"{course_name} [{career_name}]"
                course_distribution[status_name][course_key] = student_count
                logger.info(f"Course: {course_name} in career {career_name} (ID: {course_id}) has {student_count} {status_name} students")
            
            logger.info(f"Added {len(course_distribution[status_name])} courses to {status_name} distribution")
            
        except Exception as e:
            logger.error(f"Error in course distribution query for {status_name}: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
    
    # Career distribution for re-enrolled and incoming students (fixed to count distinct students only)
    career_distribution = {
        're-enrolled': {},
        'incoming': {}
    }
    
    # For each status type with fixed distinct student counting
    for status_name in ['re-enrolled', 'incoming']:
        try:
            # Direct SQL approach for more control over the query and distinct counting
            sql = """
            SELECT c.name as career_name, COUNT(DISTINCT s.id) as student_count
            FROM career c
            JOIN student_career sc ON c.id = sc.career_id
            JOIN student s ON sc.student_id = s.id
            JOIN student_status ss ON s.id = ss.student_id
            JOIN status st ON ss.status_id = st.id
            WHERE st.name = :status_name
            """
            
            params = {'status_name': status_name}
            
            if selected_career:
                sql += " AND c.name = :career_name"
                params['career_name'] = selected_career
            
            sql += """
            GROUP BY c.name
            HAVING COUNT(DISTINCT s.id) > 0
            ORDER BY c.name
            """
            
            results = db.session.execute(text(sql), params).fetchall()
            
            # Process results
            for row in results:
                career_name, student_count = row
                career_distribution[status_name][career_name] = student_count
                logger.info(f"Career: {career_name} has {student_count} {status_name} students")
            
            logger.info(f"Fixed query: Added {len(career_distribution[status_name])} careers to {status_name} distribution")
            
        except Exception as e:
            logger.error(f"Error in career distribution query for {status_name}: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
    
    # Gender distribution split by status groups with career filter
    def get_gender_distribution(status_names):
        gender_query = db.session.query(
            Student.sexo,
            func.count(distinct(Student.id)).label('student_count')
        ).join(student_status)\
        .join(Status)\
        .filter(Student.sexo != '')\
        .filter(Status.name.in_(status_names))
        
        if selected_career:
            gender_query = gender_query.join(student_career)\
                .join(Career)\
                .filter(Career.name == selected_career)
        
        gender_results = gender_query.group_by(Student.sexo).all()
        return {
            gender: count for gender, count in gender_results if gender
        }
    
    gender_distribution = {
        'enrollment': get_gender_distribution(['active', 'inactive']),
        'registration': get_gender_distribution(['re-enrolled', 'incoming'])
    }
    
    result = {
        'status_counts': status_counts,
        'course_distribution': course_distribution,
        'career_distribution': career_distribution,
        'gender_distribution': gender_distribution,
        'careers': all_careers
    }
    
    # Log the final result for course distribution
    logger.info(f"Final course distribution: {course_distribution}")
    
    return jsonify(result)