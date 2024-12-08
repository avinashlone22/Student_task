import os
from flask import Flask, render_template, request, redirect, session, url_for, flash, send_from_directory
import sqlite3
from werkzeug.utils import secure_filename
from datetime import datetime
from flask import jsonify
from flask_sqlalchemy import SQLAlchemy

application = Flask(__name__, template_folder='templates')
application.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///avi.db'
db = SQLAlchemy(application)




application.secret_key = os.getenv('FLASK_SECRET_KEY', 'your_secret_key_here')


# File upload configuration
UPLOAD_FOLDER = '/tmp/uploads'  # Recommended writable directory for Elastic Beanstalk
  # Recommended for Elastic Beanstalk
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
application.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    roll_number = db.Column(db.Integer, unique=True, nullable=False)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_name = db.Column(db.String(100), nullable=False)
    task = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(50), default='Pending')
    file_data = db.Column(db.LargeBinary)
    description = db.Column(db.String(500))
    file_path = db.Column(db.String(255))
    deadline = db.Column(db.String(50))
    remark = db.Column(db.String(255))

# Utility function to query the database
def query_db(query, args=(), one=False):
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute(query, args)
        conn.commit()
        rv = cursor.fetchall()
        return (rv[0] if rv else None) if one else rv

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Routes


@application.route('/action')
def action():
    return redirect('/student_dashboard')

@application.route('/home')
def home():
    return render_template('home.html')

@application.route('/delete_task/<int:task_id>', methods=['POST'])
def delete_task(task_id):
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

@application.route('/login', methods=['GET', 'POST'])
def login():
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
    students = User.query.all()
    return render_template('students.html', students=students)

@application.route('/students2', methods=['GET', 'POST'])
def view_students2():
    search_query = request.form.get('search_query', '')
    if search_query:
        students = User.query.filter(User.roll_number == search_query).all()
    else:
        students = User.query.all()
    return render_template('students.html', students=students)


@application.route('/delete_student/<int:student_id>', methods=['POST'])
def delete_student(student_id):
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
    if 'user' not in session or session['user'] != 'teacher':
        return redirect('/login')

    search_roll_number = request.args.get('search_roll_number')
    tasks = []

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

    if search_roll_number:
        tasks = db.session.query(Task, User).join(User, Task.student_name == User.username).filter(User.roll_number == search_roll_number).all()
    else:
        tasks = db.session.query(Task, User).join(User, Task.student_name == User.username).all()

    return render_template('teacher_dashboard.html', tasks=tasks)

@application.route('/update_remark/<int:task_id>', methods=['POST'])
def update_remark(task_id):
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
    if 'user' not in session:
        return redirect('/login')

    student_name = session['user']
    tasks = Task.query.filter_by(student_name=student_name).all()
    return render_template('student_dashboard.html', tasks=tasks)



@application.route('/view_task_file/<int:task_id>')
def view_task_file(task_id):
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
    session.pop('user', None)
    return redirect(url_for('login'))

@application.route('/health')
def health_check():
    return "OK", 200


@application.route('/')
def index():
    return redirect('/home')


if __name__ == '__main__':
    with application.app_context():
        db.create_all()
    application.run(debug=True, host='0.0.0.0', port=8080)
