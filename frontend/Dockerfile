FROM node:20-alpine AS build

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .

# VITE_API_URL wird zur Build-Zeit eingebettet (z.B. https://backend.up.railway.app)
ARG VITE_API_URL
ENV VITE_API_URL=${VITE_API_URL}

RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.standalone.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
