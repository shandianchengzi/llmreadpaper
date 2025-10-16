#!/bin/bash

# generate_dockerfile.sh - 生成动态端口的Dockerfile

# 加载环境变量文件
source .env

# 加载环境变量
if [ -f .env ]; then
    export $(cat .env | grep -v '#' | awk '/=/ {print $1}')
fi

# 设置默认端口
APP_PORT=${APP_PORT:-8080}

# 生成Dockerfile
cat > Dockerfile << EOF
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV APP_PORT=$APP_PORT

# 安装系统依赖（如果需要）
# RUN apt-get update && apt-get install -y \\
#     curl \\
#     && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir --upgrade pip && \\
    pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建非root用户（安全最佳实践）
RUN useradd -m -u 1000 appuser && \\
    chown -R appuser:appuser /app
USER appuser

# 暴露端口（使用环境变量）
EXPOSE \$APP_PORT

# 运行应用（使用环境变量端口）
CMD ["sh", "-c", "python app.py"]
EOF

echo "Dockerfile 已生成，使用端口: $APP_PORT"