from flask import Flask, render_template, redirect, url_for, request, flash
from flask_security import Security, SQLAlchemyUserDatastore, UserMixin, RoleMixin, current_user, login_required, logout_user
from flask_sqlalchemy import SQLAlchemy
from datetime import date
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///gym.db'
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'kotek')
app.config['SECURITY_PASSWORD_SALT'] = os.environ.get('SECURITY_PASSWORD_SALT', 'jakas-sol')
app.config['SECURITY_REGISTERABLE'] = True
app.config['SECURITY_SEND_REGISTER_EMAIL'] = False
app.config['SECURITY_RECOVERABLE'] = True
app.config['SECURITY_LOGIN_USER_TEMPLATE'] = 'login.html'
app.config['SECURITY_REGISTER_USER_TEMPLATE'] = 'register.html'

db = SQLAlchemy(app)

roles_users = db.Table(
    'roles_users',
    db.Column('user_id', db.Integer(), db.ForeignKey('user.id')),
    db.Column('role_id', db.Integer(), db.ForeignKey('role.id'))
)


class Workout(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)
    user_id = db.Column(db.String(255), db.ForeignKey('user.fs_uniquifier'))
    exercises = db.relationship('Exercise', backref='workout', lazy=True)


class Exercise(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    sets = db.Column(db.Integer, nullable=False)
    reps = db.Column(db.Integer, nullable=False)
    weight = db.Column(db.Float, nullable=False)
    rpe = db.Column(db.Float, nullable=False)
    workout_id = db.Column(db.Integer, db.ForeignKey('workout.id'))


class TempExercise(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    sets = db.Column(db.Integer, nullable=False)
    reps = db.Column(db.Integer, nullable=False)
    weight = db.Column(db.Float, nullable=False)
    rpe = db.Column(db.Float, nullable=False)
    user_id = db.Column(db.String(255), db.ForeignKey('user.fs_uniquifier'))
    workout_name = db.Column(db.String(100), nullable=False)


class Role(db.Model, RoleMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True)
    description = db.Column(db.String(255))


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    active = db.Column(db.Boolean(), default=True)
    confirmed_at = db.Column(db.DateTime())
    fs_uniquifier = db.Column(db.String(255), unique=True, nullable=False)
    roles = db.relationship('Role', secondary=roles_users, backref=db.backref('users', lazy='dynamic'))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.fs_uniquifier:
            import uuid
            self.fs_uniquifier = str(uuid.uuid4())


user_datastore = SQLAlchemyUserDatastore(db, User, Role)
security = Security(app, user_datastore)


@app.route('/')
@login_required
def index():
    workout_name = request.args.get('workout_name', None)
    temp_exercises = TempExercise.query.filter_by(user_id=current_user.fs_uniquifier).all()
    total_volume = sum(ex.sets * ex.reps * ex.weight for ex in temp_exercises)
    return render_template('index.html', workouts=Workout.query.filter_by(user_id=current_user.fs_uniquifier).all(), temp_exercises=temp_exercises, total_volume=total_volume, workout_name=workout_name)


@app.route('/add-exercise', methods=['POST'])
@login_required
def add_exercise():
    exercise = TempExercise(
        name=request.form.get('exercise'),
        sets=int(request.form.get('sets')),
        reps=int(request.form.get('reps')),
        weight=float(request.form.get('weight')),
        rpe=float(request.form.get('rpe')),
        user_id=current_user.fs_uniquifier,
        workout_name=request.form.get('workout_name')
    )
    db.session.add(exercise)
    db.session.commit()
    return redirect(url_for('index', workout_name=exercise.workout_name))


@app.route('/workout/<int:workout_id>')
@login_required
def workout_detail(workout_id):
    workout = Workout.query.filter_by(id=workout_id, user_id=current_user.fs_uniquifier).first()
    if not workout:
        flash("Workout not found!", "danger")
        return redirect(url_for('workout_list'))
    total_volume = sum(ex.sets * ex.reps * ex.weight for ex in workout.exercises)
    return render_template('workout_detail.html', workout=workout, total_volume=total_volume)


@app.route('/delete-workout/<int:workout_id>', methods=['POST'])
@login_required
def delete_workout(workout_id):
    workout = Workout.query.filter_by(id=workout_id, user_id=current_user.fs_uniquifier).first()
    if not workout:
        flash("Workout not found!", "danger")
        return redirect(url_for('workout_list'))
    db.session.delete(workout)
    db.session.commit()
    flash("Workout deleted successfully!", "success")
    return redirect(url_for('workout_list'))


@app.route('/save-workout', methods=['POST'])
@login_required
def save_workout():
    temp_exercises = TempExercise.query.filter_by(user_id=current_user.fs_uniquifier).all()
    if not temp_exercises:
        flash('Add at least one exercise before saving!', 'danger')
        return redirect(url_for('index'))
    
    workout_name = temp_exercises[0].workout_name
    new_workout = Workout(name=workout_name, user_id=current_user.fs_uniquifier, date=date.today())
    db.session.add(new_workout)
    db.session.flush()
    
    for ex in temp_exercises:
        exercise = Exercise(name=ex.name, sets=ex.sets, reps=ex.reps, weight=ex.weight, rpe=ex.rpe, workout_id=new_workout.id)
        db.session.add(exercise)
    
    db.session.commit()
    TempExercise.query.filter_by(user_id=current_user.fs_uniquifier).delete()
    db.session.commit()
    
    flash('Workout saved successfully!', 'success')
    return redirect(url_for('workout_list'))


@app.route('/workout_list')
@login_required
def workout_list():
    workouts = Workout.query.filter_by(user_id=current_user.fs_uniquifier).all()
    return render_template('workout_list.html', workouts=workouts)


@app.route('/set_workout_name', methods=['POST'])
@login_required
def set_workout_name():
    workout_name = request.form.get('workout_name')
    TempExercise.query.filter_by(user_id=current_user.fs_uniquifier).delete()
    db.session.commit()
    return redirect(url_for('index', workout_name=workout_name))


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('security.login'))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5001, debug=True)
