from app import app
from flask import render_template, request
from flask import Flask, render_template, redirect, url_for, request, flash, abort
from sqlalchemy.dialects.mysql import JSON
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user,user_logged_in, user_logged_out
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_migrate import Migrate
from functools import wraps
from datetime import datetime
from flask_socketio import SocketIO, emit, join_room, leave_room
from datetime import datetime
from flask_caching import Cache

import uuid
from flask import jsonify
from sqlalchemy import func

import os
import json
import redis
from functools import wraps
from sqlalchemy import or_

from flask_login import user_logged_in, user_logged_out
# caching + fuzzy
from flask_caching import Cache
from PIL import Image
from extensions import db
