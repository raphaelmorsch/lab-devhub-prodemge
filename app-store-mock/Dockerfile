FROM registry.access.redhat.com/ubi9/nodejs-22:latest

USER 0
WORKDIR /opt/app-root/src

COPY package.json ./
RUN npm install --omit=dev && npm cache clean --force

COPY server.js ./
COPY public ./public

ENV PORT=8080 \
    NODE_ENV=production

EXPOSE 8080
USER 1001

CMD ["node", "server.js"]
