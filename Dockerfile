# 使用 Playwright 官方提供的 Python 镜像
FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

WORKDIR /app

# 安装项目依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 为 Playwright 安装浏览器
RUN playwright install chromium

# 复制项目代码
COPY . .

# 设置环境变量
ENV PYTHONPATH=/app

# 默认命令 (运行所有爬虫)
CMD ["python", "runner.py"]
