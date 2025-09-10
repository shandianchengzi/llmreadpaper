from flask import Flask, request, jsonify, render_template, Response
import requests
import json
import time
from datetime import datetime

from dotenv import load_dotenv
import os
load_dotenv()

app = Flask(__name__)

# 配置
DIFY_BASE_URL = os.environ.get('DIFY_BASE_URL', 'http://127.0.0.1:1234')
TARGET_URL = DIFY_BASE_URL + "/chat"
DEFAULT_MODEL = "dify1"
AVAILABLE_MODELS = {
    "dify1": {
        "name": "dify1",
        "model": "dify1",
        "modified_at": "2025-09-10T00:00:00Z",
        "size": 0,
        "digest": "sha256:simulated",
        "details": {
            "parent_model": "",
            "format": "",
            "family": "",
            "families": [],
            "parameter_size": "",
            "quantization_level": ""
        }
    }
}

@app.route('/')
def index():
    """渲染交互测试页面"""
    return render_template('index.html')

@app.route('/api/tags', methods=['GET'])
def get_models():
    """模拟Ollama的tags接口"""
    models = list(AVAILABLE_MODELS.values())
    return jsonify({"models": models})

def transform_to_ollama(stream_data):
    """将流式数据转换为Ollama格式"""
    full_response = ""
    for line in stream_data.split('\n'):
        if line.startswith('data: '):
            try:
                data = json.loads(line[6:])
                if data.get('event') == 'message':
                    full_response += data['answer']
            except json.JSONDecodeError:
                continue
    
    return {
        "model": DEFAULT_MODEL,
        "created_at": int(time.time()),
        "response": full_response,
        "done": True
    }

@app.route('/api/generate', methods=['POST'])
def ollama_proxy():
    """增强版generate接口"""
    try:
        # 1. 获取请求参数
        user_input = request.get_json()
        prompt = user_input.get("prompt", "")
        model = user_input.get("model", DEFAULT_MODEL)  # 支持自定义模型
        
        # 2. 验证模型是否可用
        if model not in AVAILABLE_MODELS:
            return jsonify({"error": f"Model '{model}' not available"}), 400
        
        # 3. 构造Dify请求
        dify_payload = {
            "query": prompt,
            "model": model,  # 传递用户指定的模型
            "response_mode": "streaming"
        }
        
        # 4. 调用目标接口
        response = requests.post(
            TARGET_URL,
            json=dify_payload,
            stream=True,
            timeout=30
        )
        response.raise_for_status()
        
        # 5. 处理流式响应
        stream_data = ""
        for chunk in response.iter_content(chunk_size=None):
            if chunk:
                stream_data += chunk.decode('utf-8')
        
        # 6. 转换格式
        ollama_response = transform_to_ollama(stream_data)
        ollama_response["model"] = model  # 返回用户指定的模型名
        return jsonify(ollama_response)

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"API调用失败: {str(e)}"}), 502
    except Exception as e:
        return jsonify({"error": f"服务器错误: {str(e)}"}), 500

@app.route('/api/chat', methods=['POST'])
def ollama_chat():
    """模拟Ollama的流式chat接口"""
    try:
        # 1. 获取请求参数
        user_input = request.get_json()
        messages = user_input.get("messages", [])
        model = user_input.get("model", DEFAULT_MODEL)
        
        # 2. 验证模型是否可用
        if model not in AVAILABLE_MODELS:
            return jsonify({"error": f"Model '{model}' not available"}), 400
        
        # 3. 提取最后一条用户消息作为查询
        if not messages or not isinstance(messages, list):
            return jsonify({"error": "Invalid messages format"}), 400
        
        last_user_message = None
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user_message = msg.get("content", "")
                break
        
        if not last_user_message:
            return jsonify({"error": "No user message found"}), 400
        
        # 4. 构造Dify请求
        dify_payload = {
            "query": last_user_message,
            "model": model,
            "response_mode": "streaming"
        }
        
        # 5. 调用目标接口并返回流式响应
        response = requests.post(
            TARGET_URL,
            json=dify_payload,
            stream=True,
            timeout=30
        )
        response.raise_for_status()
        
        # 6. 创建生成器函数处理流式响应
        def generate():
            full_response = ""
            for chunk in response.iter_content(chunk_size=None):
                if chunk:
                    chunk_str = chunk.decode('utf-8')
                    if chunk_str.startswith('data: '):
                        try:
                            data = json.loads(chunk_str[6:])
                            if data.get('event') == 'message' and 'answer' in data:
                                content = data['answer']
                                full_response += content
                                
                                # 构造Ollama格式的流式响应
                                ollama_chunk = {
                                    "model": model,
                                    "created_at": datetime.utcnow().isoformat() + "Z",
                                    "message": {
                                        "role": "assistant",
                                        "content": content
                                    },
                                    "done": False
                                }
                                yield json.dumps(ollama_chunk) + "\n"
                        except json.JSONDecodeError:
                            continue
            
            # 发送最终完成消息
            ollama_final = {
                "model": model,
                "created_at": datetime.utcnow().isoformat() + "Z",
                "message": {
                    "role": "assistant",
                    "content": ""
                },
                "done": True
            }
            yield json.dumps(ollama_final) + "\n"
        
        # 7. 返回流式响应
        return Response(generate(), mimetype='application/json')
        
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"API调用失败: {str(e)}"}), 502
    except Exception as e:
        return jsonify({"error": f"服务器错误: {str(e)}"}), 500

if __name__ == '__main__':
    port = os.environ.get('DIFY_PORT', '1235')
    # 在生产环境中，你应该使用WSGI服务器而不是直接运行app
    from waitress import serve
    serve(app, host='127.0.0.1', port=port)