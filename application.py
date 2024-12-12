"""
This module implements a Flask application for managing student tasks, including
user authentication, task assignment, and file uploads.
"""
import os
import sqlite3
from flask import (Flask, render_template, request, redirect, session, url_for,
                   flash, send_from_directory, jsonify)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

# Application initialization
application = Flask(__name__)

# Database configuration
base_dir = os.path.abspath(os.path.dirname(__file__))
application.config['SQLALCHEMY_DATABASE_URI'] = (
    'sqlite:///' + os.path.join(base_dir, "avi.db")
)
application.config['UPLOAD_FOLDER'] = '/tmp/uploads'

os.makedirs(application.config['UPLOAD_FOLDER'], exist_ok=True)
application.secret_key = os.getenv('FLASK_SECRET_KEY', 'your_secret_key_here')

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}

db = SQLAlchemy(application)


class User(db.Model):  # pylint: disable=too-few-public-methods
    """Database model for users."""
    """Represents a user with username, password, and roll number."""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    roll_number = db.Column(db.Integer, unique=True, nullable=False)
class Task(db.Model):
    """Represents a task assigned to students."""
    id = db.Column(db.Integer, primary_key=True)
    student_name = db.Column(db.String(100), nullable=False)
    task = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(50), default='Pending')
    file_data = db.Column(db.LargeBinary)
    description = db.Column(db.String(500))
    file_path = db.Column(db.String(255))
    deadline = db.Column(db.String(50))
    remark = db.Column(db.String(255))

# Utility functions
def allowed_file(filename):
    """Checks if the uploaded file has an allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def query_db(query, args=(), one=False):
    """Executes a raw SQL query on the database."""
    with sqlite3.connect(db) as conn:
        cursor = conn.cursor()
        cursor.execute(query, args)
        conn.commit()
        rv = cursor.fetchall()
        return (rv[0] if rv else None) if one else rv

# Routes




@application.route('/home')
def home():
    """Renders the home page."""
    return render_template('home.html')


@application.route('/action')
def action():
    """Redirects to the student dashboard."""
    return redirect('/student_dashboard')



@application.route('/delete_task/<int:task_id>', methods=['POST'])
def delete_task(task_id):
    """ handle deletion task """
    if 'user' not in session or session['user'] != 'teacher':
        return redirect('/login')

    task = Task.query.get(task_id)
    if task:
        db.session.delete(task)
        db.session.commit()
        flash('Task deleted successfully.', 'success')
    else:
        flash('Task not found.', 'danger')

    return redirect('/teacher_dashboard')

def login():
    """Handles user login for teachers and students."""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Teacher login
        if username == 'teacher' and password == 'password':
            session['user'] = 'teacher'
            return redirect('/teacher_dashboard')

        # Student login
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session['user'] = username
            return redirect(url_for('student_dashboard', student_name=username))

        flash('Invalid credentials. Try again.', 'danger')
    return render_template('login.html')


@application.route('/register', methods=['GET', 'POST'])
def register():
    """Handles user regestration for teachers and students."""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        roll_number = request.form.get('roll_number')

        if not username or not password or not confirm_password or not roll_number:
            flash('All fields are required!', 'danger')
            return redirect(url_for('register'))

        if password != confirm_password:
            flash('Passwords do not match!', 'danger')
            return redirect(url_for('register'))

        if User.query.filter_by(roll_number=roll_number).first():
            flash('This roll number is already taken!', 'danger')
            return redirect(url_for('register'))

        new_user = User(username=username, password=password, roll_number=roll_number)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@application.route('/view_students', methods=['GET', 'POST'])
def view_students():
    """Handles user viewing  for students."""
    students = User.query.all()
    return render_template('students.html', students=students)

@application.route('/students2', methods=['GET', 'POST'])
def view_students2():
    """Handles user viewing for  students."""
    search_query = request.form.get('search_query', '')
    if search_query:
        students = User.query.filter(User.roll_number == search_query).all()
    else:
        students = User.query.all()
    return render_template('students.html', students=students)


@application.route('/delete_student/<int:student_id>', methods=['POST'])
def delete_student(student_id):
    """Handles user delete for students."""
    if request.form.get('_method') == 'DELETE':
        student = User.query.get(student_id)
        if student:
            db.session.delete(student)
            db.session.commit()
            flash('Student deleted successfully!', 'success')
            return redirect(url_for('view_students'))
        flash('Student not found!', 'danger')
    return redirect(url_for('view_students'))


@application.route('/submit_task/<int:task_id>', methods=['GET', 'POST'])
def submit_task(task_id):
    """Handles user submit task for  students."""
    task = Task.query.get_or_404(task_id)
    if request.method == 'POST':
        description = request.form.get('description', '').strip()
        if not description:
            flash('Description is required.', 'danger')
            return redirect(request.referrer)

        task.description = description

        file = request.files.get('file')
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(application.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            task.file_path = filename

        task.status = 'Submitted'
        db.session.commit()
        flash('Task submitted successfully!', 'success')
        return redirect('/student_dashboard')

    return render_template('submit_task.html', task=task)


@application.route('/teacher_dashboard', methods=['GET', 'POST'])
def teacher_dashboard():
    """ teacher dashboard """
    if 'user' not in session or session['user'] != 'teacher':
        return redirect('/login')

    search_roll_number = request.args.get('search_roll_number')

    # Define the base query
    tasks_query = db.session.query(Task, User).join(User, Task.student_name == User.username)

    if search_roll_number:
        # Filter tasks based on the search roll number
        tasks = tasks_query.filter(User.roll_number == search_roll_number).all()
    else:
        # Retrieve all tasks
        tasks = tasks_query.all()

    if request.method == 'POST':
        task_name = request.form['task']
        deadline = request.form['deadline']

        if not task_name or not deadline:
            flash('Task name and deadline are required!', 'danger')
            return redirect(url_for('teacher_dashboard'))

        students = User.query.all()
        for student in students:
            new_task = Task(
                student_name=student.username,
                task=task_name,
                status='Pending',
                description='',  # Initialize description
                file_path=None,
                deadline=deadline
            )
            db.session.add(new_task)

        db.session.commit()
        flash('Task assigned to all students.', 'success')

    return render_template('teacher_dashboard.html', tasks=tasks)
    
@application.route('/update_remark/<int:task_id>', methods=['POST'])
def update_remark(task_id):
    """Handles updaion remark for teachers."""
    if 'user' not in session or session['user'] != 'teacher':
        return redirect('/login')

    task = Task.query.get(task_id)
    if task:
        remark = request.form['remark']
        task.remark = remark
        db.session.commit()
        flash('Remark updated successfully!', 'success')
    else:
        flash('Task not found!', 'danger')

    return redirect('/teacher_dashboard')


@application.route('/student_dashboard')
def student_dashboard():
    """Handles user login for  students."""
    if 'user' not in session:
        return redirect('/login')

    student_name = session['user']
    tasks = Task.query.filter_by(student_name=student_name).all()
    return render_template('student_dashboard.html', tasks=tasks)



@application.route('/view_task_file/<int:task_id>')
def view_task_file(task_id):
    """Handles user viewing file for teachers and students."""
    task = Task.query.get_or_404(task_id)
    if not task.file_path:
        flash('No file uploaded for this task.', 'warning')
        return redirect(request.referrer)

    try:
        # Correctly use the 'path' argument for the directory
        return send_from_directory(
            directory=application.config['UPLOAD_FOLDER'],  # Path to your upload folder
            path=task.file_path,  # The filename
            as_attachment=False
        )

    except FileNotFoundError:
        flash('File not found.', 'danger')
        return redirect(request.referrer)


@application.route('/logout')
def logout():
    """Handles user logout for teachers and students."""
    session.pop('user', None)
    return redirect(url_for('login'))



@application.route('/')
def index():
    """Handles index ."""
    return redirect('/home')

@application.route('/health')
def health_check():
    """Handles health check."""
    return "OK", 200

@application.route('/debug')
def debug():
    """Handles debug ."""
    return jsonify({
        'cwd': os.getcwd(),
        'templates': os.listdir(os.path.join(application.root_path, 'templates')),
        'static': os.listdir(os.path.join(application.root_path, 'static'))
    })




def debug_templates():
    """Debugs template folder content."""
    return jsonify({
        "templates_folder": application.template_folder,
        "template_files": os.listdir(application.template_folder)  
    })
if __name__ == '__main__':
    with application.app_context():
        db.create_all()
        application.run()   #  application.run(debug=True, host='0.0.0.0', port=8080)
        