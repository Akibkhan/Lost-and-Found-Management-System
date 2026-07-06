from app import app
from extensions import db
from flask_login import login_required, current_user
from flask import request, jsonify, render_template, url_for
from functools import wraps
from datetime import datetime
from math import radians, sin, cos, sqrt, asin
from models import Item, Category, User
from sqlalchemy import or_
from extensions import cache

#Search feature
# Helper to serialize Item
def serialize_item(item):
    return {
        'id': item.id,
        'name': item.name,
        'description': item.description,
        'photo': item.photo or '',
        'location': item.location or '',
        'date_reported': item.date_reported.strftime('%Y-%m-%d %H:%M'),
        'status': item.status,
        'category': item.category.name if item.category else None,
        'user': {
            'id': item.user.id,
            'username': item.user.username
        }
    }

def cache_key_for_search():
    args = request.args.to_dict(flat=True)
    key = "|".join(f"{k}:{v}" for k, v in sorted(args.items()))
    return f"search:{key}"


def require_json(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if not request.is_json and request.args.get('q') is None and request.method == 'GET':
            # allow normal GETs with query params
            pass
        return f(*a, **kw)
    return wrapper


@app.route('/api/search')
@login_required
def api_search():
    """
    JSON API used by AJAX frontend.
    Query params:
      - q (string)
      - status (lost|found|claimed or empty)
      - category_id (int)
      - date_from (YYYY-MM-DD)
      - date_to (YYYY-MM-DD)
      - page (int) default 1
      - per_page (int) default 6
      - lat (float) optional (user lat for proximity search)
      - lng (float) optional (user lng for proximity search)
      - radius_km (float) optional radius in km
      - use_my_location (bool) optional — indicates the client wants a location-based search
      - fuzzy_max (int) optional max edit distance to accept (default 3)
    """
    # Read params
    q = request.args.get('q', '', type=str).strip()
    status = request.args.get('status', type=str)
    category_id = request.args.get('category_id', type=int)
    date_from = request.args.get('date_from', type=str)
    date_to = request.args.get('date_to', type=str)
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 6, type=int)
    lat = request.args.get('lat', type=float)
    lng = request.args.get('lng', type=float)
    radius_km = request.args.get('radius_km', type=float)
    use_my_location = request.args.get('use_my_location', type=str)  # "true" or "false" or None
    fuzzy_max = request.args.get('fuzzy_max', 3, type=int)

    # If the user asked to search near them, but coords are missing -> return 400 (client should obtain coords)
    if use_my_location and use_my_location.lower() == 'true':
        if lat is None or lng is None:
            return jsonify({'error': 'missing_coordinates', 'message': 'Latitude and longitude are required for "near me" searches.'}), 400

    # Build cache key only when user did NOT request a private location-based search.
    cache_key = None
    if not (use_my_location and use_my_location.lower() == 'true'):
        # include user id so results can be personalized if needed
        args = request.args.to_dict(flat=True)
        args['uid'] = str(current_user.id if current_user.is_authenticated else 'anon')
        cache_key = "search:" + "&".join(f"{k}={args[k]}" for k in sorted(args))
        cached = cache.get(cache_key)
        if cached:
            return jsonify(cached)

    # Base SQL filters
    qry = Item.query.outerjoin(Category).join(User)

    if status and status.lower() in ('lost','found','claimed'):
        qry = qry.filter(Item.status == status.lower())
    if category_id:
        qry = qry.filter(Item.category_id == category_id)

    try:
        if date_from:
            dtf = datetime.strptime(date_from, '%Y-%m-%d')
            qry = qry.filter(Item.date_reported >= dtf)
        if date_to:
            dtt = datetime.strptime(date_to, '%Y-%m-%d')
            dtt = datetime(dtt.year, dtt.month, dtt.day, 23, 59, 59)
            qry = qry.filter(Item.date_reported <= dtt)
    except ValueError:
        pass

    # Pull candidates from DB (bounded by SQL filters)
    base_results = qry.order_by(Item.date_reported.desc()).all()

    # Apply fuzzy and proximity filtering in Python
    candidates = []
    q_lower = q.lower()
    for it in base_results:
        accept = True

        # Proximity (only if client requested it)
        if use_my_location and use_my_location.lower() == 'true' and radius_km:
            if it.latitude is None or it.longitude is None:
                accept = False
            else:
                dist = haversine_km(lat, lng, it.latitude, it.longitude)
                if dist > radius_km:
                    accept = False

        # Textual fuzzy matching if a query present
        if q and accept:
            fields = [
                (it.name or ""),
                (it.category.name if it.category else ""),
                (it.location or ""),
                ((it.description or "")[:200])
            ]
            best = None
            for text in fields:
                if not text:
                    continue
                sc = fuzzy_score(q_lower, text.lower())
                if best is None or sc < best:
                    best = sc
            # Accept if substring match OR fuzzy distance <= fuzzy_max
            if best is None:
                accept = False
            else:
                if (q_lower in (it.name or "").lower()) or (q_lower in (it.location or "").lower()) or (it.category and q_lower in it.category.name.lower()):
                    accept = True
                else:
                    accept = (best <= fuzzy_max)

        if accept:
            candidates.append(it)

    # sort & paginate
    candidates.sort(key=lambda x: x.date_reported, reverse=True)
    total = len(candidates)
    pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, pages))
    start = (page - 1) * per_page
    end = start + per_page
    page_items = candidates[start:end]

    def serialize_item(it):
        return {
            'id': it.id,
            'name': it.name,
            'description': it.description,
            'photo': it.photo or '',
            'location': it.location,
            'latitude': it.latitude,
            'longitude': it.longitude,
            'date_reported': it.date_reported.strftime('%Y-%m-%d %H:%M'),
            'status': it.status,
            'category': it.category.name if it.category else None,
            'user': {'id': it.user.id, 'username': it.user.username}
        }

    payload = {
        'items': [serialize_item(it) for it in page_items],
        'page': page,
        'per_page': per_page,
        'total': total,
        'pages': pages
    }

    # cache only when not a "near me" request (to avoid caching user-specific results)
    if cache_key:
        cache.set(cache_key, payload, timeout=60)

    return jsonify(payload)

    def serialize_item(it):
        return {
            'id': it.id,
            'name': it.name,
            'description': it.description,
            'photo': it.photo or '',
            'location': it.location,
            'latitude': it.latitude,
            'longitude': it.longitude,
            'date_reported': it.date_reported.strftime('%Y-%m-%d %H:%M'),
            'status': it.status,
            'category': it.category.name if it.category else None,
            'user': {'id': it.user.id, 'username': it.user.username}
        }

    payload = {
        'items': [serialize_item(it) for it in page_items],
        'page': page,
        'per_page': per_page,
        'total': total,
        'pages': pages
    }

    # store in cache for a short time
    cache.set(cache_key, payload, timeout=60)  # cache 60s by default
    return jsonify(payload)


@app.route('/api/suggest')
@login_required
def api_suggest():
    """
    Provide fuzzy autocomplete suggestions for the search input.
    Returns list of strings.
    """
    q = request.args.get('q', '', type=str).strip()
    max_results = request.args.get('max', 10, type=int)
    fuzzy_max = request.args.get('fuzzy_max', 2, type=int)

    if not q:
        return jsonify([])

    # first try prefix exact matches via SQL for speed (high priority)
    likeq = f"{q}%"
    rows = db.session.query(Item.name).filter(Item.name.ilike(likeq)).group_by(Item.name).limit(max_results).all()
    suggestions = [r[0] for r in rows]

    # if not enough results, fill with fuzzy matches using edit distance
    if len(suggestions) < max_results:
        all_names = [r[0] for r in db.session.query(Item.name).distinct().all()]
        candidates = []
        ql = q.lower()
        for name in all_names:
            d = fuzzy_score(ql, name.lower())
            if d <= fuzzy_max:
                candidates.append((d, name))
        candidates.sort(key=lambda x: x[0])
        for _d, name in candidates:
            if name not in suggestions:
                suggestions.append(name)
                if len(suggestions) >= max_results:
                    break

    return jsonify(suggestions[:max_results])
@app.route("/search")
def search_item():
    try:
        query = request.args.get("query", "").strip()
        category_id = request.args.get("category", type=int)
        radius = request.args.get("radius", type=float)
        lat = request.args.get("lat", type=float)
        lon = request.args.get("lon", type=float)   # ✅ FIXED
        page = request.args.get("page", 1, type=int)
        per_page = 12

        q = Item.query

        if category_id:
            q = q.filter(Item.category_id == category_id)

        if query:
            q = q.filter(
                or_(
                    Item.name.ilike(f"%{query}%"),
                    Item.description.ilike(f"%{query}%")
                )
            )

        items = q.all()

        results = []

        for it in items:

            # Proximity filter
            if lat is not None and lon is not None and radius is not None and radius > 0:
                if it.latitude is None or it.longitude is None:
                    continue

                dist = haversine_km(lat, lon, it.latitude, it.longitude)

                if dist > radius:
                    continue

                it.distance = round(dist, 2)
            else:
                it.distance = None

            results.append(it)

        total = len(results)
        pages = max(1, (total + per_page - 1) // per_page)
        page = max(1, min(page, pages))

        start = (page - 1) * per_page
        end = start + per_page
        paginated = results[start:end]

        items_json = []

        for it in paginated:
            img_url = url_for('static', filename=f"uploads/{it.photo}") if it.photo else None

            items_json.append({
                "id": it.id,
                "name": it.name,
                "description": it.description,
                "photo": img_url,
                "category": it.category.name if it.category else None,
                "status": it.status,
                "distance": getattr(it, "distance", None)
            })

        return jsonify({
            "items": items_json,
            "page": page,
            "pages": pages,
            "total": total
        })

    except Exception as e:
        print("Search error:", e)
        return jsonify({"error": str(e)}), 500










# ---------------- Helper: fuzzy match using Levenshtein (or fallback) ----------------
def fuzzy_score(a: str, b: str) -> int:
    """
    Lower is better (distance). Uses Levenshtein.distance if available,
    otherwise falls back to a simple implementation using dynamic programming.
    """
    if not a or not b:
        return max(len(a or ""), len(b or ""))
    a = a.lower()
    b = b.lower()
    if HAVE_LEV:
        return Levenshtein.distance(a, b)
    # fallback: simple DP edit distance (Levenshtein)
    m, n = len(a), len(b)
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, n + 1):
            temp = dp[j]
            if a[i - 1] == b[j - 1]:
                dp[j] = prev
            else:
                dp[j] = 1 + min(prev, dp[j], dp[j - 1])
            prev = temp
    return dp[n]

# ---------------- Helper: haversine distance (km) ----------------
def haversine_km(lat1, lon1, lat2, lon2):
    # convert degrees to radians
    lat1, lon1, lat2, lon2 = map(radians, (lat1, lon1, lat2, lon2))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    R = 6371.0
    return R * c


@app.route("/search/page")
def search_page():
    # Preload categories (optional)
    categories = Category.query.order_by(Category.name).all()
    return render_template("search.html", categories=categories)
@app.route("/autocomplete")
def autocomplete():
    q = request.args.get("q", "").strip().lower()
    if not q:
        return jsonify([])

    # Get only item names for speed
    names = [i.name for i in Item.query.with_entities(Item.name).all()]

    # Prefix matches
    prefix_matches = [n for n in names if n.lower().startswith(q)]

    # Fuzzy matches (distance ≤ 2)
    fuzzy_matches = [
        n for n in names
        if Levenshtein.distance(q, n.lower()) <= 2
    ]

    # Combine & dedupe
    results = list(dict.fromkeys(prefix_matches + fuzzy_matches))

    return jsonify(results[:10])   # return only top 10 suggestions