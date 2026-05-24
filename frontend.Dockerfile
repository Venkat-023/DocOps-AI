FROM node:22-slim

WORKDIR /app

COPY frontend/package.json ./
COPY frontend/bun.lock* ./
RUN npm install

COPY frontend ./

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
