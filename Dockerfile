# 使用 Python 官方镜像
FROM python:3.10

# 设置工作目录
WORKDIR /app

# 复制当前目录内容到容器内
COPY . .

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 暴露端口（虽然 Telegram Bot 不需要用，但加上没坏处）
EXPOSE 8080

# 设置启动命令（关键！）
CMD ["python", "main.py"]
