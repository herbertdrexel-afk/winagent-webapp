FROM node:20-alpine AS build

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .

# Build without baking in API URL — proxy handles it at runtime
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.standalone.conf /etc/nginx/templates/default.conf.template
EXPOSE 8080

# envsubst replaces ${BACKEND_URL} in the nginx template at container start
CMD ["/bin/sh", "-c", "envsubst '${BACKEND_URL}' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"]
