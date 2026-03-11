import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from models import db, Admin, Company, Student, PlacementDrive, Application
from datetime import datetime, date
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = 'placement-portal-secret-key-2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///placement.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'resumes')
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024

db.init_app(app)

ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login first.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash('Admin access required.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def company_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'company':
            flash('Company access required.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def student_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'student':
            flash('Student access required.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


@app.route('/')
def index():
    if 'user_id' in session:
        if session['role'] == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif session['role'] == 'company':
            return redirect(url_for('company_dashboard'))
        elif session['role'] == 'student':
            return redirect(url_for('student_dashboard'))
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        role = request.form.get('role', '')

        if not email or not password or not role:
            flash('All fields are required.', 'danger')
            return redirect(url_for('login'))

        if role == 'admin':
            user = Admin.query.filter_by(email=email).first()
            if user and check_password_hash(user.password, password):
                session['user_id'] = user.id
                session['role'] = 'admin'
                session['name'] = user.username
                return redirect(url_for('admin_dashboard'))

        elif role == 'company':
            user = Company.query.filter_by(email=email).first()
            if user and check_password_hash(user.password, password):
                if user.is_blacklisted:
                    flash('Your account has been blacklisted.', 'danger')
                    return redirect(url_for('login'))
                session['user_id'] = user.id
                session['role'] = 'company'
                session['name'] = user.company_name
                if user.approval_status != 'Approved':
                    return redirect(url_for('company_pending'))
                return redirect(url_for('company_dashboard'))

        elif role == 'student':
            user = Student.query.filter_by(email=email).first()
            if user and check_password_hash(user.password, password):
                if user.is_blacklisted:
                    flash('Your account has been blacklisted.', 'danger')
                    return redirect(url_for('login'))
                session['user_id'] = user.id
                session['role'] = 'student'
                session['name'] = user.name
                return redirect(url_for('student_dashboard'))

        flash('Invalid credentials.', 'danger')
        return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('login'))


@app.route('/register/student', methods=['GET', 'POST'])
def register_student():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        phone = request.form.get('phone', '').strip()
        degree = request.form.get('degree', '').strip()
        branch = request.form.get('branch', '').strip()
        cgpa = request.form.get('cgpa', '')
        skills = request.form.get('skills', '').strip()

        if not name or not email or not password:
            flash('Name, email and password are required.', 'danger')
            return redirect(url_for('register_student'))

        if Student.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return redirect(url_for('register_student'))

        resume_filename = None
        if 'resume' in request.files:
            file = request.files['resume']
            if file and file.filename and allowed_file(file.filename):
                resume_filename = secure_filename(f"{email}_{file.filename}")
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], resume_filename))

        student = Student(
            name=name,
            email=email,
            password=generate_password_hash(password),
            phone=phone,
            degree=degree,
            branch=branch,
            cgpa=float(cgpa) if cgpa else None,
            skills=skills,
            resume=resume_filename
        )
        db.session.add(student)
        db.session.commit()
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))

    return render_template('register_student.html')


@app.route('/register/company', methods=['GET', 'POST'])
def register_company():
    if request.method == 'POST':
        company_name = request.form.get('company_name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        hr_contact = request.form.get('hr_contact', '').strip()
        phone = request.form.get('phone', '').strip()
        website = request.form.get('website', '').strip()
        industry = request.form.get('industry', '').strip()
        description = request.form.get('description', '').strip()

        if not company_name or not email or not password:
            flash('Company name, email and password are required.', 'danger')
            return redirect(url_for('register_company'))

        if Company.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return redirect(url_for('register_company'))

        company = Company(
            company_name=company_name,
            email=email,
            password=generate_password_hash(password),
            hr_contact=hr_contact,
            phone=phone,
            website=website,
            industry=industry,
            description=description
        )
        db.session.add(company)
        db.session.commit()
        flash('Registration successful! Please wait for admin approval.', 'success')
        return redirect(url_for('login'))

    return render_template('register_company.html')


# ==================== ADMIN ROUTES ====================

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    total_students = Student.query.count()
    total_companies = Company.query.count()
    total_drives = PlacementDrive.query.count()
    total_applications = Application.query.count()
    pending_companies = Company.query.filter_by(approval_status='Pending').count()
    pending_drives = PlacementDrive.query.filter_by(status='Pending').count()
    recent_applications = Application.query.order_by(Application.application_date.desc()).limit(5).all()
    return render_template('admin/dashboard.html',
                           total_students=total_students,
                           total_companies=total_companies,
                           total_drives=total_drives,
                           total_applications=total_applications,
                           pending_companies=pending_companies,
                           pending_drives=pending_drives,
                           recent_applications=recent_applications)


@app.route('/admin/companies')
@admin_required
def admin_companies():
    search = request.args.get('search', '').strip()
    if search:
        companies = Company.query.filter(
            (Company.company_name.ilike(f'%{search}%')) |
            (Company.industry.ilike(f'%{search}%'))
        ).all()
    else:
        companies = Company.query.all()
    return render_template('admin/companies.html', companies=companies, search=search)


@app.route('/admin/company/<int:id>/approve')
@admin_required
def admin_approve_company(id):
    company = Company.query.get_or_404(id)
    company.approval_status = 'Approved'
    db.session.commit()
    flash(f'{company.company_name} approved.', 'success')
    return redirect(url_for('admin_companies'))


@app.route('/admin/company/<int:id>/reject')
@admin_required
def admin_reject_company(id):
    company = Company.query.get_or_404(id)
    company.approval_status = 'Rejected'
    db.session.commit()
    flash(f'{company.company_name} rejected.', 'warning')
    return redirect(url_for('admin_companies'))


@app.route('/admin/company/<int:id>/blacklist')
@admin_required
def admin_blacklist_company(id):
    company = Company.query.get_or_404(id)
    company.is_blacklisted = not company.is_blacklisted
    db.session.commit()
    status = 'blacklisted' if company.is_blacklisted else 'unblacklisted'
    flash(f'{company.company_name} {status}.', 'info')
    return redirect(url_for('admin_companies'))


@app.route('/admin/company/<int:id>/delete')
@admin_required
def admin_delete_company(id):
    company = Company.query.get_or_404(id)
    Application.query.filter(Application.drive_id.in_(
        [d.id for d in company.drives]
    )).delete(synchronize_session=False)
    PlacementDrive.query.filter_by(company_id=id).delete()
    db.session.delete(company)
    db.session.commit()
    flash('Company deleted.', 'success')
    return redirect(url_for('admin_companies'))


@app.route('/admin/students')
@admin_required
def admin_students():
    search = request.args.get('search', '').strip()
    if search:
        students = Student.query.filter(
            (Student.name.ilike(f'%{search}%')) |
            (Student.email.ilike(f'%{search}%')) |
            (Student.phone.ilike(f'%{search}%')) |
            (Student.id == int(search) if search.isdigit() else False)
        ).all()
    else:
        students = Student.query.all()
    return render_template('admin/students.html', students=students, search=search)


@app.route('/admin/student/<int:id>/blacklist')
@admin_required
def admin_blacklist_student(id):
    student = Student.query.get_or_404(id)
    student.is_blacklisted = not student.is_blacklisted
    db.session.commit()
    status = 'blacklisted' if student.is_blacklisted else 'unblacklisted'
    flash(f'{student.name} {status}.', 'info')
    return redirect(url_for('admin_students'))


@app.route('/admin/student/<int:id>/delete')
@admin_required
def admin_delete_student(id):
    student = Student.query.get_or_404(id)
    Application.query.filter_by(student_id=id).delete()
    db.session.delete(student)
    db.session.commit()
    flash('Student deleted.', 'success')
    return redirect(url_for('admin_students'))


@app.route('/admin/drives')
@admin_required
def admin_drives():
    drives = PlacementDrive.query.order_by(PlacementDrive.created_at.desc()).all()
    return render_template('admin/drives.html', drives=drives)


@app.route('/admin/drive/<int:id>/approve')
@admin_required
def admin_approve_drive(id):
    drive = PlacementDrive.query.get_or_404(id)
    drive.status = 'Approved'
    db.session.commit()
    flash('Drive approved.', 'success')
    return redirect(url_for('admin_drives'))


@app.route('/admin/drive/<int:id>/reject')
@admin_required
def admin_reject_drive(id):
    drive = PlacementDrive.query.get_or_404(id)
    drive.status = 'Rejected'
    db.session.commit()
    flash('Drive rejected.', 'warning')
    return redirect(url_for('admin_drives'))


@app.route('/admin/applications')
@admin_required
def admin_applications():
    applications = Application.query.order_by(Application.application_date.desc()).all()
    return render_template('admin/applications.html', applications=applications)


# ==================== COMPANY ROUTES ====================

@app.route('/company/pending')
@company_required
def company_pending():
    company = Company.query.get(session['user_id'])
    return render_template('company/pending.html', company=company)


@app.route('/company/dashboard')
@company_required
def company_dashboard():
    company = Company.query.get(session['user_id'])
    if company.approval_status != 'Approved':
        return redirect(url_for('company_pending'))
    drives = PlacementDrive.query.filter_by(company_id=company.id).all()
    total_apps = 0
    for d in drives:
        total_apps += Application.query.filter_by(drive_id=d.id).count()
    return render_template('company/dashboard.html', company=company, drives=drives, total_apps=total_apps)


@app.route('/company/profile')
@company_required
def company_profile():
    company = Company.query.get(session['user_id'])
    return render_template('company/profile.html', company=company)


@app.route('/company/profile/edit', methods=['GET', 'POST'])
@company_required
def company_edit_profile():
    company = Company.query.get(session['user_id'])
    if request.method == 'POST':
        company.company_name = request.form.get('company_name', '').strip()
        company.hr_contact = request.form.get('hr_contact', '').strip()
        company.phone = request.form.get('phone', '').strip()
        company.website = request.form.get('website', '').strip()
        company.industry = request.form.get('industry', '').strip()
        company.description = request.form.get('description', '').strip()
        db.session.commit()
        session['name'] = company.company_name
        flash('Profile updated.', 'success')
        return redirect(url_for('company_profile'))
    return render_template('company/edit_profile.html', company=company)


@app.route('/company/drive/create', methods=['GET', 'POST'])
@company_required
def company_create_drive():
    company = Company.query.get(session['user_id'])
    if company.approval_status != 'Approved':
        flash('Your company must be approved first.', 'danger')
        return redirect(url_for('company_pending'))

    if request.method == 'POST':
        job_title = request.form.get('job_title', '').strip()
        job_description = request.form.get('job_description', '').strip()
        eligibility = request.form.get('eligibility', '').strip()
        salary_range = request.form.get('salary_range', '').strip()
        location = request.form.get('location', '').strip()
        required_skills = request.form.get('required_skills', '').strip()
        experience = request.form.get('experience', '').strip()
        deadline = request.form.get('deadline', '')

        if not job_title:
            flash('Job title is required.', 'danger')
            return redirect(url_for('company_create_drive'))

        drive = PlacementDrive(
            company_id=company.id,
            job_title=job_title,
            job_description=job_description,
            eligibility=eligibility,
            salary_range=salary_range,
            location=location,
            required_skills=required_skills,
            experience=experience,
            deadline=datetime.strptime(deadline, '%Y-%m-%d').date() if deadline else None
        )
        db.session.add(drive)
        db.session.commit()
        flash('Placement drive created. Waiting for admin approval.', 'success')
        return redirect(url_for('company_dashboard'))

    return render_template('company/create_drive.html')


@app.route('/company/drive/<int:id>/edit', methods=['GET', 'POST'])
@company_required
def company_edit_drive(id):
    drive = PlacementDrive.query.get_or_404(id)
    if drive.company_id != session['user_id']:
        flash('Unauthorized.', 'danger')
        return redirect(url_for('company_dashboard'))

    if request.method == 'POST':
        drive.job_title = request.form.get('job_title', '').strip()
        drive.job_description = request.form.get('job_description', '').strip()
        drive.eligibility = request.form.get('eligibility', '').strip()
        drive.salary_range = request.form.get('salary_range', '').strip()
        drive.location = request.form.get('location', '').strip()
        drive.required_skills = request.form.get('required_skills', '').strip()
        drive.experience = request.form.get('experience', '').strip()
        deadline = request.form.get('deadline', '')
        drive.deadline = datetime.strptime(deadline, '%Y-%m-%d').date() if deadline else None
        db.session.commit()
        flash('Drive updated.', 'success')
        return redirect(url_for('company_dashboard'))

    return render_template('company/edit_drive.html', drive=drive)


@app.route('/company/drive/<int:id>/close')
@company_required
def company_close_drive(id):
    drive = PlacementDrive.query.get_or_404(id)
    if drive.company_id != session['user_id']:
        flash('Unauthorized.', 'danger')
        return redirect(url_for('company_dashboard'))
    drive.status = 'Closed'
    db.session.commit()
    flash('Drive closed.', 'info')
    return redirect(url_for('company_dashboard'))


@app.route('/company/drive/<int:id>/delete')
@company_required
def company_delete_drive(id):
    drive = PlacementDrive.query.get_or_404(id)
    if drive.company_id != session['user_id']:
        flash('Unauthorized.', 'danger')
        return redirect(url_for('company_dashboard'))
    Application.query.filter_by(drive_id=id).delete()
    db.session.delete(drive)
    db.session.commit()
    flash('Drive deleted.', 'success')
    return redirect(url_for('company_dashboard'))


@app.route('/company/drive/<int:id>/applications')
@company_required
def company_drive_applications(id):
    drive = PlacementDrive.query.get_or_404(id)
    if drive.company_id != session['user_id']:
        flash('Unauthorized.', 'danger')
        return redirect(url_for('company_dashboard'))
    applications = Application.query.filter_by(drive_id=id).all()
    return render_template('company/view_applications.html', drive=drive, applications=applications)


@app.route('/company/application/<int:id>/status', methods=['POST'])
@company_required
def company_update_application_status(id):
    application = Application.query.get_or_404(id)
    drive = PlacementDrive.query.get(application.drive_id)
    if drive.company_id != session['user_id']:
        flash('Unauthorized.', 'danger')
        return redirect(url_for('company_dashboard'))

    new_status = request.form.get('status', '')
    if new_status in ['Shortlisted', 'Selected', 'Rejected']:
        application.status = new_status
        db.session.commit()
        flash(f'Application status updated to {new_status}.', 'success')
    return redirect(url_for('company_drive_applications', id=drive.id))


# ==================== STUDENT ROUTES ====================

@app.route('/student/dashboard')
@student_required
def student_dashboard():
    student = Student.query.get(session['user_id'])
    approved_drives = PlacementDrive.query.filter_by(status='Approved').order_by(PlacementDrive.created_at.desc()).all()
    my_applications = Application.query.filter_by(student_id=student.id).order_by(Application.application_date.desc()).all()
    applied_drive_ids = [a.drive_id for a in my_applications]
    return render_template('student/dashboard.html',
                           student=student,
                           approved_drives=approved_drives,
                           my_applications=my_applications,
                           applied_drive_ids=applied_drive_ids)


@app.route('/student/profile')
@student_required
def student_profile():
    student = Student.query.get(session['user_id'])
    return render_template('student/profile.html', student=student)


@app.route('/student/profile/edit', methods=['GET', 'POST'])
@student_required
def student_edit_profile():
    student = Student.query.get(session['user_id'])
    if request.method == 'POST':
        student.name = request.form.get('name', '').strip()
        student.phone = request.form.get('phone', '').strip()
        student.degree = request.form.get('degree', '').strip()
        student.branch = request.form.get('branch', '').strip()
        cgpa = request.form.get('cgpa', '')
        student.cgpa = float(cgpa) if cgpa else None
        student.skills = request.form.get('skills', '').strip()

        if 'resume' in request.files:
            file = request.files['resume']
            if file and file.filename and allowed_file(file.filename):
                resume_filename = secure_filename(f"{student.email}_{file.filename}")
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], resume_filename))
                student.resume = resume_filename

        db.session.commit()
        session['name'] = student.name
        flash('Profile updated.', 'success')
        return redirect(url_for('student_profile'))

    return render_template('student/edit_profile.html', student=student)


@app.route('/student/drives')
@student_required
def student_drives():
    search = request.args.get('search', '').strip()
    student = Student.query.get(session['user_id'])
    query = PlacementDrive.query.filter_by(status='Approved')
    if search:
        query = query.join(Company).filter(
            (PlacementDrive.job_title.ilike(f'%{search}%')) |
            (PlacementDrive.required_skills.ilike(f'%{search}%')) |
            (Company.company_name.ilike(f'%{search}%'))
        )
    drives = query.order_by(PlacementDrive.created_at.desc()).all()
    applied_drive_ids = [a.drive_id for a in Application.query.filter_by(student_id=student.id).all()]
    return render_template('student/drives.html', drives=drives, applied_drive_ids=applied_drive_ids, search=search)


@app.route('/student/drive/<int:id>/apply')
@student_required
def student_apply_drive(id):
    drive = PlacementDrive.query.get_or_404(id)
    if drive.status != 'Approved':
        flash('This drive is not available.', 'danger')
        return redirect(url_for('student_drives'))

    existing = Application.query.filter_by(student_id=session['user_id'], drive_id=id).first()
    if existing:
        flash('You have already applied for this drive.', 'warning')
        return redirect(url_for('student_drives'))

    application = Application(
        student_id=session['user_id'],
        drive_id=id
    )
    db.session.add(application)
    db.session.commit()
    flash('Application submitted successfully!', 'success')
    return redirect(url_for('student_my_applications'))


@app.route('/student/applications')
@student_required
def student_my_applications():
    applications = Application.query.filter_by(student_id=session['user_id']).order_by(Application.application_date.desc()).all()
    return render_template('student/my_applications.html', applications=applications)


@app.route('/student/history')
@student_required
def student_history():
    applications = Application.query.filter_by(student_id=session['user_id']).order_by(Application.application_date.desc()).all()
    return render_template('student/history.html', applications=applications)


# ==================== API ROUTES ====================

@app.route('/api/students', methods=['GET'])
def api_students():
    students = Student.query.all()
    return jsonify([{
        'id': s.id, 'name': s.name, 'email': s.email,
        'degree': s.degree, 'branch': s.branch, 'cgpa': s.cgpa
    } for s in students])


@app.route('/api/students/<int:id>', methods=['GET'])
def api_student(id):
    s = Student.query.get_or_404(id)
    return jsonify({
        'id': s.id, 'name': s.name, 'email': s.email,
        'phone': s.phone, 'degree': s.degree, 'branch': s.branch,
        'cgpa': s.cgpa, 'skills': s.skills
    })


@app.route('/api/companies', methods=['GET'])
def api_companies():
    companies = Company.query.all()
    return jsonify([{
        'id': c.id, 'company_name': c.company_name, 'email': c.email,
        'industry': c.industry, 'approval_status': c.approval_status
    } for c in companies])


@app.route('/api/companies/<int:id>', methods=['GET'])
def api_company(id):
    c = Company.query.get_or_404(id)
    return jsonify({
        'id': c.id, 'company_name': c.company_name, 'email': c.email,
        'hr_contact': c.hr_contact, 'website': c.website,
        'industry': c.industry, 'approval_status': c.approval_status
    })


@app.route('/api/drives', methods=['GET'])
def api_drives():
    drives = PlacementDrive.query.all()
    return jsonify([{
        'id': d.id, 'company_id': d.company_id, 'job_title': d.job_title,
        'status': d.status, 'deadline': str(d.deadline) if d.deadline else None
    } for d in drives])


@app.route('/api/drives/<int:id>', methods=['GET'])
def api_drive(id):
    d = PlacementDrive.query.get_or_404(id)
    return jsonify({
        'id': d.id, 'company_id': d.company_id, 'job_title': d.job_title,
        'job_description': d.job_description, 'eligibility': d.eligibility,
        'salary_range': d.salary_range, 'location': d.location,
        'required_skills': d.required_skills, 'status': d.status,
        'deadline': str(d.deadline) if d.deadline else None
    })


@app.route('/api/applications', methods=['GET'])
def api_applications():
    apps = Application.query.all()
    return jsonify([{
        'id': a.id, 'student_id': a.student_id, 'drive_id': a.drive_id,
        'status': a.status, 'application_date': str(a.application_date)
    } for a in apps])


@app.route('/api/applications/<int:id>', methods=['GET'])
def api_application(id):
    a = Application.query.get_or_404(id)
    return jsonify({
        'id': a.id, 'student_id': a.student_id, 'drive_id': a.drive_id,
        'status': a.status, 'application_date': str(a.application_date)
    })


def init_db():
    with app.app_context():
        db.create_all()
        if not Admin.query.first():
            admin = Admin(
                username='admin',
                password=generate_password_hash('admin123'),
                email='admin@placement.com'
            )
            db.session.add(admin)
            db.session.commit()
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
