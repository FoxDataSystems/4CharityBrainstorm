from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.config['SECRET_KEY'] = 'your-secret-key-here'  # Change this to a secure key
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ideas.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    ideas = db.relationship('Idea', backref='author', lazy=True)
    
    @property
    def is_active(self):
        return True  # This could be modified to support account deactivation

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    ideas = db.relationship('Idea', backref='category', lazy=True)

class Idea(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image_path = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    comments = db.relationship('Comment', backref='idea', lazy=True)
    notes = db.relationship('Note', backref='idea', lazy=True)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    idea_id = db.Column(db.Integer, db.ForeignKey('idea.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=True)
    likes = db.relationship('CommentLike', backref='comment', lazy='dynamic')
    user = db.relationship('User', backref='comments')
    # Add relationship for replies
    replies = db.relationship(
        'Comment',
        backref=db.backref('parent', remote_side=[id]),
        lazy='dynamic'
    )

    def get_replies_recursive(self):
        """Get all replies in a threaded structure"""
        result = []
        for reply in self.replies.order_by(Comment.created_at.asc()):
            reply_dict = {
                'comment': reply,
                'replies': reply.get_replies_recursive()
            }
            result.append(reply_dict)
        return result

class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    idea_id = db.Column(db.Integer, db.ForeignKey('idea.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref='notes')

class CommentLike(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    comment_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Create initial users
def create_initial_data():
    # Only create initial users if they don't exist
    users = [
        {'username': 'Mick', 'password': 'mick123'},
        {'username': 'Ralph', 'password': 'ralph123'},
        {'username': 'Q', 'password': 'q123'}
    ]
    for user_data in users:
        if not User.query.filter_by(username=user_data['username']).first():
            user = User(
                username=user_data['username'],
                password_hash=generate_password_hash(user_data['password'])
            )
            db.session.add(user)
    
    # Only create categories if they don't exist
    categories = ['Product Ideas', 'Process Improvements', 'Features', 'Bug Fixes']
    for cat_name in categories:
        if not Category.query.filter_by(name=cat_name).first():
            category = Category(name=cat_name)
            db.session.add(category)
    
    db.session.commit()

with app.app_context():
    # Create tables without dropping existing ones
    db.create_all()
    
    # Check if we need to create initial data
    if not User.query.first():  # Only create initial data if no users exist
        create_initial_data()

@app.route('/')
def root():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    return redirect(url_for('index'))

@app.route('/index')
@login_required
def index():
    ideas = Idea.query.order_by(Idea.created_at.desc()).all()
    categories = Category.query.all()
    
    # Group ideas by month
    ideas_by_month = {}
    for idea in ideas:
        month_key = idea.created_at.strftime('%B %Y')  # e.g., "March 2024"
        if month_key not in ideas_by_month:
            ideas_by_month[month_key] = []
        ideas_by_month[month_key].append(idea)
    
    return render_template('index.html', ideas_by_month=ideas_by_month, categories=categories)

@app.route("/idea/<int:idea_id>")
@login_required
def idea_detail(idea_id):
    idea = Idea.query.get_or_404(idea_id)
    # Get root comments (comments without parents) and their replies
    root_comments = []
    for comment in Comment.query.filter_by(idea_id=idea_id, parent_id=None).order_by(Comment.created_at.desc()):
        comment_data = {
            'comment': comment,
            'replies': comment.get_replies_recursive()
        }
        root_comments.append(comment_data)
    
    return render_template('idea_detail.html', idea=idea, root_comments=root_comments)

@app.route("/add_idea", methods=['GET', 'POST'])
@login_required
def add_idea():
    if request.method == 'GET':
        categories = Category.query.all()
        return render_template('add_idea.html', categories=categories)
    
    title = request.form['title']
    content = request.form['content']
    category_id = request.form['category_id']
    
    image_path = None
    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename:
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            image_path = f'uploads/{filename}'

    new_idea = Idea(
        title=title,
        content=content,
        image_path=image_path,
        user_id=current_user.id,  # Automatically use the logged-in user
        category_id=category_id
    )
    db.session.add(new_idea)
    db.session.commit()
    return redirect(url_for('index'))

@app.route("/add_comment/<int:idea_id>", methods=['POST'])
@login_required
def add_comment(idea_id):
    content = request.form.get('comment_content')
    if not content:
        flash('Comment content is required')
        return redirect(url_for('idea_detail', idea_id=idea_id))

    new_comment = Comment(
        content=content,
        user_id=current_user.id,
        idea_id=idea_id,
        parent_id=None  # This is a root comment
    )
    
    db.session.add(new_comment)
    db.session.commit()
    
    return redirect(url_for('idea_detail', idea_id=idea_id))

@app.route("/add_note/<int:idea_id>", methods=['POST'])
@login_required
def add_note(idea_id):
    content = request.form['note_content']
    new_note = Note(
        content=content,
        idea_id=idea_id,
        user_id=current_user.id
    )
    db.session.add(new_note)
    db.session.commit()
    return redirect(url_for('idea_detail', idea_id=idea_id))

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Redirect to index if user is already logged in
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            # Redirect to the page user wanted to access, or index if none specified
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route("/edit_idea/<int:idea_id>", methods=['GET', 'POST'])
@login_required
def edit_idea(idea_id):
    idea = Idea.query.get_or_404(idea_id)
    
    # Check if the current user is the owner of the idea
    if idea.user_id != current_user.id:
        flash('You can only edit your own ideas.')
        return redirect(url_for('index'))
    
    if request.method == 'GET':
        categories = Category.query.all()
        return render_template('edit_idea.html', idea=idea, categories=categories)
    
    # Handle POST request
    idea.title = request.form['title']
    idea.content = request.form['content']
    idea.category_id = request.form['category_id']
    
    # Handle image update
    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename:
            # Delete old image if it exists
            if idea.image_path:
                old_image_path = os.path.join(app.config['UPLOAD_FOLDER'], idea.image_path.split('/')[-1])
                if os.path.exists(old_image_path):
                    os.remove(old_image_path)
            
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            idea.image_path = f'uploads/{filename}'
    
    db.session.commit()
    return redirect(url_for('idea_detail', idea_id=idea.id))

@app.route('/like_comment/<int:comment_id>', methods=['POST'])
@login_required
def like_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    existing_like = CommentLike.query.filter_by(
        user_id=current_user.id,
        comment_id=comment_id
    ).first()
    
    if existing_like:
        db.session.delete(existing_like)
        action = 'unliked'
    else:
        like = CommentLike(user_id=current_user.id, comment_id=comment_id)
        db.session.add(like)
        action = 'liked'
    
    db.session.commit()
    
    return jsonify({
        'action': action,
        'likes_count': comment.likes.count()
    })

@app.route('/edit_comment/<int:comment_id>', methods=['POST'])
@login_required
def edit_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    
    # Check if the current user owns this comment
    if comment.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    content = request.json.get('content')
    if not content:
        return jsonify({'error': 'Content is required'}), 400
    
    comment.content = content
    db.session.commit()
    
    return jsonify({
        'content': comment.content,
        'edited': True
    })

@app.route("/delete_idea/<int:idea_id>", methods=['POST'])
@login_required
def delete_idea(idea_id):
    idea = Idea.query.get_or_404(idea_id)
    
    # Check if the current user is the owner of the idea
    if idea.user_id != current_user.id:
        flash('You can only delete your own ideas.')
        return redirect(url_for('index'))
    
    # Delete the associated image if it exists
    if idea.image_path:
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], idea.image_path.split('/')[-1])
        if os.path.exists(image_path):
            os.remove(image_path)
    
    # First delete all associated comments and their likes
    for comment in idea.comments:
        # Delete all likes associated with this comment
        CommentLike.query.filter_by(comment_id=comment.id).delete()
        db.session.delete(comment)
    
    # Delete all associated notes
    for note in idea.notes:
        db.session.delete(note)
    
    # Finally delete the idea
    db.session.delete(idea)
    db.session.commit()
    
    flash('Idea deleted successfully.')
    return redirect(url_for('index'))

@app.route("/add_reply/<int:idea_id>/<int:parent_id>", methods=['POST'])
@login_required
def add_reply(idea_id, parent_id):
    content = request.form.get('content')
    if not content:
        return jsonify({'error': 'Reply content is required'}), 400

    parent_comment = Comment.query.get_or_404(parent_id)
    new_reply = Comment(
        content=content,
        user_id=current_user.id,
        idea_id=idea_id,
        parent_id=parent_id
    )
    
    db.session.add(new_reply)
    db.session.commit()
    
    return jsonify({
        'id': new_reply.id,
        'content': new_reply.content,
        'username': new_reply.user.username,
        'created_at': new_reply.created_at.strftime('%Y-%m-%d %H:%M'),
        'user_id': new_reply.user_id
    })

@app.route("/delete_comment/<int:comment_id>", methods=['POST'])
@login_required
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    if comment.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Delete all replies recursively
    def delete_replies(comment):
        for reply in comment.replies:
            delete_replies(reply)
            db.session.delete(reply)
    
    delete_replies(comment)
    db.session.delete(comment)
    db.session.commit()
    
    return jsonify({'success': True})

@app.route("/toggle_like/<int:comment_id>", methods=['POST'])
@login_required
def toggle_like(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    existing_like = CommentLike.query.filter_by(
        user_id=current_user.id,
        comment_id=comment_id
    ).first()
    
    if existing_like:
        db.session.delete(existing_like)
        liked = False
    else:
        new_like = CommentLike(user_id=current_user.id, comment_id=comment_id)
        db.session.add(new_like)
        liked = True
    
    db.session.commit()
    return jsonify({
        'liked': liked,
        'count': comment.likes.count()
    })

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Check if username already exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))
        
        # Create new user
        new_user = User(
            username=username,
            password_hash=generate_password_hash(password)
        )
        
        try:
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful! Please login.')
            return redirect(url_for('login'))
        except:
            db.session.rollback()
            flash('An error occurred. Please try again.')
            return redirect(url_for('register'))
            
    return render_template('register.html')

if __name__ == "__main__":
    # Remove or comment out the debug-only line
    # app.run(debug=True)
    
    # Replace with this line to make it accessible on your network
    app.run(host='0.0.0.0', port=5000, debug=True)
