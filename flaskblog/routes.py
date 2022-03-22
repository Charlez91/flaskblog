import json
import secrets
import os
from urllib.parse import urlparse, urljoin
from PIL import Image
from flask import render_template, url_for, flash, redirect, request, abort
from flaskblog import app, db, bcrypt, mail, login_manager
from flaskblog.forms import (RegistrationForm, LoginForm, UpdateAccountForm, 
								PostForm, RequestResetForm, ResetPasswordForm)
from flaskblog.models import User, Post
from flask_login import login_user, current_user, logout_user, login_required
from flask_mail import Message


def load_posts():
	with open('post.json') as f:
		data = json.load(f)
	for x in data:
		posts = Post(title= x['title'], content=x['content'], author=User.query.get_or_404(x['user_id']))
		db.session.add(posts)
		db.session.commit()


@app.route('/')
@app.route('/home')
def home():
	#load_posts()
	page = request.args.get('page', 1, type=int)
	posts = Post.query.order_by(Post.date_posted.desc()).paginate(page=page, per_page=5)
	return render_template ('home.html', posts=posts)


@app.route('/about')
def about():
 	return render_template ('about.html', title='About Us')


@app.route('/register', methods=['GET', 'POST'])
def register():
	if current_user.is_authenticated:
		return redirect(url_for('home'))
	form = RegistrationForm()
	if form.validate_on_submit():
		hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
		user = User(username=form.username.data, email= form.email.data, password= hashed_password)
		db.session.add(user)
		db.session.commit()
		flash(f'Your has been Account created! You can now Login!', 'success')
		return redirect(url_for('login'))
	return render_template ('register.html', title='Register', form = form)
 		
def is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and \
           ref_url.netloc == test_url.netloc


@app.route('/login', methods=['GET', 'POST'])
def login():
	if current_user.is_authenticated:
		return redirect(url_for('home'))
	form = LoginForm()
	if form.validate_on_submit():
		user = User.query.filter_by(email=form.email.data).first()
		if user and bcrypt.check_password_hash(user.password, form.password.data):
			login_user(user, remember= form.remember.data)
			next_page = request.args.get('next')
			if not is_safe_url(next_page):
				abort(400)
			return redirect (next_page) if next_page else redirect(url_for('home'))			
		else:
			flash (f"Login Unsuccessful. Please check Email or Password", 'danger')
	return render_template ('login.html', title='Login', form = form)
 		

@app.route('/feeds')
def feeds():
	return 'Hello World'

@app.route('/logout')
@login_required
def logout():
	logout_user()
	return redirect(url_for('home'))

def save_picture(form_picture):
	random_hex = secrets.token_hex(8) #generates a random hex using secrets module
	_, f_ext = os.path.splitext(form_picture.filename) #seperates the file extension from the passed in image
	picture_fn = random_hex + f_ext #conc. the random hex and file extension
	picture_path = os.path.join(app.root_path, 'static/profile_pics', picture_fn) #creates the path to which the file will be saved
	
	#code for resizing the image passed into the function(form_picture)
	output_size = (125, 125) #125 by 125 pixels
	i = Image.open(form_picture) # a new image is created called i
	i.thumbnail(output_size) #to resize the image set to outputsize
	i.save(picture_path)#this saves the images passed in to the picture_path

	return picture_fn # after the image is passed to the path the image itself is returned

@app.route('/account', methods = ['GET', 'POST'])
@login_required
@login_manager.needs_refresh_handler
def account():
	form = UpdateAccountForm()
	if form.validate_on_submit():
		if form.picture.data:
			picture_file = save_picture(form.picture.data) # pictured data from form is passed into the save function
			current_user.image_file = picture_file #the file name is returned and equated to current user image
		current_user.username = form.username.data
		current_user.email =  form.email.data
		db.session.commit()
		flash(f"Your Account has been Updated Successfully", 'success')
		return redirect(url_for('account'))
	elif request.method == 'GET':
		form.username.data = current_user.username
		form.email.data =current_user.email		
	image_file = url_for('static', filename='profile_pics/' + current_user.image_file)
	return render_template('account.html', title= 'Account', 
											image_file=image_file, form=form)

@app.route("/post/new", methods=['GET', 'POST'])
@login_required
def new_post():
	form = PostForm()
	if form.validate_on_submit():
		post = Post(title= form.title.data, content=form.content.data, author=current_user)
		db.session.add(post)
		db.session.commit()
		flash (f"Your Post has been created!", 'success')
		return redirect (url_for('home'))
	return render_template('create_post.html', title= 'New Post', 
												form = form, legend='Create Post')


@app.route("/post/<int:post_id>", methods=['GET', 'POST'])
def post(post_id):
	post = Post.query.get_or_404(post_id)
	return render_template('post.html', title=post.title, post=post)

@app.route("/post/<int:post_id>/update", methods=['GET', 'POST'])
def update_post(post_id):
	post = Post.query.get_or_404(post_id)
	if post.author != current_user:
		abort(403)
	form = PostForm()
	if form.validate_on_submit():
		post.title = form.title.data
		post.content = form.content.data
		db.session.commit()
		flash (f"Your Post has been Updated!", 'success')
		return redirect (url_for('post', post_id=post.id))
	elif request.method == 'GET':
		form.title.data = post.title
		form.content.data = post.content
	return render_template('create_post.html', title= 'Update Post', 
												form = form, legend= 'Update Post')

@app.route("/post/<int:post_id>/delete", methods=[ 'POST'])
def delete_post(post_id):
	post = Post.query.get_or_404(post_id)
	if post.author != current_user:
		abort(403)
	if request.method == 'POST':
		db.session.delete(post)
		db.session.commit()
		flash (f"Your Post has been Deleted!", 'success')		
	return redirect(url_for('home'))



@app.route('/user/<string:username>')
def user_posts(username):
	page = request.args.get('page', 1, type=int)
	user = User.query.filter_by(username = username).first_or_404()
	posts = Post.query\
				.filter_by(author = user)\
				.order_by(Post.date_posted.desc())\
				.paginate(page=page, per_page=5)
	return render_template ('user_posts.html', posts=posts, user=user)


def send_reset_email(user):
	token = user.get_reset_token()
	msg = Message('Password Reset Request',
					sender = 'charlezokeke91@gmail.com',
					recipients = [user.email])
	msg.body = f''' To reset your password, visits the following link:
{url_for('reset_token', token = token, _external = True)}
If you did not make this request then simply ignore this email and no changes will be made
'''
	mail.send(msg)


@app.route("/reset_password", methods=['GET', 'POST'])
def reset_request():
	if current_user.is_authenticated:
		return redirect(url_for('home'))
	form = RequestResetForm()
	if form.validate_on_submit():
		user = User.query.filter_by(email=form.email.data).first()
		send_reset_email(user)
		flash(f'An email with instructions has been sent to your mailbox','info')
		return redirect(url_for('login'))
	return render_template('reset_request.html', title= 'Reset Password', form=form)


@app.route("/reset_password/<token>", methods=['GET', 'POST'])
def reset_token(token):
	if current_user.is_authenticated:
		return redirect(url_for('home'))
	user = User.verify_reset_token(token)
	if user is None:
		flash('That is an invalid or expired token', 'warning')
		return redirect(url_for('reset_request'))
	form = ResetPasswordForm()
	if form.validate_on_submit():
		hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
		user.password = hashed_password
		db.session.commit()
		flash(f'Your Password has been updated, You are now able to login', 'success')
		return render_template(url_for('login'))
	return render_template('reset_token.html',title = 'Reset Password', form = form)
