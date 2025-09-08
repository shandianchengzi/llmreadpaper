# 停止并删除所有相关容器
docker-compose down

# 强制重新构建（不使用缓存）
docker-compose build --no-cache

# 重新创建服务
docker-compose up -d