from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime, timedelta, date
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from models import db, User, Schedule
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import io
import base64
import os
import calendar

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///schedule.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'supersecretkey'

# 初始化資料庫
db.init_app(app)
migrate = Migrate(app, db)

# 初始化登入管理
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# 設定字體路徑，避免中文亂碼
font_path = os.path.join(os.path.dirname(__file__), 'fonts', 'SimHei.ttf')
if os.path.exists(font_path):
    font_prop = fm.FontProperties(fname=font_path)
else:
    font_prop = fm.FontProperties(family='SimHei')
plt.rcParams['axes.unicode_minus'] = False

# 生成月曆的輔助函數
def generate_calendar(year, month):
    cal = calendar.HTMLCalendar(firstweekday=6)  # 星期天作為一周的第一天
    html_calendar = cal.formatmonth(year, month)
    html_calendar = html_calendar.replace('Mon', 'M').replace('Tue', 'T').replace('Wed', 'W').replace('Thu', 'T').replace('Fri', 'F').replace('Sat', 'S').replace('Sun', 'S')

    # 為每一天加上點選功能
    for day in range(1, 32):
        try:
            date_obj = datetime(year, month, day)
            day_link = f'<a href="#" onclick="selectDay({day})">{day}</a>'
            html_calendar = html_calendar.replace(f'>{day}<', f'>{day_link}<', 1)
        except ValueError:
            break

    return html_calendar

# 生成週期的輔助函數
def generate_weekly_labels(start_date):
    # 確保從星期天開始
    week_labels = [(start_date + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(7)]
    return week_labels

# 首頁，顯示日曆與行程列表
@app.route('/')
@login_required
def index():
    year = request.args.get('year', type=int, default=date.today().year)
    month = request.args.get('month', type=int, default=date.today().month)
    selected_date_str = request.args.get('selected_day', default=None)
    week_start_str = request.args.get('week_start', default=None)

    if selected_date_str:
        selected_day = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
    else:
        selected_day = date.today()

    # 取得登入當日的行程或選取日期的行程
    schedules = Schedule.query.filter_by(user_id=current_user.id).filter(
        db.func.date(Schedule.start_time) == selected_day).order_by(Schedule.start_time).all()

    study_hours = [0] * 7
    subject_hours = {}

    # 計算每週讀書時間和各科目時間分配
    if week_start_str:
        week_start = datetime.strptime(week_start_str, '%Y-%m-%d').date()
    else:
        # 確保週從星期天開始
        week_start = selected_day - timedelta(days=selected_day.weekday() + 1)
    week_end = week_start + timedelta(days=7)
    weekly_schedules = Schedule.query.filter_by(user_id=current_user.id).filter(
        Schedule.start_time >= week_start, Schedule.start_time < week_end ).all()
    
    for schedule in weekly_schedules:
        day_index = (schedule.start_time.date() - week_start).days
        duration = (schedule.end_time - schedule.start_time).total_seconds() / 3600
        print(f"行程標題: {schedule.title}, 起始時間: {schedule.start_time}, 結束時間: {schedule.end_time}, day_index: {day_index}, 時數: {duration}")
        if 0 <= day_index <= 6:
            
            study_hours[day_index] += duration
            print(f"更新後的 study_hours: {study_hours}")

            if schedule.title in subject_hours:
                subject_hours[schedule.title] += duration
            else:
                subject_hours[schedule.title] = duration

    # 生成當前月曆
    calendar_html = generate_calendar(year, month)
    week_labels = generate_weekly_labels(week_start)
    
    return render_template(
        'index.html', 
        schedules=schedules, 
        days=week_labels, 
        study_hours=study_hours, 
        subject_hours=subject_hours, 
        calendar_html=calendar_html, 
        current_year=year, 
        current_month=month, 
        today=date.today(), 
        selected_day=selected_day, 
        week_start=week_start, 
        timedelta=timedelta
    )


# 上一個月
@app.route('/prev_month/<int:year>/<int:month>')
@login_required
def prev_month(year, month):
    prev_month_date = datetime(year, month, 1) - timedelta(days=1)
    return redirect(url_for('index', year=prev_month_date.year, month=prev_month_date.month))

# 下一個月
@app.route('/next_month/<int:year>/<int:month>')
@login_required
def next_month(year, month):
    next_month_date = datetime(year, month, 28) + timedelta(days=4)
    next_month_date = next_month_date.replace(day=1)
    return redirect(url_for('index', year=next_month_date.year, month=next_month_date.month))

# 上一週
@app.route('/prev_week')
@login_required
def prev_week():
    week_start_str = request.args.get('week_start', default=(date.today() - timedelta(days=(date.today().weekday() + 1) % 7)).strftime('%Y-%m-%d'))
    week_start = datetime.strptime(week_start_str, '%Y-%m-%d').date() - timedelta(days=7)
    return redirect(url_for('index', week_start=week_start.strftime('%Y-%m-%d')))

# 下一週
@app.route('/next_week')
@login_required
def next_week():
    week_start_str = request.args.get('week_start', default=(date.today() - timedelta(days=(date.today().weekday() + 1) % 7)).strftime('%Y-%m-%d'))
    week_start = datetime.strptime(week_start_str, '%Y-%m-%d').date() + timedelta(days=7)
    return redirect(url_for('index', week_start=week_start.strftime('%Y-%m-%d')))

# 登入頁面
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash('登入成功！', 'success')
            return redirect(url_for('index'))
        else:
            flash('無效的使用者名稱或密碼', 'danger')
            return redirect(url_for('login'))
    return render_template('login.html')

# 註冊頁面
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            flash('使用者名稱已被註冊', 'danger')
            return redirect(url_for('register'))
        new_user = User(username=username)
        new_user.set_password(password)
        with app.app_context():
            db.session.add(new_user)
            db.session.commit()
        flash('註冊成功，請登入', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

# 登出
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# 新增行程頁面
@app.route('/add_schedule', methods=['GET', 'POST'])
@login_required
def add_schedule():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        start_time = datetime.strptime(request.form['start_time'], '%Y-%m-%dT%H:%M')
        end_time = datetime.strptime(request.form['end_time'], '%Y-%m-%dT%H:%M')
        new_schedule = Schedule(title=title, description=description, start_time=start_time, end_time=end_time, user_id=current_user.id)
        with app.app_context():
            db.session.add(new_schedule)
            db.session.commit()
        flash('行程新增成功', 'success')
        return redirect(url_for('index'))
    return render_template('add_schedule.html')

@app.route('/get_pie_chart_data')
@login_required
def get_pie_chart_data():
    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)
    day = request.args.get('day', type=int)
    
    # 獲取該日期的行程資料
    target_date = datetime(year, month, day)
    schedules = Schedule.query.filter_by(user_id=current_user.id).filter(
        db.func.date(Schedule.start_time) == target_date.date()).all()
    
    subject_hours = {}
    for schedule in schedules:
        duration = (schedule.end_time - schedule.start_time).total_seconds() / 3600
        if schedule.title in subject_hours:
            subject_hours[schedule.title] += duration
        else:
            subject_hours[schedule.title] = duration

    labels = list(subject_hours.keys())
    values = list(subject_hours.values())

    return {'labels': labels, 'values': values}

# 新增：編輯行程
@app.route('/edit_schedule/<int:schedule_id>', methods=['GET', 'POST'])
@login_required
def edit_schedule(schedule_id):
    schedule = Schedule.query.get_or_404(schedule_id)
    if request.method == 'POST':
        schedule.title = request.form['title']
        schedule.description = request.form['description']
        schedule.start_time = datetime.strptime(request.form['start_time'], '%Y-%m-%dT%H:%M')
        schedule.end_time = datetime.strptime(request.form['end_time'], '%Y-%m-%dT%H:%M')
        db.session.commit()
        flash('行程更新成功', 'success')
        return redirect(url_for('index'))
    return render_template('edit_schedule.html', schedule=schedule)

# 新增：刪除行程
@app.route('/delete_schedule/<int:schedule_id>', methods=['POST'])
@login_required
def delete_schedule(schedule_id):
    schedule = Schedule.query.get_or_404(schedule_id)
    db.session.delete(schedule)
    db.session.commit()
    flash('行程已刪除', 'success')
    return redirect(url_for('index'))

# 新增：獲取特定日期的行程資料
@app.route('/get_schedule_data')
@login_required
def get_schedule_data():
    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)
    day = request.args.get('day', type=int)
    
    # 獲取該日期的行程資料
    target_date = datetime(year, month, day).date()
    schedules = Schedule.query.filter_by(user_id=current_user.id).filter(
        db.func.date(Schedule.start_time) == target_date).all()

    schedule_list = []
    for schedule in schedules:
        schedule_list.append({
            'id': schedule.id,
            'title': schedule.title,
            'description': schedule.description,
            'start_time': schedule.start_time.strftime('%Y-%m-%d %H:%M'),
            'end_time': schedule.end_time.strftime('%Y-%m-%d %H:%M')
        })

    return jsonify({'schedules': schedule_list})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
