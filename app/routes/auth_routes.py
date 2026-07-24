"""Authentication routes."""
from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from app.services.auth_service import authenticate_user, current_user, sign_in_user, sign_out_user, signup_user


auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/signin', methods=['GET', 'POST'])
def signin():
    if current_user() and request.method == 'GET':
        return redirect(url_for('pages.dashboard'))

    error = ''
    if request.method == 'POST':
        user = authenticate_user(request.form.get('email'), request.form.get('password'))
        if user:
            sign_in_user(user)
            next_url = request.args.get('next') or url_for('pages.dashboard')
            return redirect(next_url)
        error = 'Invalid email or password.'

    return render_template('auth/signin.html', error=error, email=request.form.get('email', ''))


@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user() and request.method == 'GET':
        return redirect(url_for('pages.dashboard'))

    error = ''
    if request.method == 'POST':
        try:
            user = signup_user(
                request.form.get('full_name'),
                request.form.get('email'),
                request.form.get('password'),
                request.form.get('company_identifier'),
            )
            sign_in_user(user)
            return redirect(url_for('pages.dashboard'))
        except ValueError as exc:
            error = str(exc)

    return render_template(
        'auth/signup.html',
        error=error,
        values={
            'full_name': request.form.get('full_name', ''),
            'email': request.form.get('email', ''),
            'company_identifier': request.form.get('company_identifier', ''),
        },
    )


@auth_bp.route('/signout', methods=['POST'])
def signout():
    sign_out_user()
    return redirect(url_for('auth.signin'))


@auth_bp.route('/me', methods=['GET'])
def me():
    user = current_user()
    if not user:
        return jsonify({'status': 'error', 'message': 'Not authenticated'}), 401
    return jsonify({'status': 'success', 'data': user.to_dict()}), 200
