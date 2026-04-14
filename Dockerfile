# 使用 Playwright 官方提供的 Python 镜像
FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

WORKDIR /app

# 安装项目依赖
COPY requirements.txt .
RUN pip install --default-timeout=300 --no-cache-dir -r requirements.txt
COPY requirements-local-embedding.txt .
RUN pip install --default-timeout=300 --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu "torch==2.5.1+cpu"
RUN pip install --default-timeout=300 --no-cache-dir -r requirements-local-embedding.txt

# 为 Playwright 安装浏览器
RUN playwright install chromium

# 复制项目代码
COPY . .

# 设置环境变量
ENV PYTHONPATH=/app

# 默认命令 (运行所有爬虫)
CMD ["python", "runner.py"]
