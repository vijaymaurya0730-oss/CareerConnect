# Online Job Portal Management System

A medium-level B.Sc. IT project built with Python Flask, SQLite, HTML and CSS.

## Features
- Job seeker and employer registration/login
- Password hashing
- Search jobs by keyword and location
- Employers can post vacancies
- Job seekers can apply and view application status
- Employers can review applications and update status
- Basic administrator dashboard

## Setup
1. Install Python 3.10 or later.
2. Open a terminal in this folder.
3. Create and activate a virtual environment:
   - Windows: `python -m venv venv` then `venv\\Scripts\\activate`
   - macOS/Linux: `python3 -m venv venv` then `source venv/bin/activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Run: `python app.py`
6. Open `http://127.0.0.1:5000` in a browser.

## Demo administrator
- Email: `admin@jobportal.test`
- Password: `Admin@123`

Change the demo password and Flask secret key before any real deployment. This is an academic prototype; production use requires CSRF protection, email verification, rate limiting, secure secret management, HTTPS, backups and stronger administrative controls.

## Database
SQLite database `jobportal.db` is created automatically on first run. Tables: `users`, `jobs`, `applications`.
