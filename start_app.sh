#!/bin/bash

# 环境准备
mv .env.example .env

# 安装依赖
pip install -r requirements.txt

# 启动应用
python app.py