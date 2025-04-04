# 使用官方 Node.js LTS 版本作为基础镜像
FROM node:16

# 设置工作目录
WORKDIR /app

# 将 package.json 和 package-lock.json 复制到工作目录
COPY package*.json ./

# 安装依赖包
RUN npm install

# 将当前项目的所有文件复制到工作目录中
COPY . .

# 暴露端口（如果你使用 Express 提供 webhook 或其他 HTTP 服务）
EXPOSE 3000

# 启动应用
CMD ["node", "bot.js"]
