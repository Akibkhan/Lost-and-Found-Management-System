# Lost and Found Management System

A Flask-based **Lost and Found Management System** with AI-powered image recognition, real-time communication, and database support.

---

# Installation Guide

## Prerequisites

Before installing the application, ensure the following are installed on your system:

- Python 3.9 or later (recommended)
- pip
- virtualenv (optional but recommended)
- Redis Server

---

## 1. Create a Virtual Environment

### Linux / macOS

```bash
python3 -m venv venv
source venv/bin/activate
```

### Windows

```bash
python -m venv venv
venv\Scripts\activate
```

---

## 2. Upgrade pip

```bash
pip install --upgrade pip
```

---

## 3. Install Project Dependencies

Install all required packages from `requirements.txt`.

```bash
pip install -r requirements.txt
```

---

## 4. Install Salesforce BLIP

BLIP models are provided through Hugging Face Transformers.

```bash
pip install transformers accelerate sentencepiece
```

---

## 5. Install PyTorch

Install the appropriate version based on your system.

### CPU Version

```bash
pip install torch torchvision
```

### CUDA (GPU) Version

Check your CUDA version and install the matching PyTorch build.

Example:

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

Official Installation Guide:

https://pytorch.org/get-started/locally/

---

## 6. Flask-SocketIO Setup

Install Flask-SocketIO:

```bash
pip install flask-socketio
```

Optional asynchronous workers:

```bash
pip install eventlet
```

Example initialization:

```python
from flask_socketio import SocketIO

socketio = SocketIO(app, cors_allowed_origins="*")
```

Run the application:

```python
socketio.run(app, host="0.0.0.0", port=5000)
```

---

## 7. SQLAlchemy

Install SQLAlchemy:

```bash
pip install SQLAlchemy
```

---

## 8. Geopy

Install Geopy:

```bash
pip install geopy
```

---

## 9. Pillow (PIL)

Install Pillow:

```bash
pip install Pillow
```

---

# Common Issues

## PyTorch Installation Fails

Upgrade your packaging tools:

```bash
pip install --upgrade pip setuptools wheel
```

---

## BLIP Model Download Issues

The BLIP model weights are downloaded automatically from Hugging Face during the first execution.

Ensure that:

- Internet access is available
- Firewall or proxy settings do not block downloads

---

# Recommended Production Setup

For production deployment, it is recommended to use:

- Gunicorn
- Nginx
- Redis
- Eventlet or Gevent
- PostgreSQL or MySQL (instead of SQLite)

Install production dependencies:

```bash
pip install gunicorn eventlet
```

---

# Full Installation (Single Command)

```bash
pip install Flask Flask-SocketIO redis SQLAlchemy geopy numpy Pillow \
torch torchvision torchaudio transformers accelerate sentencepiece eventlet
```

---

# Database Configuration

Update the `config.ini` file with your database credentials.

Example:

- Host
- Port
- Database
- Username
- Password

according to your database server configuration.

---

# Database Migration (Flask)

This application uses **Flask-Migrate** for database schema management.

### Initialize the migration repository (run once)

```bash
flask db init
```

### Generate a migration

```bash
flask db migrate -m "Initial migration"
```

### Apply migrations

```bash
flask db upgrade
```

### Revert the last migration

```bash
flask db downgrade
```

> **Note**
>
> Make sure the following packages are installed:
>
> - Flask-Migrate
> - Flask-SQLAlchemy

---

# Running the Application

Run using Python:

```bash
python app.py
```

Or using Flask:

```bash
flask run --debug
```

---

# Default Admin Credentials

| Username | Password |
|----------|----------|
| admin | admin123 |

> **Important:** Change the default administrator password immediately after the first login for security purposes.

---

# Technology Stack

- Flask
- Flask-SocketIO
- SQLAlchemy
- Flask-Migrate
- Redis
- Hugging Face Transformers (BLIP)
- PyTorch
- Pillow
- Geopy
- NumPy

# License

This project is licensed under the **GNU General Public License v3.0 (GPL-3.0)**.

Copyright (C) 2026

This program is free software: you can redistribute it and/or modify
it under the terms of the **GNU General Public License** as published by
the Free Software Foundation, either **version 3 of the License**, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but **WITHOUT ANY WARRANTY**; without even the implied warranty of
**MERCHANTABILITY** or **FITNESS FOR A PARTICULAR PURPOSE**. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see:

https://www.gnu.org/licenses/gpl-3.0.html

A copy of the full license text is included in the `LICENSE` file located
at the root of this repository.

---
# Support

If you encounter any issues or have questions, please open an issue in this repository.
