import os
from flask import Flask, render_template, request, redirect, url_for, abort
from datetime import datetime
import markdown
import json
import pytz
tz = pytz.timezone('Asia/Taipei')

app = Flask(__name__)

def json_serial(obj):
    if isinstance(obj, datetime):
        return obj.astimezone(tz).strftime("%Y-%m-%d %H:%M:%S")
    raise TypeError("輸入值無法序列化")

def save_data(data):
    with open("data.json", "w") as file:
        json.dump({"posts": data}, file, default=json_serial, indent=4)

def load_data():
    try:
        with open("data.json", "r") as file:
            data = json.load(file)
            if isinstance(data, dict) and "posts" in data:
                return data["posts"]
            else:
                return []
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_audit_data(ip_address, action):
    with open("audit_log.txt", "a") as file:
        timestamp = datetime.now(tz).replace(microsecond=0).isoformat(' ', 'seconds')
        file.write(f"IP Address: {ip_address} - Action: {action} - Time: {timestamp}\n")

def load_blocked_ips():
    raw_content = ""  # 新增初始化
    try:
        if not os.path.exists("blocked_ips.json"):
            with open("blocked_ips.json", "w", encoding='utf-8-sig') as f:
                json.dump([], f, ensure_ascii=False)
            return []
        
        # 確保 raw_content 在 try 區塊外仍可訪問
        with open("blocked_ips.json", "r", encoding='utf-8-sig') as file:
            raw_content = file.read()  # 移至此處
            if not raw_content.strip():
                return []
            blocked_ips = json.loads(raw_content)
            return blocked_ips if isinstance(blocked_ips, list) else []
    except Exception as e:
        print(f"[CRITICAL] JSON 加載失敗！錯誤細節：{str(e)}")
        print(f"文件原始內容：\n{raw_content[:100]}...")  # 此時 raw_content 已定義
        return []


def save_blocked_ips(blocked_ips):
    with open("blocked_ips.json", "w", encoding='utf-8') as file:
        json.dump(blocked_ips, file, indent=4, ensure_ascii=False)

def get_client_ip():
    if request.headers.getlist("X-Forwarded-For"):
        # Pega a primeira parte da lista dividida por vírgulas
        ip_address = request.headers.getlist("X-Forwarded-For")[0].split(",")[0].strip()
    else:
        ip_address = request.environ.get('REMOTE_ADDR')
    return ip_address

blocked_ips = load_blocked_ips()

def check_blocked_ip():
    client_ip = get_client_ip()
    print(f"[DEBUG] Current IP: {client_ip}, Blocked List: {blocked_ips}")  # 新增此行
    if client_ip in blocked_ips:
        return render_template("blocked.html")
    return None

@app.before_request
def handle_blocked_ip():
    global blocked_ips  # 添加全局聲明
    blocked_ips = load_blocked_ips()  # 每次請求重新加載
    blocked_template = check_blocked_ip()
    if blocked_template:
        response = app.make_response(blocked_template)
        response.status_code = 403
        return response

posts = load_data()

@app.route("/")
def index():
    ip_address = get_client_ip()
    timestamp = datetime.now(tz).isoformat()
    save_audit_data(ip_address, "Accessed homepage")

    sorted_posts = sorted(posts, 
        key=lambda x: tz.localize(datetime.strptime(x['timestamp'], "%Y-%m-%d %H:%M:%S")),
        reverse=True
    )
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 10))
    
    # 分頁切片計算
    total_posts = len(sorted_posts)
    start = (page - 1) * per_page
    end = start + per_page
    paginated_posts = sorted_posts[start:end]
    return render_template("index.html", 
                         posts=paginated_posts,
                         current_page=page,
                         per_page=per_page,
                         total_posts=total_posts)

@app.route("/post/<int:post_id>")
def post(post_id):
    post = next((p for p in posts if p["id"] == post_id), None)

    if post:
        post['content'] = markdown.markdown(post['content'], extensions=['markdown.extensions.fenced_code'])
        ip_address = get_client_ip()
        save_audit_data(ip_address, f"Accessed post {post_id}")
        return render_template("post.html", post=post)

    return "Post não encontrado", 404

@app.route("/create_post", methods=["GET", "POST"])
def create_post():
    if request.method == "POST":
        title = request.form.get("title")
        author = request.form.get("author")
        content = request.form.get("content")

        ip_address = get_client_ip()
        save_audit_data(ip_address, "Created a new post")

        new_post = {
            "id": len(posts) + 1,
            "title": title,
            "content": content,
            "author": author,
            "timestamp": datetime.now(tz).replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S"),
            "comments": [],
            "ip_address": ip_address  # Adiciona a informação do endereço IP ao post
        }

        posts.append(new_post)
        save_data(posts)

        return redirect(url_for("index"))

    return render_template("create_post.html")

@app.route("/post/<int:post_id>/add_comment", methods=["POST"])
def add_comment(post_id):
    post = next((p for p in posts if p["id"] == post_id), None)

    if post:
        comment_author = request.form.get("comment_author")
        comment_content = request.form.get("comment_content")

        ip_address = get_client_ip()
        save_audit_data(ip_address, f"Added a comment to post {post_id}")

        new_comment = {
            "author": comment_author,
            "content": comment_content,
            "ip_address": ip_address  # Adiciona a informação do endereço IP ao comentário
        }

        post["comments"].append(new_comment)
        save_data(posts)

    return redirect(url_for("post", post_id=post_id))

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=81)

# Substitua app.run(debug=True) por app.run(host='0.0.0.0', port=81) para tornar o site público
