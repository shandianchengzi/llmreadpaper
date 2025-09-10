from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, jsonify
import os
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import requests

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Ollama API配置
OLLAMA_BASE_URL = os.environ.get('OLLAMA_BASE_URL', 'http://127.0.0.1:11434')

users = {}

# 从环境变量加载用户
llm_user = os.environ.get('LLM_USER', 'admin')
llm_password = os.environ.get('LLM_PASSWORD', 'admin123')

users[llm_user] = {
    'password_hash': generate_password_hash(llm_password),
    'name': '管理员'
}

# 登录装饰器
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# 通用API代理 - 处理所有Ollama API请求
@app.route('/api/<path:subpath>', methods=['GET', 'POST', 'PUT', 'DELETE'])
@login_required
def ollama_proxy(subpath):
    """代理所有Ollama API请求"""
    try:
        url = f"{OLLAMA_BASE_URL}/api/{subpath}"
        
        # 准备请求参数
        request_args = {
            'timeout': 120 if request.method == 'POST' else 30
        }
        
        # 添加查询参数（对于GET请求）
        if request.method == 'GET':
            request_args['params'] = request.args
        
        # 添加JSON数据（对于POST/PUT请求）
        if request.method in ['POST', 'PUT'] and request.is_json:
            request_args['json'] = request.get_json()
        
        # 转发请求
        if request.method == 'GET':
            response = requests.get(url, **request_args)
        elif request.method == 'POST':
            response = requests.post(url, **request_args)
        elif request.method == 'PUT':
            response = requests.put(url, **request_args)
        elif request.method == 'DELETE':
            response = requests.delete(url, **request_args)
        else:
            return jsonify({'error': 'Method not allowed'}), 405
        
        # 过滤掉不允许的响应头
        excluded_headers = ['connection', 'keep-alive', 'proxy-authenticate',
                          'proxy-authorization', 'te', 'trailers', 
                          'transfer-encoding', 'upgrade']
        headers = [
            (k, v) for k, v in response.headers.items()
            if k.lower() not in excluded_headers
        ]
        
        # 确保正确的Content-Type
        if not any(k.lower() == 'content-type' for k, v in headers) and response.content:
            headers.append(('Content-Type', 'application/json'))
        
        return response.content, response.status_code, headers
    
    except requests.exceptions.Timeout:
        return jsonify({'error': 'Request timeout'}), 504
    except requests.exceptions.ConnectionError:
        return jsonify({'error': 'Cannot connect to Ollama'}), 502
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/')
def index():
    if 'logged_in' in session:
        return redirect(url_for('main_app'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if username in users and check_password_hash(users[username]['password_hash'], password):
            session['logged_in'] = True
            session['username'] = username
            session['name'] = users[username]['name']
            
            next_url = request.args.get('next')
            if next_url:
                return redirect(next_url)
            return redirect(url_for('main_app'))
        else:
            return render_template('login.html', error='用户名或密码错误')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/main')
@login_required
def main_app():
    return send_from_directory('.', 'llmreadpaper.html')

@app.route('/chat')
@login_required
def chat():
    """渲染交互测试页面"""
    return render_template('index.html')

if __name__ == '__main__':
    app_port = int(os.environ.get('APP_PORT', 8080))
    # 检查是否是开发环境
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    if debug_mode:
        print("运行在开发模式")
        app.run(host='0.0.0.0', port=app_port, debug=True)
    else:
        print("运行在生产模式")
        # 在生产环境中，你应该使用WSGI服务器而不是直接运行app
        from waitress import serve
        serve(app, host='0.0.0.0', port=app_port)